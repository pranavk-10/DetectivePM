"""Maps a source type to its connector and syncs the registry file into the database.

Add a company by editing backend/data/company_registry.yaml and running
`python -m backend.sources.registry`. No connector changes are needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Company, Source
from backend.sources.ashby import AshbyConnector
from backend.sources.authorized_api import AdzunaConnector, RemotiveConnector
from backend.sources.base import BaseConnector
from backend.sources.company_careers import CompanyCareersConnector
from backend.sources.greenhouse import GreenhouseConnector
from backend.sources.lever import LeverConnector
from backend.sources.manual_submission import ManualSubmissionConnector
from backend.sources.rss_feed import RssFeedConnector

log = logging.getLogger("detectivepm.registry")

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "company_registry.yaml"
MANUAL_SOURCE = "manual:submissions"

CONNECTORS: dict[str, type[BaseConnector]] = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
    "company_careers": CompanyCareersConnector,
    "rss": RssFeedConnector,
    "adzuna": AdzunaConnector,
    "remotive": RemotiveConnector,
    "manual": ManualSubmissionConnector,
}

ATS_BASE_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}",
    "lever": "https://api.lever.co/v0/postings/{board}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
}


def connector_for(source: Source, client=None) -> BaseConnector:
    return CONNECTORS[source.source_type](dict(source.config or {}), client=client)


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _upsert_source(db: Session, name: str, **fields) -> Source:
    source = db.scalar(select(Source).where(Source.source_name == name))
    if source is None:
        source = Source(source_name=name, **fields)
        db.add(source)
    else:
        for key, value in fields.items():
            setattr(source, key, value)  # never touches an administrator's `enabled` choice
    return source


def sync_registry(db: Session, path: Path = REGISTRY_PATH) -> dict[str, int]:
    data = load_registry(path)
    companies = 0
    for entry in data.get("companies", []):
        slug = entry["slug"]
        company = db.scalar(select(Company).where(Company.slug == slug))
        if company is None:
            company = Company(slug=slug, name=entry["name"])
            db.add(company)
        company.name = entry["name"]
        company.website = entry.get("website")
        company.careers_url = entry.get("careers_url")
        company.ats_provider = entry.get("ats_provider")
        company.ats_board = entry.get("ats_board")
        company.headquarters = entry.get("headquarters")
        company.india_presence = entry.get("india_presence")
        company.industry = entry.get("industry")
        company.monitoring_status = entry.get("monitoring_status", "pending_source")
        company.verification_evidence = entry.get("verification_evidence")
        db.flush()
        companies += 1
        provider = company.ats_provider
        if provider in ATS_BASE_URLS and company.monitoring_status == "monitored":
            _upsert_source(
                db,
                f"{provider}:{company.ats_board}",
                source_type=provider,
                base_url=ATS_BASE_URLS[provider].format(board=company.ats_board),
                company_id=company.id,
                config={"board": company.ats_board, "company": company.name, "website": company.website},
            )
    feeds = 0
    for feed in data.get("feeds", []):
        _upsert_source(
            db,
            feed["source_name"],
            source_type=feed["source_type"],
            base_url=feed.get("base_url"),
            config=feed.get("config") or {},
            min_interval_hours=feed.get("min_interval_hours", 0),
        )
        feeds += 1
    _upsert_source(db, MANUAL_SOURCE, source_type="manual", base_url=None, config={})
    db.commit()
    return {"companies": companies, "feeds": feeds}


if __name__ == "__main__":
    from backend.db import session_scope

    with session_scope() as session:
        print(sync_registry(session))
