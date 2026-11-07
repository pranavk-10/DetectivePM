"""
DetectivePM - Google Sheets sync helper.

Reads CSV export and uploads rows to a target Google Sheet using
Google API Client libraries with a service account.
Gracefully skips if credentials.json is missing.
"""

import os
from typing import Optional

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
CSV_PATH = os.path.join(os.path.dirname(__file__), "detective_pm_jobs.csv")


def sync_to_gsheets(spreadsheet_id: str) -> Optional[str]:
    """
    Sync detective_pm_jobs.csv to a Google Sheet.

    Args:
        spreadsheet_id: The Google Sheets ID from the spreadsheet URL.

    Returns:
        Status message string, or None if skipped due to missing credentials.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"[gsheets] {CREDENTIALS_PATH} not found. Skipping Google Sheets sync.")
        return None

    if not os.path.exists(CSV_PATH):
        print(f"[gsheets] {CSV_PATH} not found. Run a scrape or export first.")
        return "CSV file not found"

    try:
        import pandas as pd
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)

        df = pd.read_csv(CSV_PATH)
        df = df.fillna("")

        values = [df.columns.tolist()] + df.values.tolist()
        body = {"values": values}

        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range="Sheet1!A:Z", body={}
        ).execute()

        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )

        updated_cells = result.get("updatedCells", 0)
        print(f"[gsheets] Successfully synced {updated_cells} cells to Google Sheet.")
        return f"Successfully synced {updated_cells} cells."

    except Exception as e:
        err_msg = f"Google Sheets sync failed: {str(e)}"
        print(f"[gsheets] {err_msg}")
        return err_msg
