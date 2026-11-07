"""Lever public Postings API: https://github.com/lever/postings-api"""

from __future__ import annotations

from urllib.parse import urlsplit

from backend.sources.base import BaseConnector, NormalizedJob, employment_label, parse_datetime
from backend.sources.text import html_to_text

API = "https://api.lever.co/v0/postings"


class LeverConnector(BaseConnector):
    source_type = "lever"

    @property
    def board(self) -> str:
        return self.config["board"]

    def fetch_jobs(self) -> list[dict]:
        return self.get_json(f"{API}/{self.board}", params={"mode": "json"})

    def fetch_one(self, job_id: str) -> dict:
        return self.get_json(f"{API}/{self.board}/{job_id}", params={"mode": "json"})

    def extract_metadata(self, raw: dict) -> dict:
        categories = raw.get("categories") or {}
        return {"team": categories.get("team"), "department": categories.get("department")}

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        categories = raw.get("categories") or {}
        sections = [raw.get("descriptionPlain") or html_to_text(raw.get("description"))]
        for item in raw.get("lists") or []:
            sections.append(f"{item.get('text', '')}\n{html_to_text(item.get('content'))}")
        sections.append(raw.get("additionalPlain") or html_to_text(raw.get("additional")))
        description = "\n\n".join(part.strip() for part in sections if part and part.strip())
        salary = raw.get("salaryRange") or {}
        all_locations = categories.get("allLocations") or []
        job = NormalizedJob(
            external_job_id=str(raw.get("id", "")),
            title=(raw.get("text") or "").strip(),
            company=self.config.get("company") or self.board,
            description=description,
            application_url=raw.get("applyUrl") or raw.get("hostedUrl") or "",
            source_url=raw.get("hostedUrl"),
            company_domain=urlsplit(self.config.get("website") or "").netloc or None,
            location=categories.get("location"),
            extra_locations=[loc for loc in all_locations if loc != categories.get("location")],
            # Lever's country describes the primary location only.
            structured_country=raw.get("country") if len(all_locations) <= 1 else None,
            workplace_hint=raw.get("workplaceType"),
            employment_type=employment_label(categories.get("commitment")),
            date_posted=parse_datetime(raw.get("createdAt")),
            salary_min=salary.get("min"),
            salary_max=salary.get("max"),
            salary_currency=salary.get("currency"),
        )
        return self.finish(job, raw)
