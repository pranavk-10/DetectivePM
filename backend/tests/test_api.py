"""API behaviour: contract, filters, auth, exports."""

import csv
import io
from datetime import timedelta

import pytest
from sqlalchemy import select

from backend import gsheets
from backend.models import Recruiter, ScrapeRun, Source, utcnow
from backend.schemas import JobPage
from backend.sources.registry import MANUAL_SOURCE
from backend.tests.conftest import ADMIN, GOOD_DESCRIPTION, add_listing


def test_health_reports_database(client):
    body = client.get("/api/health").json()
    assert body == {"status": "healthy", "service": "DetectivePM API", "database": "connected", "environment": "test"}


def test_empty_database_shows_honest_zeros(client):
    metrics = client.get("/api/jobs/metrics").json()
    assert metrics["total_jobs"] == 0 and metrics["by_city"] == [] and metrics["discovered_over_time"] == []
    page = client.get("/api/jobs").json()
    assert page == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}


def test_startup_does_not_scrape(db, client):
    """Regression: the first scrape used to run synchronously at boot."""
    client.get("/api/health")
    assert db.scalar(select(ScrapeRun)) is None


def test_job_page_matches_schema(db, client):
    add_listing(db)
    JobPage.model_validate(client.get("/api/jobs").json())


def test_pagination(db, client):
    for index in range(25):
        add_listing(db, title=f"Associate Product Manager {index:02d}")
    first = client.get("/api/jobs", params={"page_size": 10}).json()
    last = client.get("/api/jobs", params={"page_size": 10, "page": 3}).json()
    assert (first["total"], first["total_pages"], len(first["items"]), len(last["items"])) == (25, 3, 10, 5)
    ids = {i["id"] for i in first["items"]} & {i["id"] for i in last["items"]}
    assert not ids


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"sort_by": "password"}, {"status": "nope"},
                                    {"workplace_type": "Moon"}, {"discovered_within_days": 0}])
def test_invalid_parameters_get_a_structured_422(client, params):
    response = client.get("/api/jobs", params=params)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error" and error["details"]


def test_not_found_is_structured(client):
    response = client.get("/api/jobs/999")
    assert response.status_code == 404
    assert response.json()["error"] == {"code": "not_found", "message": "Job not found", "details": None}


def test_sorting(db, client):
    add_listing(db, title="B Product Analyst", classification="Product Analyst", relevance_score=10)
    add_listing(db, title="A Product Analyst", classification="Product Analyst", relevance_score=90)
    titles = lambda **p: [i["title"] for i in client.get("/api/jobs", params=p).json()["items"]]  # noqa: E731
    assert titles(sort_by="title", sort_order="asc")[0].startswith("A")
    assert titles(sort_by="title", sort_order="desc")[0].startswith("B")
    assert titles(sort_by="relevance_score")[0].startswith("A")


def test_filters_combine(db, client):
    add_listing(db, title="Target PM Intern", classification="Product Management Intern", industry="FinTech",
                city="Pune", state="Maharashtra", workplace_type="Hybrid")
    add_listing(db, title="Wrong City", classification="Product Management Intern", industry="FinTech", city="Mumbai")
    add_listing(db, title="Wrong Role", classification="Product Analyst", industry="FinTech", city="Pune")
    get = lambda **p: client.get("/api/jobs", params=p).json()["total"]  # noqa: E731
    assert get(role="Product Management Intern") == 2
    assert get(role=["Product Management Intern", "Product Analyst"]) == 3
    assert get(industry="FinTech", city="Pune") == 2
    assert get(role="Product Management Intern", city="Pune", workplace_type="Hybrid") == 1
    assert get(workplace_type="Remote") == 0


def test_all_is_not_a_filter_value(db, client):
    """Regression: the old UI sent role_type=All and genre=All."""
    add_listing(db)
    assert client.get("/api/jobs", params={"role": "All"}).json()["total"] == 0  # the client must omit it


def test_search_covers_title_company_city_and_skills(db, client):
    add_listing(db, title="Product Analyst", classification="Product Analyst", company="Zephyr", city="Kochi",
                state="Kerala", skills=["Mixpanel"])
    add_listing(db, title="Associate Product Manager", company="Other")
    for term, expected in (("analyst", 1), ("zephyr", 1), ("kochi", 1), ("mixpanel", 1), ("nothing-matches", 0)):
        assert client.get("/api/jobs", params={"search": term}).json()["total"] == expected


def test_search_treats_wildcards_and_quotes_as_text(db, client):
    add_listing(db)
    for term in ("%", "_", "'; DROP TABLE jobs; --"):
        assert client.get("/api/jobs", params={"search": term}).json()["total"] == 0
    assert client.get("/api/jobs").json()["total"] == 1


