"""Rebuild backend/data/company_registry.yaml from live evidence.

    python scripts/build_registry.py

A board is only marked `monitored` if its public API responds now and the job
text (or Greenhouse's board name) names the company. A careers URL is only
recorded if it loads. Failures are printed and left out, never assumed.
"""

from __future__ import annotations

import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "backend" / "data" / "company_registry.yaml"

INDIA_RE = re.compile(
    r"india|bengaluru|bangalore|mumbai|gurgaon|gurugram|hyderabad|pune|delhi|noida|chennai", re.I
)

# name, website, industry, headquarters, provider, board
BOARDS = [
    ("Groww", "https://groww.in", "FinTech", "Bengaluru, India", "greenhouse", "groww"),
    ("InMobi", "https://www.inmobi.com", "Enterprise Technology", "Bengaluru, India", "greenhouse", "inmobi"),
    ("Observe.AI", "https://www.observe.ai", "AI/ML", "San Francisco, USA", "greenhouse", "observeai"),
    ("Okta", "https://www.okta.com", "Enterprise Technology", "San Francisco, USA", "greenhouse", "okta"),
    ("Databricks", "https://www.databricks.com", "AI/ML", "San Francisco, USA", "greenhouse", "databricks"),
    ("Zscaler", "https://www.zscaler.com", "Enterprise Technology", "San Jose, USA", "greenhouse", "zscaler"),
    ("MongoDB", "https://www.mongodb.com", "Enterprise Technology", "New York, USA", "greenhouse", "mongodb"),
    ("Stripe", "https://stripe.com", "FinTech", "San Francisco, USA", "greenhouse", "stripe"),
    ("GitLab", "https://about.gitlab.com", "Enterprise Technology", "San Francisco, USA", "greenhouse", "gitlab"),
    ("Rubrik", "https://www.rubrik.com", "Enterprise Technology", "Palo Alto, USA", "greenhouse", "rubrik"),
    ("Toast", "https://pos.toasttab.com", "SaaS", "Boston, USA", "greenhouse", "toast"),
    ("Elastic", "https://www.elastic.co", "Enterprise Technology", "San Francisco, USA", "greenhouse", "elastic"),
    ("Twilio", "https://www.twilio.com", "SaaS", "San Francisco, USA", "greenhouse", "twilio"),
    ("Coinbase", "https://www.coinbase.com", "FinTech", "USA", "greenhouse", "coinbase"),
    ("Agoda", "https://www.agoda.com", "Consumer Technology", "Singapore", "greenhouse", "agoda"),
    ("Airbnb", "https://www.airbnb.com", "Consumer Technology", "San Francisco, USA", "greenhouse", "airbnb"),
    ("Turing", "https://www.turing.com", "AI/ML", "San Francisco, USA", "greenhouse", "turing"),
    ("Datadog", "https://www.datadoghq.com", "Enterprise Technology", "New York, USA", "greenhouse", "datadog"),
    ("Anthropic", "https://www.anthropic.com", "AI/ML", "San Francisco, USA", "greenhouse", "anthropic"),
    ("Figma", "https://www.figma.com", "SaaS", "San Francisco, USA", "greenhouse", "figma"),
    ("Mixpanel", "https://mixpanel.com", "SaaS", "San Francisco, USA", "greenhouse", "mixpanel"),
    ("Vercel", "https://vercel.com", "Enterprise Technology", "San Francisco, USA", "greenhouse", "vercel"),
    ("Paytm", "https://paytm.com", "FinTech", "Noida, India", "lever", "paytm"),
    ("Meesho", "https://www.meesho.com", "E-commerce", "Bengaluru, India", "lever", "meesho"),
    ("Zeta", "https://www.zeta.tech", "FinTech", "Bengaluru, India", "lever", "zeta"),
    ("Mindtickle", "https://www.mindtickle.com", "SaaS", "San Francisco, USA", "lever", "mindtickle"),
    ("FamPay", "https://famapp.in", "FinTech", "Bengaluru, India", "lever", "fampay"),
    ("CRED", "https://cred.club", "FinTech", "Bengaluru, India", "lever", "cred"),
    ("Tekion", "https://tekion.com", "SaaS", "San Carlos, USA", "ashby", "tekion"),
    ("Sarvam", "https://www.sarvam.ai", "AI/ML", "Bengaluru, India", "ashby", "sarvam"),
    ("Snowflake", "https://www.snowflake.com", "Enterprise Technology", "USA", "ashby", "snowflake"),
    ("Airwallex", "https://www.airwallex.com", "FinTech", "Singapore", "ashby", "airwallex"),
    ("OpenAI", "https://openai.com", "AI/ML", "San Francisco, USA", "ashby", "openai"),
    ("Atlan", "https://atlan.com", "SaaS", "Singapore", "ashby", "atlan"),
    ("Notion", "https://www.notion.so", "SaaS", "San Francisco, USA", "ashby", "notion"),
    ("Amplitude", "https://amplitude.com", "SaaS", "San Francisco, USA", "ashby", "amplitude"),
]

