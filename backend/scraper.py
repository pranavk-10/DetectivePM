"""
DetectivePM - Scraping engine.

Attempts to scrape LinkedIn for Product Management job posts via Playwright.
Falls back automatically to a realistic mock-data generator so the app works
out of the box even when scraping is blocked or Playwright is not installed.
"""

import hashlib
import random
import re
import string
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

INTERN_PATTERNS = re.compile(
    r"\b(intern|internship|pm\s*intern|co.?op|trainee|apprentice)\b",
    re.IGNORECASE,
)

FULLTIME_PATTERNS = re.compile(
    r"\b(full.?time|junior|associate|entry.?level|new.?grad|graduate)\b",
    re.IGNORECASE,
)

GENRE_KEYWORDS: dict[str, list[str]] = {
    "SaaS": ["saas", "software as a service", "b2b", "enterprise software", "cloud platform"],
    "B2C": ["b2c", "consumer", "e-commerce", "marketplace", "retail", "d2c"],
    "FinTech": ["fintech", "finance", "banking", "payments", "lending", "crypto", "insurtech"],
    "EdTech": ["edtech", "education", "learning", "e-learning", "upskilling", "lms"],
    "HealthTech": ["healthtech", "health", "medical", "healthcare", "biotech", "telemedicine"],
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")


def classify_role_type(text: str) -> str:
    """Return 'Intern' or 'Full-time' based on keyword matching."""
    if INTERN_PATTERNS.search(text):
        return "Intern"
    return "Full-time"


def classify_genre(text: str) -> str:
    """Return the most likely genre bucket for a post body."""
    lower = text.lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return genre
    return "General/Other"


def extract_contacts(text: str) -> str:
    """Return a comma-joined string of emails and phone numbers found in text."""
    emails = EMAIL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    contacts = list(dict.fromkeys(emails + [p.strip() for p in phones]))
    return ", ".join(contacts) if contacts else ""


def make_post_id(content: str, url: str = "") -> str:
    """Generate a stable SHA-256-based post ID from URL or content."""
    raw = (url or content).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Mock data generator
# ---------------------------------------------------------------------------

_MOCK_COMPANIES = [
    "Notion", "Linear", "Figma", "Loom", "Coda", "Airtable", "Webflow",
    "Vercel", "Supabase", "PlanetScale", "Retool", "Stripe", "Brex",
    "Ramp", "Mercury", "Duolingo", "Coursera", "Byju's", "Headspace",
    "Oscar Health", "Tempus", "Flatiron Health", "Calm", "Peloton",
]

_MOCK_NAMES = [
    "Alexandra Chen", "Marcus Williams", "Priya Patel", "Jordan Lee",
    "Sam Rivera", "Taylor Brooks", "Morgan Kim", "Casey Thompson",
    "Alex Johnson", "Jamie Martinez", "Riley Davis", "Avery Wilson",
    "Dana Garcia", "Quinn Robinson", "Blair Anderson",
]

_MOCK_TEMPLATES: list[dict] = [
    {
        "genre": "SaaS",
        "body": (
            "🚀 We're hiring a {role} at {company}! \n\n"
            "We're building the future of B2B SaaS and need a passionate PM "
            "to join our product team. You'll own the roadmap for our core "
            "collaboration features and work closely with engineering & design.\n\n"
            "✅ 0-2 years experience\n"
            "✅ Strong analytical skills\n"
            "✅ Experience with Agile/Scrum\n\n"
            "Send your resume to careers@{slug}.io or DM me directly!"
        ),
    },
    {
        "genre": "FinTech",
        "body": (
            "💳 Exciting opportunity: {role} at {company}\n\n"
            "We're a fast-growing fintech startup disrupting payments and lending. "
            "Looking for a sharp PM who can translate complex finance workflows "
            "into delightful user experiences.\n\n"
            "What you'll do:\n"
            "• Define product vision for our payment rails\n"
            "• Partner with compliance & engineering\n"
            "• Drive 0→1 feature launches\n\n"
            "Reach out: hiring@{slug}.com | +1-415-555-{phone}"
        ),
    },
    {
        "genre": "EdTech",
        "body": (
            "📚 Join our mission! {role} opening at {company}\n\n"
            "We're reimagining online learning for the next billion learners. "
            "As a PM intern you'll work on our adaptive learning engine and "
            "content recommendation systems.\n\n"
            "Requirements:\n"
            "• Passion for education\n"
            "• Data-driven mindset\n"
            "• Strong communication skills\n\n"
            "Apply via: jobs@{slug}.co"
        ),
    },
    {
        "genre": "HealthTech",
        "body": (
            "🏥 {company} is looking for a {role}!\n\n"
            "We're building the operating system for modern healthcare. "
            "Help us improve patient outcomes through intelligent product design.\n\n"
            "Ideal candidate:\n"
            "• Background in health systems or biotech\n"
            "• Experience with clinical workflows\n"
            "• Empathetic user researcher\n\n"
            "Contact: talent@{slug}.health"
        ),
    },
    {
        "genre": "B2C",
        "body": (
            "🛒 {role} role at {company} — apply now!\n\n"
            "Consumer product at scale is hard. We need a PM who thrives in "
            "ambiguity, loves A/B testing, and is obsessed with user retention.\n\n"
            "About us: Top-rated marketplace with 50M+ users\n\n"
            "What we offer:\n"
            "• Competitive stipend/salary\n"
            "• Mentorship from senior PMs\n"
            "• Remote-friendly\n\n"
            "DM me or send CV to: {slug}.careers@gmail.com"
        ),
    },
    {
        "genre": "General/Other",
        "body": (
            "📣 Hiring: {role} @ {company}\n\n"
            "Looking for a driven product thinker to join our growing team. "
            "You'll shape strategy, work cross-functionally, and ship features "
            "that make a real impact.\n\n"
            "Skills we value:\n"
            "• Product sense\n"
            "• Technical fluency\n"
            "• Leadership under ambiguity\n\n"
            "Apply: https://careers.{slug}.com/pm-roles"
        ),
    },
]

_MOCK_ROLES = [
    "Product Manager Intern",
    "PM Intern",
    "Junior Product Manager",
    "Associate Product Manager",
    "Product Management Intern",
]


def generate_mock_posts(count: int = 30) -> list[dict]:
    """
    Generate ``count`` realistic-looking mock PM job posts.

    This is used as a fallback when Playwright scraping fails or is blocked,
    ensuring the app works end-to-end without real LinkedIn credentials.
    """
    posts = []
    now = datetime.utcnow()

    for i in range(count):
        company = random.choice(_MOCK_COMPANIES)
        name = random.choice(_MOCK_NAMES)
        role = random.choice(_MOCK_ROLES)
        template = random.choice(_MOCK_TEMPLATES)
        slug = company.lower().replace(" ", "")
        phone_suffix = "".join(random.choices(string.digits, k=4))

        body = template["body"].format(
            role=role, company=company, slug=slug, phone=phone_suffix
        )
        genre = template["genre"]
        role_type = classify_role_type(role)
        contacts = extract_contacts(body)

        # Spread timestamps over the past 5 days
        delta_hours = random.uniform(0, 120)
        ts = (now - timedelta(hours=delta_hours)).replace(microsecond=0)

        uid = f"mock_{i}_{company}_{role}".replace(" ", "_")
        post_id = make_post_id(uid)

        posts.append(
            {
                "post_id": post_id,
                "timestamp": ts.isoformat(),
                "name": name,
                "account_id": f"linkedin_{hashlib.md5(name.encode()).hexdigest()[:10]}",
                "post_content": body,
                "role_type": role_type,
                "genre": genre,
                "contacts_present": contacts,
            }
        )

    return posts


# ---------------------------------------------------------------------------
# Playwright scraper (best-effort)
# ---------------------------------------------------------------------------

_SEARCH_QUERIES = [
    "Product Manager Intern",
    "Junior Product Manager",
    "Associate Product Manager",
    "PM Intern hiring",
]

_STEALTH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def _scrape_with_playwright(query: str, max_posts: int = 10) -> list[dict]:
    """
    Attempt to scrape LinkedIn search results for ``query`` using Playwright.

    Returns a (possibly empty) list of post dicts.
    Raises on any browser / network failure so the caller can fall back.
    """
    from playwright.sync_api import sync_playwright  # deferred import

    results: list[dict] = []
    url = (
        "https://www.linkedin.com/search/results/content/"
        f"?keywords={query.replace(' ', '%20')}&origin=SWITCH_SEARCH_VERTICAL"
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(extra_http_headers=_STEALTH_HEADERS)
        page = context.new_page()

        page.goto(url, timeout=20_000, wait_until="networkidle")
        page.wait_for_timeout(3000)

        post_elements = page.query_selector_all(
            "div.feed-shared-update-v2, article.occludable-update"
        )

        for el in post_elements[:max_posts]:
            try:
                content_el = el.query_selector(
                    "div.feed-shared-text, span.break-words"
                )
                content = content_el.inner_text().strip() if content_el else ""

                author_el = el.query_selector(
                    "span.feed-shared-actor__name, span.update-components-actor__name"
                )
                name = author_el.inner_text().strip() if author_el else "Unknown"

                link_el = el.query_selector("a[data-control-name='actor']")
                profile_url = link_el.get_attribute("href") if link_el else ""

                if not content:
                    continue

                post_id = make_post_id(content, profile_url)
                role_type = classify_role_type(content)
                genre = classify_genre(content)
                contacts = extract_contacts(content)

                results.append(
                    {
                        "post_id": post_id,
                        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat(),
                        "name": name,
                        "account_id": profile_url.split("/in/")[-1].rstrip("/")
                        if "/in/" in profile_url
                        else profile_url,
                        "post_content": content,
                        "role_type": role_type,
                        "genre": genre,
                        "contacts_present": contacts,
                    }
                )
            except Exception:
                continue

        browser.close()

    return results


def _scrape_with_requests(query: str, max_posts: int = 10) -> list[dict]:
    """
    Light fallback: use requests + BeautifulSoup against a public search endpoint.
    Returns empty list if no results or if blocked.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        url = (
            "https://www.linkedin.com/search/results/content/"
            f"?keywords={query.replace(' ', '+')}"
        )
        resp = requests.get(url, headers=_STEALTH_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        posts = []
        for block in soup.select("div.search-result__wrapper")[:max_posts]:
            text_el = block.select_one("p.search-result__snippets")
            content = text_el.get_text(separator=" ").strip() if text_el else ""
            if not content:
                continue

            post_id = make_post_id(content)
            posts.append(
                {
                    "post_id": post_id,
                    "timestamp": datetime.utcnow().replace(microsecond=0).isoformat(),
                    "name": "LinkedIn User",
                    "account_id": "",
                    "post_content": content,
                    "role_type": classify_role_type(content),
                    "genre": classify_genre(content),
                    "contacts_present": extract_contacts(content),
                }
            )
        return posts
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_posts(use_mock_on_failure: bool = True) -> list[dict]:
    """
    Scrape LinkedIn for PM job posts.

    Tries Playwright first, then requests+BS4, then falls back to mock data.

    Args:
        use_mock_on_failure: When True (default), returns generated mock posts
            if both real scraping methods fail. Set to False in tests that
            explicitly want to detect scraping failures.

    Returns:
        List of post dicts ready for ``database.insert_post``.
    """
    all_posts: list[dict] = []
    scraped_ok = False

    for query in _SEARCH_QUERIES:
        try:
            posts = _scrape_with_playwright(query, max_posts=8)
            if posts:
                all_posts.extend(posts)
                scraped_ok = True
        except Exception:
            # Playwright unavailable or blocked — try requests fallback
            try:
                posts = _scrape_with_requests(query, max_posts=8)
                if posts:
                    all_posts.extend(posts)
                    scraped_ok = True
            except Exception:
                pass

    if not scraped_ok and use_mock_on_failure:
        print("[scraper] Real scraping unavailable — using mock data generator.")
        all_posts = generate_mock_posts(count=30)

    # Deduplicate by post_id within this batch
    seen: set[str] = set()
    unique: list[dict] = []
    for post in all_posts:
        if post["post_id"] not in seen:
            seen.add(post["post_id"])
            unique.append(post)

    return unique
