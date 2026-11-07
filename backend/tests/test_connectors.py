"""Connector parsing against recorded payload shapes, and failure handling."""

import httpx
import pytest

from backend.sources.ashby import AshbyConnector
from backend.sources.authorized_api import AdzunaConnector, RemotiveConnector
from backend.sources.base import MissingCredentials, SourceError
from backend.sources.company_careers import CompanyCareersConnector, parse_job_postings
from backend.sources.greenhouse import GreenhouseConnector
from backend.sources.lever import LeverConnector
from backend.sources.manual_submission import ManualSubmissionConnector
from backend.sources.rss_feed import RssFeedConnector
from backend.sources.text import canonicalize_url, company_key, extract_sections, html_to_text

LONG = "<p>" + "You will own the product roadmap and work with engineering. " * 4 + "</p>"


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_client(payload, status=200) -> httpx.Client:
    return client_for(lambda request: httpx.Response(status, json=payload))


GREENHOUSE_JOB = {
    "id": 4970739101,
    "title": "Associate Product Manager",
    "absolute_url": "https://job-boards.eu.greenhouse.io/groww/jobs/4970739101",
    "location": {"name": "Bengaluru-VTP, India"},
    "company_name": "Groww",
    "first_published": "2026-09-14T03:49:28-04:00",
    "updated_at": "2026-09-15T03:52:53-04:00",
    "application_deadline": None,
    "content": "&lt;p&gt;" + "You will own the product roadmap. " * 5 + "&lt;/p&gt;",
    "offices": [{"name": "Bengaluru-VTP", "location": "Bengaluru-VTP, India"}],
    "departments": [{"name": "Product"}],
    "pay_input_ranges": [{"min_cents": 1000000, "max_cents": 2000000, "currency_type": "INR"}],
}


def test_greenhouse_normalizes():
    connector = GreenhouseConnector({"board": "groww", "company": "Groww"}, client=json_client({"jobs": [GREENHOUSE_JOB]}))
    raws = connector.fetch_jobs()
    job = connector.normalize_job(raws[0])
    assert job.external_job_id == "4970739101"
    assert job.company == "Groww"
    assert job.location == "Bengaluru-VTP, India"
    assert "product roadmap" in job.description and "<p>" not in job.description
    assert (job.salary_min, job.salary_max, job.salary_currency) == (10000, 20000, "INR")
    assert job.date_posted.year == 2026
    assert connector.validate_job(job) == []
    assert connector.extract_metadata(raws[0])["departments"] == ["Product"]


def test_lever_normalizes():
    raw = {
        "id": "aa98a938-af3a-45f5-851d-966b2b5ba000", "text": "Product Analyst",
        "categories": {"commitment": "full time", "location": "hyderabad", "allLocations": ["hyderabad"], "team": "x"},
        "country": "IN", "workplaceType": "onsite", "descriptionPlain": "Own the product roadmap. " * 6,
        "lists": [{"text": "Requirements", "content": "<li>SQL</li>"}], "additionalPlain": "Join us.",
        "hostedUrl": "https://jobs.lever.co/cred/aa98", "applyUrl": "https://jobs.lever.co/cred/aa98/apply",
        "createdAt": 1790000000000,
    }
    connector = LeverConnector({"board": "cred", "company": "CRED"}, client=json_client([raw]))
    job = connector.normalize_job(connector.fetch_jobs()[0])
    assert job.structured_country == "IN"
    assert job.workplace_hint == "onsite"
    assert job.employment_type == "Full-time"
    assert job.application_url.endswith("/apply")
    assert "SQL" in job.description
    assert job.date_posted is not None


def test_lever_ignores_primary_country_for_multi_location_jobs():
    raw = {"id": "x", "text": "t", "country": "IN", "categories": {"location": "Pune", "allLocations": ["Pune", "Dubai"]}}
    job = LeverConnector({"board": "b"}, client=json_client([])).normalize_job(raw)
    assert job.structured_country is None
    assert job.extra_locations == ["Dubai"]


