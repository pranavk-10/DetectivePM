"""API contract. The frontend's TypeScript types are generated from these models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Health(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    database: Literal["connected", "unavailable"]
    environment: str


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RecruiterOut(ORMModel):
    id: int
    job_id: int
    recruiter_name: str | None
    designation: str | None
    company: str | None
    email: str | None
    phone: str | None
    public_profile_url: str | None
    source_url: str
    contact_kind: str
    evidence: str | None
    verification_status: str
    confidence_score: float
    discovered_at: datetime


class RecruiterPage(BaseModel):
    items: list[RecruiterOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class RecruiterCreate(BaseModel):
    recruiter_name: str | None = Field(default=None, max_length=200)
    designation: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=40)
    public_profile_url: HttpUrl | None = None
    source_url: HttpUrl
    evidence: str = Field(min_length=5, max_length=1000)
    verification_status: Literal["Verified", "Publicly Listed", "Unverified"] = "Publicly Listed"


class RecruiterVerify(BaseModel):
    verification_status: Literal["Verified", "Publicly Listed", "Unverified"]
    evidence: str = Field(min_length=5, max_length=1000)


class JobListItem(ORMModel):
    id: int
    title: str
    company: str
    industry: str
    classification: str | None
    relevance_score: int
    location: str | None
    city: str | None
    state: str | None
    country_code: str | None
    workplace_type: str | None
    employment_type: str | None
    date_posted: datetime | None
    date_discovered: datetime
    source_name: str
    verification_status: str
    is_active: bool
    application_url: str
    provenance: str
    recruiter_available: bool = False
    freshness: Literal["new", "recent", "older"] = "older"


class JobDetail(JobListItem):
    description: str
    requirements: str | None
    responsibilities: str | None
    skills: list[str]
    company_domain: str | None
    country_name: str | None
    remote_eligibility: str | None
    india_eligible: bool
    location_confidence: float
    location_evidence: str | None
    experience_level: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    source_url: str | None
    canonical_url: str
    last_verified_at: datetime | None
    expiry_date: datetime | None
    verification_reason: str | None
    classification_reason: str | None
    classification_confidence: float
    classifier_version: str | None
    industry_confidence: float
    industry_reason: str | None
    recruiters: list[RecruiterOut]
    sources: list[str] = []


class JobPage(BaseModel):
    items: list[JobListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CountBucket(BaseModel):
    name: str
    count: int


class DateBucket(BaseModel):
    date: str
    count: int


class JobMetrics(BaseModel):
    total_jobs: int
    active_jobs: int
    internships: int
    apm_positions: int
    junior_graduate_positions: int
    verified_recruiter_contacts: int
    public_recruiter_contacts: int
    new_last_24h: int
    new_last_7d: int
    by_industry: list[CountBucket]
    by_role: list[CountBucket]
    by_company: list[CountBucket]
    by_city: list[CountBucket]
    by_source: list[CountBucket]
    by_verification: list[CountBucket]
    discovered_over_time: list[DateBucket]


class ScrapeRunOut(ORMModel):
    id: int
    source_id: int
    source_name: str
    trigger: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    records_found: int
    records_inserted: int
    records_updated: int
    records_rejected: int
    error_details: str | None


class ScrapeRunPage(BaseModel):
    items: list[ScrapeRunOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskResult(BaseModel):
    status: str
    at: str
    error: str | None = None
    summary: dict | None = None


class SchedulerStatus(BaseModel):
    state: Literal["running", "stopped", "not_started"]
    last_heartbeat: datetime | None
    owner: str | None
    next_runs: dict[str, str]
    last_results: dict[str, TaskResult]


class ScraperStatus(BaseModel):
    scheduler: SchedulerStatus
    ingestion_running: bool
    last_successful_ingestion: datetime | None
    sources_total: int
    sources_healthy: int
    sources_failing: int
    sources_needing_credentials: int
    sources_never_run: int


class SourceOut(ORMModel):
    id: int
    source_name: str
    source_type: str
    base_url: str | None
    enabled: bool
    health: Literal["healthy", "failing", "needs_credentials", "never_run", "disabled", "manual"]
    last_run_at: datetime | None
    last_successful_run: datetime | None
    last_failure_at: datetime | None
    last_run_status: str | None
    consecutive_failures: int
    jobs_discovered: int
    jobs_inserted: int
    error_message: str | None


class ScrapeRequest(BaseModel):
    source_id: int | None = None


class ScrapeAccepted(BaseModel):
    status: Literal["accepted"]
    message: str


class JobVerifyRequest(BaseModel):
    """With no decision, re-check the listing. With one, record a manual review."""

    decision: Literal["approve", "reject"] | None = None
    note: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    classification: str | None = None


class JobVerifyResult(BaseModel):
    id: int
    verification_status: str
    verification_reason: str | None
    review_status: str
    last_verified_at: datetime | None


class ReviewItem(ORMModel):
    id: int
    title: str
    company: str
    location: str | None
    source_name: str
    application_url: str
    relevance_score: int
    review_reason: str | None
    location_evidence: str | None
    date_discovered: datetime


class ReviewPage(BaseModel):
    items: list[ReviewItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class IndustryCorrection(BaseModel):
    industry: str
    reason: str = Field(min_length=3, max_length=500)


class JobSubmission(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=500)
    company: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=50_000)
    location: str | None = Field(default=None, max_length=500)
    employment_type: str | None = Field(default=None, max_length=50)


class JobSubmissionResult(BaseModel):
    outcome: Literal["inserted", "updated", "unchanged", "rejected"]
    job_id: int | None
    message: str


class SheetsStatus(BaseModel):
    configured: bool
    last_status: str | None
    last_started_at: datetime | None
    last_completed_at: datetime | None
    rows_updated: int
    rows_appended: int
    error_details: str | None


class SourceToggle(BaseModel):
    enabled: bool
