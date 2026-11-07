"""Industry classification.

Registry data is preferred. Without it, a description must show at least two
distinct signals for one category, so a single phrase such as "machine
learning" or "learning" cannot decide a company's industry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INDUSTRIES = (
    "FinTech", "SaaS", "B2C", "AI/ML", "E-commerce", "EdTech", "HealthTech", "Enterprise Technology",
    "Logistics", "Mobility", "Consumer Technology", "General/Other",
)
GENERAL = "General/Other"
MIN_SIGNALS = 2

_SIGNALS: dict[str, tuple[str, ...]] = {
    "FinTech": ("fintech", "payments?", "lending", "credit card", "upi", "neobank", "banking", "insurtech",
                "wealth management", "mutual funds?", "stock broking", "nbfc"),
    "SaaS": ("saas", "software as a service", "b2b software", "subscription software", "multi-tenant",
             "arr\\b", "enterprise customers"),
    "AI/ML": ("generative ai", "llms?", "large language models?", "foundation models?", "ai agents?",
              "machine learning platform", "ai[- ]native", "ai[- ]first"),
    "E-commerce": ("e-?commerce", "online marketplace", "sellers?", "online shopping", "quick commerce",
                   "cart", "catalog(?:ue)?"),
    "EdTech": ("edtech", "learners?", "online courses?", "students?", "upskilling", "teachers?", "curriculum"),
    "HealthTech": ("healthtech", "patients?", "clinical", "hospitals?", "healthcare", "telemedicine", "pharmacy"),
    "Logistics": ("logistics", "last[- ]mile", "supply chain", "freight", "warehous", "fulfil+ment", "shipping"),
    "Mobility": ("mobility", "ride[- ]hailing", "electric vehicles?", "\\bev\\b", "fleet", "drivers?"),
    "B2C": ("b2c", "direct[- ]to[- ]consumer", "d2c", "consumer brand"),
    "Consumer Technology": ("consumer app", "consumer internet", "social media", "gaming", "streaming",
                            "millions of users", "creators?"),
    "Enterprise Technology": ("enterprise software", "cloud infrastructure", "cybersecurity", "data platform",
                              "observability", "developer tools?", "api platform"),
}
_COMPILED = {
    industry: [re.compile(rf"\b{pattern}", re.I) for pattern in patterns] for industry, patterns in _SIGNALS.items()
}


@dataclass
class IndustryResult:
    industry: str
    confidence: float
    reason: str


def classify_industry(company: str, description: str, registry_industry: str | None = None) -> IndustryResult:
    if registry_industry in INDUSTRIES and registry_industry != GENERAL:
        return IndustryResult(registry_industry, 0.95, f"company registry lists {company} as {registry_industry}")

    text = f"{company}\n{description or ''}"
    matches: dict[str, list[str]] = {}
    for industry, patterns in _COMPILED.items():
        found = {m.group(0).lower() for pattern in patterns if (m := pattern.search(text))}
        if len(found) >= MIN_SIGNALS:
            matches[industry] = sorted(found)

    if not matches:
        return IndustryResult(GENERAL, 0.3, f"fewer than {MIN_SIGNALS} distinct signals for any category")

    ranked = sorted(matches.items(), key=lambda item: len(item[1]), reverse=True)
    best, signals = ranked[0]
    tied = len(ranked) > 1 and len(ranked[1][1]) == len(signals)
    confidence = min(0.85, 0.45 + 0.1 * len(signals)) - (0.15 if tied else 0)
    return IndustryResult(best, round(confidence, 2), f"signals: {', '.join(signals)}")
