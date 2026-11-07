"""Connector contract and shared HTTP behaviour."""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from backend.config import settings
from backend.sources.text import extract_sections, extract_skills

log = logging.getLogger("detectivepm.sources")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MIN_DESCRIPTION_CHARS = 80


class SourceError(Exception):
    """The source could not be read. The run is recorded as failed."""


class MissingCredentials(SourceError):
    """The connector is implemented but its credentials are not configured."""


@dataclass
class NormalizedJob:
    external_job_id: str
    title: str
    company: str
    description: str
    application_url: str
    source_url: str | None = None
    company_domain: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    location: str | None = None
    extra_locations: list[str] = field(default_factory=list)
    structured_country: str | None = None
    workplace_hint: str | None = None
    is_remote: bool | None = None
    employment_type: str | None = None
    skills: list[str] = field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    date_posted: datetime | None = None
    expiry_date: datetime | None = None
    closed: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class HealthResult:
    ok: bool
    detail: str


def parse_datetime(value: str | int | float | None) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def employment_label(value: str | None) -> str | None:
    if not value:
        return None
    key = re.sub(r"[^a-z]", "", value.lower())
    return {
        "fulltime": "Full-time", "parttime": "Part-time", "contract": "Contract", "contractor": "Contract",
        "intern": "Internship", "internship": "Internship", "temporary": "Temporary", "temp": "Temporary",
    }.get(key, value.strip()[:50])


def build_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": settings.http_user_agent, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"},
    )


class BaseConnector(ABC):
    """Common interface implemented by every source."""

    source_type = "base"
    max_attempts = 3
    backoff_seconds = 1.0

    def __init__(self, config: dict | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or {}
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = build_client()
        return self._client

    def get(self, url: str, **kwargs) -> httpx.Response:
        """GET with exponential backoff on transient failures only."""
        last_error = "unknown error"
        for attempt in range(self.max_attempts):
            try:
                response = self.client.get(url, **kwargs)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in RETRYABLE_STATUS:
                    return response
                last_error = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    time.sleep(min(int(retry_after), 30))
                    continue
            if attempt + 1 < self.max_attempts:
                time.sleep(self.backoff_seconds * (2**attempt))
        raise SourceError(f"{url}: {last_error}")

    def get_json(self, url: str, **kwargs):
        response = self.get(url, **kwargs)
        if response.status_code != 200:
            raise SourceError(f"{url}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(f"{url}: response was not JSON") from exc

    def robots_allowed(self, url: str) -> bool:
        """Honour robots.txt for HTML pages. A missing file means no restriction."""
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            response = self.client.get(robots_url)
        except httpx.HTTPError:
            return False
        if response.status_code == 404:
            return True
        if response.status_code != 200:
            return False
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(settings.http_user_agent, url)

    @abstractmethod
    def fetch_jobs(self) -> list[dict]:
        """Return raw records. Raise SourceError when the source cannot be read."""

    @abstractmethod
    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        """Map one raw record onto the common schema."""

    def extract_metadata(self, raw: dict) -> dict:
        """Source-specific extras kept alongside the job."""
        return {}

    def validate_job(self, job: NormalizedJob) -> list[str]:
        """Return reasons the record cannot be used. Empty means valid."""
        problems = []
        if not job.external_job_id:
            problems.append("missing external id")
        if not job.title.strip():
            problems.append("missing title")
        if not job.company.strip():
            problems.append("missing company")
        if len(job.description.strip()) < MIN_DESCRIPTION_CHARS:
            problems.append("description too short")
        parts = urlsplit(job.application_url or "")
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            problems.append("invalid application url")
        return problems

    def health_check(self) -> HealthResult:
        try:
            raws = self.fetch_jobs()
        except SourceError as exc:
            return HealthResult(False, str(exc))
        return HealthResult(True, f"retrieved {len(raws)} records")

    def finish(self, job: NormalizedJob, raw: dict) -> NormalizedJob:
        """Fill in fields derived from the description."""
        requirements, responsibilities = extract_sections(job.description)
        job.requirements = job.requirements or requirements
        job.responsibilities = job.responsibilities or responsibilities
        job.skills = job.skills or extract_skills(job.description)
        job.metadata = {**job.metadata, **self.extract_metadata(raw)}
        return job
