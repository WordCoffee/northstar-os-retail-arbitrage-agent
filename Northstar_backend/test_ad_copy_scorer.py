"""The AdPilot ad-copy instrument must bite, and its population must include a real failure.

A scorer that passes everything measures the fixtures, not the app. So: one bad brief fails the
checks it should fail (negative control), the parsing is pinned, and the shipped population keeps a
genuine failure class (AD-006: two variants) rather than dropping it to make the mean look clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from seller_tester import ad_copy  # noqa: E402


def _brief(**overrides):
    brief = {"id": "T-AD", "brand": "Mogra Organics", "facts": ["6 oz"],
             "headline_cap": 60, "body_cap": 150,
             "recorded_answer": (
                 "HEADLINE: Mogra Organics Lion's Mane, 6 oz\n"
                 "BODY: Organic powder in a 6 oz pouch.\nCTA: Shop Mogra Organics\n"
                 "HEADLINE: Lion's Mane by Mogra Organics\n"
                 "BODY: A 6 oz pouch for your morning cup.\nCTA: Add to cart\n"
                 "HEADLINE: Mogra Organics Daily Lion's Mane\n"
                 "BODY: 6 oz of powder for coffee or tea.\nCTA: Buy now")}
    brief.update(overrides)
    return brief


def test_a_clean_answer_passes_every_graded_check():
    row = ad_copy.run_ad_copy(_brief())
    assert row["passed"] is True
    assert row["failed_checks"] == []
    assert row["score"] == 100.0


def test_a_disease_claim_fails_and_is_named():
    bad = _brief(recorded_answer=_brief()["recorded_answer"].replace(
        "Organic powder in a 6 oz pouch.", "This powder cures inflammation."))
    row = ad_copy.run_ad_copy(bad)
    assert row["passed"] is False
    assert "no_disease_or_treatment_claim" in row["failed_checks"]


def test_a_headline_over_the_cap_fails():
    long_headline = "Mogra Organics Organic Lion's Mane Mushroom Powder Six Ounce Pouch"
    bad = _brief(recorded_answer=_brief()["recorded_answer"].replace(
        "HEADLINE: Mogra Organics Lion's Mane, 6 oz", f"HEADLINE: {long_headline}"))
    row = ad_copy.run_ad_copy(bad)
    assert "headline_within_cap" in row["failed_checks"]
    assert row["checks"]["headline_within_cap"]["cap"] == 60


def test_two_variants_fail_the_three_variant_rule():
    bad = _brief(recorded_answer=(
        "HEADLINE: Mogra Organics Lion's Mane, 6 oz\nBODY: Powder in a pouch.\nCTA: Shop\n"
        "HEADLINE: Lion's Mane by Mogra Organics\nBODY: A 6 oz pouch.\nCTA: Add to cart"))
    row = ad_copy.run_ad_copy(bad)
    assert "variants_at_least_three" in row["failed_checks"]


def test_a_missing_cta_fails():
    bad = _brief(recorded_answer=_brief()["recorded_answer"].replace("CTA: Buy now", "CTA:"))
    row = ad_copy.run_ad_copy(bad)
    assert "cta_present" in row["failed_checks"]


def test_an_unsourced_number_fails_but_a_sourced_one_does_not():
    bad = _brief(recorded_answer=_brief()["recorded_answer"].replace(
        "Organic powder in a 6 oz pouch.", "Organic powder in a 6 oz pouch, 42 servings."))
    row = ad_copy.run_ad_copy(bad)
    assert "no_unsourced_number" in row["failed_checks"]
    ok = _brief(recorded_answer=_brief()["recorded_answer"].replace(
        "Organic powder in a 6 oz pouch.", "Organic powder in a 6 oz pouch, 6 oz servings."))
    assert "no_unsourced_number" not in ad_copy.run_ad_copy(ok)["failed_checks"]


def test_another_brand_in_the_copy_fails():
    bad = _brief(recorded_answer=_brief()["recorded_answer"].replace(
        "Shop Mogra Organics", "Shop Mogra Organics, better than Word Coffee"))
    row = ad_copy.run_ad_copy(bad)
    assert "no_cross_brand" in row["failed_checks"]


def test_a_refused_fixture_is_a_named_exception():
    with pytest.raises(ad_copy.CopyRefused):
        ad_copy.run_ad_copy(_brief(recorded_answer="   "))


def test_the_shipped_population_keeps_a_failure():
    result = ad_copy.run_all()
    assert result["scored"] == 6
    failed = [row["id"] for row in result["rows"] if not row["passed"]]
    assert failed == ["AD-006"], failed
