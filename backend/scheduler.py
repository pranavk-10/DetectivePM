"""
DetectivePM - Recurring Scheduler module.

Uses APScheduler BackgroundScheduler to run scrape_and_store() every 5 hours (18,000 seconds).
Tracks execution timestamps and provides status introspection.
"""

from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.database import insert_post, export_to_csv
from backend.scraper import scrape_posts

# State tracking
_last_run: Optional[datetime] = None
_next_run: Optional[datetime] = None
_scheduler: Optional[BackgroundScheduler] = None
_is_running: bool = False


def scrape_and_store() -> int:
    """
    Run scraper, insert new unique posts into DB, export CSV, and update run timestamps.

    Returns:
        Number of newly inserted posts.
    """
    global _last_run, _next_run
    print(f"[scheduler] Starting scheduled scrape cycle at {datetime.utcnow()}...")
    _last_run = datetime.utcnow()

    posts = scrape_posts(use_mock_on_failure=True)
    inserted_count = 0
    for post in posts:
        if insert_post(post):
            inserted_count += 1

    export_to_csv()

    if _scheduler:
        job = _scheduler.get_job("scrape_job")
        if job and job.next_run_time:
            _next_run = job.next_run_time.replace(tzinfo=None)

    print(f"[scheduler] Scrape cycle complete. Inserted {inserted_count} new posts.")
    return inserted_count


def start_scheduler() -> None:
    """Initialize and start the BackgroundScheduler (every 5 hours)."""
    global _scheduler, _is_running, _next_run
    if _is_running and _scheduler:
        return

    _scheduler = BackgroundScheduler()
    # 5 hours = 18,000 seconds
    trigger = IntervalTrigger(seconds=18000)
    _scheduler.add_job(
        scrape_and_store,
        trigger=trigger,
        id="scrape_job",
        name="Scrape PM posts every 5 hours",
        replace_existing=True,
    )
    _scheduler.start()
    _is_running = True

    job = _scheduler.get_job("scrape_job")
    if job and job.next_run_time:
        _next_run = job.next_run_time.replace(tzinfo=None)

    print("[scheduler] BackgroundScheduler started (interval: 5 hours).")


def stop_scheduler() -> None:
    """Stop the background scheduler if running."""
    global _scheduler, _is_running
    if _scheduler and _is_running:
        _scheduler.shutdown(wait=False)
        _is_running = False
        print("[scheduler] BackgroundScheduler stopped.")


def get_scheduler_status() -> dict:
    """
    Return scheduler status information.

    Returns:
        Dict with last_run, next_run, and is_running.
    """
    global _scheduler
    if _scheduler:
        job = _scheduler.get_job("scrape_job")
        if job and job.next_run_time:
            global _next_run
            _next_run = job.next_run_time.replace(tzinfo=None)

    return {
        "last_run": _last_run.isoformat() if _last_run else None,
        "next_run": _next_run.isoformat() if _next_run else None,
        "is_running": _is_running,
    }