# Target companies with no public board found. name, website, industry, headquarters, careers page
PENDING = [
    ("Google", "https://www.google.com", "Enterprise Technology", "Mountain View, USA", "https://www.google.com/about/careers/applications/"),
    ("Microsoft", "https://www.microsoft.com", "Enterprise Technology", "Redmond, USA", "https://careers.microsoft.com/"),
    ("Amazon", "https://www.amazon.com", "E-commerce", "Seattle, USA", "https://www.amazon.jobs/"),
    ("Atlassian", "https://www.atlassian.com", "SaaS", "Sydney, Australia", "https://www.atlassian.com/company/careers"),
    ("Adobe", "https://www.adobe.com", "SaaS", "San Jose, USA", "https://careers.adobe.com/"),
    ("Salesforce", "https://www.salesforce.com", "SaaS", "San Francisco, USA", "https://careers.salesforce.com/"),
    ("Uber", "https://www.uber.com", "Mobility", "San Francisco, USA", "https://www.uber.com/careers/"),
    ("PhonePe", "https://www.phonepe.com", "FinTech", "Bengaluru, India", "https://www.phonepe.com/careers/"),
    ("Razorpay", "https://razorpay.com", "FinTech", "Bengaluru, India", "https://razorpay.com/jobs/"),
    ("Swiggy", "https://www.swiggy.com", "Consumer Technology", "Bengaluru, India", "https://careers.swiggy.com/"),
    ("Zomato (Eternal)", "https://www.eternal.com", "Consumer Technology", "Gurugram, India", "https://www.zomato.com/careers"),
    ("Zepto", "https://www.zeptonow.com", "E-commerce", "Mumbai, India", "https://www.zeptonow.com/careers"),
    ("Flipkart", "https://www.flipkart.com", "E-commerce", "Bengaluru, India", "https://www.flipkartcareers.com/"),
    ("Zerodha", "https://zerodha.com", "FinTech", "Bengaluru, India", "https://zerodha.com/careers/"),
    ("Juspay", "https://juspay.io", "FinTech", "Bengaluru, India", "https://juspay.io/careers"),
    ("BrowserStack", "https://www.browserstack.com", "SaaS", "Mumbai, India", "https://www.browserstack.com/careers"),
    ("Postman", "https://www.postman.com", "Enterprise Technology", "San Francisco, USA", "https://www.postman.com/company/careers/"),
    ("Freshworks", "https://www.freshworks.com", "SaaS", "San Mateo, USA", "https://www.freshworks.com/company/careers/"),
    ("Zoho", "https://www.zoho.com", "SaaS", "Chennai, India", "https://www.zoho.com/careers/"),
    ("Chargebee", "https://www.chargebee.com", "SaaS", "San Francisco, USA", "https://www.chargebee.com/careers/"),
    ("ShareChat", "https://sharechat.com", "Consumer Technology", "Bengaluru, India", "https://sharechat.com/careers"),
    ("Acko", "https://www.acko.com", "FinTech", "Bengaluru, India", "https://www.acko.com/careers/"),
    ("Urban Company", "https://www.urbancompany.com", "Consumer Technology", "Gurugram, India", "https://careers.urbancompany.com/"),
    ("Porter", "https://porter.in", "Logistics", "Bengaluru, India", "https://porter.in/careers"),
    ("PolicyBazaar", "https://www.policybazaar.com", "FinTech", "Gurugram, India", "https://www.policybazaar.com/careers/"),
    ("Nykaa", "https://www.nykaa.com", "E-commerce", "Mumbai, India", "https://www.nykaa.com/careers"),
    ("Lenskart", "https://www.lenskart.com", "E-commerce", "Gurugram, India", "https://www.lenskart.com/careers"),
    ("Dream Sports", "https://www.dreamsports.group", "Consumer Technology", "Mumbai, India", "https://www.dreamsports.group/careers"),
    ("upGrad", "https://www.upgrad.com", "EdTech", "Mumbai, India", "https://www.upgrad.com/careers/"),
    ("Cars24", "https://www.cars24.com", "E-commerce", "Gurugram, India", "https://www.cars24.com/careers/"),
    ("Ola", "https://www.olacabs.com", "Mobility", "Bengaluru, India", "https://www.olacabs.com/careers"),
    ("Delhivery", "https://www.delhivery.com", "Logistics", "Gurugram, India", "https://www.delhivery.com/careers"),
    ("Shiprocket", "https://www.shiprocket.in", "Logistics", "New Delhi, India", "https://www.shiprocket.in/careers/"),
    ("Innovaccer", "https://innovaccer.com", "HealthTech", "San Francisco, USA", "https://innovaccer.com/careers"),
    ("Cashfree", "https://www.cashfree.com", "FinTech", "Bengaluru, India", "https://www.cashfree.com/careers/"),
    ("PayU", "https://corporate.payu.com", "FinTech", "Gurugram, India", "https://corporate.payu.com/careers/"),
    ("BharatPe", "https://bharatpe.com", "FinTech", "New Delhi, India", "https://bharatpe.com/careers"),
    ("Pine Labs", "https://www.pinelabs.com", "FinTech", "Noida, India", "https://www.pinelabs.com/careers"),
    ("CoinDCX", "https://coindcx.com", "FinTech", "Mumbai, India", "https://coindcx.com/careers"),
    ("INDmoney", "https://www.indmoney.com", "FinTech", "Gurugram, India", "https://www.indmoney.com/careers"),
    ("Intuit", "https://www.intuit.com", "FinTech", "Mountain View, USA", "https://www.intuit.com/careers/"),
    ("PayPal", "https://www.paypal.com", "FinTech", "San Jose, USA", "https://careers.pypl.com/"),
    ("Visa", "https://www.visa.com", "FinTech", "San Francisco, USA", "https://corporate.visa.com/en/jobs/"),
    ("Mastercard", "https://www.mastercard.com", "FinTech", "New York, USA", "https://careers.mastercard.com/"),
    ("ServiceNow", "https://www.servicenow.com", "SaaS", "Santa Clara, USA", "https://careers.servicenow.com/"),
    ("Workday", "https://www.workday.com", "SaaS", "Pleasanton, USA", "https://www.workday.com/en-us/company/careers/overview.html"),
    ("Sprinklr", "https://www.sprinklr.com", "SaaS", "New York, USA", "https://www.sprinklr.com/careers/"),
    ("Whatfix", "https://whatfix.com", "SaaS", "San Jose, USA", "https://whatfix.com/careers/"),
    ("CleverTap", "https://clevertap.com", "SaaS", "Mountain View, USA", "https://clevertap.com/careers/"),
    ("MoEngage", "https://www.moengage.com", "SaaS", "San Francisco, USA", "https://www.moengage.com/careers/"),
    ("Darwinbox", "https://darwinbox.com", "SaaS", "Hyderabad, India", "https://darwinbox.com/careers"),
    ("Fractal", "https://fractal.ai", "AI/ML", "New York, USA", "https://fractal.ai/careers/"),
    ("Gupshup", "https://www.gupshup.ai", "SaaS", "San Francisco, USA", "https://www.gupshup.ai/careers"),
    ("Khatabook", "https://khatabook.com", "FinTech", "Bengaluru, India", "https://khatabook.com/careers"),
    ("Blinkit", "https://blinkit.com", "E-commerce", "Gurugram, India", "https://blinkit.com/careers"),
    ("MakeMyTrip", "https://www.makemytrip.com", "Consumer Technology", "Gurugram, India", "https://careers.makemytrip.com/"),
    ("Ixigo", "https://www.ixigo.com", "Consumer Technology", "Gurugram, India", "https://www.ixigo.com/about/careers/"),
    ("Kissflow", "https://kissflow.com", "SaaS", "Chennai, India", "https://kissflow.com/careers/"),
    ("Myntra", "https://www.myntra.com", "E-commerce", "Bengaluru, India", "https://careers.myntra.com/"),
    ("Shopify", "https://www.shopify.com", "E-commerce", "Ottawa, Canada", "https://www.shopify.com/careers"),
    ("Booking.com", "https://www.booking.com", "Consumer Technology", "Amsterdam, Netherlands", "https://jobs.booking.com/"),
    ("HubSpot", "https://www.hubspot.com", "SaaS", "Cambridge, USA", "https://www.hubspot.com/careers"),
    ("Nutanix", "https://www.nutanix.com", "Enterprise Technology", "San Jose, USA", "https://www.nutanix.com/company/careers"),
    ("Expedia Group", "https://www.expediagroup.com", "Consumer Technology", "Seattle, USA", "https://careers.expediagroup.com/"),
]