def test_date_filter_and_freshness(db, client):
    add_listing(db, title="New Product Analyst", classification="Product Analyst")
    add_listing(db, title="Old Product Analyst", classification="Product Analyst", date_discovered=utcnow() - timedelta(days=30))
    assert client.get("/api/jobs", params={"discovered_within_days": 7}).json()["total"] == 1
    items = client.get("/api/jobs", params={"sort_by": "title", "sort_order": "asc"}).json()["items"]
    assert {item["title"]: item["freshness"] for item in items} == {"New Product Analyst": "new", "Old Product Analyst": "older"}


def test_recruiter_filter(db, client):
    job = add_listing(db)
    add_listing(db, title="Product Analyst", classification="Product Analyst")
    db.add(Recruiter(job_id=job.id, email="careers@acme.com", source_url="https://x.example.com",
                     contact_kind="company_recruiting_email", verification_status="Publicly Listed"))
    db.commit()
    assert client.get("/api/jobs", params={"has_recruiter": True}).json()["total"] == 1
    assert client.get("/api/jobs", params={"has_recruiter": False}).json()["total"] == 1
    assert client.get("/api/jobs").json()["items"][-1]["recruiter_available"] in (True, False)


def test_metrics_come_from_rows(db, client):
    job = add_listing(db, classification="Product Management Intern", industry="FinTech")
    add_listing(db, title="APM", classification="Associate Product Manager", city="Pune", state="Maharashtra")
    add_listing(db, title="Junior PM", classification="Junior Product Manager", is_active=False, verification_status="Closed",
                date_discovered=utcnow() - timedelta(days=30))
    db.add(Recruiter(job_id=job.id, email="a@acme.com", source_url="https://x.example.com", contact_kind="x",
                     verification_status="Verified"))
    db.add(Recruiter(job_id=job.id, email="b@acme.com", source_url="https://x.example.com", contact_kind="x",
                     verification_status="Publicly Listed"))
    db.commit()
    body = client.get("/api/jobs/metrics").json()
    assert (body["total_jobs"], body["active_jobs"], body["internships"], body["apm_positions"]) == (3, 2, 1, 1)
    assert body["junior_graduate_positions"] == 1
    assert (body["verified_recruiter_contacts"], body["public_recruiter_contacts"]) == (1, 1)
    assert (body["new_last_24h"], body["new_last_7d"]) == (2, 2)
    assert {"name": "Bengaluru", "count": 2} in body["by_city"]
    assert sum(point["count"] for point in body["discovered_over_time"]) == 3


def test_filter_option_endpoints(db, client):
    add_listing(db, industry="FinTech")
    assert client.get("/api/jobs/industries").json() == [{"name": "FinTech", "count": 1}]
    assert client.get("/api/jobs/roles").json() == [{"name": "Associate Product Manager", "count": 1}]
    assert client.get("/api/jobs/locations").json() == [{"name": "Bengaluru", "count": 1}]


def test_detail_has_full_evidence(db, client):
    job = add_listing(db, location_evidence="structured country 'IN'", classification_reason="score 80/100")
    body = client.get(f"/api/jobs/{job.id}").json()
    assert body["description"].startswith(GOOD_DESCRIPTION[:20])
    assert body["location_evidence"] and body["classification_reason"] and body["india_eligible"] is True


def test_detail_hides_review_rows(db, client):
    job = add_listing(db, india_eligible=False, country_code=None, review_status="manual_review")
    assert client.get(f"/api/jobs/{job.id}").status_code == 404


def test_demo_rows_are_hidden_by_default(db, client):
    add_listing(db, provenance="demo_seed")
    assert client.get("/api/jobs").json()["total"] == 0
    assert client.get("/api/jobs/metrics").json()["total_jobs"] == 0
    assert "Associate" not in client.get("/api/export/csv").text.split("\n", 1)[1]


ADMIN_ROUTES = [
    ("post", "/api/scraper/run"),
    ("post", "/api/jobs/1/verify"),
    ("get", "/api/jobs/review-queue"),
    ("post", "/api/jobs/submit"),
    ("patch", "/api/jobs/1/industry"),
    ("post", "/api/jobs/1/recruiters"),
    ("post", "/api/recruiters/1/verify"),
    ("patch", "/api/sources/1"),
    ("post", "/api/export/google-sheets/sync"),
]


@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_admin_routes_refuse_anonymous_callers(client, method, path):
    assert getattr(client, method)(path).status_code in (401, 422)
    assert getattr(client, method)(path, headers={"X-Admin-Key": "wrong"}).status_code in (401, 422)


