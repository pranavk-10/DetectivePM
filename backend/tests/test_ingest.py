"""Deduplication, updates, and source failure isolation."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.models import Job, JobSourceLink, ScrapeRun, Source
from backend.pipeline.ingest import INSERTED, REJECTED, UNCHANGED, UPDATED, assess, run_discovery, run_source, upsert_job
from backend.sources.registry import MANUAL_SOURCE, load_registry, sync_registry
from backend.tests.conftest import GOOD_DESCRIPTION, add_listing, make_job


def count(db, model=Job) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_good_job_is_accepted(db, source):
    assert upsert_job(db, source, make_job()) == INSERTED
    db.commit()
    job = db.scalar(select(Job))
    assert (job.review_status, job.india_eligible, job.country_code) == ("accepted", True, "IN")
    assert job.provenance == "live_source"
    assert job.classification == "Associate Product Manager"
    assert job.classification_reason and job.classifier_version and job.location_evidence


def test_same_source_and_id_does_not_duplicate(db, source):
    upsert_job(db, source, make_job())
    assert upsert_job(db, source, make_job()) == UNCHANGED
    db.commit()
    assert count(db) == 1


def test_changed_description_updates_the_same_row(db, source):
    upsert_job(db, source, make_job())
    db.commit()
    original = db.scalar(select(Job))
    first_hash, discovered = original.content_hash, original.date_discovered
    assert upsert_job(db, source, make_job(description=GOOD_DESCRIPTION + " Now hiring two people.")) == UPDATED
    db.commit()
    db.refresh(original)
    assert count(db) == 1
    assert original.content_hash != first_hash
    assert "two people" in original.description
    assert original.date_discovered == discovered


def test_same_url_from_two_sources_is_one_job_with_two_links(db, source):
    other = Source(source_name="rss:other", source_type="rss")
    db.add(other)
    db.commit()
    upsert_job(db, source, make_job())
    upsert_job(db, other, make_job(external_job_id="different-id"))
    db.commit()
    assert count(db) == 1
    assert count(db, JobSourceLink) == 2


def test_tracking_parameters_do_not_create_duplicates(db, source):
    upsert_job(db, source, make_job(application_url="https://jobs.example.com/1?utm_source=a"))
    upsert_job(db, source, make_job(external_job_id="2", application_url="https://jobs.example.com/1?utm_source=b"))
    db.commit()
    assert count(db) == 1


def test_same_content_at_a_new_url_is_one_job(db, source):
    upsert_job(db, source, make_job())
    upsert_job(db, source, make_job(external_job_id="2", application_url="https://jobs.example.com/acme/2"))
    db.commit()
    assert count(db) == 1


def test_same_role_and_city_from_another_source_merges(db, source):
    other = Source(source_name="adzuna:india", source_type="adzuna")
    db.add(other)
    db.commit()
    upsert_job(db, source, make_job())
    upsert_job(
        db, other,
        make_job(external_job_id="z", application_url="https://adzuna.in/z", description=GOOD_DESCRIPTION + " Short copy."),
    )
    db.commit()
    assert count(db) == 1
    assert count(db, JobSourceLink) == 2


def test_two_openings_with_different_text_stay_separate(db, source):
    upsert_job(db, source, make_job())
    upsert_job(
        db, source,
        make_job(external_job_id="2", application_url="https://jobs.example.com/2", description=GOOD_DESCRIPTION + " Payments team."),
    )
    db.commit()
    assert count(db) == 2


def test_author_or_profile_urls_play_no_part_in_identity(db, source):
    """Regression: the old id came from the poster's profile, losing their second job."""
    upsert_job(db, source, make_job(external_job_id="1", application_url="https://j.example.com/a"))
    upsert_job(
        db, source,
        make_job(external_job_id="2", title="Product Analyst", application_url="https://j.example.com/b",
                 description=GOOD_DESCRIPTION + " analytics"),
    )
    db.commit()
    assert count(db) == 2


def test_unique_constraints_exist_at_database_level(db):
    add_listing(db, application_url="https://u.example.com/1", canonical_url="https://u.example.com/1")
    with pytest.raises(IntegrityError):
        add_listing(db, application_url="https://u.example.com/2", canonical_url="https://u.example.com/1")
    db.rollback()


def test_database_refuses_accepted_rows_outside_india(db):
    with pytest.raises(IntegrityError):
        add_listing(db, country_code="US", country_name="United States")
    db.rollback()
    with pytest.raises(IntegrityError):
        add_listing(db, india_eligible=False)
    db.rollback()


def test_uncertain_remote_goes_to_review_and_stays_hidden(db, source, client):
    assert upsert_job(db, source, make_job(location="Remote")) == INSERTED
    db.commit()
    job = db.scalar(select(Job))
    assert (job.review_status, job.india_eligible, job.country_code) == ("manual_review", False, None)
    assert client.get("/api/jobs").json()["total"] == 0


def test_irrelevant_role_is_not_stored(db, source):
    assert upsert_job(db, source, make_job(title="Software Engineer")) == REJECTED
    assert assess(make_job(title="Software Engineer")).decision == "reject"
    db.commit()
    assert count(db) == 0


def test_rerun_does_not_overrule_an_administrator(db, source, client):
    upsert_job(db, source, make_job(location="Remote"))
    db.commit()
    job = db.scalar(select(Job))
    response = client.post(
        f"/api/jobs/{job.id}/verify", headers={"X-Admin-Key": "test-admin-key"},
        json={"decision": "approve", "note": "Careers page says India-remote", "city": "Bengaluru"},
    )
    assert response.status_code == 200
    upsert_job(db, source, make_job(location="Remote", description=GOOD_DESCRIPTION + " edited"))
    db.commit()
    db.expire_all()
    assert db.scalar(select(Job)).review_status == "accepted"


