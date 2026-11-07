"""Freshness signals and recruiter evidence."""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

from backend.models import JobSourceLink, Recruiter, Source, utcnow
from backend.pipeline.recruiters import (
    KIND_COMPANY,
    KIND_INDIVIDUAL,
    KIND_PHONE,
    KIND_UNVERIFIED,
    enrich_job,
    extract_contacts,
    run_enrichment,
)
from backend.pipeline.verify import check_url, verify_batch, verify_job
from backend.tests.conftest import add_listing


def responder(status=200, text="ok"):
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text=text)))


def link(db, job, missed=0):
    source = db.scalar(select(Source)) or Source(source_name="s", source_type="greenhouse")
    db.add(source)
    db.flush()
    db.add(JobSourceLink(job_id=job.id, source_id=source.id, external_job_id=str(job.id), missed_runs=missed))
    db.commit()
    db.refresh(job)


def test_live_page_keeps_job_active(db):
    job = add_listing(db)
    link(db, job)
    assert verify_job(job, responder()) == "Active"
    assert job.is_active and job.last_verified_at


def test_past_deadline_expires(db):
    job = add_listing(db, expiry_date=utcnow() - timedelta(days=1))
    assert verify_job(job, responder()) == "Expired"
    assert job.is_active is False


def test_one_404_is_not_enough_to_close(db):
    job = add_listing(db)
    link(db, job)
    assert verify_job(job, responder(404)) == "Active"
    assert job.is_active
    assert "next check" in job.verification_reason
    assert verify_job(job, responder(404)) == "Closed"
    assert job.is_active is False


def test_recovered_page_resets_the_failure_count(db):
    job = add_listing(db)
    link(db, job)
    verify_job(job, responder(404))
    verify_job(job, responder(200))
    assert job.url_failure_count == 0
    assert verify_job(job, responder(404)) == "Active"


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_errors_never_expire_a_job(db, status):
    job = add_listing(db)
    assert verify_job(job, responder(status)) == "Unreachable"
    assert job.is_active is True


def test_server_error_with_listing_stays_active(db):
    job = add_listing(db)
    link(db, job)
    assert verify_job(job, responder(503)) == "Active"


def test_timeout_is_not_expiry(db):
    def handler(request):
        raise httpx.ReadTimeout("slow")

    job = add_listing(db)
    assert verify_job(job, httpx.Client(transport=httpx.MockTransport(handler))) == "Unreachable"
    assert job.is_active


@pytest.mark.parametrize("status", [401, 403, 429])
def test_bot_blocks_do_not_close_a_listed_job(db, status):
    job = add_listing(db)
    link(db, job)
    assert verify_job(job, responder(status)) == "Active"
    assert "refused automated checks" in job.verification_reason


def test_delisted_by_source_closes(db):
    job = add_listing(db)
    link(db, job, missed=2)
    assert verify_job(job, responder()) == "Closed"


def test_one_missed_run_does_not_close(db):
    job = add_listing(db)
    link(db, job, missed=1)
    assert verify_job(job, responder()) == "Active"


def test_closed_wording_on_the_page_closes():
    assert check_url(responder(text="Sorry, this job is no longer available"), "https://x.example.com").kind == "closed"


def test_expired_job_leaves_active_listings_but_stays_filterable(db, client):
    add_listing(db, is_active=False, verification_status="Expired")
    assert client.get("/api/jobs").json()["total"] == 0
    assert client.get("/api/jobs", params={"status": "expired"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"status": "all"}).json()["total"] == 1


def test_verify_batch_counts_states(db):
    add_listing(db)
    assert verify_batch(db, responder(), pause=0) == {"Active": 1}


def company_email_text():
    return "To apply, send your resume to careers@acme.com with the subject PM."


def test_company_recruiting_email_is_publicly_listed_not_verified():
    contact = extract_contacts(company_email_text(), "Acme", "acme.com")[0]
    assert (contact.email, contact.kind, contact.status) == ("careers@acme.com", KIND_COMPANY, "Publicly Listed")
    assert contact.evidence


def test_individual_email_is_distinguished():
    contact = extract_contacts("Reach out to Priya Sharma at priya.sharma@acme.com to apply.", "Acme", "acme.com")[0]
    assert (contact.kind, contact.status, contact.name) == (KIND_INDIVIDUAL, "Publicly Listed", "Priya Sharma")


def test_free_mail_is_unverified():
    contact = extract_contacts("Send CV to acmehiring@gmail.com to apply", "Acme", "acme.com")[0]
    assert (contact.kind, contact.status) == (KIND_UNVERIFIED, "Unverified")


def test_other_company_domain_is_unverified():
    assert extract_contacts("Apply: jobs@agency.example", "Acme", "acme.com")[0].status == "Unverified"


@pytest.mark.parametrize(
    "text",
    [
        "For accommodations during hiring contact accommodations@acme.com",
        "Our privacy team: privacy@acme.com handles applications data",
        "Report recruitment fraud to security@acme.com",
        "Our support line is help@acme.com",
        "Write to billing@acme.com",
        "Customers can write to someone@acme.com",
    ],
)
def test_non_recruiting_addresses_are_ignored(text):
    assert extract_contacts(text, "Acme", "acme.com") == []


def test_no_email_is_ever_guessed():
    text = "Join Acme! Our recruiter is Priya Sharma. We are hiring a PM."
    assert extract_contacts(text, "Acme", "acme.com") == []


def test_public_phone_needs_recruiting_context():
    assert extract_contacts("Call our HR to apply: +91 98765 43210", "Acme", None)[0].kind == KIND_PHONE
    assert extract_contacts("Ticket reference 9876543210 in our system", "Acme", None) == []


def test_enrichment_is_idempotent_and_never_auto_verifies(db):
    job = add_listing(db, description=company_email_text() + " " * 90, company_domain="acme.com")
    assert enrich_job(db, job) == 1
    db.commit()
    assert enrich_job(db, job) == 0
    db.commit()
    assert db.scalar(select(func.count()).select_from(Recruiter)) == 1
    assert db.scalar(select(Recruiter)).verification_status == "Publicly Listed"
    assert db.scalar(select(Recruiter)).source_url == job.application_url


def test_job_without_contact_stays_listed(db, client):
    job = add_listing(db)
    assert run_enrichment()["contacts_added"] == 0
    body = client.get(f"/api/jobs/{job.id}").json()
    assert body["recruiters"] == [] and body["recruiter_available"] is False
    assert client.get("/api/jobs").json()["total"] == 1
