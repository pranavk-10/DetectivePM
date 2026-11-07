"""Ashby public job postings API: https://developers.ashbyhq.com/docs/public-job-posting-api"""

from __future__ import annotations

from urllib.parse import urlsplit

from backend.sources.base import BaseConnector, NormalizedJob, employment_label, parse_datetime
from backend.sources.text import html_to_text

API = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyConnector(BaseConnector):
    source_type = "ashby"

    @property
    def board(self) -> str:
        return self.config["board"]

    def fetch_jobs(self) -> list[dict]:
        data = self.get_json(f"{API}/{self.board}", params={"includeCompensation": "true"})
        return [job for job in data.get("jobs", []) if job.get("isListed", True)]

    def extract_metadata(self, raw: dict) -> dict:
        return {"department": raw.get("department"), "team": raw.get("team")}

    @staticmethod
    def _salary(raw: dict) -> tuple[float | None, float | None, str | None]:
        for tier in (raw.get("compensation") or {}).get("compensationTiers") or []:
            for component in tier.get("components") or []:
                if component.get("compensationType") == "Salary":
                    return component.get("minValue"), component.get("maxValue"), component.get("currencyCode")
        return None, None, None

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        address = ((raw.get("address") or {}).get("postalAddress")) or {}
        secondary = []
        for entry in raw.get("secondaryLocations") or []:
            name = entry.get("location") if isinstance(entry, dict) else entry
            if name:
                secondary.append(name)
        low, high, currency = self._salary(raw)
        job = NormalizedJob(
            external_job_id=str(raw.get("id", "")),
            title=(raw.get("title") or "").strip(),
            company=self.config.get("company") or self.board,
            description=raw.get("descriptionPlain") or html_to_text(raw.get("descriptionHtml")),
            application_url=raw.get("applyUrl") or raw.get("jobUrl") or "",
            source_url=raw.get("jobUrl"),
            company_domain=urlsplit(self.config.get("website") or "").netloc or None,
            location=raw.get("location"),
            extra_locations=secondary,
            # The address describes the primary location only.
            structured_country=address.get("addressCountry") if not secondary else None,
            workplace_hint=raw.get("workplaceType"),
            is_remote=raw.get("isRemote"),
            employment_type=employment_label(raw.get("employmentType")),
            date_posted=parse_datetime(raw.get("publishedAt")),
            salary_min=low,
            salary_max=high,
            salary_currency=currency,
        )
        return self.finish(job, raw)