def board(payload):
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"jobs": payload})))


def gh_job(job_id, title="Associate Product Manager", location="Pune, India"):
    return {
        "id": job_id, "title": title, "absolute_url": f"https://job-boards.greenhouse.io/test/jobs/{job_id}",
        "location": {"name": location}, "company_name": "Test Co", "content": GOOD_DESCRIPTION + f" Req {job_id}.",
        "first_published": "2026-10-01T00:00:00Z",
    }


def test_run_records_counts(db, source):
    client = board([gh_job(1), gh_job(2, location="Berlin, Germany"), gh_job(3, title="Sales Lead")])
    result = run_source(source.id, "manual", client=client)
    assert result["status"] == "success"
    assert (result["found"], result["inserted"], result["rejected"]) == (3, 1, 2)
    db.expire_all()
    run = db.scalar(select(ScrapeRun))
    assert (run.status, run.trigger, run.records_found, run.records_inserted, run.records_rejected) == ("success", "manual", 3, 1, 2)
    assert run.completed_at is not None
    assert db.get(Source, source.id).last_successful_run is not None


def test_failed_source_records_truth_and_adds_nothing(db, source):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    result = run_source(source.id, client=client)
    assert result["status"] == "failed"
    db.expire_all()
    row = db.get(Source, source.id)
    assert row.last_run_status == "failed" and "404" in row.error_message
    assert row.consecutive_failures == 1 and row.last_successful_run is None
    assert db.scalar(select(ScrapeRun)).status == "failed"
    assert count(db) == 0


def test_one_failed_connector_does_not_stop_the_others(db):
    db.add_all(
        [
            Source(source_name="greenhouse:broken", source_type="greenhouse", config={"board": "broken"}),
            Source(source_name="greenhouse:good", source_type="greenhouse", config={"board": "good"}),
        ]
    )
    db.commit()

    def handler(request):
        if "broken" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, json={"jobs": [gh_job(1)]})

    summary = run_discovery(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert (summary["failed"], summary["success"], summary["inserted"]) == (1, 1, 1)
    assert count(db) == 1


def test_a_bad_record_does_not_fail_the_source(db, source):
    client = board([{"id": 5}, gh_job(1)])
    result = run_source(source.id, client=client)
    assert result["status"] == "success" and result["inserted"] == 1


def test_provider_minimum_interval_is_respected(db):
    from backend.models import utcnow

    row = Source(source_name="remotive:product", source_type="remotive", min_interval_hours=6, last_run_at=utcnow())
    db.add(row)
    db.commit()

    def fail(request):
        raise AssertionError("rate limit ignored")

    assert run_source(row.id, client=httpx.Client(transport=httpx.MockTransport(fail)))["status"] == "skipped"


def test_disabled_and_manual_sources_are_not_polled(db):
    db.add_all(
        [
            Source(source_name="greenhouse:off", source_type="greenhouse", enabled=False, config={"board": "x"}),
            Source(source_name=MANUAL_SOURCE, source_type="manual"),
        ]
    )
    db.commit()
    assert run_discovery()["sources"] == 0


def test_missing_credentials_is_reported_honestly(db):
    row = Source(source_name="adzuna:india", source_type="adzuna")
    db.add(row)
    db.commit()
    assert run_source(row.id)["status"] == "needs_credentials"
    db.expire_all()
    assert db.get(Source, row.id).last_run_status == "needs_credentials"


def test_empty_read_does_not_mark_jobs_missing(db, source):
    run_source(source.id, client=board([gh_job(1)]))
    run_source(source.id, client=board([]))
    db.expire_all()
    assert db.scalar(select(JobSourceLink)).missed_runs == 0


def test_delisted_job_counts_a_missed_run(db, source):
    run_source(source.id, client=board([gh_job(1), gh_job(2)]))
    run_source(source.id, client=board([gh_job(2)]))
    db.expire_all()
    assert sorted(db.scalars(select(JobSourceLink.missed_runs))) == [0, 1]


def test_registry_file_contains_only_evidenced_boards():
    data = load_registry()
    monitored = [c for c in data["companies"] if c["monitoring_status"] == "monitored"]
    assert len(data["companies"]) >= 100 and monitored
    for company in monitored:
        assert company["ats_provider"] and company["ats_board"] and company["verification_evidence"]
    for company in data["companies"]:
        if company["monitoring_status"] != "monitored":
            assert company["ats_board"] is None


def test_known_false_board_matches_stay_out_of_the_registry():
    boards = {(c["ats_provider"], c["ats_board"]) for c in load_registry()["companies"]}
    for wrong in [("lever", "porter"), ("greenhouse", "porter"), ("greenhouse", "slice"), ("ashby", "navi"),
                  ("lever", "fi"), ("lever", "eternal"), ("lever", "hevo"), ("greenhouse", "remote"), ("greenhouse", "wise")]:
        assert wrong not in boards


def test_registry_sync_is_idempotent_and_keeps_admin_choices(db):
    sync_registry(db)
    first = count(db, Source)
    row = db.scalar(select(Source).where(Source.source_type == "lever"))
    row.enabled = False
    db.commit()
    sync_registry(db)
    db.expire_all()
    assert count(db, Source) == first
    assert db.get(Source, row.id).enabled is False
