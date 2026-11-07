"""Job feeds published as RSS for syndication."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from backend.sources.base import BaseConnector, NormalizedJob, SourceError
from backend.sources.text import html_to_text


class RssFeedConnector(BaseConnector):
    source_type = "rss"

    def fetch_jobs(self) -> list[dict]:
        url = self.config["url"]
        response = self.get(url)
        if response.status_code != 200:
            raise SourceError(f"{url}: HTTP {response.status_code}")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise SourceError(f"{url}: invalid XML: {exc}") from exc
        items = []
        for item in root.iter("item"):
            items.append({re.sub(r"^\{.*\}", "", child.tag): (child.text or "") for child in item})
        return items

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        heading = (raw.get("title") or "").strip()
        # We Work Remotely style: "Company: Role".
        company, _, title = heading.partition(":")
        if not title:
            company, title = self.config.get("company", ""), heading
        try:
            posted = parsedate_to_datetime(raw.get("pubDate", "")) if raw.get("pubDate") else None
        except (TypeError, ValueError):
            posted = None
        link = (raw.get("link") or raw.get("guid") or "").strip()
        job = NormalizedJob(
            external_job_id=(raw.get("guid") or link).strip(),
            title=title.strip(),
            company=company.strip(),
            description=html_to_text(raw.get("description")),
            application_url=link,
            source_url=link,
            location=(raw.get("region") or raw.get("location") or "").strip() or None,
            is_remote=True if self.config.get("remote_feed") else None,
            date_posted=posted,
        )
        return self.finish(job, raw)
