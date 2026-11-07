"""Transparent, deterministic role scoring for early-career product roles."""

from __future__ import annotations

import re
from dataclasses import dataclass

CLASSIFIER_VERSION = "rules-1.1"

ACCEPT = "accept"
REVIEW = "review"
REJECT = "reject"

ACCEPT_THRESHOLD = 60
REVIEW_THRESHOLD = 40
MAX_ENTRY_YEARS = 2  # a plain "Product Manager" asking for more is not entry-level
MAX_TITLED_YEARS = 3  # APM and junior titles often ask for slightly more
REJECT_FROM_YEARS = 5

ROLE_INTERN = "Product Management Intern"
ROLE_APM = "Associate Product Manager"
ROLE_JUNIOR = "Junior Product Manager"
ROLE_GRADUATE = "Graduate Product Manager"
ROLE_ENTRY = "Entry-Level Product Manager"
ROLE_ANALYST = "Product Analyst"
ROLE_OPS = "Product Operations"
ROLES = (ROLE_INTERN, ROLE_APM, ROLE_JUNIOR, ROLE_GRADUATE, ROLE_ENTRY, ROLE_ANALYST, ROLE_OPS)

_SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|director|head|vp|vice president|chief|cpo|group product|"
    r"gpm|manager of product|ii|iii|iv)\b",
    re.I,
)
# Always a different job, even when "product" or "PM" appears in the title.
_EXCLUDED_ALWAYS_RE = re.compile(
    r"\b(product (marketing|marketer|engineer|engineering|designer|design|owner|support|specialist|counsel|"
    r"security|sales|trainer)|program manager|project manager|delivery manager|engineering manager|"
    r"scrum master|account (executive|manager))\b",
    re.I,
)
# Functions that only count against a title without a real PM phrase, because
# "Product Manager, Customer Success" names a domain rather than a function.
_EXCLUDED_FUNCTION_RE = re.compile(
    r"\b(engineer(ing)?|developer|sde|devops|qa|tester|scientist|architect|designer|design|marketing|marketer|"
    r"sales|business development|customer|support|success|recruiter|talent|counsel|legal|finance|accountant|"
    r"compliance|security|content|copywriter|writer|trainer)\b",
    re.I,
)
_PM_PHRASE_RE = re.compile(r"\b(product manager|product management)\b", re.I)
_PM_RE = re.compile(r"\b(product manager|product management|pm)\b", re.I)
_INTERN_RE = re.compile(r"\b(interns?|internship|summer analyst)\b", re.I)
_APM_RE = re.compile(r"\b(associate product manager|apm|product manager,? associate|rotational product)\b", re.I)
_JUNIOR_RE = re.compile(r"\b(junior|jr\.?)\s+(product manager|pm)\b|\bproduct manager\s+(i|1)\b", re.I)
_GRAD_RE = re.compile(r"\b(graduate|new grad|campus|fresher|university grad)\b", re.I)
_ENTRY_RE = re.compile(r"\b(entry[- ]level)\b", re.I)
_ANALYST_RE = re.compile(r"\bproduct analyst\b", re.I)
_OPS_RE = re.compile(r"\bproduct op(s|erations)\b", re.I)
_YEARS_RE = re.compile(
    r"(?<![\d.])(\d{1,2})\s*(?:\+|plus)?\s*(?:[-–to]+\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs?)\b[^.\n]{0,40}"
    r"(?:experience|exp\b|product|work|relevant)",
    re.I,
)

_TITLE_YEARS_RE = re.compile(r"\bexp(?:erience)?\.?\s*[:\-]?\s*(\d{1,2})\s*(?:\+|[-–to]+\s*\d{1,2})?\s*(?:years?|yrs?)", re.I)

_RESPONSIBILITY_SIGNALS = {
    "lifecycle": r"product (life ?cycle|development|launch|release)|ship(ping)? (features|products)|go-to-market",
    "research": r"user research|customer (research|interviews|insights)|user interviews|voice of (the )?customer",
    "discovery": r"product discovery|problem discovery|identify (customer|user) (needs|problems|pain)",
    "roadmap": r"road ?map",
    "prioritisation": r"prioriti[sz]",
    "requirements": r"\bprds?\b|product requirements?|user stories|product spec",
    "analytics": r"product analytics|funnel|retention|cohort|a/b test|experimentation|product metrics|kpis?\b",
    "stakeholders": r"stakeholder|cross[- ]functional|engineering,? (and |& )?design",
    "strategy": r"product strategy|business strategy|market (research|analysis)|competitive analysis",
}
_SKILL_SIGNALS = {
    "sql": r"\bsql\b",
    "analytics tools": r"mixpanel|amplitude|google analytics|tableau|looker|power bi",
    "experimentation": r"a/b test|experiment",
    "agile": r"\bagile\b|\bscrum\b|\bjira\b",
    "design tools": r"\bfigma\b|wireframe|prototyp",
    "communication": r"communication skills|storytelling",
    "data analysis": r"data[- ](driven|analysis)|analytical skills|excel",
    "product sense": r"product sense|user empathy|customer empathy",
}
_OWNERSHIP_SIGNALS = (
    r"\bown(s|ing|ership)?\b",
    r"drive (the )?(product|feature|roadmap)",
    r"define (the )?(product|feature|roadmap|vision|requirements)",
    r"be responsible for",
    r"take (end-to-end|full) (ownership|responsibility)",
    r"end[- ]to[- ]end",
)


