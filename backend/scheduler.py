"""Recurring tasks, guarded by a database lease so instances never overlap."""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from backend.config import settings
from backend.db import session_scope
from backend.models import RUN_FAILED, RUN_RUNNING, RUN_SUCCESS, ScrapeRun, SchedulerHeartbeat, SchedulerLease, utcnow
from backend.pipeline.ingest import run_discovery
from backend.pipeline.recruiters import run_enrichment
from backend.pipeline.verify import run_verification

log = logging.getLogger("detectivepm.scheduler")

OWNER = f"{socket.gethostname()}:{os.getpid()}"
LEASE_TTL = timedelta(hours=3)
HEARTBEAT_SECONDS = 60
HEARTBEAT_STALE = timedelta(minutes=3)
RUN_RETENTION = timedelta(days=90)

TASK_DISCOVERY = "discovery"
TASK_VERIFICATION = "verification"
TASK_ENRICHMENT = "enrichment"
TASK_MAINTENANCE = "maintenance"


def acquire_lease(name: str, owner: str = OWNER, ttl: timedelta = LEASE_TTL) -> bool:
    now = utcnow()
    try:
        with session_scope() as db:
            if db.get(SchedulerLease, name) is None:
                db.add(SchedulerLease(name=name))
    except IntegrityError:
        pass  # another process created the row first
    with session_scope() as db:
        result = db.execute(
            update(SchedulerLease)
            .where(
                SchedulerLease.name == name,
                (SchedulerLease.expires_at.is_(None)) | (SchedulerLease.expires_at < now),
            )
            .values(owner=owner, acquired_at=now, expires_at=now + ttl)
        )
        return result.rowcount == 1


def release_lease(name: str, owner: str = OWNER) -> None:
    with session_scope() as db:
        db.execute(
            update(SchedulerLease)
            .where(SchedulerLease.name == name, SchedulerLease.owner == owner)
            .values(expires_at=None)
        )


def lease_held(name: str) -> bool:
    with session_scope() as db:
        lease = db.get(SchedulerLease, name)
        return bool(lease and lease.expires_at and lease.expires_at > utcnow())


def run_locked(name: str, task: Callable[[], dict]) -> dict | None:
    """Run a task if nothing else holds its lease. A failure is recorded, never raised."""
    if not acquire_lease(name):
        log.info("%s skipped: another run holds the lease", name)
        return None
    try:
        result = task()
        _record_result(name, {"status": "success", "at": utcnow().isoformat(), "summary": _short(result)})
        return result
    except Exception as exc:  # noqa: BLE001 - the schedule must survive a bad run
        log.exception("%s failed", name)
        _record_result(name, {"status": "failed", "at": utcnow().isoformat(), "error": str(exc)[:500]})
        return None
    finally:
        release_lease(name)


def _short(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "results"}


def _heartbeat_row(db) -> SchedulerHeartbeat:
    row = db.scalar(select(SchedulerHeartbeat).where(SchedulerHeartbeat.owner == OWNER))
    if row is None:
        row = SchedulerHeartbeat(owner=OWNER, next_runs={}, last_results={})
        db.add(row)
    return row


def _record_result(name: str, value: dict) -> None:
    with session_scope() as db:
        row = _heartbeat_row(db)
        row.last_results = {**(row.last_results or {}), name: value}
        row.last_beat = utcnow()


def heartbeat(scheduler: BaseScheduler) -> None:
    next_runs = {
        job.id: job.next_run_time.isoformat() for job in scheduler.get_jobs() if job.next_run_time and job.id != "heartbeat"
    }
    with session_scope() as db:
        row = _heartbeat_row(db)
        row.last_beat = utcnow()
        row.next_runs = next_runs


def run_maintenance() -> dict:
    now = utcnow()
    with session_scope() as db:
        stale = db.execute(
            update(ScrapeRun)
            .where(ScrapeRun.status == RUN_RUNNING, ScrapeRun.started_at < now - LEASE_TTL)
            .values(status=RUN_FAILED, completed_at=now, error_details="interrupted: no completion was recorded")
        ).rowcount
        pruned = db.execute(delete(ScrapeRun).where(ScrapeRun.started_at < now - RUN_RETENTION)).rowcount
        beats = db.execute(
            delete(SchedulerHeartbeat).where(SchedulerHeartbeat.last_beat < now - timedelta(days=2))
        ).rowcount
    return {"stale_runs_closed": stale, "runs_pruned": pruned, "heartbeats_pruned": beats}


def discovery_task() -> dict | None:
    return run_locked(TASK_DISCOVERY, lambda: run_discovery("scheduled"))


def verification_task() -> dict | None:
    return run_locked(TASK_VERIFICATION, run_verification)


def enrichment_task() -> dict | None:
    return run_locked(TASK_ENRICHMENT, run_enrichment)


def maintenance_task() -> dict | None:
    return run_locked(TASK_MAINTENANCE, run_maintenance)


def last_discovery_success() -> datetime | None:
    with session_scope() as db:
        return db.scalar(
            select(ScrapeRun.completed_at)
            .where(ScrapeRun.status == RUN_SUCCESS)
            .order_by(ScrapeRun.completed_at.desc())
            .limit(1)
        )


def configure(scheduler: BaseScheduler) -> BaseScheduler:
    """Register tasks. A first run is queued only when the data is already stale."""
    interval = settings.discovery_interval_seconds
    shared = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 900, "replace_existing": True}
    now = datetime.now(scheduler.timezone)

    last = last_discovery_success()
    overdue = last is None or (utcnow() - last).total_seconds() > interval
    first_discovery = now + (timedelta(seconds=30) if overdue else timedelta(seconds=interval))

    scheduler.add_job(discovery_task, "interval", seconds=interval, id=TASK_DISCOVERY,
                      next_run_time=first_discovery, **shared)
    scheduler.add_job(enrichment_task, "interval", seconds=interval, id=TASK_ENRICHMENT,
                      next_run_time=now + timedelta(minutes=20), **shared)
    scheduler.add_job(verification_task, "interval", hours=6, id=TASK_VERIFICATION,
                      next_run_time=now + timedelta(minutes=40), **shared)
    scheduler.add_job(maintenance_task, "interval", hours=24, id=TASK_MAINTENANCE,
                      next_run_time=now + timedelta(hours=1), **shared)
    scheduler.add_job(heartbeat, "interval", seconds=HEARTBEAT_SECONDS, id="heartbeat", args=[scheduler],
                      next_run_time=now + timedelta(seconds=2), max_instances=1, coalesce=True, replace_existing=True)
    return scheduler


def start_background() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    configure(scheduler)
    scheduler.start()
    log.info("scheduler started inside the API process as %s", OWNER)
    return scheduler


def scheduler_state() -> dict:
    """Real state, from the heartbeat of whichever process runs the schedule."""
    with session_scope() as db:
        row = db.scalar(select(SchedulerHeartbeat).order_by(SchedulerHeartbeat.last_beat.desc()).limit(1))
        if row is None:
            return {"state": "not_started", "last_heartbeat": None, "owner": None, "next_runs": {}, "last_results": {}}
        alive = utcnow() - row.last_beat < HEARTBEAT_STALE
        return {
            "state": "running" if alive else "stopped",
            "last_heartbeat": row.last_beat,
            "owner": row.owner,
            "next_runs": row.next_runs or {},
            "last_results": row.last_results or {},
        }
