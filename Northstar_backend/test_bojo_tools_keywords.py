"""Tests for the Bojo keyword tool (`track_keywords`).

Offline: no network, no model, no database. The real ``seo_score`` engine runs
for the pass path (so the assertions pin the documented head 3.0 / body 1.5
weighting and the ``None``-without-a-denominator rule), and a fake scorer proves
the injection seam.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import keywords as kw  # noqa: E402
from bojo_tools.keywords import TOOLS, track_keywords  # noqa: E402

PROFILE = {
    "name": "Northstar Matcha",
    "keyword_clusters": {
        "head": ["matcha", "green tea"],
        "body": ["stone milled", "ceremonial"],
        "negative": ["cheap", "detox"],
    },
    "competitors": ["Jade Leaf"],
}

LISTING = {
    "title": "Northstar Matcha Green Tea Powder",
    "bullets": ["CEREMONIAL: made in small batches"],
    "backend_terms": "usucha koicha",
    "description": "A ceremonial matcha for daily drinking.",
}


class FakeStore:
    def __init__(self, profile=None, error=None):
        self.profile = profile
        self.error = error
        self.calls = []

    def get_profile(self, brand_key):
        self.calls.append(brand_key)
        if self.error is not None:
            raise self.error
        return self.profile


class FakeScorer:
    def __init__(self, scored):
        self.scored = scored

    def score_listing(self, profile, listing):
        return dict(self.scored)

    def keyword_clusters(self, profile):
        return ["head-term"], ["body-term"], ["bad-term"]


def test_tools_registry_exports_track_keywords():
    assert set(TOOLS) == {"track_keywords"}
    assert TOOLS["track_keywords"] is track_keywords


def test_track_keywords_scores_real_coverage():
    result = track_keywords(LISTING, profile=PROFILE)

    assert result["ok"] is True
    assert result["tool"] == "track_keywords"
    data = result["data"]
    # Two head terms (3.0 each) matched, plus "ceremonial" (body, 1.5):
    # 7.5 of 9 weighted points -> 83%.
    assert data["coverage_pct"] == 83
    assert data["head_total"] == 2
    assert data["body_total"] == 2
    assert data["matched_count"] == 3
    assert data["missing"] == [{"term": "stone milled", "section": "body"}]
    assert data["clusters"]["head"] == ["matcha", "green tea"]
    assert data["clusters"]["negative"] == ["cheap", "detox"]
    # The honesty caveat travels with the score.
    assert any("not a rank" in c for c in data["caveats"])
    json.dumps(result)


def test_track_keywords_reports_the_gaps_and_where_terms_were_found():
    listing = {"title": "Northstar Matcha Powder", "bullets": [], "description": ""}

    result = track_keywords(listing, profile=PROFILE)

    data = result["data"]
    assert data["coverage_pct"] == 33  # one head term of nine weighted points
    assert data["matched"][0]["where"] == "title"
    gaps = set(data["gaps"])
    assert {"green tea", "stone milled", "ceremonial"} <= gaps


def test_track_keywords_uses_an_injected_profile_store():
    store = FakeStore(profile=PROFILE)

    result = track_keywords(LISTING, brand_key="northstar", profile_store=store)

    assert result["ok"] is True
    assert store.calls == ["northstar"]
    assert result["data"]["brand_key"] == "northstar"


def test_track_keywords_without_a_profile_is_a_business_failure():
    result = track_keywords(LISTING)

    assert result["ok"] is False
    assert result["tool"] == "track_keywords"
    assert "no brand SEO profile supplied" in result["reason"]


def test_track_keywords_profile_with_no_clusters_is_a_business_failure():
    result = track_keywords(LISTING, profile={"name": "No clusters here"})

    assert result["ok"] is False
    assert "no keyword clusters" in result["reason"]


def test_track_keywords_empty_listing_is_a_business_failure():
    result = track_keywords(
        {"title": "", "bullets": [], "description": ""}, profile=PROFILE
    )

    assert result["ok"] is False
    assert result["reason"] == "the listing has no copy to score"


def test_track_keywords_store_error_is_reported_not_raised():
    store = FakeStore(error=RuntimeError("profile table is gone"))

    result = track_keywords(LISTING, brand_key="northstar", profile_store=store)

    assert result["ok"] is False
    assert result["reason"].startswith("profile lookup failed: RuntimeError")


def test_track_keywords_scorer_is_injectable():
    scorer = FakeScorer({
        "score": 42,
        "matched": [{"term": "head-term", "section": "head", "where": "title"}],
        "missing": [{"term": "body-term", "section": "body"}],
        "head_total": 1,
        "body_total": 1,
        "matched_count": 1,
        "violations": ["cheap"],
        "competitor_mentions": ["Jade Leaf"],
        "caveats": ["stub scorer"],
    })

    result = track_keywords(LISTING, profile=PROFILE, scorer=scorer)

    assert result["ok"] is True
    assert result["data"]["coverage_pct"] == 42
    assert result["data"]["gaps"] == ["body-term"]
    assert result["data"]["violations"] == ["cheap"]
    assert result["data"]["competitor_mentions"] == ["Jade Leaf"]
    assert result["data"]["clusters"]["head"] == ["head-term"]


def test_track_keywords_programmer_errors_raise():
    with pytest.raises(TypeError):
        track_keywords("a listing")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        track_keywords(LISTING, profile=["matcha"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        track_keywords(LISTING, brand_key=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        track_keywords({"title": "x", "bullets": {"a": 1}})  # type: ignore[dict-item]


def test_default_scorer_is_the_real_seo_score_module():
    import seo_score

    assert kw._default_scorer() is seo_score
    assert track_keywords.__defaults__[-1] is None
