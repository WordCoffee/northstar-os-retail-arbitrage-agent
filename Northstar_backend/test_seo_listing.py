"""Listing revisions + profile-aware SEO scoring tests (V3 S7 §5.2/§5.3).

Offline: in-memory SQLite, no server, no network.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_tools  # noqa: E402
import data_layer  # noqa: E402
import seo_router  # noqa: E402
import seo_schema  # noqa: E402
import seo_score  # noqa: E402


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


PROFILE = {
    "keyword_clusters": {
        "head": ["turmeric powder", "organic turmeric"],
        "body": ["curcumin", "anti-inflammatory", "golden milk"],
        "negative": ["miracle cure"],
    },
    "competitors": ["BrandX"],
}


# ── Scoring (pure) ──────────────────────────────────────────────────────────

def test_score_full_coverage_is_100():
    listing = {"title": "Organic Turmeric Powder",
               "bullets": ["curcumin anti-inflammatory", "great for golden milk"]}
    out = seo_score.score_listing(PROFILE, listing)
    assert out["score"] == 100
    assert out["missing"] == []


def test_score_partial_coverage_and_missing():
    out = seo_score.score_listing(PROFILE, {"title": "Organic Turmeric Powder"})
    assert 0 < out["score"] < 100
    assert {m["term"] for m in out["missing"]} >= {"curcumin", "anti-inflammatory", "golden milk"}
    assert all("Deterministic" in c for c in out["caveats"][:1])


def test_score_reports_violations_and_competitors():
    out = seo_score.score_listing(PROFILE, {"title": "A miracle cure", "bullets": ["beats BrandX"]})
    assert out["violations"] == ["miracle cure"]
    assert out["competitor_mentions"] == ["BrandX"]


def test_score_is_none_without_profile_keywords():
    out = seo_score.score_listing({}, {"title": "anything"})
    assert out["score"] is None
    assert "No keyword clusters" in out["caveats"][1]


def test_score_flags_where_terms_land():
    out = seo_score.score_listing(PROFILE, {"title": "organic turmeric powder", "backend_terms": "curcumin"})
    head = next(m for m in out["matched"] if m["term"] == "turmeric powder")
    assert "title" in head["where"]


# ── Revision store ──────────────────────────────────────────────────────────

def test_revisions_are_monotonic_and_latest_wins(db):
    k = "b0001"
    r1 = db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": k, "title": "v1"})
    r2 = db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": k, "title": "v2"})
    assert (r1["revision"], r2["revision"]) == (1, 2)
    assert db.seo.revisions.get_latest("acct-1", k)["title"] == "v2"
    assert db.seo.revisions.get("acct-1", k, 1)["title"] == "v1"  # v1 unchanged


def test_revision_bullets_roundtrip_as_json(db):
    r = db.seo.revisions.add_revision({
        "account_id": "acct-1", "listing_key": "x", "bullets": ["a", "b"]})
    assert r["bullets"] == ["a", "b"]


def test_list_revisions_newest_first_and_latest_per_key(db):
    for t in ("v1", "v2", "v3"):
        db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": "k1", "title": t})
    db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": "k2", "title": "only"})
    assert [r["title"] for r in db.seo.revisions.list_revisions("acct-1", "k1")] == ["v3", "v2", "v1"]
    latest = db.seo.revisions.list_latest("acct-1")
    assert sorted(r["listing_key"] for r in latest) == ["k1", "k2"]
    assert next(r for r in latest if r["listing_key"] == "k1")["title"] == "v3"


def test_revision_requires_listing_key(db):
    with pytest.raises(ValueError):
        db.seo.revisions.add_revision({"account_id": "acct-1", "title": "no key"})


def test_revisions_are_tenant_scoped(db):
    db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": "k", "title": "mine"})
    assert db.seo.revisions.get_latest("acct-2", "k") is None
    assert db.seo.revisions.list_revisions("acct-2", "k") == []


# ── The seo_check tool ──────────────────────────────────────────────────────

def _ctx(db):
    return {"db": db, "account_id": "acct-1"}


def test_seo_check_scores_latest_revision(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    db.seo.revisions.add_revision({"account_id": "acct-1", "listing_key": "b1", "title": "stale"})
    db.seo.revisions.add_revision({
        "account_id": "acct-1", "listing_key": "b1",
        "title": "Organic Turmeric Powder", "bullets": ["curcumin", "golden milk", "anti-inflammatory"]})
    out = chat_tools.run_tool("seo_check", {"brand_key": "mogra", "listing_key": "b1"}, _ctx(db))
    assert out["ok"] is True
    assert out["data"]["score"] == 100
    assert out["data"]["card"]["title"] == "SEO check"


def test_seo_check_scores_inline_copy(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_check", {"title": "Organic Turmeric Powder"}, _ctx(db))
    assert out["ok"] is True
    assert 0 < out["data"]["score"] < 100


def test_seo_check_honest_when_no_profile(db):
    out = chat_tools.run_tool("seo_check", {"listing_key": "b1"}, _ctx(db))
    assert out["ok"] is False and "No brand SEO profile" in out["summary"]


def test_seo_check_honest_when_no_revision(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_check", {"listing_key": "ghost"}, _ctx(db))
    assert out["ok"] is False and "No listing revisions" in out["summary"]


def test_seo_check_requires_a_listing(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_check", {}, _ctx(db))
    assert out["ok"] is False and "listing" in out["summary"].lower()


def test_seo_check_registered_and_in_grow_focus():
    import shell_focus
    assert "seo_check" in chat_tools.TOOLS
    assert "seo_check" in shell_focus.tools_for_focus("grow")


# ── Router (revisions are usable through the API) ───────────────────────────

def test_router_appends_and_reads_revisions(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        r1 = seo_router.add_listing_revision(
            "b1", seo_router.ListingRevisionIn(title="v1"), acct="acct-1")
        r2 = seo_router.add_listing_revision(
            "b1", seo_router.ListingRevisionIn(title="v2", bullets="one\ntwo"),
            acct="acct-1")
        latest = seo_router.get_latest_listing("b1", acct="acct-1")
        revs = seo_router.list_listing_revisions("b1", acct="acct-1")
        one = seo_router.get_listing_revision("b1", 1, acct="acct-1")
    assert (r1["revision"], r2["revision"]) == (1, 2)
    assert r2["bullets"] == ["one", "two"]
    assert latest["revision"] == 2
    assert [v["revision"] for v in revs["revisions"]] == [2, 1]
    assert one["title"] == "v1"


def test_router_list_listings_returns_latest_per_key(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        seo_router.add_listing_revision("k1", seo_router.ListingRevisionIn(title="a"), acct="acct-1")
        seo_router.add_listing_revision("k1", seo_router.ListingRevisionIn(title="b"), acct="acct-1")
        seo_router.add_listing_revision("k2", seo_router.ListingRevisionIn(title="c"), acct="acct-1")
        out = seo_router.list_listings(acct="acct-1")
    rows = {r["listing_key"]: r["title"] for r in out["listings"]}
    assert rows == {"k1": "b", "k2": "c"}


def test_router_missing_listing_is_404(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            seo_router.get_latest_listing("ghost", acct="acct-1")
    assert "404" in str(getattr(ei.value, "status_code", "")) + str(ei.value)