FEEDS = [
    {
        "source_name": "remotive:product",
        "source_type": "remotive",
        "base_url": "https://remotive.com/api/remote-jobs",
        "min_interval_hours": 6,
        "config": {},
    },
    {
        "source_name": "rss:weworkremotely-product",
        "source_type": "rss",
        "base_url": "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "config": {"url": "https://weworkremotely.com/categories/remote-product-jobs.rss", "remote_feed": True},
    },
    {
        "source_name": "adzuna:india",
        "source_type": "adzuna",
        "base_url": "https://api.adzuna.com/v1/api/jobs/in/search",
        "config": {},
    },
]

client = httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent": "DetectivePM-registry-check/1.0"})
browser_client = httpx.Client(
    timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; DetectivePM/2.0)"}
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def text_of(value) -> str:
    return re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))


def read_board(provider: str, board: str) -> tuple[list[tuple[str, str]], str | None]:
    """Return [(location, text)] and a board display name, from the public API."""
    if provider == "greenhouse":
        base = f"https://boards-api.greenhouse.io/v1/boards/{board}"
        rows = client.get(f"{base}/jobs", params={"content": "true"})
        rows.raise_for_status()
        display = client.get(base).json().get("name")
        return [((j.get("location") or {}).get("name", ""), text_of(j.get("content"))) for j in rows.json()["jobs"]], display
    if provider == "lever":
        rows = client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
        rows.raise_for_status()
        return [
            (" ".join((j.get("categories") or {}).get("allLocations") or [(j.get("categories") or {}).get("location") or ""]),
             j.get("descriptionPlain") or text_of(j.get("description")))
            for j in rows.json()
        ], None
    rows = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    rows.raise_for_status()
    return [
        (" ".join([j.get("location") or "", str(j.get("secondaryLocations") or ""), str(j.get("address") or "")]),
         j.get("descriptionPlain") or "")
        for j in rows.json()["jobs"]
    ], None


