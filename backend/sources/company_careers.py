"""Official careers pages that publish schema.org JobPosting markup.

Only structured data the company publishes for machines is read, and
robots.txt is honoured. A page without JobPosting data yields nothing rather
than guessed HTML parsing.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from backend.sources.base import BaseConnector, NormalizedJob, SourceError, employment_label, parse_datetime
from backend.sources.text import canonicalize_url, html_to_text


def _walk(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            yield node
        for key in ("@graph", "itemListElement", "item"):
            if key in node:
                yield from _walk(node[key])


def parse_job_postings(markup: str) -> list[dict]:
    soup = BeautifulSoup(markup, "html.parser")
    postings: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        postings.extend(_walk(data))
    return postings


def _location(posting: dict) -> tuple[str | None, str | None]:
    places = posting.get("jobLocation") or []
    places = places if isinstance(places, list) else [places]
    for place in places:
        address = (place or {}).get("address") or {}
        if isinstance(address, str):
            return address, None
        country = address.get("addressCountry")
        country = country.get("name") if isinstance(country, dict) else country
        parts = [address.get("addressLocality"), address.get("addressRegion"), country]
        text = ", ".join(str(p) for p in parts if p)
        if text:
            return text, country
    return None, None


class CompanyCareersConnector(BaseConnector):
    source_type = "company_careers"

    def fetch_jobs(self) -> list[dict]:
        url = self.config["url"]
        if not self.robots_allowed(url):
            raise SourceError(f"robots.txt does not permit reading {url}")
        response = self.get(url)
        if response.status_code != 200:
            raise SourceError(f"{url}: HTTP {response.status_code}")
        return parse_job_postings(response.text)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        url = raw.get("url") or raw.get("sameAs") or self.config["url"]
        identifier = raw.get("identifier")
        identifier = identifier.get("value") if isinstance(identifier, dict) else identifier
        organisation = raw.get("hiringOrganization") or {}
        organisation = organisation if isinstance(organisation, dict) else {"name": organisation}
        location, country = _location(raw)
        salary = raw.get("baseSalary") if isinstance(raw.get("baseSalary"), dict) else {}
        value = salary.get("value") if isinstance(salary.get("value"), dict) else {}
        employment = raw.get("employmentType")
        employment = employment[0] if isinstance(employment, list) and employment else employment
        job = NormalizedJob(
            external_job_id=str(identifier or canonicalize_url(url)),
            title=(raw.get("title") or "").strip(),
            company=self.config.get("company") or organisation.get("name") or "",
            description=html_to_text(raw.get("description")),
            application_url=url,
            source_url=self.config["url"],
            company_domain=urlsplit(self.config.get("website") or url).netloc or None,
            location=location,
            structured_country=country,
            is_remote=True if raw.get("jobLocationType") == "TELECOMMUTE" else None,
            employment_type=employment_label(employment if isinstance(employment, str) else None),
            date_posted=parse_datetime(raw.get("datePosted")),
            expiry_date=parse_datetime(raw.get("validThrough")),
            salary_min=value.get("minValue"),
            salary_max=value.get("maxValue"),
            salary_currency=salary.get("currency"),
        )
        return self.finish(job, raw)
