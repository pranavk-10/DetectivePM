"""Job listing, detail, metrics and review endpoints."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, case, cast, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.auth import require_admin
from backend.db import get_db
from backend.models import (
    CONTACT_PUBLIC,
    CONTACT_VERIFIED,
    REVIEW_ACCEPTED,
    REVIEW_MANUAL,
    REVIEW_REJECTED,
    VERIFY_ACTIVE,
    Job,
    Recruiter,
    Source,
    utcnow,
)
from backend.pipeline.geo import INDIA_CODE, INDIA_NAME
from backend.pipeline.industry import INDUSTRIES
from backend.pipeline.ingest import INSERTED, REJECTED, ingest_manual
from backend.pipeline.recruiters import enrich_job
from backend.pipeline.roles import ROLE_APM, ROLE_ENTRY, ROLE_GRADUATE, ROLE_INTERN, ROLE_JUNIOR, ROLES
from backend.pipeline.verify import verify_job
from backend.queries import visible_condition, visible_jobs
from backend.schemas import (
    CountBucket,
    DateBucket,
    ErrorResponse,
    IndustryCorrection,
    JobDetail,
    JobListItem,
    JobMetrics,
    JobPage,
    JobSubmission,
    JobSubmissionResult,
    JobVerifyRequest,
    JobVerifyResult,
    ReviewItem,
    ReviewPage,
)
from backend.sources.base import SourceError, build_client
from backend.sources.manual_submission import ManualSubmissionConnector
from backend.sources.registry import MANUAL_SOURCE

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SORTABLE = {
    "date_discovered": Job.date_discovered,
    "date_posted": Job.date_posted,
    "title": Job.title,
    "company": Job.company,
    "city": Job.city,
    "relevance_score": Job.relevance_score,
}
BREAKDOWN_LIMIT = 10


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _freshness(job: Job, now) -> str:
    age = now - job.date_discovered
    if age <= timedelta(hours=24):
        return "new"
    return "recent" if age <= timedelta(days=7) else "older"


def _list_item(job: Job, now) -> JobListItem:
    item = JobListItem.model_validate(job)
    item.recruiter_available = bool(job.recruiters)
    item.freshness = _freshness(job, now)
    return item


def _detail(job: Job) -> JobDetail:
    data = JobDetail.model_validate(job)
    data.recruiter_available = bool(job.recruiters)
    data.freshness = _freshness(job, utcnow())
    data.sources = sorted({link.source.source_name for link in job.source_links})
    return data


def _page_count(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


@router.get("", response_model=JobPage)
def list_jobs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: Literal["date_discovered", "date_posted", "title", "company", "city", "relevance_score"] = "date_discovered",
    sort_order: Literal["asc", "desc"] = "desc",
    search: str | None = Query(None, max_length=200),
    role: list[str] | None = Query(None),
    industry: str | None = Query(None, max_length=50),
    city: str | None = Query(None, max_length=100),
    workplace_type: Literal["Remote", "Hybrid", "On-site"] | None = None,
    status_filter: Literal["active", "expired", "all"] = Query("active", alias="status"),
    discovered_within_days: int | None = Query(None, ge=1, le=365),
    has_recruiter: bool | None = None,
) -> JobPage:
    query = visible_jobs()
    if search and search.strip():
        pattern = _like(search.strip())
        query = query.where(
            or_(
                Job.title.ilike(pattern, escape="\\"),
                Job.company.ilike(pattern, escape="\\"),
                Job.city.ilike(pattern, escape="\\"),
                cast(Job.skills, String).ilike(pattern, escape="\\"),
            )
        )
    if role:
        query = query.where(Job.classification.in_(role))
    if industry:
        query = query.where(Job.industry == industry)
    if city:
        query = query.where(Job.city == city)
    if workplace_type:
        query = query.where(Job.workplace_type == workplace_type)
    if status_filter == "active":
        query = query.where(Job.is_active.is_(True))
    elif status_filter == "expired":
        query = query.where(Job.is_active.is_(False))
    if discovered_within_days:
        query = query.where(Job.date_discovered >= utcnow() - timedelta(days=discovered_within_days))
    if has_recruiter is not None:
        contact = exists().where(Recruiter.job_id == Job.id)
        query = query.where(contact if has_recruiter else ~contact)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = SORTABLE[sort_by]
    ordering = column.asc() if sort_order == "asc" else column.desc()
    jobs = db.scalars(
        query.options(selectinload(Job.recruiters))
        .order_by(ordering.nulls_last(), Job.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    now = utcnow()
    return JobPage(
        items=[_list_item(job, now) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_page_count(total, page_size),
    )


def _breakdown(db: Session, column, *, limit: int | None = BREAKDOWN_LIMIT) -> list[CountBucket]:
    count = func.count(Job.id)
    query = (
        select(column, count)
        .where(visible_condition(), column.is_not(None))
        .group_by(column)
        .order_by(count.desc(), column)
    )
    if limit:
        query = query.limit(limit)
    return [CountBucket(name=str(name), count=value) for name, value in db.execute(query)]


@router.get("/metrics", response_model=JobMetrics)
def job_metrics(db: Session = Depends(get_db)) -> JobMetrics:
    now = utcnow()

    def count_where(condition) -> func:
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    row = db.execute(
        select(
            func.count(Job.id),
            count_where(Job.is_active.is_(True)),
            count_where(Job.classification == ROLE_INTERN),
            count_where(Job.classification == ROLE_APM),
            count_where(Job.classification.in_((ROLE_JUNIOR, ROLE_GRADUATE, ROLE_ENTRY))),
            count_where(Job.date_discovered >= now - timedelta(hours=24)),
            count_where(Job.date_discovered >= now - timedelta(days=7)),
        ).where(visible_condition())
    ).one()

    contacts = dict(
        db.execute(
            select(Recruiter.verification_status, func.count(Recruiter.id))
            .join(Job, Job.id == Recruiter.job_id)
            .where(visible_condition())
            .group_by(Recruiter.verification_status)
        ).all()
    )

    day = func.date(Job.date_discovered)
    timeline = db.execute(
        select(day, func.count(Job.id)).where(visible_condition()).group_by(day).order_by(day)
    ).all()

    return JobMetrics(
        total_jobs=row[0],
        active_jobs=row[1],
        internships=row[2],
        apm_positions=row[3],
        junior_graduate_positions=row[4],
        verified_recruiter_contacts=contacts.get(CONTACT_VERIFIED, 0),
        public_recruiter_contacts=contacts.get(CONTACT_PUBLIC, 0),
        new_last_24h=row[5],
        new_last_7d=row[6],
        by_industry=_breakdown(db, Job.industry, limit=None),
        by_role=_breakdown(db, Job.classification, limit=None),
        by_company=_breakdown(db, Job.company),
        by_city=_breakdown(db, Job.city),
        by_source=_breakdown(db, Job.source_name),
        by_verification=_breakdown(db, Job.verification_status, limit=None),
        discovered_over_time=[DateBucket(date=str(date), count=count) for date, count in timeline],
    )


@router.get("/industries", response_model=list[CountBucket])
def job_industries(db: Session = Depends(get_db)) -> list[CountBucket]:
    return _breakdown(db, Job.industry, limit=None)


@router.get("/roles", response_model=list[CountBucket])
def job_roles(db: Session = Depends(get_db)) -> list[CountBucket]:
    return _breakdown(db, Job.classification, limit=None)


@router.get("/locations", response_model=list[CountBucket])
def job_locations(db: Session = Depends(get_db)) -> list[CountBucket]:
    return _breakdown(db, Job.city, limit=None)


@router.get("/review-queue", response_model=ReviewPage, dependencies=[Depends(require_admin)])
def review_queue(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReviewPage:
    query = select(Job).where(Job.review_status == REVIEW_MANUAL)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    jobs = db.scalars(
        query.order_by(Job.date_discovered.desc(), Job.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return ReviewPage(
        items=[ReviewItem.model_validate(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_page_count(total, page_size),
    )


@router.post(
    "/submit",
    response_model=JobSubmissionResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    responses={400: {"model": ErrorResponse}},
)
def submit_job(payload: JobSubmission, db: Session = Depends(get_db)) -> JobSubmissionResult:
    """Add a job by URL. Only known ATS links are fetched; others need their details supplied."""
    url = str(payload.url)
    client = build_client()
    connector = ManualSubmissionConnector(client=client)
    try:
        job = connector.from_url(url)
    except SourceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not read that job: {exc}") from exc
    finally:
        client.close()

    if job is None:
        if not (payload.title and payload.company and payload.description):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This link is not a supported ATS, so it is not fetched. Provide title, company and description.",
            )
        job = connector.from_fields(
            url=url, title=payload.title, company=payload.company, description=payload.description,
            location=payload.location, employment_type=payload.employment_type,
        )

    problems = connector.validate_job(job)
    if problems:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid job: " + ", ".join(problems))

    source = db.scalar(select(Source).where(Source.source_name == MANUAL_SOURCE))
    if source is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Registry has not been synced")
    outcome, stored = ingest_manual(db, source, job)
    db.commit()
    if outcome == REJECTED:
        message = "Rejected: this job failed the India or role validation and was not stored."
    elif stored and stored.review_status == REVIEW_MANUAL:
        message = f"Stored for manual review: {stored.review_reason}"
    elif outcome == INSERTED:
        message = "Added to active listings."
    else:
        message = "Already known; record refreshed."
    return JobSubmissionResult(outcome=outcome, job_id=stored.id if stored else None, message=message)


@router.get("/{job_id}", response_model=JobDetail, responses={404: {"model": ErrorResponse}})
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobDetail:
    job = db.scalar(
        visible_jobs()
        .where(Job.id == job_id)
        .options(selectinload(Job.recruiters), selectinload(Job.source_links))
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _detail(job)


@router.post(
    "/{job_id}/verify",
    response_model=JobVerifyResult,
    dependencies=[Depends(require_admin)],
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def verify_endpoint(job_id: int, payload: JobVerifyRequest | None = None, db: Session = Depends(get_db)) -> JobVerifyResult:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    payload = payload or JobVerifyRequest()

    if payload.decision == "approve":
        if payload.classification and payload.classification not in ROLES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown classification")
        if not (payload.classification or job.classification):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Approving needs a role classification")
        note = (payload.note or "").strip()
        if not note:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Approving needs a note recording the India evidence")
        job.review_status = REVIEW_ACCEPTED
        job.review_locked = True
        job.review_reason = f"approved by administrator: {note}"
        job.india_eligible = True
        job.country_code = INDIA_CODE
        job.country_name = INDIA_NAME
        job.location_evidence = f"manual review: {note}"
        job.city = payload.city or job.city
        job.state = payload.state or job.state
        job.classification = payload.classification or job.classification
        job.verification_status = VERIFY_ACTIVE
        job.verification_reason = "approved in manual review"
        job.is_active = True
        job.last_verified_at = utcnow()
    elif payload.decision == "reject":
        job.review_status = REVIEW_REJECTED
        job.review_locked = True
        job.review_reason = f"rejected by administrator: {(payload.note or '').strip() or 'no note'}"
        job.india_eligible = False
        job.country_code = None
        job.country_name = None
        job.is_active = False
    else:
        client = build_client()
        try:
            verify_job(job, client)
        finally:
            client.close()
    db.commit()
    return JobVerifyResult(
        id=job.id,
        verification_status=job.verification_status,
        verification_reason=job.verification_reason,
        review_status=job.review_status,
        last_verified_at=job.last_verified_at,
    )


@router.patch(
    "/{job_id}/industry",
    response_model=JobDetail,
    dependencies=[Depends(require_admin)],
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def correct_industry(job_id: int, payload: IndustryCorrection, db: Session = Depends(get_db)) -> JobDetail:
    if payload.industry not in INDUSTRIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown industry")
    job = db.scalar(visible_jobs().where(Job.id == job_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    job.industry = payload.industry
    job.industry_confidence = 1.0
    job.industry_reason = f"manual correction: {payload.reason}"
    job.industry_locked = True
    db.commit()
    return _detail(job)


@router.post(
    "/{job_id}/enrich",
    response_model=JobDetail,
    dependencies=[Depends(require_admin)],
    responses={404: {"model": ErrorResponse}},
)
def enrich_endpoint(job_id: int, db: Session = Depends(get_db)) -> JobDetail:
    job = db.scalar(visible_jobs().where(Job.id == job_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    enrich_job(db, job)
    db.commit()
    db.refresh(job)
    return _detail(job)

