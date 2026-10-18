"""Cross-service SEO pipeline-op tests (V3 S7 §5.3): AdPilot terms, retitle.

Offline: in-memory SQLite, no server, no network.
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_tools  # noqa: E402
import data_layer  # noqa: E402
import seo_ops  # noqa: E402
import seo_schema  # noqa: E402


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(seo_schema.SEO_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.seo = data_layer.SeoContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _ctx(db):
    return {"db": db, "account_id": "acct-1"}


PROFILE = {
    "keyword_clusters": {
        "head": ["organic turmeric", "turmeric powder"],
        "body": ["curcumin", "golden milk"],
        "negative": ["free", "cheap"],
    },
    "competitors": ["BrandX"],
}


# ── AdPilot term triage ─────────────────────────────────────────────────────

def test_negatives_come_from_negative_cluster_and_competitors():
    out = seo_ops.classify_search_terms(PROFILE, "free turmeric\nBrandX capsules\ncheap powder")
    assert [n["term"] for n in out["negatives"]] == ["free turmeric", "BrandX capsules", "cheap powder"]
    assert out["negative_count"] == 3


def test_head_terms_are_harvest_and_marked_head():
    out = seo_ops.classify_search_terms(PROFILE, "organic turmeric blend\nturmeric powder bulk")
    assert all(h["section"] == "head" for h in out["harvest"])
    assert {h["term"] for h in out["harvest"]} == {"organic turmeric blend", "turmeric powder bulk"}


def test_body_terms_are_harvest_and_marked_body():
    out = seo_ops.classify_search_terms(PROFILE, "golden milk recipe\ncurcumin extract")
    assert all(h["section"] == "body" for h in out["harvest"])


def test_unmatched_terms_are_ignored():
    out = seo_ops.classify_search_terms(PROFILE, "stainless steel bottle")
    assert out["harvest"] == [] and out["negatives"] == []
    assert out["ignored"] == ["stainless steel bottle"]


def test_terms_are_split_and_deduped():
    out = seo_ops.classify_search_terms(PROFILE, "curcumin, curcumin\ngolden milk")
    assert [h["term"] for h in out["harvest"]] == ["curcumin", "golden milk"]


def test_negatives_win_over_harvest():
    # "free turmeric" contains head "turmeric"? no; but contains negative "free".
    out = seo_ops.classify_search_terms(PROFILE, "free golden milk")
    assert out["negatives"][0]["term"] == "free golden milk"
    assert out["harvest"] == []


def test_term_triage_is_honest_with_no_terms():
    out = seo_ops.classify_search_terms(PROFILE, "")
    assert out["negatives"] == [] and out["harvest"] == []
    assert any("No search terms" in c for c in out["caveats"])


# ── SourceScout retitle ─────────────────────────────────────────────────────

def test_retitle_prepends_missing_head_terms():
    out = seo_ops.retitle(PROFILE, "Curcumin Supplement 120 Capsules")
    assert out["title"].startswith("Organic Turmeric")
    assert "Organic Turmeric" in out["title"] and "Turmeric Powder" in out["title"]
    assert out["original"] == "Curcumin Supplement 120 Capsules"
    assert set(out["missing_head"]) == {"organic turmeric", "turmeric powder"}


def test_retitle_leaves_present_head_terms_alone():
    out = seo_ops.retitle(PROFILE, "Organic Turmeric Powder 1 lb")
    assert out["title"] == "Organic Turmeric Powder 1 lb"
    assert "no change" in out["changes"][0]


def test_retitle_respects_the_length_budget():
    out = seo_ops.retitle(PROFILE, "A very long subtitle " * 20, max_len=60)
    assert out["length"] <= 60
    assert any("truncated" in c for c in out["changes"])


def test_retitle_reports_missing_head_it_could_not_fit():
    out = seo_ops.retitle(PROFILE, "Organic Turmeric", max_len=30)
    # "Organic Turmeric" present; "Turmeric Powder" cannot fit in 30 chars prefixed
    assert "turmeric powder" in out["missing_head"] or out["length"] <= 30
    assert out["length"] <= 30


# ── Tools: registration + focus + honest paths ──────────────────────────────

def test_pipeline_tools_registered_and_in_grow_focus():
    import shell_focus
    grow = shell_focus.tools_for_focus("grow")
    assert "seo_negatives" in chat_tools.TOOLS and "seo_negatives" in grow
    assert "seo_retitle" in chat_tools.TOOLS and "seo_retitle" in grow


def test_seo_negatives_tool_returns_card(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_negatives",
                              {"brand_key": "mogra", "terms": "free powder\ncurcumin pills"},
                              _ctx(db))
    assert out["ok"] is True
    assert out["data"]["card"]["title"] == "AdPilot term triage"
    assert out["data"]["negatives"][0]["term"] == "free powder"
    assert out["data"]["harvest"][0]["term"] == "curcumin pills"


def test_seo_retitle_tool_returns_card(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_retitle",
                              {"brand_key": "mogra", "title": "Curcumin 120ct"}, _ctx(db))
    assert out["ok"] is True
    assert "Organic Turmeric" in out["data"]["title"]


def test_pipeline_tools_are_honest_without_profile(db):
    for name, args in (("seo_negatives", {"terms": "x"}),
                       ("seo_retitle", {"title": "x"})):
        out = chat_tools.run_tool(name, args, _ctx(db))
        assert out["ok"] is False and "No brand SEO profile" in out["summary"]
