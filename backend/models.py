"""Database schema. Migrations live in backend/alembic."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")
UtcDateTime = DateTime(timezone=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Value sets ----------------------------------------------------------------
PROVENANCE_LIVE = "live_source"
PROVENANCE_MANUAL = "manually_added"
PROVENANCE_DEMO = "demo_seed"

REVIEW_ACCEPTED = "accepted"
REVIEW_MANUAL = "manual_review"
REVIEW_REJECTED = "rejected"

VERIFY_ACTIVE = "Active"
VERIFY_EXPIRED = "Expired"
VERIFY_CLOSED = "Closed"
VERIFY_UNREACHABLE = "Unreachable"
VERIFY_REVIEW = "Requires Manual Review"
VERIFICATION_STATES = (VERIFY_ACTIVE, VERIFY_EXPIRED, VERIFY_CLOSED, VERIFY_UNREACHABLE, VERIFY_REVIEW)

CONTACT_VERIFIED = "Verified"
CONTACT_PUBLIC = "Publicly Listed"
CONTACT_UNVERIFIED = "Unverified"
CONTACT_NONE = "Not Available"
CONTACT_STATES = (CONTACT_VERIFIED, CONTACT_PUBLIC, CONTACT_UNVERIFIED, CONTACT_NONE)

RUN_RUNNING = "running"
RUN_SUCCESS = "success"
RUN_FAILED = "failed"
RUN_SKIPPED = "skipped"


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({quoted})"


class Company(Base):
    """Registry of monitored companies. Identifiers are only added once verified live."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    website: Mapped[str | None] = mapped_column(String(500))
    careers_url: Mapped[str | None] = mapped_column(String(500))
    ats_provider: Mapped[str | None] = mapped_column(String(50))
    ats_board: Mapped[str | None] = mapped_column(String(200))
    headquarters: Mapped[str | None] = mapped_column(String(200))
    india_presence: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(50))
    monitoring_status: Mapped[str] = mapped_column(String(30), default="pending_source")
    verification_evidence: Mapped[str | None] = mapped_column(Text)
    last_successful_scan: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("ats_provider", "ats_board", name="uq_companies_ats_board"),
        Index("ix_companies_monitoring_status", "monitoring_status"),
    )


