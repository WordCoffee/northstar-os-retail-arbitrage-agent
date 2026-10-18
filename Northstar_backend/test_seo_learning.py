"""Profile learning from imported measurement tests (V3 S7 §5.4).

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
import seo_learn  # noqa: E402
import seo_router  # noqa: E402
import seo_schema  # noqa: E402

SQP_SQL = """
CREATE TABLE IF NOT EXISTS search_query_performance (
    id TEXT PRIMARY KEY, query TEXT NOT NULL, asin TEXT,
    date_start TEXT, date_end TEXT,
    impressions INTEGER, clicks INTEGER, cart_adds INTEGER, purchases INTEGER,
    impression_share REAL, click_share REAL, cart_share REAL, purchase_share REAL,
    search_frequency_rank INTEGER, recorded_at TEXT DEFAULT (datetime('now'))
);
"""


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(seo_schema.SEO_TABLES_SQL)
        self.conn.executescript(SQP_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.seo = data_layer.SeoContainer(self.layer)

    def add_sqp(self, query, asin, impressions=0, clicks=0, purchases=0, sfr=None):
        self.layer.execute(
            "INSERT INTO search_query_performance "
            "(id, query, asin, impressions, clicks, purchases, search_frequency_rank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{asin}:{query}", query, asin, impressions, clicks, purchases, sfr))
        self.layer.commit()


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


PROFILE = {"keyword_clusters": {"head": ["turmeric powder"], "negative": ["free"]}}


# ── Pure proposal engine ────────────────────────────────────────────────────

def test_proposals_exclude_terms_already_in_profile():
    rows = [{"query": "turmeric powder", "impressions": 900, "search_frequency_rank": 1},
            {"query": "organic turmeric capsules", "impressions": 500, "search_frequency_rank": 2}]
    out = seo_learn.propose_from_sqp(PROFILE, rows)
    assert [p["term"] for p in out["proposals"]] == ["organic turmeric capsules"]


def test_proposals_rank_by_search_frequency_then_impressions():
    rows = [
        {"query": "golden milk", "impressions": 10, "search_frequency_rank": 5},
        {"query": "curcumin pills", "impressions": 800, "search_frequency_rank": 2},
        {"query": "anti inflammatory tea", "impressions": 200, "search_frequency_rank": 5},
    ]
    out = seo_learn.propose_from_sqp(PROFILE, rows)
    assert [p["term"] for p in out["proposals"]] == [
        "curcumin pills", "anti inflammatory tea", "golden milk"]


def test_proposals_aggregate_duplicate_queries():
    rows = [{"query": "golden milk", "impressions": 100, "clicks": 5},
            {"query": "Golden Milk", "impressions": 300, "clicks": 7}]
    out = seo_learn.propose_from_sqp(PROFILE, rows)
    assert len(out["proposals"]) == 1
    assert out["proposals"][0]["impressions"] == 400
    assert out["proposals"][0]["clicks"] == 12


def test_proposals_are_honest_with_no_rows():
    out = seo_learn.propose_from_sqp(PROFILE, [])
    assert out["proposals"] == []
    assert any("No SQP rows" in c for c in out["caveats"])
    assert any("No rank" in c for c in out["caveats"])


def test_proposals_min_impressions_filter():
    rows = [{"query": "tiny", "impressions": 1}, {"query": "big", "impressions": 100}]
    out = seo_learn.propose_from_sqp(PROFILE, rows, min_impressions=10)
    assert [p["term"] for p in out["proposals"]] == ["big"]


# ── SQP read store scope ────────────────────────────────────────────────────

def test_sqp_rows_are_scoped_by_asin(db):
    db.add_sqp("golden milk", "B001", impressions=100)
    db.add_sqp("curcumin pills", "B002", impressions=50)
    rows = db.seo.sqp.rows(asins=["B001"])
    assert [r["query"] for r in rows] == ["golden milk"]


# ── The seo_propose tool ────────────────────────────────────────────────────

def _ctx(db):
    return {"db": db, "account_id": "acct-1"}


def test_seo_propose_returns_candidates(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    db.add_sqp("golden milk", "B001", impressions=300, sfr=4)
    db.add_sqp("turmeric powder", "B001", impressions=900, sfr=1)
    out = chat_tools.run_tool("seo_propose", {"brand_key": "mogra", "asin": "B001"}, _ctx(db))
    assert out["ok"] is True
    terms = [p["term"] for p in out["data"]["proposals"]]
    assert terms == ["golden milk"]        # profile term excluded
    assert out["data"]["card"]["title"] == "SEO proposals"


def test_seo_propose_needs_an_asin(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    out = chat_tools.run_tool("seo_propose", {"brand_key": "mogra"}, _ctx(db))
    assert out["ok"] is False and "ASIN" in out["summary"]


def test_seo_propose_honest_without_profile(db):
    out = chat_tools.run_tool("seo_propose", {"asin": "B001"}, _ctx(db))
    assert out["ok"] is False and "No brand SEO profile" in out["summary"]


def test_seo_propose_registered_and_in_grow_focus():
    import shell_focus
    assert "seo_propose" in chat_tools.TOOLS
    assert "seo_propose" in shell_focus.tools_for_focus("grow")


# ── Router proposals endpoint (read-only) ───────────────────────────────────

def test_router_proposals_are_read_only(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    db.add_sqp("golden milk", "B001", impressions=300, sfr=4)
    before = db.seo.profiles.get_by_brand_key("acct-1", "mogra")["current_version"]
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        out = seo_router.list_proposals(brand_key="mogra", asin="B001", acct="acct-1")
    after = db.seo.profiles.get_by_brand_key("acct-1", "mogra")["current_version"]
    assert [p["term"] for p in out["proposals"]] == ["golden milk"]
    assert before == after == 1            # nothing was written


def test_router_proposals_requires_asin(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra", "body": PROFILE})
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            seo_router.list_proposals(brand_key="mogra", asin=None, acct="acct-1")
    assert "400" in str(getattr(ei.value, "status_code", "")) + str(ei.value)
