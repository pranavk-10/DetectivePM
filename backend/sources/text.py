"""Text and URL normalisation shared by connectors."""

from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

_TRACKING_PARAMS = re.compile(r"^(utm_.*|gh_src|lever-source.*|lever-origin|source|src|ref|referrer|t)$", re.I)

_REQUIREMENT_HEADINGS = re.compile(
    r"^\W*(requirements?|qualifications?|what (we'?re|we are) looking for|who you are|what you('ll)? (need|bring)|"
    r"must[- ]haves?|skills?( required)?|about you|you (should|will) have|preferred qualifications?)\W*$",
    re.I,
)
_RESPONSIBILITY_HEADINGS = re.compile(
    r"^\W*(responsibilities|key responsibilities|what you('ll| will) do|the role|your role|what you'll be doing|"
    r"what this role involves|your impact|day[- ]to[- ]day)\W*$",
    re.I,
)
_OTHER_HEADING = re.compile(
    r"^\W*(benefits|perks|about (us|the company)|why join|what we offer|compensation|equal opportunity|"
    r"who we are|our (mission|values))\b.{0,30}$",
    re.I,
)

SKILL_VOCABULARY = {
    "SQL": r"\bsql\b",
    "Python": r"\bpython\b",
    "Excel": r"\bexcel\b",
    "Tableau": r"\btableau\b",
    "Power BI": r"\bpower ?bi\b",
    "Looker": r"\blooker\b",
    "Mixpanel": r"\bmixpanel\b",
    "Amplitude": r"\bamplitude\b",
    "Google Analytics": r"\bgoogle analytics\b",
    "A/B Testing": r"\ba/b test",
    "Figma": r"\bfigma\b",
    "Jira": r"\bjira\b",
    "Agile": r"\bagile\b",
    "Scrum": r"\bscrum\b",
    "Wireframing": r"\bwirefram",
    "User Research": r"\buser research\b",
    "Product Analytics": r"\bproduct analytics\b",
    "Roadmapping": r"\broad ?map",
    "Stakeholder Management": r"\bstakeholder",
    "Go-to-Market": r"\bgo[- ]to[- ]market\b",
    "Market Research": r"\bmarket research\b",
}


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    soup = BeautifulSoup(html.unescape(markup), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(["br"]):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "ul", "ol"]):
        tag.append("\n")
    text = soup.get_text()
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def extract_sections(text: str) -> tuple[str | None, str | None]:
    """Return (requirements, responsibilities) from headed sections, if any."""
    current: str | None = None
    sections: dict[str, list[str]] = {"req": [], "resp": []}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) <= 60:
            if _REQUIREMENT_HEADINGS.match(stripped):
                current = "req"
                continue
            if _RESPONSIBILITY_HEADINGS.match(stripped):
                current = "resp"
                continue
            if _OTHER_HEADING.match(stripped):
                current = None
                continue
        if current:
            sections[current].append(stripped)
    return ("\n".join(sections["req"]) or None, "\n".join(sections["resp"]) or None)


def extract_skills(text: str) -> list[str]:
    return [skill for skill, pattern in SKILL_VOCABULARY.items() if re.search(pattern, text, re.I)]


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    deduped = list(dict.fromkeys(query))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(deduped), ""))


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9/+ ]+", " ", title.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def company_key(name: str) -> str:
    cleaned = re.sub(
        r"\b(inc|llc|ltd|limited|pvt|private|corp|corporation|technologies|technology)\b\.?", " ", name.lower()
    )
    return re.sub(r"[^a-z0-9]+", "", cleaned) or re.sub(r"[^a-z0-9]+", "", name.lower())


def content_hash(company: str, title: str, description: str) -> str:
    body = re.sub(r"\s+", " ", description.lower()).strip()
    raw = f"{company_key(company)}|{normalize_title(title)}|{body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