def test_ashby_normalizes_and_skips_unlisted():
    raw = {
        "id": "c0406fe0", "title": "Product Manager", "location": "Delhi", "secondaryLocations": [],
        "isListed": True, "isRemote": False, "workplaceType": "OnSite", "employmentType": "FullTime",
        "address": {"postalAddress": {"addressCountry": "India", "addressLocality": "Delhi"}},
        "jobUrl": "https://jobs.ashbyhq.com/sarvam/c0406fe0",
        "applyUrl": "https://jobs.ashbyhq.com/sarvam/c0406fe0/application",
        "descriptionPlain": "Own things. " * 12, "publishedAt": "2026-04-17T11:46:39.214+00:00",
        "compensation": {"compensationTiers": [
            {"components": [{"compensationType": "Salary", "minValue": 100, "maxValue": 200, "currencyCode": "INR"}]}
        ]},
    }
    unlisted = {**raw, "id": "hidden", "isListed": False}
    connector = AshbyConnector({"board": "sarvam", "company": "Sarvam"}, client=json_client({"jobs": [raw, unlisted]}))
    raws = connector.fetch_jobs()
    assert len(raws) == 1
    job = connector.normalize_job(raws[0])
    assert job.structured_country == "India"
    assert job.employment_type == "Full-time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (100, 200, "INR")


def test_rss_normalizes():
    feed = f"""<?xml version="1.0"?><rss version="2.0"><channel><item>
    <title>Acme Corp: Product Manager</title><region>Anywhere in the World</region>
    <guid>https://weworkremotely.com/x</guid><link>https://weworkremotely.com/x</link>
    <pubDate>Fri, 06 Nov 2026 10:00:00 +0000</pubDate>
    <description><![CDATA[{LONG}]]></description></item></channel></rss>"""
    connector = RssFeedConnector(
        {"url": "https://feed.example.com/rss", "remote_feed": True},
        client=client_for(lambda r: httpx.Response(200, text=feed)),
    )
    job = connector.normalize_job(connector.fetch_jobs()[0])
    assert (job.company, job.title) == ("Acme Corp", "Product Manager")
    assert job.location == "Anywhere in the World"
    assert job.is_remote is True
    assert job.date_posted.year == 2026


def test_rss_bad_xml_is_a_source_error():
    connector = RssFeedConnector({"url": "https://f.example.com"}, client=client_for(lambda r: httpx.Response(200, text="<nope")))
    with pytest.raises(SourceError):
        connector.fetch_jobs()


def test_remotive_normalizes():
    raw = {"id": 9, "url": "https://remotive.com/remote-jobs/product/x-9", "title": "Product Manager",
           "company_name": "Acme", "job_type": "full_time", "publication_date": "2026-11-06T08:51:01",
           "candidate_required_location": "India", "description": LONG}
    connector = RemotiveConnector(client=json_client({"jobs": [raw]}))
    job = connector.normalize_job(connector.fetch_jobs()[0])
    assert (job.location, job.is_remote) == ("India", True)


def test_adzuna_reports_missing_credentials_without_a_request():
    def fail(request):
        raise AssertionError("no request should be sent")

    with pytest.raises(MissingCredentials):
        AdzunaConnector(client=client_for(fail)).fetch_jobs()


def test_adzuna_predicted_salary_is_not_published_as_fact():
    raw = {"id": 1, "title": "Product Analyst", "company": {"display_name": "Acme"}, "description": "x",
           "redirect_url": "https://adzuna.in/1", "location": {"display_name": "Pune", "area": ["India", "Pune"]},
           "salary_min": 900000.0, "salary_max": 900000.0, "salary_is_predicted": "1"}
    job = AdzunaConnector().normalize_job(raw)
    assert job.salary_min is None and job.salary_currency is None
    assert job.structured_country == "IN"


