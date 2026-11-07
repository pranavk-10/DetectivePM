"""Source -> validate -> classify -> dedupe -> persist, with a recorded run per source."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db import session_scope
from backend.models import (
    PROVENANCE_LIVE,
    PROVENANCE_MANUAL,
    REVIEW_ACCEPTED,
    REVIEW_MANUAL,
    RUN_FAILED,
    RUN_SKIPPED,
    RUN_SUCCESS,
    VERIFY_ACTIVE,
    VERIFY_EXPIRED,
    VERIFY_REVIEW,
    Job,
    JobSourceLink,
    ScrapeRun,
    Source,
    utcnow,
)
from backend.pipeline import geo as geo_module
from backend.pipeline import roles as roles_module
from backend.pipeline.geo import GeoInput, GeoResult, evaluate_location
from backend.pipeline.industry import classify_industry
from backend.pipeline.roles import RoleResult, classify_role
from backend.sources.base import BaseConnector, MissingCredentials, NormalizedJob, SourceError
from backend.sources.registry import connector_for
from backend.sources.text import canonicalize_url, company_key, content_hash, normalize_title

log = logging.getLogger("detectivepm.ingest")

STATUS_NEEDS_CREDENTIALS = "needs_credentials"
PAUSE_BETWEEN_SOURCES = 0.5

INSERTED = "inserted"
UPDATED = "updated"
REJECTED = "rejected"
UNCHANGED = "unchanged"


@dataclass
class Assessment:
    decision: str  # accept, review or reject
    geo: GeoResult
    role: RoleResult
    reason: str


def assess(job: NormalizedJob) -> Assessment:
    geo = evaluate_location(
        GeoInput(
            location=job.location,
            extra_locations=job.extra_locations,
            structured_country=job.structured_country,
            workplace_hint=job.workplace_hint,
            is_remote=job.is_remote,
            description=job.description,
        )
    )
    role = classify_role(job.title, job.description)
    if geo.decision == geo_module.REJECT:
        return Assessment("reject", geo, role, f"location: {geo.location_evidence}")
    if role.decision == roles_module.REJECT:
        return Assessment("reject", geo, role, f"role: {role.reason}")
    if geo.decision == geo_module.REVIEW:
        return Assessment("review", geo, role, f"location unconfirmed: {geo.location_evidence}")
    if role.decision == roles_module.REVIEW:
        return Assessment("review", geo, role, f"role uncertain: {role.reason}")
    return Assessment("accept", geo, role, "passed location and role checks")


def find_existing(db: Session, source: Source, job: NormalizedJob, canonical: str, digest: str) -> Job | None:
    """Match order: same source and id, same URL, same content, then same role from another source."""
    link = db.scalar(
        select(JobSourceLink).where(
            JobSourceLink.source_id == source.id, JobSourceLink.external_job_id == job.external_job_id
        )
    )
    if link:
        return link.job
    key = company_key(job.company)
    found = db.scalar(select(Job).where(Job.canonical_url == canonical))
    if found:
        return found
    found = db.scalar(select(Job).where(Job.company_key == key, Job.content_hash == digest))
    if found:
        return found
    return None


def find_cross_source(db: Session, source: Source, job: NormalizedJob, city: str | None) -> Job | None:
    """The same title and city at one company, seen via a different source, is one listing."""
    if not city:
        return None
    return db.scalar(
        select(Job).where(
            Job.company_key == company_key(job.company),
            Job.normalized_title == normalize_title(job.title),
            Job.city == city,
            Job.source_name != source.source_name,
        )
    )


def _apply(target: Job, job: NormalizedJob, result: Assessment, registry_industry: str | None) -> bool:
    """Copy fields onto a row. Returns True if anything changed."""
    geo, role = result.geo, result.role
    accepted = result.decision == "accept"
    industry = classify_industry(job.company, job.description, registry_industry)
    values = {
        "title": job.title,
        "normalized_title": normalize_title(job.title),
        "company": job.company,
        "company_key": company_key(job.company),
        "company_domain": job.company_domain,
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
        "location": (job.location or "")[:500] or None,
        "city": geo.city,
        "state": geo.state,
        "country_code": geo.country_code,
        "country_name": geo.country_name,
        "workplace_type": geo.workplace_type,
        "remote_eligibility": geo.remote_eligibility,
        "india_eligible": geo.india_eligible,
        "location_confidence": geo.location_confidence,
        "location_evidence": geo.location_evidence,
        "employment_type": job.employment_type,
        "experience_level": role.experience_level,
        "skills": job.skills,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "application_url": job.application_url,
        "date_posted": job.date_posted,
        "expiry_date": job.expiry_date,
        "relevance_score": role.relevance_score,
        "classification": role.classification,
        "classification_reason": role.reason,
        "classification_confidence": role.confidence,
        "classifier_version": role.classifier_version,
    }
    if not target.review_locked:
        values["review_status"] = REVIEW_ACCEPTED if accepted else REVIEW_MANUAL
        values["review_reason"] = result.reason
    else:
        # An administrator's decision stands; only source facts are refreshed.
        for field in ("india_eligible", "country_code", "country_name", "classification"):
            values.pop(field)
    if not target.industry_locked:
        values["industry"] = industry.industry
        values["industry_confidence"] = industry.confidence
        values["industry_reason"] = industry.reason
    changed = False
    for field, value in values.items():
        if getattr(target, field, None) != value:
            setattr(target, field, value)
            changed = True
    return changed


def upsert_job(
    db: Session,
    source: Source,
    job: NormalizedJob,
    *,
    provenance: str = PROVENANCE_LIVE,
    registry_industry: str | None = None,
    now: datetime | None = None,
) -> str:
    now = now or utcnow()
    canonical = canonicalize_url(job.application_url)
    digest = content_hash(job.company, job.title, job.description)
    result = assess(job)
    existing = find_existing(db, source, job, canonical, digest)

    if result.decision == "reject":
        if existing and not existing.review_locked:
            # A listing edited to another country or role must leave the board.
            existing.review_status = REVIEW_MANUAL
            existing.review_reason = f"now fails validation: {result.reason}"
            existing.india_eligible = False
            existing.country_code = None
            existing.country_name = None
            existing.verification_status = VERIFY_REVIEW
            existing.verification_reason = result.reason
        return REJECTED

    if existing is None:
        existing = find_cross_source(db, source, job, result.geo.city)

    if existing is not None:
        changed = _apply(existing, job, result, registry_industry)
        if existing.content_hash != digest:
            clash = db.scalar(
                select(Job.id).where(
                    Job.company_key == existing.company_key, Job.content_hash == digest, Job.id != existing.id
                )
            )
            if clash is None:
                existing.content_hash = digest
                changed = True
        if existing.canonical_url != canonical and not db.scalar(
            select(Job.id).where(Job.canonical_url == canonical, Job.id != existing.id)
        ):
            existing.canonical_url = canonical
        if not existing.is_active and existing.verification_status != VERIFY_EXPIRED:
            existing.is_active = True
            existing.verification_status = VERIFY_ACTIVE
            existing.verification_reason = "listed by the source again"
            changed = True
        target, outcome = existing, (UPDATED if changed else UNCHANGED)
    else:
        target = Job(
            external_job_id=job.external_job_id,
            canonical_url=canonical,
            content_hash=digest,
            source_name=source.source_name,
            source_url=job.source_url,
            company_id=source.company_id,
            provenance=provenance,
            date_discovered=now,
            is_active=True,
            verification_status=VERIFY_ACTIVE if result.decision == "accept" else VERIFY_REVIEW,
            verification_reason="listed by source at discovery",
        )
        _apply(target, job, result, registry_industry)
        db.add(target)
        db.flush()
        outcome = INSERTED

    link = db.scalar(
        select(JobSourceLink).where(
            JobSourceLink.source_id == source.id, JobSourceLink.external_job_id == job.external_job_id
        )
    )
    if link is None:
        db.add(
            JobSourceLink(
                job_id=target.id, source_id=source.id, external_job_id=job.external_job_id,
                source_url=job.source_url, first_seen_at=now, last_seen_at=now,
            )
        )
    else:
        link.last_seen_at = now
        link.missed_runs = 0
    return outcome


def process_records(db: Session, source: Source, connector: BaseConnector, run: ScrapeRun, raws: list[dict]) -> set[str]:
    seen: set[str] = set()
    registry_industry = source.company.industry if source.company else None
    for raw in raws:
        try:
            job = connector.normalize_job(raw)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            log.warning("%s: could not normalize a record: %s", source.source_name, exc)
            run.records_rejected += 1
            continue
        if job is None:
            run.records_rejected += 1
            continue
        if job.external_job_id:
            seen.add(job.external_job_id)
        if connector.validate_job(job):
            run.records_rejected += 1
            continue
        try:
            with db.begin_nested():
                outcome = upsert_job(db, source, job, registry_industry=registry_industry)
        except IntegrityError as exc:
            log.warning("%s: skipped %s: %s", source.source_name, job.external_job_id, exc.orig)
            run.records_rejected += 1
            continue
        if outcome == INSERTED:
            run.records_inserted += 1
        elif outcome == UPDATED:
            run.records_updated += 1
        elif outcome == REJECTED:
            run.records_rejected += 1
    return seen


def record_listing_presence(db: Session, source: Source, seen: set[str], now: datetime) -> None:
    """After a complete read, count which known jobs the source no longer lists."""
    query = update(JobSourceLink).where(JobSourceLink.source_id == source.id)
    if seen:
        query = query.where(JobSourceLink.external_job_id.not_in(seen))
    db.execute(query.values(missed_runs=JobSourceLink.missed_runs + 1))


def run_source(source_id: int, trigger: str = "scheduled", client: httpx.Client | None = None) -> dict:
    """Run one source in its own transaction. Failure never propagates to other sources."""
    with session_scope() as db:
        source = db.get(Source, source_id)
        if source is None:
            raise ValueError(f"unknown source {source_id}")
        name = source.source_name
        run = ScrapeRun(source_id=source.id, trigger=trigger)
        db.add(run)
        now = utcnow()
        if source.last_run_at and source.min_interval_hours:
            due = source.last_run_at + timedelta(hours=source.min_interval_hours)
            if due > now:
                run.status = RUN_SKIPPED
                run.completed_at = now
                run.error_details = f"provider rate limit: next allowed at {due.isoformat()}"
                return {"source": name, "status": RUN_SKIPPED}
        db.flush()
        run_id = run.id

    outcome: dict
    try:
        with session_scope() as db:
            source = db.get(Source, source_id)
            run = db.get(ScrapeRun, run_id)
            connector = connector_for(source, client=client)
            raws = connector.fetch_jobs()
            run.records_found = len(raws)
            seen = process_records(db, source, connector, run, raws)
            now = utcnow()
            if raws:  # an empty read proves nothing about existing listings
                record_listing_presence(db, source, seen, now)
            run.status = RUN_SUCCESS
            run.completed_at = now
            source.last_run_at = now
            source.last_successful_run = now
            source.last_run_status = RUN_SUCCESS
            source.consecutive_failures = 0
            source.error_message = None
            source.jobs_discovered = run.records_found
            source.jobs_inserted += run.records_inserted
            if source.company:
                source.company.last_successful_scan = now
            outcome = {
                "source": source.source_name, "status": RUN_SUCCESS, "found": run.records_found,
                "inserted": run.records_inserted, "updated": run.records_updated,
                "rejected": run.records_rejected,
            }
    except Exception as exc:  # noqa: BLE001 - one bad source must not stop the rest
        status = STATUS_NEEDS_CREDENTIALS if isinstance(exc, MissingCredentials) else RUN_FAILED
        message = str(exc)[:2000] if isinstance(exc, SourceError) else f"{type(exc).__name__}: {str(exc)[:1900]}"
        if status == RUN_FAILED:
            log.warning("source %s failed: %s", name, message)
        with session_scope() as db:
            source = db.get(Source, source_id)
            run = db.get(ScrapeRun, run_id)
            now = utcnow()
            run.status = status if status == RUN_FAILED else RUN_SKIPPED
            run.completed_at = now
            run.error_details = message
            source.last_run_at = now
            source.last_run_status = status
            source.error_message = message
            if status == RUN_FAILED:
                source.last_failure_at = now
                source.consecutive_failures += 1
        outcome = {"source": name, "status": status, "error": message}
    return outcome


def run_discovery(trigger: str = "scheduled", source_id: int | None = None, client: httpx.Client | None = None) -> dict:
    with session_scope() as db:
        if source_id is not None:
            ids = [source_id]
        else:
            ids = list(
                db.scalars(
                    select(Source.id)
                    .where(Source.enabled.is_(True), Source.source_type != "manual")
                    .order_by(Source.id)
                )
            )
    summary = {"sources": len(ids), "success": 0, "failed": 0, "skipped": 0, "inserted": 0, "updated": 0, "results": []}
    for index, sid in enumerate(ids):
        result = run_source(sid, trigger, client=client)
        summary["results"].append(result)
        if result["status"] == RUN_SUCCESS:
            summary["success"] += 1
            summary["inserted"] += result["inserted"]
            summary["updated"] += result["updated"]
        elif result["status"] == RUN_FAILED:
            summary["failed"] += 1
        else:
            summary["skipped"] += 1
        if client is None and index + 1 < len(ids):
            time.sleep(PAUSE_BETWEEN_SOURCES)
    log.info(
        "discovery finished: %s sources, %s ok, %s failed, %s inserted",
        summary["sources"], summary["success"], summary["failed"], summary["inserted"],
    )
    return summary


def ingest_manual(db: Session, source: Source, job: NormalizedJob) -> tuple[str, Job | None]:
    canonical = canonicalize_url(job.application_url)
    outcome = upsert_job(db, source, job, provenance=PROVENANCE_MANUAL)
    db.flush()
    return outcome, db.scalar(select(Job).where(Job.canonical_url == canonical))