def check_board(entry: tuple) -> dict | None:
    name, website, industry, hq, provider, board = entry
    try:
        jobs, display = read_board(provider, board)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"SKIP {name}: board {provider}/{board} unreadable ({type(exc).__name__})")
        return None
    token = re.sub(r"[^a-z0-9]", "", name.lower())
    named = sum(1 for _, text in jobs if token in re.sub(r"[^a-z0-9]", "", text.lower()))
    india = sum(1 for location, _ in jobs if INDIA_RE.search(location))
    board_named = bool(display and token in re.sub(r"[^a-z0-9]", "", display.lower()))
    if not board_named and named == 0:
        print(f"SKIP {name}: identity not confirmed on {provider}/{board}")
        return None
    if india == 0:
        print(f"SKIP {name}: no India locations on {provider}/{board} today")
        return None
    return {
        "name": name, "slug": slugify(name), "website": website, "careers_url": None, "ats_provider": provider,
        "ats_board": board, "headquarters": hq, "india_presence": "india_hiring_confirmed", "industry": industry,
        "monitoring_status": "monitored",
        "verification_evidence": (
            f"{date.today()}: public {provider} API returned {len(jobs)} jobs, {india} in India; identity "
            f"confirmed by {'board name ' + repr(display) if board_named else str(named) + ' job descriptions naming the company'}"
        ),
    }


def check_pending(entry: tuple) -> dict:
    name, website, industry, hq, careers = entry
    try:
        response = browser_client.get(careers)
        loaded = response.status_code == 200
        detail = f"HTTP {response.status_code}"
        final = str(response.url).split("#")[0]
    except httpx.HTTPError as exc:
        loaded, detail, final = False, type(exc).__name__, careers
    return {
        "name": name, "slug": slugify(name), "website": website, "careers_url": final if loaded else None,
        "ats_provider": None, "ats_board": None, "headquarters": hq, "india_presence": "to_verify",
        "industry": industry, "monitoring_status": "pending_source",
        "verification_evidence": (
            f"{date.today()}: no public Greenhouse, Lever or Ashby board found; careers page check: {detail}"
        ),
    }


def main() -> int:
    with ThreadPoolExecutor(6) as pool:
        monitored = [row for row in pool.map(check_board, BOARDS) if row]
        pending = list(pool.map(check_pending, PENDING))
    data = {
        "generated_on": str(date.today()),
        "note": "Generated by scripts/build_registry.py from live checks. Do not hand-add unverified identifiers.",
        "companies": monitored + pending,
        "feeds": FEEDS,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    print(f"monitored={len(monitored)} pending={len(pending)} careers_verified={sum(1 for p in pending if p['careers_url'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