@dataclass
class RoleResult:
    decision: str
    classification: str | None
    relevance_score: int
    confidence: float
    reason: str
    experience_level: str | None
    classifier_version: str = CLASSIFIER_VERSION


def required_years(description: str) -> int | None:
    """Largest stated minimum, so '2+ years product, 5+ years overall' reads as 5."""
    found = [int(m.group(1)) for m in _YEARS_RE.finditer(description)]
    found += [int(m.group(1)) for m in _TITLE_YEARS_RE.finditer(description)]
    found = [y for y in found if y <= 25]
    return max(found) if found else None


def _reject(reason: str, score: int = 0) -> RoleResult:
    return RoleResult(REJECT, None, score, 0.95, reason, None)


def _title_role(title: str) -> str | None:
    if _OPS_RE.search(title):
        return ROLE_OPS
    if _ANALYST_RE.search(title):
        return ROLE_INTERN if _INTERN_RE.search(title) else ROLE_ANALYST
    has_pm = bool(_PM_RE.search(title)) or bool(re.search(r"\bproduct\b", title, re.I))
    if _INTERN_RE.search(title) and has_pm:
        return ROLE_INTERN
    if _APM_RE.search(title):
        return ROLE_APM
    if _JUNIOR_RE.search(title):
        return ROLE_JUNIOR
    if _PM_RE.search(title):
        if _GRAD_RE.search(title):
            return ROLE_GRADUATE
        if _ENTRY_RE.search(title):
            return ROLE_ENTRY
    return None


def _count(signals: dict[str, str], text: str) -> list[str]:
    return [name for name, pattern in signals.items() if re.search(pattern, text, re.I)]


def classify_role(title: str, description: str) -> RoleResult:
    clean_title = re.sub(r"\s+", " ", title or "").strip()
    text = description or ""

    if _APM_RE.search(clean_title) is None and _SENIOR_RE.search(clean_title):
        return _reject(f"seniority in title: '{clean_title}'")
    if _EXCLUDED_ALWAYS_RE.search(clean_title):
        return _reject(f"different function in title: '{clean_title}'")
    if not _PM_PHRASE_RE.search(clean_title) and _EXCLUDED_FUNCTION_RE.search(clean_title):
        return _reject(f"non-product function in title: '{clean_title}'")

    role = _title_role(clean_title)
    plain_pm = role is None and bool(_PM_RE.search(clean_title))
    if role is None and not plain_pm:
        return _reject(f"title is not a product role: '{clean_title}'")

    years = required_years(clean_title + " . " + text)
    if years is not None and years >= REJECT_FROM_YEARS and role != ROLE_INTERN:
        return _reject(f"requires {years}+ years of experience")
    limit = MAX_TITLED_YEARS if role else MAX_ENTRY_YEARS

    responsibilities = _count(_RESPONSIBILITY_SIGNALS, text)
    skills = _count(_SKILL_SIGNALS, text)
    ownership = [p for p in _OWNERSHIP_SIGNALS if re.search(p, text, re.I)]

    title_points = 30 if role else 18
    responsibility_points = min(30, len(responsibilities) * 6)
    skill_points = min(20, len(skills) * 5)
    if years is None:
        seniority_points = 10 if role else 3
    elif years <= limit:
        seniority_points = 10
    else:
        seniority_points = 3
    ownership_points = min(10, len(ownership) * 4)
    score = title_points + responsibility_points + skill_points + seniority_points + ownership_points

    if role is None:
        role = ROLE_ENTRY if years is not None and years <= MAX_ENTRY_YEARS else None

    reason = (
        f"score {score}/100: title {title_points}/30, responsibilities {responsibility_points}/30 "
        f"({', '.join(responsibilities) or 'none'}), skills {skill_points}/20 ({', '.join(skills) or 'none'}), "
        f"seniority {seniority_points}/10 (years stated: {years if years is not None else 'none'}), "
        f"ownership {ownership_points}/10"
    )

    # An untitled "Product Manager" with no evidence of being junior cannot be
    # called entry-level; a human decides.
    if role is None:
        return RoleResult(
            REVIEW if score >= REVIEW_THRESHOLD else REJECT, None, score, 0.4,
            reason + "; plain 'Product Manager' title without entry-level evidence", None,
        )
    if years is not None and years > limit:
        return RoleResult(REVIEW, role, score, 0.45, reason + f"; {years} years is above entry level", "Mid")

    level = "Internship" if role == ROLE_INTERN else "Entry"
    if score >= ACCEPT_THRESHOLD:
        return RoleResult(ACCEPT, role, score, min(0.99, score / 100), reason, level)
    if score >= REVIEW_THRESHOLD:
        return RoleResult(REVIEW, role, score, score / 100, reason + "; below acceptance threshold", level)
    return RoleResult(REJECT, role, score, 0.7, reason + "; below review threshold", level)
