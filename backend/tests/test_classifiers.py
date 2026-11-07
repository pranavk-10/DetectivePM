"""Role and industry classification. Titles here come from real postings seen in ingestion."""

import pytest

from backend.pipeline import roles
from backend.pipeline.industry import classify_industry
from backend.pipeline.roles import (
    ROLE_ANALYST,
    ROLE_APM,
    ROLE_ENTRY,
    ROLE_GRADUATE,
    ROLE_INTERN,
    ROLE_JUNIOR,
    ROLE_OPS,
    classify_role,
    required_years,
)
from backend.tests.conftest import GOOD_DESCRIPTION


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Product Management Intern", ROLE_INTERN),
        ("PM Intern", ROLE_INTERN),
        ("Product Manager Intern, Payments", ROLE_INTERN),
        ("Associate Product Manager", ROLE_APM),
        ("APM - Growth", ROLE_APM),
        ("Junior Product Manager", ROLE_JUNIOR),
        ("Product Manager I", ROLE_JUNIOR),
        ("Graduate Product Manager", ROLE_GRADUATE),
        ("Entry-Level Product Manager", ROLE_ENTRY),
        ("Product Analyst", ROLE_ANALYST),
        ("Product Management- Product Analyst- Telco", ROLE_ANALYST),
        ("Product Operations Associate", ROLE_OPS),
    ],
)
def test_target_roles_are_accepted(title, expected):
    result = classify_role(title, GOOD_DESCRIPTION)
    assert result.decision == roles.ACCEPT, result.reason
    assert result.classification == expected
    assert result.classifier_version == roles.CLASSIFIER_VERSION
    assert "score" in result.reason


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineer, Product", "Product Engineer", "Senior Product Manager", "Lead Product Manager",
        "Principal PM", "Group Product Manager", "Director of Product", "Head of Product",
        "Product Marketing Manager", "Product Marketing Intern", "Product Designer", "Product Design Intern",
        "Project Manager", "Technical Program Manager", "Sales Manager", "Product Support Specialist",
        "Customer Success Manager", "Data Scientist", "Software Engineering Intern", "Account Manager",
        "Product Specialist", "Finance Intern", "VP Product",
    ],
)
def test_irrelevant_titles_are_rejected(title):
    assert classify_role(title, GOOD_DESCRIPTION).decision == roles.REJECT


def test_description_mentioning_product_does_not_qualify_a_role():
    assert classify_role("Operations Coordinator", GOOD_DESCRIPTION).decision == roles.REJECT


def test_pm_in_a_domain_is_not_mistaken_for_that_function():
    result = classify_role("Associate Product Manager, Customer Success", GOOD_DESCRIPTION)
    assert result.decision == roles.ACCEPT


def test_plain_pm_without_years_needs_a_human():
    description = GOOD_DESCRIPTION.replace("0-1 years of product experience.", "")
    result = classify_role("Product Manager", description)
    assert result.decision == roles.REVIEW
    assert result.classification is None


def test_plain_pm_with_entry_experience_is_entry_level():
    result = classify_role("Product Manager", GOOD_DESCRIPTION.replace("0-1 years", "1-2 years"))
    assert result.classification == ROLE_ENTRY
    assert result.decision == roles.ACCEPT


@pytest.mark.parametrize(
    "stated",
    ["3+ years of Product Management experience", "3 to 6 years of hands-on product management experience",
     "3–5 years of product management experience"],
)
def test_mid_level_pm_is_not_labelled_entry_level(stated):
    """Regression: these real Paytm, Okta and Sarvam postings were accepted as entry-level."""
    description = GOOD_DESCRIPTION.replace("0-1 years of product experience.", stated)
    result = classify_role("Product Manager, Product Platform", description)
    assert result.decision == roles.REVIEW
    assert result.classification != ROLE_ENTRY


def test_years_in_the_title_count():
    """Regression: 'Product Management - UPI Product | Experience : 3-5 yrs'."""
    result = classify_role("Product Management - UPI Product | Experience : 3-5 yrs", GOOD_DESCRIPTION)
    assert result.decision == roles.REVIEW


def test_five_or_more_years_is_rejected():
    description = GOOD_DESCRIPTION.replace("0-1 years of product experience.", "7+ years of product experience.")
    assert classify_role("Product Manager", description).decision == roles.REJECT


def test_apm_may_ask_for_slightly_more_experience():
    description = GOOD_DESCRIPTION.replace("0-1 years", "3 years")
    assert classify_role("Associate Product Manager", description).decision == roles.ACCEPT


def test_thin_description_goes_to_review_not_accept():
    assert classify_role("Associate Product Manager", "Short posting about a role.").decision != roles.ACCEPT


def test_score_is_bounded():
    assert 0 <= classify_role("Associate Product Manager", GOOD_DESCRIPTION * 3).relevance_score <= 100


def test_required_years_takes_the_largest_stated_minimum():
    assert required_years("Overall experience of 3+ yrs with at least 1+ yrs in product") == 3
    assert required_years("No experience needed") is None


def test_machine_learning_phrase_is_not_edtech():
    text = "You will work with machine learning teams and learning from customers."
    assert classify_industry("Acme", text).industry != "EdTech"


def test_single_keyword_never_decides():
    assert classify_industry("Acme", "We also touch payments sometimes.").industry == "General/Other"


def test_two_signals_decide():
    result = classify_industry("Acme", "A payments and lending company.")
    assert result.industry == "FinTech"
    assert "payments" in result.reason


def test_registry_outranks_text():
    result = classify_industry("Acme", "payments and lending and upi", "SaaS")
    assert (result.industry, result.confidence) == ("SaaS", 0.95)
