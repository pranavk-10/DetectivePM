"""Job freshness. A listing is only closed on evidence, never on one bad request."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import session_scope
from backend.models import (
    REVIEW_ACCEPTED,
    VERIFY_ACTIVE,
    VERIFY_CLOSED,
    VERIFY_EXPIRED,
    VERIFY_UNREACHABLE,
    Job,
    utcnow,
)
from backend.sources.base import build_client

log = logging.getLogger("detectivepm.verify")

MISSED_RUNS_TO_CLOSE = 2
URL_FAILURES_TO_CLOSE = 2
PAUSE_SECONDS = 0.3

_CLOSED_TEXT = re.compile(
    r"(no longer (accepting|available|open)|position has been filled|job (has )?(closed|expired)|"
    r"this (job|role|position) is (closed|no longer)|posting has (closed|expired))",
    re.I,
)


@dataclass
class UrlSignal:
    kind: str  # ok, gone, closed, blocked, error
    detail: str


def check_url(client: httpx.Client, url: str) -> UrlSignal:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return UrlSignal("error", f"{type(exc).__name__} reaching the application page")
    code = response.status_code
    if code in (404, 410):
        return UrlSignal("gone", f"application page returned HTTP {code}")
    if code in (401, 403, 406, 429):
        return UrlSignal("blocked", f"application page refused automated checks (HTTP {code})")
    if code >= 500:
        return UrlSignal("error", f"application page returned HTTP {code}")
    if code == 200:
        match = _CLOSED_TEXT.search(response.text[:200_000])
        if match:
            return UrlSignal("closed", f"page states '{match.group(0)}'")
        return UrlSignal("ok", "application page returned HTTP 200")
    return UrlSignal("error", f"unexpected HTTP {code}")


def _set(job: Job, status: str, reason: str, active: bool) -> None:
    job.verification_status = status
    job.verification_reason = reason
    job.is_active = active


def verify_job(job: Job, client: httpx.Client) -> str:
    """Combine expiry, source listing and page signals into one state."""
    now = utcnow()

    if job.expiry_date and job.expiry_date < now:
        _set(job, VERIFY_EXPIRED, f"application deadline passed on {job.expiry_date.date()}", False)
        job.last_verified_at = now
        return job.verification_status

    links = job.source_links
    delisted = bool(links) and all(link.missed_runs >= MISSED_RUNS_TO_CLOSE for link in links)
    still_listed = any(link.missed_runs == 0 for link in links)

    signal = check_url(client, job.application_url)

    if signal.kind == "closed":
        _set(job, VERIFY_CLOSED, signal.detail, False)
    elif signal.kind == "gone":
        job.url_failure_count += 1
        if delisted or job.url_failure_count >= URL_FAILURES_TO_CLOSE:
            _set(job, VERIFY_CLOSED, f"{signal.detail} on {job.url_failure_count} checks", False)
        else:
            job.verification_reason = f"{signal.detail}; will confirm on the next check"
    elif delisted:
        _set(job, VERIFY_CLOSED, f"source stopped listing this job for {MISSED_RUNS_TO_CLOSE}+ complete reads", False)
    elif signal.kind == "ok":
        job.url_failure_count = 0
        reason = "source lists the job and the page loads" if still_listed else "application page loads"
        _set(job, VERIFY_ACTIVE, reason, True)
    elif signal.kind == "blocked":
        job.url_failure_count = 0
        if still_listed:
            _set(job, VERIFY_ACTIVE, f"source still lists the job; {signal.detail}", True)
        else:
            job.verification_reason = signal.detail
    else:
        # Temporary failures never expire a job.
        if still_listed:
            job.verification_reason = f"source still lists the job; {signal.detail}"
        else:
            _set(job, VERIFY_UNREACHABLE, signal.detail, True)

    job.last_verified_at = now
    return job.verification_status


def verify_batch(db: Session, client: httpx.Client, limit: int = 500, pause: float = PAUSE_SECONDS) -> dict[str, int]:
    jobs = db.scalars(
        select(Job)
        .where(Job.review_status == REVIEW_ACCEPTED, Job.verification_status != VERIFY_EXPIRED)
        .order_by(Job.last_verified_at.asc().nulls_first())
        .limit(limit)
    ).all()
    counts: dict[str, int] = {}
    for job in jobs:
        state = verify_job(job, client)
        counts[state] = counts.get(state, 0) + 1
        db.commit()
        if pause:
            time.sleep(pause)
    return counts


def run_verification(limit: int = 500) -> dict[str, int]:
    client = build_client()
    try:
        with session_scope() as db:
            return verify_batch(db, client, limit)
    finally:
        client.close()
