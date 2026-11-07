"""Google Sheets sync. Upserts by job id, so re-running never duplicates rows."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.exports import CSV_COLUMNS, job_to_row
from backend.models import Job, SheetSyncLog, utcnow
from backend.queries import visible_jobs

log = logging.getLogger("detectivepm.gsheets")

SHEET = "Jobs"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = ["Job ID", *CSV_COLUMNS]


def is_configured() -> bool:
    return bool(settings.google_sheets_id and settings.google_service_account_json)


def _service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(settings.google_service_account_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _column(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _ensure_sheet(values_api, sheets_api, spreadsheet_id: str) -> None:
    metadata = sheets_api.get(spreadsheetId=spreadsheet_id).execute()
    titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
    if SHEET not in titles:
        sheets_api.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": SHEET}}}]},
        ).execute()
    values_api.update(
        spreadsheetId=spreadsheet_id, range=f"{SHEET}!A1", valueInputOption="RAW", body={"values": [HEADER]}
    ).execute()


def sync_jobs(db: Session, service=None) -> SheetSyncLog:
    entry = SheetSyncLog(status="running")
    db.add(entry)
    db.commit()
    if not is_configured() and service is None:
        entry.status = "not_configured"
        entry.error_details = "GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON are not set"
        entry.completed_at = utcnow()
        db.commit()
        return entry
    try:
        service = service or _service()
        sheets_api = service.spreadsheets()
        values_api = sheets_api.values()
        spreadsheet_id = settings.google_sheets_id
        _ensure_sheet(values_api, sheets_api, spreadsheet_id)

        existing = values_api.get(spreadsheetId=spreadsheet_id, range=f"{SHEET}!A2:A").execute().get("values", [])
        row_by_id = {row[0]: index + 2 for index, row in enumerate(existing) if row}

        jobs = db.scalars(visible_jobs().options(selectinload(Job.recruiters)).order_by(Job.id)).all()
        last_column = _column(len(HEADER))
        updates, appends = [], []
        for job in jobs:
            row = [str(job.id), *job_to_row(job, for_spreadsheet=False)]
            if str(job.id) in row_by_id:
                number = row_by_id[str(job.id)]
                updates.append({"range": f"{SHEET}!A{number}:{last_column}{number}", "values": [row]})
            else:
                appends.append(row)
        if updates:
            values_api.batchUpdate(
                spreadsheetId=spreadsheet_id, body={"valueInputOption": "RAW", "data": updates}
            ).execute()
        if appends:
            values_api.append(
                spreadsheetId=spreadsheet_id, range=f"{SHEET}!A1", valueInputOption="RAW",
                insertDataOption="INSERT_ROWS", body={"values": appends},
            ).execute()
        entry.status = "success"
        entry.rows_updated = len(updates)
        entry.rows_appended = len(appends)
    except Exception as exc:  # noqa: BLE001 - recorded for the status endpoint
        log.warning("google sheets sync failed: %s", type(exc).__name__)
        entry.status = "failed"
        entry.error_details = f"{type(exc).__name__}: {str(exc)[:500]}"
    entry.completed_at = utcnow()
    db.commit()
    return entry
