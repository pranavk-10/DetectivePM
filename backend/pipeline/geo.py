"""India eligibility validation.

The rule of the module: a job is accepted only on positive evidence of India
eligibility. Unknown geography goes to manual review. The word "Remote" is
never evidence on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ACCEPT = "accept"
REVIEW = "review"
REJECT = "reject"

INDIA_CODE = "IN"
INDIA_NAME = "India"

# canonical city -> (state, spellings)
_CITIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "Bengaluru": ("Karnataka", ("bengaluru", "bangalore", "blr")),
    "Mumbai": ("Maharashtra", ("mumbai", "bombay", "navi mumbai", "thane", "powai", "andheri")),
    "Pune": ("Maharashtra", ("pune",)),
    "Hyderabad": ("Telangana", ("hyderabad", "secunderabad")),
    "Delhi": ("Delhi", ("delhi", "new delhi", "delhi ncr", "ncr")),
    "Gurugram": ("Haryana", ("gurugram", "gurgaon")),
    "Noida": ("Uttar Pradesh", ("noida", "greater noida")),
    "Chennai": ("Tamil Nadu", ("chennai", "madras")),
    "Kolkata": ("West Bengal", ("kolkata", "calcutta")),
    "Ahmedabad": ("Gujarat", ("ahmedabad", "gandhinagar", "gift city")),
    "Jaipur": ("Rajasthan", ("jaipur",)),
    "Indore": ("Madhya Pradesh", ("indore",)),
    "Kochi": ("Kerala", ("kochi", "cochin", "ernakulam")),
    "Chandigarh": ("Chandigarh", ("chandigarh", "mohali", "panchkula")),
    "Thiruvananthapuram": ("Kerala", ("thiruvananthapuram", "trivandrum")),
    "Bhubaneswar": ("Odisha", ("bhubaneswar", "bhubaneshwar")),
    "Lucknow": ("Uttar Pradesh", ("lucknow",)),
    "Surat": ("Gujarat", ("surat",)),
    "Nagpur": ("Maharashtra", ("nagpur",)),
    "Coimbatore": ("Tamil Nadu", ("coimbatore",)),
    "Visakhapatnam": ("Andhra Pradesh", ("visakhapatnam", "vizag")),
    "Mysuru": ("Karnataka", ("mysuru", "mysore")),
    "Vadodara": ("Gujarat", ("vadodara", "baroda")),
    "Bhopal": ("Madhya Pradesh", ("bhopal",)),
    "Patna": ("Bihar", ("patna",)),
    "Guwahati": ("Assam", ("guwahati",)),
    "Faridabad": ("Haryana", ("faridabad",)),
    "Ghaziabad": ("Uttar Pradesh", ("ghaziabad",)),
    "Goa": ("Goa", ("panaji",)),
}

_STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep",
    "Puducherry",
)
# States shared with places abroad (Punjab, Pakistan) still need the foreign
# check below, which runs first.

_CITY_LOOKUP = {spelling: city for city, (_, names) in _CITIES.items() for spelling in names}
_CITY_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in sorted(_CITY_LOOKUP, key=len, reverse=True)) + r")\b", re.I
)
_STATE_RE = re.compile(r"\b(" + "|".join(re.escape(s) for s in _STATES) + r")\b", re.I)
_INDIA_RE = re.compile(r"\b(india|bharat)\b|\bind\b(?=\s*$)", re.I)

_FOREIGN_COUNTRIES = (
    "united states", "usa", "u\\.s\\.a?\\.?", "us", "united kingdom", "uk", "u\\.k\\.", "england", "scotland", "wales",
    "ireland", "singapore", "canada", "australia", "new zealand", "germany", "france", "spain", "portugal",
    "italy", "netherlands", "belgium", "switzerland", "austria", "sweden", "norway", "denmark", "finland",
    "poland", "romania", "bulgaria", "czech republic", "czechia", "hungary", "greece", "turkey", "türkiye",
    "israel", "uae", "united arab emirates", "dubai", "abu dhabi", "saudi arabia", "qatar", "egypt", "kenya",
    "nigeria", "south africa", "japan", "south korea", "korea", "china", "hong kong", "taiwan", "thailand",
    "vietnam", "malaysia", "indonesia", "philippines", "pakistan", "bangladesh", "sri lanka", "nepal",
    "brazil", "mexico", "argentina", "colombia", "chile", "peru", "serbia", "croatia", "ukraine", "lithuania",
    "latvia", "estonia", "north macedonia", "cyprus", "malta", "luxembourg",
)
_FOREIGN_CITIES = (
    "san francisco", "new york", "new york city", "nyc", "seattle", "austin", "boston", "chicago", "los angeles",
    "denver", "atlanta", "palo alto", "mountain view", "sunnyvale", "san jose", "miami", "dallas", "washington",
    "london", "manchester", "edinburgh", "dublin", "berlin", "munich", "paris", "amsterdam", "madrid", "barcelona",
    "lisbon", "zurich", "stockholm", "toronto", "vancouver", "montreal", "sydney", "melbourne", "tokyo", "seoul",
    "shanghai", "beijing", "tel aviv", "sao paulo", "são paulo", "mexico city", "bangkok", "jakarta", "manila",
    "kuala lumpur", "karachi", "lahore", "dhaka", "colombo",
)
_FOREIGN_REGIONS = (
    "north america", "latin america", "latam", "south america", "americas", "europe", "eu", "emea", "european union",
    "nordics", "dach", "benelux", "middle east", "africa", "oceania", "anz",
)
_FOREIGN_RE = re.compile(
    r"(?<![\w-])(" + "|".join(_FOREIGN_COUNTRIES + _FOREIGN_CITIES + _FOREIGN_REGIONS) + r")(?![\w-])", re.I
)
_US_STATE_RE = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|"
    r"OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
)
_ASIA_AMBIGUOUS_RE = re.compile(r"\b(apac|asia[\s-]*pacific|asia|south\s*asia|emea\s*&?\s*apac|global south)\b", re.I)
_REMOTE_RE = re.compile(r"\b(remote|work from home|wfh|distributed|telecommute|anywhere)\b", re.I)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)
_WORLDWIDE_RE = re.compile(r"\b(world\s*-?wide|global(ly)?|anywhere|any\s+location|international)\b", re.I)

_PERMIT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:remote|work from anywhere|hire|hiring|open|available|welcome|eligible|applicants?|candidates?)[^.\n]{0,80}"
        r"\b(?:in|from|across|including|within|based in|residing in)\s+india\b",
        r"\bindia[- ]based\b",
        r"\bindia[- ]remote\b",
        r"\bremote[,:\s-]+\(?india\)?\b",
    )
]
_EXCLUDE_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\b(?:us|u\.s\.|united states|uk|u\.k\.|united kingdom|europe|eu|canada|singapore)[- ]only\b",
        r"\bonly\s+(?:open|available|hiring|accepting)[^.\n]{0,40}\b(?:us|u\.s\.|united states|uk|united kingdom|europe|eu|canada|singapore)\b",
        r"\b(?:must|required to|need to)\s+(?:be\s+)?(?:located|based|reside|live|residing)\s+in\s+(?:the\s+)?"
        r"(?:us|u\.s\.|united states|uk|united kingdom|europe|eu|canada|singapore)\b",
        r"\bauthori[sz]ed to work in (?:the\s+)?(?:us|u\.s\.|united states|uk|united kingdom|eu|canada)\b",
        r"\bnot (?:open|available|eligible)[^.\n]{0,40}\bindia\b",
        r"\bexcluding\s+india\b",
    )
]

_COUNTRY_NAMES_TO_CODE = {"india": "IN", "in": "IN", "ind": "IN"}


@dataclass
class GeoInput:
    location: str | None = None
    extra_locations: list[str] = field(default_factory=list)
    structured_country: str | None = None
    workplace_hint: str | None = None
    is_remote: bool | None = None
    description: str = ""


@dataclass
class GeoResult:
    decision: str
    india_eligible: bool
    country_code: str | None
    country_name: str | None
    city: str | None
    state: str | None
    workplace_type: str | None
    remote_eligibility: str
    location_confidence: float
    location_evidence: str


def _segments(locations: list[str]) -> list[str]:
    parts: list[str] = []
    for text in locations:
        parts.extend(s.strip() for s in re.split(r"\s*(?:[;|/\n•]|\bor\b|\band\b|\s[–—-]\s(?=[A-Z][a-z]+,))\s*", text) if s.strip())
    return parts


def _india_match(segment: str) -> tuple[str | None, str | None, bool] | None:
    """Return (city, state, explicit_country) when the text names an Indian place."""
    if _FOREIGN_RE.search(segment) or _US_STATE_RE.search(segment):
        # "Hyderabad, Pakistan" or "Delhi, NY" must not pass as India, unless
        # India itself is also named.
        if not _INDIA_RE.search(segment):
            return None
    explicit = bool(_INDIA_RE.search(segment))
    city_match = _CITY_RE.search(segment)
    if city_match:
        city = _CITY_LOOKUP[city_match.group(1).lower()]
        return city, _CITIES[city][0], explicit
    state_match = _STATE_RE.search(segment)
    if state_match:
        return None, state_match.group(1).title(), explicit
    if explicit:
        return None, None, True
    return None


def _workplace(geo: GeoInput, text: str) -> str | None:
    hint = (geo.workplace_hint or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    if hint in {"remote"}:
        return "Remote"
    if hint in {"hybrid"}:
        return "Hybrid"
    if hint in {"onsite", "inoffice", "office"}:
        return "On-site"
    if _HYBRID_RE.search(text):
        return "Hybrid"
    if geo.is_remote or _REMOTE_RE.search(text):
        return "Remote"
    return "On-site" if text.strip() else None


def _result(
    decision: str,
    *,
    workplace: str | None,
    evidence: str,
    remote: str,
    confidence: float,
    city: str | None = None,
    state: str | None = None,
    india: bool = False,
) -> GeoResult:
    return GeoResult(
        decision=decision,
        india_eligible=india,
        country_code=INDIA_CODE if india else None,
        country_name=INDIA_NAME if india else None,
        city=city,
        state=state,
        workplace_type=workplace,
        remote_eligibility=remote,
        location_confidence=confidence,
        location_evidence=evidence,
    )


def evaluate_location(geo: GeoInput) -> GeoResult:
    raw = [loc for loc in [geo.location, *geo.extra_locations] if loc]
    joined = " | ".join(raw)
    workplace = _workplace(geo, joined)
    is_remote = workplace == "Remote"
    description = geo.description or ""

    structured = (geo.structured_country or "").strip().lower()
    structured_india = _COUNTRY_NAMES_TO_CODE.get(structured) == INDIA_CODE

    # A hard exclusion in the text beats a vague location.
    exclusion = next((m.group(0) for p in _EXCLUDE_PATTERNS if (m := p.search(description))), None)

    # 1. Any segment naming India or an Indian place.
    best: tuple[str | None, str | None, bool] | None = None
    for segment in _segments(raw):
        match = _india_match(segment)
        if match and (best is None or (match[0] and not best[0]) or (match[2] and not best[2])):
            best = match

    if best is not None or structured_india:
        city, state, explicit = best or (None, None, False)
        evidence_parts = []
        if structured_india:
            evidence_parts.append(f"structured country '{geo.structured_country}'")
        if best is not None:
            evidence_parts.append(f"location text '{joined[:160]}'")
        confidence = 1.0 if structured_india else (0.98 if explicit else 0.9)
        if is_remote:
            remote = "india_remote"
        elif workplace == "Hybrid":
            remote = "not_remote_hybrid_india"
        else:
            remote = "not_remote_onsite_india"
        return _result(
            ACCEPT, workplace=workplace, evidence="; ".join(evidence_parts), remote=remote,
            confidence=confidence, city=city, state=state, india=True,
        )

    # 2. A structured non-India country is decisive.
    if structured and not structured_india:
        return _result(
            REJECT, workplace=workplace, remote="restricted_other_country", confidence=0.95,
            evidence=f"structured country '{geo.structured_country}' is not India",
        )

    # 3. Named foreign locations with no Indian option.
    has_foreign = bool(_FOREIGN_RE.search(joined) or _US_STATE_RE.search(joined))
    if has_foreign:
        return _result(
            REJECT, workplace=workplace, remote="restricted_other_country", confidence=0.9,
            evidence=f"location '{joined[:160]}' names only non-India places",
        )

    if exclusion:
        return _result(
            REJECT, workplace=workplace, remote="restricted_other_country", confidence=0.85,
            evidence=f"description restricts eligibility: '{exclusion[:120]}'",
        )

    permission = next((m.group(0) for p in _PERMIT_PATTERNS if (m := p.search(description))), None)

    # 4. Worldwide or plain remote: needs an explicit statement about India.
    if is_remote or _WORLDWIDE_RE.search(joined):
        if permission:
            return _result(
                ACCEPT, workplace="Remote", remote="worldwide_india_permitted", confidence=0.8, india=True,
                evidence=f"remote role, description states: '{permission[:160]}'",
            )
        return _result(
            REVIEW, workplace="Remote", remote="unknown", confidence=0.2,
            evidence=f"'{joined[:120] or 'remote'}' with no statement that India is eligible",
        )

    # 5. Asia-wide regions might include India but do not say so.
    if _ASIA_AMBIGUOUS_RE.search(joined):
        return _result(
            REVIEW, workplace=workplace, remote="unknown", confidence=0.3,
            evidence=f"regional location '{joined[:120]}' does not confirm India",
        )

    return _result(
        REVIEW, workplace=workplace, remote="unknown", confidence=0.1,
        evidence=f"could not resolve location '{joined[:120] or 'none given'}'",
    )
