"""Recruiter contacts, taken only from text the employer published.

Nothing is guessed. A contact is stored only if the posting itself shows it,
next to wording about applying. "Verified" is never set here: that takes a
human with evidence, through the admin endpoint.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import session_scope
from backend.models import CONTACT_PUBLIC, CONTACT_UNVERIFIED, REVIEW_ACCEPTED, Job, Recruiter, utcnow

log = logging.getLogger("detectivepm.recruiters")

KIND_COMPANY = "company_recruiting_email"
KIND_INDIVIDUAL = "individual_recruiter_email"
KIND_UNVERIFIED = "unverified_address"
KIND_PHONE = "public_phone"

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<![\d-])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d-])")
_APPLY_CONTEXT = re.compile(
    r"\b(apply|applications?|resumes?|cvs?|recruit\w*|hiring|talent|send|share|reach out|contact|careers?|hr)\b", re.I
)
_EXCLUDE_CONTEXT = re.compile(
    r"\b(accommodations?|disabilit\w+|privacy|data protection|gdpr|fraud\w*|scams?|phishing|report|dpo|"
    r"grievance|whistle\w*|ethics|benefits|customers?|press|media)\b",
    re.I,
)
_EXCLUDE_LOCAL = re.compile(
    r"^(accommodations?|privacy|legal|compliance|security|support|help|noreply|no-reply|abuse|press|dpo|grievance|"
    r"ethics|billing|sales|info|contact|hello|admin)\b",
    re.I,
)
_ROLE_LOCAL = re.compile(r"(careers?|jobs?|talent|recruit\w*|hiring|hr|people|apply|campus|ta)\b", re.I)
_FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me", "protonmail.com", "icloud.com"}
_NAME_BEFORE = re.compile(
    r"(?i:contact|reach out to|write to|email|e-mail|send (?:your )?(?:cv|resume) to)\s+"
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})\s*(?:at|on|via|:|\(|,|-)?\s*$"
)


@dataclass
class FoundContact:
    email: str | None
    phone: str | None
    name: str | None
    kind: str
    status: str
    confidence: float
    evidence: str


def _window(text: str, start: int, end: int, size: int = 120) -> str:
    return text[max(0, start - size) : end + size]


def _domain_matches(domain: str, company_domain: str | None, company: str) -> bool:
    if company_domain:
        root = company_domain.lower().removeprefix("www.")
        if domain == root or domain.endswith("." + root):
            return True
    token = re.sub(r"[^a-z0-9]", "", company.lower())
    return bool(token) and token in re.sub(r"[^a-z0-9]", "", domain)


def extract_contacts(description: str, company: str, company_domain: str | None) -> list[FoundContact]:
    found: list[FoundContact] = []
    seen: set[str] = set()

    for match in _EMAIL_RE.finditer(description):
        email = match.group(0).lower()
        if email in seen:
            continue
        local, domain = email.split("@", 1)
        context = _window(description, match.start(), match.end())
        if _EXCLUDE_LOCAL.match(local) or _EXCLUDE_CONTEXT.search(context) or not _APPLY_CONTEXT.search(context):
            continue
        seen.add(email)
        evidence = re.sub(r"\s+", " ", context).strip()[:300]
        name_match = _NAME_BEFORE.search(description[max(0, match.start() - 80) : match.start()])
        name = name_match.group(1) if name_match else None
        if domain in _FREE_MAIL or not _domain_matches(domain, company_domain, company):
            found.append(FoundContact(email, None, name, KIND_UNVERIFIED, CONTACT_UNVERIFIED, 0.4, evidence))
        elif _ROLE_LOCAL.match(local):
            found.append(FoundContact(email, None, None, KIND_COMPANY, CONTACT_PUBLIC, 0.85, evidence))
        else:
            found.append(FoundContact(email, None, name, KIND_INDIVIDUAL, CONTACT_PUBLIC, 0.75, evidence))

    for match in _PHONE_RE.finditer(description):
        phone = re.sub(r"[\s-]", "", match.group(0))
        if phone in seen:
            continue
        context = _window(description, match.start(), match.end(), 80)
        if _EXCLUDE_CONTEXT.search(context) or not _APPLY_CONTEXT.search(context):
            continue
        seen.add(phone)
        evidence = re.sub(r"\s+", " ", context).strip()[:300]
        found.append(FoundContact(None, phone, None, KIND_PHONE, CONTACT_PUBLIC, 0.6, evidence))

    return found


def enrich_job(db: Session, job: Job) -> int:
    """Separate from ingestion: a job with no contact is still a genuine job."""
    added = 0
    for contact in extract_contacts(job.description, job.company, job.company_domain):
        exists = db.scalar(
            select(Recruiter.id).where(
                Recruiter.job_id == job.id, Recruiter.email == contact.email, Recruiter.phone == contact.phone
            )
        )
        if exists:
            continue
        db.add(
            Recruiter(
                job_id=job.id,
                recruiter_name=contact.name,
                company=job.company,
                email=contact.email,
                phone=contact.phone,
                source_url=job.application_url,
                contact_kind=contact.kind,
                evidence=contact.evidence,
                verification_status=contact.status,
                confidence_score=contact.confidence,
            )
        )
        added += 1
    job.recruiters_checked_at = utcnow()
    return added


def run_enrichment(limit: int = 1000) -> dict[str, int]:
    with session_scope() as db:
        jobs = db.scalars(
            select(Job)
            .where(Job.review_status == REVIEW_ACCEPTED, Job.recruiters_checked_at.is_(None))
            .limit(limit)
        ).all()
        added = sum(enrich_job(db, job) for job in jobs)
        return {"jobs_checked": len(jobs), "contacts_added": added}
