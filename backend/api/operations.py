"""Scraper, source, recruiter and export endpoints."""

from __future__ import annotations

import math
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend import gsheets
from backend.auth import require_admin
from backend.config import settings
from backend.db import get_db
from backend.exports import stream_csv
from backend.models import (
    RUN_SUCCESS,
    Job,
    Recruiter,
    ScrapeRun,
    SheetSyncLog,
    Source,
    utcnow,
)
from backend.pipeline.ingest import STATUS_NEEDS_CREDENTIALS, run_discovery
from backend.pipeline.recruiters import KIND_COMPANY, KIND_INDIVIDUAL, KIND_PHONE
from backend.queries import visible_condition, visible_jobs
from backend.scheduler import TASK_DISCOVERY, lease_held, run_locked, scheduler_state
from backend.schemas import (
    ErrorResponse,
    RecruiterCreate,
    RecruiterOut,
    RecruiterPage,
    RecruiterVerify,
    ScrapeAccepted,
    ScrapeRequest,
    ScrapeRunOut,
    ScrapeRunPage,
    ScraperStatus,
    SheetsStatus,
    SourceOut,
    SourceToggle,
)

router = APIRouter(prefix="/api")


def source_health(source: Source) -> str:
    if source.source_type == "manual":
        return "manual"
    if not source.enabled:
        return "disabled"
    if source.last_run_status == STATUS_NEEDS_CREDENTIALS:
        return "needs_credentials"
    if source.last_run_status is None:
        return "never_run"
    return "healthy" if source.last_run_status == RUN_SUCCESS else "failing"


def _source_out(source: Source) -> SourceOut:
    return SourceOut(
        id=source.id, source_name=source.source_name, source_type=source.source_type, base_url=source.base_url,
        enabled=source.enabled, health=source_health(source), last_run_at=source.last_run_at,
        last_successful_run=source.last_successful_run, last_failure_at=source.last_failure_at,
        last_run_status=source.last_run_status, consecutive_failures=source.consecutive_failures,
        jobs_discovered=source.jobs_discovered, jobs_inserted=source.jobs_inserted,
        error_message=source.error_message,
    )


@router.get("/scraper/status", response_model=ScraperStatus, tags=["scraper"])
def scraper_status(db: Session = Depends(get_db)) -> ScraperStatus:
    sources = db.scalars(select(Source).where(Source.source_type != "manual")).all()
    health = [source_health(source) for source in sources]
    last = db.scalar(select(func.max(Source.last_successful_run)))
    return ScraperStatus(
        scheduler=scheduler_state(),
        ingestion_running=lease_held(TASK_DISCOVERY),
        last_successful_ingestion=last,
        sources_total=len(sources),
        sources_healthy=health.count("healthy"),
        sources_failing=health.count("failing"),
        sources_needing_credentials=health.count("needs_credentials"),
        sources_never_run=health.count("never_run"),
    )