class Source(Base):
    """One row per ingestible feed: an ATS board, an RSS feed, an API or manual input."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(200), unique=True)
    source_type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    config: Mapped[dict] = mapped_column(JsonType, default=dict)
    min_interval_hours: Mapped[float] = mapped_column(Float, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_successful_run: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_failure_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_run_status: Mapped[str | None] = mapped_column(String(30))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0)
    jobs_inserted: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company | None] = relationship()

    __table_args__ = (Index("ix_sources_enabled", "enabled"),)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_job_id: Mapped[str | None] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(300))
    company_key: Mapped[str] = mapped_column(String(300))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    company_domain: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[str | None] = mapped_column(Text)

    location: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(2))
    country_name: Mapped[str | None] = mapped_column(String(100))
    workplace_type: Mapped[str | None] = mapped_column(String(20))
    remote_eligibility: Mapped[str | None] = mapped_column(String(50))
    india_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    location_confidence: Mapped[float] = mapped_column(Float, default=0)
    location_evidence: Mapped[str | None] = mapped_column(Text)

    employment_type: Mapped[str | None] = mapped_column(String(50))
    experience_level: Mapped[str | None] = mapped_column(String(50))
    skills: Mapped[list] = mapped_column(JsonType, default=list)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(10))

    application_url: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(1000))
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    date_posted: Mapped[datetime | None] = mapped_column(UtcDateTime)
    date_discovered: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    expiry_date: Mapped[datetime | None] = mapped_column(UtcDateTime)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[str] = mapped_column(String(40), default=VERIFY_ACTIVE)
    verification_reason: Mapped[str | None] = mapped_column(Text)
    url_failure_count: Mapped[int] = mapped_column(Integer, default=0)

    review_status: Mapped[str] = mapped_column(String(20), default=REVIEW_MANUAL)
    review_reason: Mapped[str | None] = mapped_column(Text)
    review_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(20), default=PROVENANCE_LIVE)

    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str | None] = mapped_column(String(50))
    classification_reason: Mapped[str | None] = mapped_column(Text)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0)
    classifier_version: Mapped[str | None] = mapped_column(String(20))

    industry: Mapped[str] = mapped_column(String(50), default="General/Other")
    industry_confidence: Mapped[float] = mapped_column(Float, default=0)
    industry_reason: Mapped[str | None] = mapped_column(Text)
    industry_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    recruiters_checked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    recruiters: Mapped[list["Recruiter"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Recruiter.id"
    )
    source_links: Mapped[list["JobSourceLink"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "review_status <> 'accepted' OR (india_eligible AND country_code = 'IN')",
            name="ck_jobs_accepted_is_india",
        ),
        CheckConstraint(_in("review_status", (REVIEW_ACCEPTED, REVIEW_MANUAL, REVIEW_REJECTED)), name="ck_jobs_review_status"),
        CheckConstraint(
            _in("provenance", (PROVENANCE_LIVE, PROVENANCE_MANUAL, PROVENANCE_DEMO)), name="ck_jobs_provenance"
        ),
        CheckConstraint(_in("verification_status", VERIFICATION_STATES), name="ck_jobs_verification_status"),
        UniqueConstraint("canonical_url", name="uq_jobs_canonical_url"),
        UniqueConstraint("company_key", "content_hash", name="uq_jobs_company_content"),
        Index("ix_jobs_listing", "review_status", "india_eligible", "provenance", "is_active"),
        Index("ix_jobs_date_discovered", "date_discovered"),
        Index("ix_jobs_date_posted", "date_posted"),
        Index("ix_jobs_classification", "classification"),
        Index("ix_jobs_industry", "industry"),
        Index("ix_jobs_city", "city"),
        Index("ix_jobs_workplace_type", "workplace_type"),
        Index("ix_jobs_company_key", "company_key"),
        Index("ix_jobs_verification_status", "verification_status"),
        Index("ix_jobs_dedupe", "company_key", "normalized_title", "city"),
    )


class JobSourceLink(Base):
    """Every source that lists a job, so duplicates keep their provenance."""

    __tablename__ = "job_source_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    external_job_id: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    first_seen_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    missed_runs: Mapped[int] = mapped_column(Integer, default=0)

    job: Mapped[Job] = relationship(back_populates="source_links")
    source: Mapped[Source] = relationship()

    __table_args__ = (
        UniqueConstraint("source_id", "external_job_id", name="uq_job_source_external"),
        Index("ix_job_source_links_job_id", "job_id"),
    )


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    recruiter_name: Mapped[str | None] = mapped_column(String(200))
    designation: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    public_profile_url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str] = mapped_column(String(1000))
    contact_kind: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(30), default=CONTACT_PUBLIC)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    discovered_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    job: Mapped[Job] = relationship(back_populates="recruiters")

    __table_args__ = (
        CheckConstraint(_in("verification_status", CONTACT_STATES), name="ck_recruiters_verification_status"),
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL OR public_profile_url IS NOT NULL",
            name="ck_recruiters_has_contact",
        ),
        UniqueConstraint("job_id", "email", "phone", name="uq_recruiters_job_contact"),
        Index("ix_recruiters_job_id", "job_id"),
        Index("ix_recruiters_verification_status", "verification_status"),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    trigger: Mapped[str] = mapped_column(String(20), default="scheduled")
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(20), default=RUN_RUNNING)
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_review: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship()

    __table_args__ = (
        Index("ix_scrape_runs_source_started", "source_id", "started_at"),
        Index("ix_scrape_runs_started_at", "started_at"),
    )


class SchedulerLease(Base):
    """Lease row per task. Prevents overlap across processes and instances."""

    __tablename__ = "scheduler_leases"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(100))
    acquired_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class SchedulerHeartbeat(Base):
    """Written by whichever process runs the schedule, read by the API."""

    __tablename__ = "scheduler_heartbeats"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), unique=True)
    last_beat: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    next_runs: Mapped[dict] = mapped_column(JsonType, default=dict)
    last_results: Mapped[dict] = mapped_column(JsonType, default=dict)


class SheetSyncLog(Base):
    __tablename__ = "sheet_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(20))
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_appended: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[str | None] = mapped_column(Text)
