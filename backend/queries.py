"""The single definition of what the public may see.

Every list, metric, search and export path starts from `visible_jobs()`, so
India-only enforcement cannot be missed by an individual endpoint.
"""

from __future__ import annotations

from sqlalchemy import Select, and_, select
from sqlalchemy.sql.elements import ColumnElement

from backend.config import settings
from backend.models import PROVENANCE_DEMO, PROVENANCE_LIVE, PROVENANCE_MANUAL, REVIEW_ACCEPTED, Job


def allowed_provenance() -> tuple[str, ...]:
    if settings.show_demo_data and not settings.is_production:
        return (PROVENANCE_LIVE, PROVENANCE_MANUAL, PROVENANCE_DEMO)
    return (PROVENANCE_LIVE, PROVENANCE_MANUAL)


def visible_condition() -> ColumnElement[bool]:
    return and_(
        Job.india_eligible.is_(True),
        Job.country_code == "IN",
        Job.review_status == REVIEW_ACCEPTED,
        Job.provenance.in_(allowed_provenance()),
    )


def visible_jobs() -> Select:
    return select(Job).where(visible_condition())