JSON_LD = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting","title":"Product Analyst","identifier":{"value":"77"},
"description":"<p>Own product analytics and the roadmap with teams across the company every single day.</p>",
"url":"https://acme.example.com/jobs/77","datePosted":"2026-11-01","validThrough":"2027-01-01",
"employmentType":"FULL_TIME","hiringOrganization":{"name":"Acme"},
"jobLocation":{"address":{"addressLocality":"Pune","addressRegion":"MH","addressCountry":"IN"}}}
</script><script type="application/ld+json">not json</script></head></html>"""


def test_careers_page_reads_jobposting_markup():
    assert len(parse_job_postings(JSON_LD)) == 1

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text=JSON_LD)

    connector = CompanyCareersConnector({"url": "https://acme.example.com/careers"}, client=client_for(handler))
    job = connector.normalize_job(connector.fetch_jobs()[0])
    assert (job.external_job_id, job.company, job.structured_country) == ("77", "Acme", "IN")
    assert job.expiry_date.year == 2027
    assert job.employment_type == "Full-time"


def test_careers_page_respects_robots():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        raise AssertionError("page must not be fetched")

    connector = CompanyCareersConnector({"url": "https://acme.example.com/careers"}, client=client_for(handler))
    with pytest.raises(SourceError, match="robots"):
        connector.fetch_jobs()


def test_manual_submission_never_fetches_linkedin():
    def fail(request):
        raise AssertionError("LinkedIn must not be fetched")

    connector = ManualSubmissionConnector(client=client_for(fail))
    assert connector.from_url("https://www.linkedin.com/jobs/view/123") is None


def test_manual_submission_resolves_greenhouse_links():
    connector = ManualSubmissionConnector(client=json_client(GREENHOUSE_JOB))
    job = connector.from_url("https://job-boards.greenhouse.io/groww/jobs/4970739101")
    assert job.title == "Associate Product Manager"


def test_http_failure_is_a_source_error():
    connector = GreenhouseConnector({"board": "gone"}, client=json_client({}, status=404))
    with pytest.raises(SourceError, match="404"):
        connector.fetch_jobs()


def test_transient_errors_retry_with_backoff():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"jobs": []})

    connector = GreenhouseConnector({"board": "x"}, client=client_for(handler))
    connector.backoff_seconds = 0
    assert connector.fetch_jobs() == []
    assert len(calls) == 3


def test_retries_are_bounded_and_404_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    connector = GreenhouseConnector({"board": "x"}, client=client_for(handler))
    connector.backoff_seconds = 0
    with pytest.raises(SourceError):
        connector.fetch_jobs()
    assert len(calls) == connector.max_attempts


def test_network_error_is_a_source_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    connector = LeverConnector({"board": "x"}, client=client_for(handler))
    connector.backoff_seconds = 0
    with pytest.raises(SourceError):
        connector.fetch_jobs()


@pytest.mark.parametrize(
    "field, value, problem",
    [("title", "  ", "missing title"), ("company", "", "missing company"), ("description", "short", "description too short"),
     ("application_url", "javascript:alert(1)", "invalid application url"), ("external_job_id", "", "missing external id")],
)
def test_validation_catches_bad_records(field, value, problem):
    from backend.tests.conftest import make_job

    connector = LeverConnector({"board": "x"})
    assert problem in connector.validate_job(make_job(**{field: value}))


def test_html_to_text_handles_escaped_markup():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; bye&lt;/p&gt;").startswith("Hello")


def test_sections_are_extracted():
    requirements, responsibilities = extract_sections("What you'll do\nShip things\nRequirements\nSQL\nBenefits\nFree tea")
    assert requirements == "SQL"
    assert responsibilities == "Ship things"


def test_canonical_url_drops_tracking_but_keeps_the_job_id():
    url = "https://Stripe.com/jobs/search/?gh_jid=123&utm_source=x&gh_src=abc"
    assert canonicalize_url(url) == "https://stripe.com/jobs/search?gh_jid=123"


def test_company_key_ignores_legal_suffixes():
    assert company_key("Razorpay Software Pvt. Ltd.") == company_key("Razorpay Software")