def test_wrong_key_is_401_with_valid_body(client):
    response = client.post("/api/scraper/run", json={}, headers={"X-Admin-Key": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_repeated_bad_keys_are_rate_limited(client):
    for _ in range(10):
        client.post("/api/scraper/run", json={}, headers={"X-Admin-Key": "wrong"})
    assert client.post("/api/scraper/run", json={}, headers={"X-Admin-Key": "wrong"}).status_code == 429


def test_manual_run_starts_and_is_limited(db, client, monkeypatch):
    calls = []
    monkeypatch.setattr("backend.api.operations.run_discovery", lambda trigger, source_id=None: calls.append(trigger) or {})
    response = client.post("/api/scraper/run", json={}, headers=ADMIN)
    assert response.status_code == 202 and calls == ["manual"]
    source = Source(source_name="s", source_type="rss")
    db.add(source)
    db.flush()
    db.add(ScrapeRun(source_id=source.id, trigger="manual"))
    db.commit()
    assert client.post("/api/scraper/run", json={}, headers=ADMIN).status_code == 429


def test_manual_run_refuses_overlap(client):
    from backend.scheduler import TASK_DISCOVERY, acquire_lease, release_lease

    assert acquire_lease(TASK_DISCOVERY, "other-worker")
    assert client.post("/api/scraper/run", json={}, headers=ADMIN).status_code == 409
    release_lease(TASK_DISCOVERY, "other-worker")


def test_review_flow(db, client):
    job = add_listing(db, title="Product Analyst", classification="Product Analyst", india_eligible=False,
                      country_code=None, country_name=None, review_status="manual_review", review_reason="location unconfirmed")
    queue = client.get("/api/jobs/review-queue", headers=ADMIN).json()
    assert queue["total"] == 1 and queue["items"][0]["review_reason"]
    assert client.post(f"/api/jobs/{job.id}/verify", json={"decision": "approve"}, headers=ADMIN).status_code == 400
    response = client.post(f"/api/jobs/{job.id}/verify", json={"decision": "approve", "note": "Posting says India"}, headers=ADMIN)
    assert response.json()["review_status"] == "accepted"
    assert client.get(f"/api/jobs/{job.id}").status_code == 200


def test_review_reject_hides_job(db, client):
    job = add_listing(db)
    client.post(f"/api/jobs/{job.id}/verify", json={"decision": "reject", "note": "Actually Dubai"}, headers=ADMIN)
    assert client.get(f"/api/jobs/{job.id}").status_code == 404


def test_industry_correction_sticks(db, client):
    job = add_listing(db)
    url = f"/api/jobs/{job.id}/industry"
    assert client.patch(url, json={"industry": "Astrology", "reason": "wrong"}, headers=ADMIN).status_code == 400
    body = client.patch(url, json={"industry": "SaaS", "reason": "Registry was wrong"}, headers=ADMIN).json()
    assert body["industry"] == "SaaS" and "manual" in body["industry_reason"]


def test_recruiter_needs_a_contact_and_evidence(db, client):
    job = add_listing(db)
    url = f"/api/jobs/{job.id}/recruiters"
    bad = {"source_url": "https://acme.example.com/careers", "evidence": "Listed on careers page"}
    assert client.post(url, json=bad, headers=ADMIN).status_code == 400
    assert client.post(url, json={**bad, "email": "careers@acme.com", "evidence": ""}, headers=ADMIN).status_code == 422
    made = client.post(url, json={**bad, "email": "careers@acme.com"}, headers=ADMIN)
    assert made.status_code == 201
    recruiter_id = made.json()["id"]
    assert client.get(f"/api/recruiters/{recruiter_id}").json()["verification_status"] == "Publicly Listed"
    assert client.get("/api/recruiters").json()["total"] == 1


def test_recruiter_detail_hidden_for_hidden_jobs(db, client):
    job = add_listing(db, india_eligible=False, country_code=None, review_status="manual_review")
    row = Recruiter(job_id=job.id, email="a@acme.com", source_url="https://x.example.com", contact_kind="x")
    db.add(row)
    db.commit()
    assert client.get(f"/api/recruiters/{row.id}").status_code == 404
    assert client.get("/api/recruiters").json()["total"] == 0


def test_manual_linkedin_link_needs_details_and_is_not_fetched(db, client, monkeypatch):
    db.add(Source(source_name=MANUAL_SOURCE, source_type="manual"))
    db.commit()
    url = "https://www.linkedin.com/jobs/view/123"
    assert client.post("/api/jobs/submit", json={"url": url}, headers=ADMIN).status_code == 400
    payload = {"url": url, "title": "Associate Product Manager", "company": "Acme", "description": GOOD_DESCRIPTION,
               "location": "Pune, India"}
    body = client.post("/api/jobs/submit", json=payload, headers=ADMIN).json()
    assert body["outcome"] == "inserted"
    assert client.get(f"/api/jobs/{body['job_id']}").json()["provenance"] == "manually_added"


def test_manual_submission_still_enforces_india(db, client):
    db.add(Source(source_name=MANUAL_SOURCE, source_type="manual"))
    db.commit()
    payload = {"url": "https://example.com/j", "title": "Associate Product Manager", "company": "Acme",
               "description": GOOD_DESCRIPTION, "location": "Berlin, Germany"}
    assert client.post("/api/jobs/submit", json=payload, headers=ADMIN).json()["outcome"] == "rejected"
    assert client.get("/api/jobs").json()["total"] == 0


def test_csv_has_required_columns_and_only_visible_rows(db, client):
    job = add_listing(db, salary_min=1000, salary_max=2000, salary_currency="INR")
    add_listing(db, title="Closed Product Analyst", classification="Product Analyst", is_active=False, verification_status="Closed")
    response = client.get("/api/export/csv")
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    row = rows[0]
    assert row["Job Title"] == job.title
    assert (row["Country"], row["India Eligibility"], row["Verification Status"]) == ("India", "Yes", "Active")
    assert row["Salary"] == "INR 1,000 - 2,000"
    assert row["Recruiter Contact"] == "Not Available"
    assert row["Application URL"] == job.application_url


def test_csv_neutralises_formulas(db, client):
    add_listing(db, title="=HYPERLINK(evil) Associate Product Manager")
    rows = list(csv.DictReader(io.StringIO(client.get("/api/export/csv").text)))
    assert rows[0]["Job Title"].startswith("'=")


def test_sheets_status_without_configuration(client):
    assert client.get("/api/export/google-sheets/status").json()["configured"] is False
    body = client.post("/api/export/google-sheets/sync", headers=ADMIN).json()
    assert body["last_status"] == "not_configured"


class FakeRequest:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def execute(self):
        if self.error:
            raise self.error
        return self.result or {}


class FakeSheets:
    def __init__(self, ids=()):
        self.ids, self.appended, self.updated = list(ids), [], []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        if "range" in kwargs:
            return FakeRequest({"values": [[value] for value in self.ids]})
        return FakeRequest({"sheets": [{"properties": {"title": "Jobs"}}]})

    def update(self, **kwargs):
        return FakeRequest()

    def batchUpdate(self, **kwargs):  # noqa: N802 - Google client name
        self.updated.extend(kwargs["body"].get("data", []))
        return FakeRequest()

    def append(self, **kwargs):
        self.appended.extend(kwargs["body"]["values"])
        self.ids.extend(row[0] for row in kwargs["body"]["values"])
        return FakeRequest()


def test_sheets_upsert_never_duplicates(db):
    add_listing(db)
    fake = FakeSheets()
    first = gsheets.sync_jobs(db, service=fake)
    assert (first.status, first.rows_appended, first.rows_updated) == ("success", 1, 0)
    second = gsheets.sync_jobs(db, service=fake)
    assert (second.rows_appended, second.rows_updated) == (0, 1)
    assert len(fake.appended) == 1


def test_sheets_failure_is_logged_without_secrets(db):
    class Broken(FakeSheets):
        def get(self, **kwargs):
            return FakeRequest(error=RuntimeError("quota exceeded"))

    entry = gsheets.sync_jobs(db, service=Broken())
    assert entry.status == "failed" and "quota" in entry.error_details


def test_sources_report_real_health(db, client):
    db.add_all(
        [
            Source(source_name="a", source_type="lever", last_run_status="success", last_successful_run=utcnow()),
            Source(source_name="b", source_type="lever", last_run_status="failed", error_message="HTTP 404"),
            Source(source_name="c", source_type="adzuna", last_run_status="needs_credentials"),
            Source(source_name="d", source_type="lever"),
            Source(source_name="e", source_type="lever", enabled=False),
        ]
    )
    db.commit()
    health = {row["source_name"]: row["health"] for row in client.get("/api/sources").json()}
    assert health == {"a": "healthy", "b": "failing", "c": "needs_credentials", "d": "never_run", "e": "disabled"}
    status = client.get("/api/scraper/status").json()
    assert (status["sources_healthy"], status["sources_failing"], status["sources_never_run"]) == (1, 1, 1)
    assert status["scheduler"]["state"] == "not_started"
    assert status["last_successful_ingestion"] is not None


def test_history_lists_runs(db, client):
    source = Source(source_name="a", source_type="lever")
    db.add(source)
    db.flush()
    db.add(ScrapeRun(source_id=source.id, status="failed", error_details="HTTP 500"))
    db.commit()
    body = client.get("/api/scraper/history").json()
    assert body["items"][0]["source_name"] == "a" and body["items"][0]["error_details"] == "HTTP 500"


def test_source_can_be_disabled(db, client):
    source = Source(source_name="a", source_type="lever")
    db.add(source)
    db.commit()
    assert client.patch(f"/api/sources/{source.id}", json={"enabled": False}, headers=ADMIN).json()["health"] == "disabled"


def test_cors_allows_only_known_origins(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    blocked = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in blocked.headers
