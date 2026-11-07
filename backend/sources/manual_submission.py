"""Administrator-submitted jobs.

Supported ATS links are read from the ATS's public API. Any other link,
including LinkedIn, is never fetched: the administrator supplies the details.
"""

from __future__ import annotations

import re

from backend.sources.ashby import AshbyConnector
from backend.sources.base import BaseConnector, NormalizedJob, SourceError
from backend.sources.greenhouse import GreenhouseConnector
from backend.sources.lever import LeverConnector
from backend.sources.text import canonicalize_url, extract_sections, extract_skills

_GREENHOUSE = re.compile(r"(?:job-boards(?:\.eu)?|boards(?:\.eu)?)\.greenhouse\.io/([^/]+)/jobs/(\d+)")
_LEVER = re.compile(r"jobs(?:\.eu)?\.lever\.co/([^/]+)/([0-9a-f-]{36})")
_ASHBY = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})")


class ManualSubmissionConnector(BaseConnector):
    source_type = "manual"

    def fetch_jobs(self) -> list[dict]:
        return []  # Jobs arrive through POST /api/jobs/submit, not by polling.

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        return None

    def from_url(self, url: str) -> NormalizedJob | None:
        """Resolve a supported ATS link. Returns None for other links."""
        if match := _GREENHOUSE.search(url):
            connector = GreenhouseConnector({"board": match.group(1)}, client=self._client)
            return connector.normalize_job(connector.fetch_one(match.group(2)))
        if match := _LEVER.search(url):
            board = match.group(1)
            connector = LeverConnector({"board": board, "company": board.title()}, client=self._client)
            return connector.normalize_job(connector.fetch_one(match.group(2)))
        if match := _ASHBY.search(url):
            board, job_id = match.group(1), match.group(2)
            connector = AshbyConnector({"board": board, "company": board.title()}, client=self._client)
            for raw in connector.fetch_jobs():
                if raw.get("id") == job_id:
                    return connector.normalize_job(raw)
            raise SourceError(f"Ashby board {board} does not list job {job_id}")
        return None

    def from_fields(
        self,
        *,
        url: str,
        title: str,
        company: str,
        description: str,
        location: str | None,
        employment_type: str | None = None,
    ) -> NormalizedJob:
        requirements, responsibilities = extract_sections(description)
        return NormalizedJob(
            external_job_id=canonicalize_url(url),
            title=title.strip(),
            company=company.strip(),
            description=description.strip(),
            application_url=url,
            source_url=url,
            location=location,
            employment_type=employment_type,
            requirements=requirements,
            responsibilities=responsibilities,
            skills=extract_skills(description),
        )
