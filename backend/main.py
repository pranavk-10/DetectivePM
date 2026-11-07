"""
DetectivePM - FastAPI Application.

Exposes REST endpoints for stats, filtered posts, manual scrape triggers,
CSV downloads, and Google Sheets sync. Handles CORS and app lifecycle events.
"""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.database import init_db, get_all_posts, get_stats, export_to_csv, CSV_PATH
from backend.scheduler import start_scheduler, stop_scheduler, scrape_and_store, get_scheduler_status
from backend.gsheets import sync_to_gsheets

app = FastAPI(
    title="DetectivePM API",
    description="Automated job-scraping and analytics dashboard for Product Management roles",
    version="1.0.0",
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    """Initialize database and start recurring background scraper."""
    init_db()
    start_scheduler()
    # Perform an initial scrape on startup if database is empty
    stats = get_stats()
    if stats["total_posts"] == 0:
        print("[main] Database empty. Triggering initial scrape...")
        try:
            scrape_and_store()
        except Exception as e:
            print(f"[main] Initial scrape failed: {e}")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """Stop the scheduler on app shutdown."""
    stop_scheduler()


@app.get("/api/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "DetectivePM API"}


@app.get("/api/stats")
def api_get_stats() -> dict:
    """Return dashboard stats including total posts, intern/fulltime counts, genre breakdown, and schedule status."""
    db_stats = get_stats()
    sched_status = get_scheduler_status()
    return {
        **db_stats,
        "scheduler": sched_status,
    }


@app.get("/api/posts")
def api_get_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role_type: Optional[str] = Query(None, regex="^(Intern|Full-time)$"),
    genre: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Return paginated and filtered posts."""
    return get_all_posts(
        page=page,
        page_size=page_size,
        role_type=role_type,
        genre=genre,
        search=search,
    )


@app.post("/api/trigger-scrape")
def api_trigger_scrape(background_tasks: BackgroundTasks) -> dict:
    """Manually trigger a scrape cycle."""
    try:
        new_count = scrape_and_store()
        return {
            "status": "success",
            "message": f"Scrape completed successfully. Added {new_count} new posts.",
            "new_posts": new_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")


@app.get("/api/export-csv")
def api_export_csv() -> FileResponse:
    """Export and download detective_pm_jobs.csv."""
    csv_path = export_to_csv()
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV export not found")
    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename="detective_pm_jobs.csv",
    )


class GSheetsSyncRequest(BaseModel):
    spreadsheet_id: str


@app.post("/api/sync-gsheets")
def api_sync_gsheets(payload: GSheetsSyncRequest) -> dict:
    """Sync CSV data to Google Sheets using provided spreadsheet_id."""
    result = sync_to_gsheets(payload.spreadsheet_id)
    if result is None:
        return {
            "status": "skipped",
            "message": "credentials.json not found on backend server. Google Sheets sync skipped.",
        }
    if "failed" in result.lower() or "not found" in result.lower():
        raise HTTPException(status_code=400, detail=result)
    return {"status": "success", "message": result}
