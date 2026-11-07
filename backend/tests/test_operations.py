"""Scheduler, migrations, production guards and proof that mock paths are gone."""

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import inspect, select, text

from backend import db as db_module
from backend import scheduler as sched
from backend.config import Settings, normalise_db_url
from backend.db import Base
from backend.models import ScrapeRun, SchedulerHeartbeat, Source, utcnow
from backend.tests.conftest import alembic_config

ROOT = Path(__file__).resolve().parents[2]


def test_database_is_postgresql(db):
    assert "PostgreSQL" in db.execute(text("SELECT version()")).scalar()


def test_migrations_match_the_models():
    with db_module.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_migration_downgrades_and_upgrades():
    config = alembic_config()
    command.downgrade(config, "base")
    assert "jobs" not in inspect(db_module.engine).get_table_names()
    command.upgrade(config, "head")
    assert {"jobs", "recruiters", "sources", "scrape_runs", "companies"} <= set(inspect(db_module.engine).get_table_names())


def test_required_indexes_and_constraints_exist():
    inspector = inspect(db_module.engine)
    assert {"ix_jobs_listing", "ix_jobs_date_discovered", "ix_jobs_city"} <= {i["name"] for i in inspector.get_indexes("jobs")}
    assert "uq_jobs_canonical_url" in {c["name"] for c in inspector.get_unique_constraints("jobs")}
    assert "ck_jobs_accepted_is_india" in {c["name"] for c in inspector.get_check_constraints("jobs")}
    assert inspector.get_foreign_keys("recruiters")


def test_discovery_runs_every_five_hours():
    scheduler = BackgroundScheduler(timezone="UTC")
    sched.configure(scheduler)
    job = scheduler.get_job(sched.TASK_DISCOVERY)
    assert job.trigger.interval == timedelta(hours=5)
    assert job.max_instances == 1 and job.coalesce is True
    assert {j.id for j in scheduler.get_jobs()} == {
        sched.TASK_DISCOVERY, sched.TASK_VERIFICATION, sched.TASK_ENRICHMENT, sched.TASK_MAINTENANCE, "heartbeat",
    }


def test_lease_blocks_a_second_owner():
    assert sched.acquire_lease("t", "a")
    assert not sched.acquire_lease("t", "b")
    sched.release_lease("t", "b")  # not the owner, so nothing changes
    assert sched.lease_held("t")
    sched.release_lease("t", "a")
    assert sched.acquire_lease("t", "b")


def test_expired_lease_can_be_taken_over():
    assert sched.acquire_lease("t", "dead", ttl=timedelta(seconds=-1))
    assert sched.acquire_lease("t", "alive")


def test_overlapping_run_is_skipped():
    calls = []
    assert sched.acquire_lease("x", "other")
    assert sched.run_locked("x", lambda: calls.append(1) or {}) is None
    assert calls == []


def test_failed_task_is_recorded_and_lease_released(db):
    def boom():
        raise RuntimeError("source exploded")

    assert sched.run_locked("y", boom) is None
    assert not sched.lease_held("y")
    results = db.scalar(select(SchedulerHeartbeat)).last_results
    assert results["y"]["status"] == "failed" and "exploded" in results["y"]["error"]


def test_scheduler_state_reflects_heartbeats(db):
    assert sched.scheduler_state()["state"] == "not_started"
    scheduler = BackgroundScheduler(timezone="UTC")
    sched.configure(scheduler)
    scheduler.start(paused=True)
    sched.heartbeat(scheduler)
    scheduler.shutdown(wait=False)
    state = sched.scheduler_state()
    assert state["state"] == "running" and sched.TASK_DISCOVERY in state["next_runs"]

    row = db.scalar(select(SchedulerHeartbeat))
    row.last_beat = utcnow() - timedelta(hours=1)
    db.commit()
    assert sched.scheduler_state()["state"] == "stopped"


def test_maintenance_closes_interrupted_runs(db):
    source = Source(source_name="a", source_type="lever")
    db.add(source)
    db.flush()
    db.add(ScrapeRun(source_id=source.id, status="running", started_at=utcnow() - timedelta(hours=9)))
    db.add(ScrapeRun(source_id=source.id, status="success", started_at=utcnow() - timedelta(days=120)))
    db.commit()
    assert sched.run_maintenance()["stale_runs_closed"] == 1
    db.expire_all()
    assert db.scalar(select(ScrapeRun)).status == "failed"


def test_postgres_urls_are_normalised():
    expected = "postgresql+psycopg://u:p@h/d"
    assert normalise_db_url("postgres://u:p@h/d") == expected
    assert normalise_db_url("postgresql://u:p@h/d") == expected


@pytest.mark.parametrize(
    "overrides, problem",
    [
        ({"database_url": "sqlite:///x.db", "admin_api_key": "k"}, "PostgreSQL"),
        ({"database_url": "postgresql+psycopg://h/d", "admin_api_key": ""}, "ADMIN_API_KEY"),
        ({"database_url": "postgresql+psycopg://h/d", "admin_api_key": "k", "show_demo_data": True}, "SHOW_DEMO_DATA"),
    ],
)
def test_production_refuses_unsafe_configuration(overrides, problem):
    with pytest.raises(RuntimeError, match=problem):
        Settings(environment="production", **overrides).validate()


def test_production_cors_is_only_the_frontend():
    settings = Settings(environment="production", frontend_url="https://app.example.com")
    assert settings.cors_origins == ["https://app.example.com"]


def test_seed_refuses_production():
    result = subprocess.run(
        [sys.executable, "-m", "backend.seed_demo"],
        cwd=ROOT, capture_output=True, text=True,
        env={"ENVIRONMENT": "production", "DATABASE_URL": "postgresql://x@127.0.0.1:1/x", "ADMIN_API_KEY": "k",
             "PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )
    assert result.returncode == 1
    assert "Refusing" in result.stderr


def test_no_production_path_imports_the_demo_seed():
    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" in path.parts or path.name == "seed_demo.py" or "alembic" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        assert "seed_demo" not in body, path


def test_mock_generator_and_browser_scraping_are_gone():
    forbidden = ("generate_mock_posts", "use_mock_on_failure", "playwright", "_MOCK_", "linkedin.com/search")
    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        for word in forbidden:
            assert word not in body, f"{word} found in {path}"


def test_openapi_lists_every_required_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    required = [
        "/api/health", "/api/jobs", "/api/jobs/{job_id}", "/api/jobs/metrics", "/api/jobs/industries",
        "/api/jobs/roles", "/api/jobs/locations", "/api/scraper/status", "/api/scraper/history", "/api/sources",
        "/api/recruiters", "/api/recruiters/{recruiter_id}", "/api/scraper/run", "/api/jobs/{job_id}/verify",
        "/api/export/csv", "/api/export/google-sheets/status",
    ]
    assert not [route for route in required if route not in paths]


def test_generated_frontend_types_are_current(client):
    schema_file = ROOT / "frontend" / "openapi.json"
    import json

    assert json.loads(schema_file.read_text(encoding="utf-8")) == client.get("/openapi.json").json()
