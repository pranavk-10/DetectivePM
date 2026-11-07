"""Tests run on a real, throwaway PostgreSQL, migrated with Alembic."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_data_dir = tempfile.mkdtemp(prefix="detectivepm-test-pg-")
_server = None
_external = os.environ.get("TEST_DATABASE_URL")
if not _external:
    import pgserver

    _server = pgserver.get_server(Path(_data_dir))
    _server.psql("CREATE DATABASE detectivepm_test;")
    _external = _server.get_uri().rsplit("/", 1)[0] + "/detectivepm_test"

os.environ.update(
    DATABASE_URL=_external,
    ENVIRONMENT="test",
    ADMIN_API_KEY="test-admin-key",
    MANUAL_RUN_COOLDOWN_SECONDS="300",
    SHOW_DEMO_DATA="false",
    RUN_SCHEDULER_IN_API="false",
    GOOGLE_SHEETS_ID="",
    GOOGLE_SERVICE_ACCOUNT_JSON="",
    ADZUNA_APP_ID="",
    ADZUNA_APP_KEY="",
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend import db as db_module  # noqa: E402
from backend.auth import reset_failures  # noqa: E402
from backend.db import Base, SessionLocal  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Job, Source, utcnow  # noqa: E402
from backend.sources.base import NormalizedJob  # noqa: E402
from backend.sources.text import canonicalize_url, company_key, content_hash, normalize_title  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ADMIN = {"X-Admin-Key": "test-admin-key"}

GOOD_DESCRIPTION = (
    "You will own the product roadmap and prioritise features with engineering and design. "
    "Run user research, write PRDs, and track product metrics, funnels and retention. "
    "Work cross-functional with stakeholders. Strong SQL, A/B testing, Figma and analytical skills. "
    "0-1 years of product experience."
)


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", _external.replace("%", "%%"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    command.upgrade(alembic_config(), "head")
    yield
    db_module.engine.dispose()
    if _server is not None:
        _server.cleanup()
        shutil.rmtree(_data_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_tables():
    reset_failures()
    yield
    names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with db_module.engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def source(db):
    row = Source(source_name="greenhouse:test", source_type="greenhouse", config={"board": "test"})
    db.add(row)
    db.commit()
    return row


def make_job(**overrides) -> NormalizedJob:
    values = dict(
        external_job_id="1",
        title="Associate Product Manager",
        company="Acme",
        description=GOOD_DESCRIPTION,
        application_url="https://jobs.example.com/acme/1",
        source_url="https://jobs.example.com/acme/1",
        location="Bengaluru, India",
    )
    values.update(overrides)
    return NormalizedJob(**values)


def add_listing(db, **overrides) -> Job:
    """Insert a row directly, for API tests that are not about ingestion."""
    title = overrides.pop("title", "Associate Product Manager")
    company = overrides.pop("company", "Acme")
    number = db.query(Job).count() + 1
    url = overrides.pop("application_url", f"https://jobs.example.com/{number}")
    defaults = dict(
        external_job_id=str(number), title=title, normalized_title=normalize_title(title), company=company,
        company_key=company_key(company), description=f"{GOOD_DESCRIPTION} {number}", location="Bengaluru, India",
        city="Bengaluru", state="Karnataka", country_code="IN", country_name="India", workplace_type="On-site",
        india_eligible=True, location_confidence=1.0, classification="Associate Product Manager",
        application_url=url, canonical_url=canonicalize_url(url), source_name="greenhouse:test",
        content_hash=content_hash(company, title, f"{GOOD_DESCRIPTION} {number}"), review_status="accepted",
        date_discovered=utcnow(), is_active=True, skills=["SQL"],
    )
    defaults.update(overrides)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    return job
