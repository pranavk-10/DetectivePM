"""Job APIs whose providers publish them for third-party use."""

from __future__ import annotations

from backend.config import settings
from backend.sources.base import (
    BaseConnector,
    MissingCredentials,
    NormalizedJob,
    employment_label,
    parse_datetime,
)
from backend.sources.text import html_to_text


class AdzunaConnector(BaseConnector):
    """Adzuna India search API. Needs a free key: https://developer.adzuna.com/"""

    source_type = "adzuna"
    API = "https://api.adzuna.com/v1/api/jobs/in/search"
    QUERIES = ("associate product manager", "product manager intern", "product analyst", "junior product manager")

    def fetch_jobs(self) -> list[dict]:
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            raise MissingCredentials("ADZUNA_APP_ID and ADZUNA_APP_KEY are not configured")
        results: dict[str, dict] = {}
        for query in self.QUERIES:
            data = self.get_json(
                f"{self.API}/1",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what_phrase": query,
                    "results_per_page": 50,
                    "max_days_old": 30,
                    "content-type": "application/json",
                },
            )
            for row in data.get("results", []):
                results[str(row.get("id"))] = row
        return list(results.values())

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        location = raw.get("location") or {}
        area = location.get("area") or []
        predicted = str(raw.get("salary_is_predicted")) == "1"  # never show an estimate as a published salary
        job = NormalizedJob(
            external_job_id=str(raw.get("id", "")),
            title=html_to_text(raw.get("title")),
            company=(raw.get("company") or {}).get("display_name") or "",
            description=html_to_text(raw.get("description")),
            application_url=raw.get("redirect_url") or "",
            source_url=raw.get("redirect_url"),
            location=location.get("display_name"),
            # This endpoint only serves India, so the country is structured evidence.
            structured_country="IN" if "India" in area or not area else None,
            employment_type=employment_label(raw.get("contract_time")),
            date_posted=parse_datetime(raw.get("created")),
            salary_min=None if predicted else raw.get("salary_min"),
            salary_max=None if predicted else raw.get("salary_max"),
            salary_currency=None if predicted or not raw.get("salary_min") else "INR",
        )
        return self.finish(job, raw)


class RemotiveConnector(BaseConnector):
    """Remotive public API. Its terms ask for attribution and infrequent calls,
    which the source label and the source's minimum interval satisfy."""

    source_type = "remotive"
    API = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(self) -> list[dict]:
        return self.get_json(self.API, params={"category": "product"}).get("jobs", [])

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        job = NormalizedJob(
            external_job_id=str(raw.get("id", "")),
            title=(raw.get("title") or "").strip(),
            company=(raw.get("company_name") or "").strip(),
            description=html_to_text(raw.get("description")),
            application_url=raw.get("url") or "",
            source_url=raw.get("url"),
            location=raw.get("candidate_required_location"),
            is_remote=True,
            employment_type=employment_label(raw.get("job_type")),
            date_posted=parse_datetime(raw.get("publication_date")),
        )
        return self.finish(job, raw)
