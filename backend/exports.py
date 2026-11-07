"""CSV export of India-eligible genuine jobs."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import datetime

from backend.models import Job

CSV_COLUMNS = [
    "Job Title", "Company", "Location", "Country", "Role Type", "Industry", "Employment Type", "Description",
    "Skills", "Salary", "Application URL", "Source", "Date Posted", "Date Discovered", "Last Verified",
    "Recruiter Contact", "India Eligibility", "Verification Status",
]
NOT_AVAILABLE = "Not Available"


def _date(value: datetime | None) -> str:
    return value.date().isoformat() if value else ""


def _salary(job: Job) -> str:
    if job.salary_min is None and job.salary_max is None:
        return NOT_AVAILABLE
    amounts = [f"{value:,.0f}" for value in (job.salary_min, job.salary_max) if value is not None]
    return f"{job.salary_currency or ''} {' - '.join(amounts)}".strip()


def _recruiter(job: Job) -> str:
    contacts = [
        f"{r.email or r.phone or r.public_profile_url} ({r.verification_status})" for r in job.recruiters
    ]
    return "; ".join(contacts) or NOT_AVAILABLE


def _safe_cell(value: str) -> str:
    """Stop spreadsheet apps from running scraped text as a formula."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def job_to_row(job: Job, for_spreadsheet: bool = True) -> list[str]:
    row = [
        job.title, job.company, job.location or job.city or "", job.country_name or "",
        job.classification or "", job.industry, job.employment_type or "", job.description,
        ", ".join(job.skills or []), _salary(job), job.application_url, job.source_name,
        _date(job.date_posted), _date(job.date_discovered), _date(job.last_verified_at), _recruiter(job),
        "Yes" if job.india_eligible else "No", job.verification_status,
    ]
    return [_safe_cell(value) for value in row]


def stream_csv(jobs: Iterable[Job]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for job in jobs:
        writer.writerow(job_to_row(job))
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
    if buffer.getvalue():
        yield buffer.getvalue()