@router.get("/scraper/history", response_model=ScrapeRunPage, tags=["scraper"])
def scraper_history(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    source_id: int | None = None,
) -> ScrapeRunPage:
    query = select(ScrapeRun)
    if source_id is not None:
        query = query.where(ScrapeRun.source_id == source_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    runs = db.scalars(
        query.options(joinedload(ScrapeRun.source))
        .order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    items = [
        ScrapeRunOut(
            id=run.id, source_id=run.source_id, source_name=run.source.source_name, trigger=run.trigger,
            started_at=run.started_at, completed_at=run.completed_at, status=run.status,
            records_found=run.records_found, records_inserted=run.records_inserted,
            records_updated=run.records_updated, records_rejected=run.records_rejected,
            error_details=run.error_details,
        )
        for run in runs
    ]
    return ScrapeRunPage(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.post(
    "/scraper/run",
    response_model=ScrapeAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
    tags=["scraper"],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def trigger_scrape(
    background: BackgroundTasks, payload: ScrapeRequest | None = None, db: Session = Depends(get_db)
) -> ScrapeAccepted:
    source_id = payload.source_id if payload else None
    if source_id is not None and db.get(Source, source_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if lease_held(TASK_DISCOVERY):
        raise HTTPException(status.HTTP_409_CONFLICT, "An ingestion run is already in progress")
    last_manual = db.scalar(select(func.max(ScrapeRun.started_at)).where(ScrapeRun.trigger == "manual"))
    if last_manual and source_id is None:
        wait = timedelta(seconds=settings.manual_run_cooldown_seconds) - (utcnow() - last_manual)
        if wait.total_seconds() > 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Manual runs are limited; try again in {int(wait.total_seconds()) + 1} seconds",
            )
    background.add_task(run_locked, TASK_DISCOVERY, lambda: run_discovery("manual", source_id))
    return ScrapeAccepted(status="accepted", message="Ingestion started")


@router.get("/sources", response_model=list[SourceOut], tags=["sources"])
def list_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    return [_source_out(s) for s in db.scalars(select(Source).order_by(Source.source_type, Source.source_name))]


@router.patch(
    "/sources/{source_id}",
    response_model=SourceOut,
    dependencies=[Depends(require_admin)],
    tags=["sources"],
    responses={404: {"model": ErrorResponse}},
)
def toggle_source(source_id: int, payload: SourceToggle, db: Session = Depends(get_db)) -> SourceOut:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    source.enabled = payload.enabled
    db.commit()
    return _source_out(source)


@router.get("/recruiters", response_model=RecruiterPage, tags=["recruiters"])
def list_recruiters(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verification_status: str | None = Query(None, max_length=30),
) -> RecruiterPage:
    query = select(Recruiter).join(Job, Job.id == Recruiter.job_id).where(visible_condition())
    if verification_status:
        query = query.where(Recruiter.verification_status == verification_status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Recruiter.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    return RecruiterPage(
        items=[RecruiterOut.model_validate(row) for row in rows], total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.get(
    "/recruiters/{recruiter_id}", response_model=RecruiterOut, tags=["recruiters"],
    responses={404: {"model": ErrorResponse}},
)
def get_recruiter(recruiter_id: int, db: Session = Depends(get_db)) -> RecruiterOut:
    row = db.scalar(
        select(Recruiter)
        .join(Job, Job.id == Recruiter.job_id)
        .where(Recruiter.id == recruiter_id, visible_condition())
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recruiter not found")
    return RecruiterOut.model_validate(row)


@router.post(
    "/jobs/{job_id}/recruiters",
    response_model=RecruiterOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    tags=["recruiters"],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def add_recruiter(job_id: int, payload: RecruiterCreate, db: Session = Depends(get_db)) -> RecruiterOut:
    """Record a contact from a public source. Evidence and a source URL are mandatory."""
    job = db.scalar(visible_jobs().where(Job.id == job_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if not (payload.email or payload.phone or payload.public_profile_url):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide an email, phone or public profile URL")
    if payload.email:
        kind = KIND_INDIVIDUAL if payload.recruiter_name else KIND_COMPANY
    else:
        kind = KIND_PHONE if payload.phone else "public_profile"
    row = Recruiter(
        job_id=job.id, recruiter_name=payload.recruiter_name, designation=payload.designation, company=job.company,
        email=payload.email, phone=payload.phone,
        public_profile_url=str(payload.public_profile_url) if payload.public_profile_url else None,
        source_url=str(payload.source_url), contact_kind=kind, evidence=payload.evidence,
        verification_status=payload.verification_status,
        confidence_score=1.0 if payload.verification_status == "Verified" else 0.7,
    )
    db.add(row)
    db.commit()
    return RecruiterOut.model_validate(row)


@router.post(
    "/recruiters/{recruiter_id}/verify",
    response_model=RecruiterOut,
    dependencies=[Depends(require_admin)],
    tags=["recruiters"],
    responses={404: {"model": ErrorResponse}},
)
def verify_recruiter(recruiter_id: int, payload: RecruiterVerify, db: Session = Depends(get_db)) -> RecruiterOut:
    row = db.get(Recruiter, recruiter_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recruiter not found")
    row.verification_status = payload.verification_status
    row.evidence = f"{row.evidence or ''}\nmanual review: {payload.evidence}".strip()
    row.confidence_score = 1.0 if payload.verification_status == "Verified" else row.confidence_score
    db.commit()
    return RecruiterOut.model_validate(row)


@router.get("/export/csv", tags=["export"], response_class=StreamingResponse)
def export_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    jobs = db.scalars(
        visible_jobs()
        .where(Job.is_active.is_(True))
        .options(selectinload(Job.recruiters))
        .order_by(Job.date_discovered.desc(), Job.id.desc())
    ).all()
    stamp = utcnow().strftime("%Y%m%d")
    return StreamingResponse(
        stream_csv(jobs),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="detectivepm_india_jobs_{stamp}.csv"'},
    )


def _sheets_status(db: Session) -> SheetsStatus:
    last = db.scalar(select(SheetSyncLog).order_by(SheetSyncLog.started_at.desc(), SheetSyncLog.id.desc()).limit(1))
    return SheetsStatus(
        configured=gsheets.is_configured(),
        last_status=last.status if last else None,
        last_started_at=last.started_at if last else None,
        last_completed_at=last.completed_at if last else None,
        rows_updated=last.rows_updated if last else 0,
        rows_appended=last.rows_appended if last else 0,
        error_details=last.error_details if last else None,
    )


@router.get("/export/google-sheets/status", response_model=SheetsStatus, tags=["export"])
def google_sheets_status(db: Session = Depends(get_db)) -> SheetsStatus:
    return _sheets_status(db)


@router.post(
    "/export/google-sheets/sync",
    response_model=SheetsStatus,
    dependencies=[Depends(require_admin)],
    tags=["export"],
)
def google_sheets_sync(db: Session = Depends(get_db)) -> SheetsStatus:
    gsheets.sync_jobs(db)
    return _sheets_status(db)

