"""Development-only demo rows: python -m backend.seed_demo

Rows are marked provenance=demo_seed and stay hidden unless SHOW_DEMO_DATA=true.
Nothing in the application calls this module. Use `--remove` to delete the rows.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import delete, func, select

from backend.config import settings
from backend.db import session_scope
from backend.models import PROVENANCE_DEMO, REVIEW_ACCEPTED, Job
from backend.sources.text import canonicalize_url, company_key, content_hash, normalize_title

_DEMO_ROWS = (
    ("Demo Associate Product Manager", "Bengaluru", "Karnataka", "Associate Product Manager"),
    ("Demo Product Management Intern", "Pune", "Maharashtra", "Product Management Intern"),
    ("Demo Product Analyst", "Hyderabad", "Telangana", "Product Analyst"),
)
DEMO_COMPANY = "Example Demo Company"


def seed() -> int:
    if settings.is_production:
        print("Refusing to run: backend.seed_demo cannot run when ENVIRONMENT=production.", file=sys.stderr)
        return 1
    with session_scope() as db:
        added = 0
        for title, city, state, classification in _DEMO_ROWS:
            url = canonicalize_url(f"https://example.com/demo/{normalize_title(title).replace(' ', '-')}")
            if db.scalar(select(Job.id).where(Job.canonical_url == url)):
                continue
            description = f"DEMO RECORD, NOT A REAL JOB. {title} sample for local UI work."
            db.add(
                Job(
                    external_job_id=f"demo-{normalize_title(title)}", title=title,
                    normalized_title=normalize_title(title), company=DEMO_COMPANY,
                    company_key=company_key(DEMO_COMPANY), description=description, location=f"{city}, India",
                    city=city, state=state, country_code="IN", country_name="India", workplace_type="On-site",
                    india_eligible=True, location_confidence=1.0, location_evidence="demo seed",
                    classification=classification, relevance_score=0, application_url=url, canonical_url=url,
                    source_name="demo:seed", content_hash=content_hash(DEMO_COMPANY, title, description),
                    provenance=PROVENANCE_DEMO, review_status=REVIEW_ACCEPTED,
                )
            )
            added += 1
    print(f"Added {added} demo rows. Set SHOW_DEMO_DATA=true to display them.")
    return 0


def remove() -> int:
    with session_scope() as db:
        count = db.scalar(select(func.count()).select_from(Job).where(Job.provenance == PROVENANCE_DEMO))
        db.execute(delete(Job).where(Job.provenance == PROVENANCE_DEMO))
    print(f"Removed {count} demo rows.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    sys.exit(remove() if parser.parse_args().remove else seed())
