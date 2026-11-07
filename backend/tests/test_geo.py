"""India eligibility, including the twelve required cases."""

import pytest

from backend.pipeline.geo import ACCEPT, REJECT, REVIEW, GeoInput, evaluate_location
from backend.tests.conftest import add_listing, make_job
from backend.pipeline.ingest import REJECTED, upsert_job


def check(location=None, **kwargs):
    return evaluate_location(GeoInput(location=location, **kwargs))


@pytest.mark.parametrize(
    "location, city, state",
    [
        ("Bengaluru, Karnataka, India", "Bengaluru", "Karnataka"),
        ("Mumbai, Maharashtra", "Mumbai", "Maharashtra"),
        ("Pune", "Pune", "Maharashtra"),
        ("Hyderabad, India", "Hyderabad", "Telangana"),
        ("Bangalore", "Bengaluru", "Karnataka"),
        ("Gurgaon", "Gurugram", "Haryana"),
        ("Bengaluru-VTP, India", "Bengaluru", "Karnataka"),
        ("Bangalore HQ", "Bengaluru", "Karnataka"),
        ("hyderabad", "Hyderabad", "Telangana"),
        ("Trivandrum", "Thiruvananthapuram", "Kerala"),
    ],
)
def test_indian_cities_are_accepted(location, city, state):
    result = check(location)
    assert result.decision == ACCEPT
    assert (result.city, result.state, result.country_code, result.india_eligible) == (city, state, "IN", True)
    assert result.country_name == "India"


@pytest.mark.parametrize("location", ["Remote - India", "Remote, India", "India (Remote)", "Remote (India)"])
def test_remote_india_is_accepted(location):
    result = check(location)
    assert result.decision == ACCEPT
    assert result.workplace_type == "Remote"
    assert result.remote_eligibility == "india_remote"


def test_worldwide_remote_explicitly_permitting_india_is_accepted():
    result = check("Remote - Worldwide", description="We hire globally, and candidates based in India are welcome.")
    assert result.decision == ACCEPT
    assert result.remote_eligibility == "worldwide_india_permitted"
    assert result.location_evidence


@pytest.mark.parametrize(
    "location",
    ["San Francisco, CA", "New York, NY", "United States", "Remote - US", "USA", "Remote, United States"],
)
def test_us_only_is_rejected(location):
    assert check(location).decision == REJECT


@pytest.mark.parametrize("location", ["London, United Kingdom", "London", "Remote - UK", "United Kingdom"])
def test_uk_only_is_rejected(location):
    assert check(location).decision == REJECT


@pytest.mark.parametrize("location", ["Singapore", "Singapore, Singapore", "Remote - Singapore"])
def test_singapore_only_is_rejected(location):
    assert check(location).decision == REJECT


@pytest.mark.parametrize("location", ["Remote", "Anywhere", "Worldwide", "Anywhere in the World"])
def test_remote_with_unknown_eligibility_goes_to_review(location):
    result = check(location, description="A great job with a great team.")
    assert result.decision == REVIEW
    assert result.india_eligible is False
    assert result.country_code is None


def test_remote_word_alone_is_never_permission():
    assert check("Remote", is_remote=True, description="").decision == REVIEW


def test_description_mentioning_india_in_passing_is_not_permission():
    description = "Our founders once visited India and loved it."
    assert check("Remote", description=description).decision == REVIEW


def test_restrictive_description_rejects_remote():
    assert check("Remote", description="This role is US-only.").decision == REJECT
    assert check("Remote", description="You must be located in the United States.").decision == REJECT


def test_multiple_locations_keep_the_indian_option():
    assert check("Bengaluru or Singapore").decision == ACCEPT
    assert check("London | Pune").city == "Pune"


@pytest.mark.parametrize("location", ["Hyderabad, Pakistan", "Delhi, NY", "Kochi, Japan"])
def test_foreign_places_sharing_indian_names_are_rejected(location):
    assert check(location).decision == REJECT


def test_structured_country_is_decisive():
    assert check("Headquarters", structured_country="IN").decision == ACCEPT
    assert check("Headquarters", structured_country="India").location_confidence == 1.0
    assert check("Bengaluru", structured_country="US").decision == ACCEPT  # the location still names India
    assert check("Dubai", structured_country="AE").decision == REJECT


@pytest.mark.parametrize("location", ["APAC", "Asia Pacific", "Asia"])
def test_asia_regions_need_a_human(location):
    assert check(location).decision == REVIEW


def test_unknown_place_goes_to_review():
    assert check("Mars Colony One").decision == REVIEW
    assert check(None).decision == REVIEW


@pytest.mark.parametrize("location", ["Europe", "EMEA", "North America", "LATAM"])
def test_non_india_regions_are_rejected(location):
    assert check(location).decision == REJECT


def test_workplace_type_comes_from_structured_hint():
    assert check("Pune", workplace_hint="hybrid").workplace_type == "Hybrid"
    assert check("Pune", workplace_hint="onsite").workplace_type == "On-site"
    assert check("Pune", workplace_hint="OnSite").workplace_type == "On-site"
    assert check("Pune", workplace_hint="remote").workplace_type == "Remote"


def test_non_india_job_cannot_enter_active_listings(db, source):
    assert upsert_job(db, source, make_job(location="Austin, TX")) == REJECTED
    db.commit()
    assert db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM jobs")).scalar() == 0


def test_listing_moved_abroad_leaves_the_board(db, source, client):
    upsert_job(db, source, make_job())
    db.commit()
    assert client.get("/api/jobs").json()["total"] == 1
    upsert_job(db, source, make_job(location="London, UK"))
    db.commit()
    assert client.get("/api/jobs").json()["total"] == 0
    assert client.get("/api/jobs/metrics").json()["total_jobs"] == 0


def test_non_india_rows_never_appear_in_exports_or_metrics(db, client):
    add_listing(db, title="Visible PM Intern Bengaluru", company="Visible")
    add_listing(
        db, title="Hidden Review Job", company="Hidden", india_eligible=False, country_code=None,
        country_name=None, review_status="manual_review",
    )
    csv_text = client.get("/api/export/csv").text
    assert "Visible PM Intern Bengaluru" in csv_text
    assert "Hidden Review Job" not in csv_text
    assert client.get("/api/jobs/metrics").json()["total_jobs"] == 1
    assert client.get("/api/jobs", params={"search": "Hidden"}).json()["total"] == 0
