"""Greenhouse public Job Board API: https://developers.greenhouse.io/job-board.html"""

from __future__ import annotations

from urllib.parse import urlsplit

from backend.sources.base import BaseConnector, NormalizedJob, SourceError, parse_datetime
from backend.sources.text import html_to_text

API = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseConnector(BaseConnector):
    source_type = "greenhouse"

    @property
    def board(self) -> str:
        return self.config["board"]

    def fetch_jobs(self) -> list[dict]:
        data = self.get_json(f"{API}/{self.board}/jobs", params={"content": "true", "pay_transparency": "true"})
        if "jobs" not in data:
            raise SourceError(f"greenhouse board {self.board}: no jobs key in response")
        return data["jobs"]

    def fetch_one(self, job_id: str) -> dict:
        return self.get_json(f"{API}/{self.board}/jobs/{job_id}", params={"pay_transparency": "true"})

    def extract_metadata(self, raw: dict) -> dict:
        return {
            "departments": [d.get("name") for d in raw.get("departments", [])],
            "requisition_id": raw.get("requisition_id"),
        }

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        url = raw.get("absolute_url") or ""
        offices = [o.get("location") or o.get("name") for o in raw.get("offices", []) if o]
        pay = (raw.get("pay_input_ranges") or [{}])[0]
        job = NormalizedJob(
            external_job_id=str(raw.get("id", "")),
            title=(raw.get("title") or "").strip(),
            company=self.config.get("company") or raw.get("company_name") or "",
            description=html_to_text(raw.get("content")),
            application_url=url,
            source_url=f"{API}/{self.board}/jobs/{raw.get('id')}",
            company_domain=urlsplit(self.config.get("website") or "").netloc or None,
            location=(raw.get("location") or {}).get("name"),
            extra_locations=[o for o in offices if o],
            date_posted=parse_datetime(raw.get("first_published") or raw.get("updated_at")),
            expiry_date=parse_datetime(raw.get("application_deadline")),
            salary_min=pay.get("min_cents", 0) / 100 if pay.get("min_cents") else None,
            salary_max=pay.get("max_cents", 0) / 100 if pay.get("max_cents") else None,
            salary_currency=pay.get("currency_type"),
        )
        return self.finish(job, raw)
