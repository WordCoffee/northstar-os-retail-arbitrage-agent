"""Brand SEO Profile tests (V3 S7 — the cross-service SEO engine foundation).

Covers the canonical, versioned profile: creation, immutable append-only
versions, tenant scoping, body validation, and the router surface. Offline:
in-memory SQLite, no server, no network.
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

import data_layer  # noqa: E402
import seo_profile  # noqa: E402
import seo_router  # noqa: E402
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


BODY_V1 = {
    "entities": ["MOGRA", "Mogra Organics"],
    "keyword_clusters": {"head": ["turmeric powder"], "negative": ["free"]},
    "voice_rules": "Warm, provenance-first.",
    "prohibited_claims": ["cures disease"],
    "competitors": ["BrandX"],
    "provenance": {"keywords": "operator", "competitors": "inferred"},
}


# ── Validation ──────────────────────────────────────────────────────────────

def test_body_must_be_object():
    ok, err = seo_profile.normalize_body(["not", "an", "object"])
    assert ok is False and "JSON object" in err


def test_unknown_keys_are_preserved_not_dropped():
    ok, norm = seo_profile.normalize_body({"entities": [], "future_field": {"a": 1}})
    assert ok is True and norm["future_field"] == {"a": 1}


def test_wrong_section_shape_rejected():
    ok, err = seo_profile.normalize_body({"keyword_clusters": "oops"})
    assert ok is False and "keyword_clusters" in err


# ── Store ───────────────────────────────────────────────────────────────────

def test_create_profile_starts_at_version_1(db):
    p = db.seo.profiles.create_profile({
        "account_id": "acct-1", "brand_key": "MOGRA", "name": "Mogra Organics",
        "body": BODY_V1, "note": "initial"})
    assert p["brand_key"] == "mogra"       # normalized to a slug
    assert p["current_version"] == 1
    assert p["version_count"] == 1
    assert p["body"]["entities"] == ["MOGRA", "Mogra Organics"]


def test_duplicate_brand_key_rejected(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    with pytest.raises(ValueError):
        db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "MOGRA"})


def test_versions_are_append_only_and_immutable(db):
    p = db.seo.profiles.create_profile({
        "account_id": "acct-1", "brand_key": "mogra", "body": BODY_V1})
    pid = p["id"]
    p2 = db.seo.profiles.add_version(pid, "acct-1",
                                     {"keyword_clusters": {"head": ["turmeric"]},
                                      "note": "tightened"})
    assert p2["current_version"] == 2
    assert p2["version_count"] == 2
    # v1 is untouched by the new version.
    v1 = db.seo.profiles.get_version(pid, 1, account_id="acct-1")
    assert v1["body_json"]["entities"] == ["MOGRA", "Mogra Organics"]
    # current body is v2.
    assert p2["body"]["keyword_clusters"]["head"] == ["turmeric"]


def test_add_version_validates_body(db):
    p = db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    with pytest.raises(ValueError):
        db.seo.profiles.add_version(p["id"], "acct-1", {"competitors": "not-a-list"})


def test_list_versions_newest_first(db):
    p = db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    db.seo.profiles.add_version(p["id"], "acct-1", {"note": "v2"})
    versions = db.seo.profiles.list_versions(p["id"], account_id="acct-1")
    assert [v["version"] for v in versions] == [2, 1]


# ── Tenant scoping ──────────────────────────────────────────────────────────

def test_profile_is_tenant_scoped(db):
    p = db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    assert db.seo.profiles.get_profile(p["id"], account_id="acct-2") is None
    assert db.seo.profiles.add_version(p["id"], "acct-2", {}) is None
    assert db.seo.profiles.get_version(p["id"], 1, account_id="acct-2") is None


def test_list_profiles_is_scoped(db):
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    db.seo.profiles.create_profile({"account_id": "acct-2", "brand_key": "other"})
    assert [p["brand_key"] for p in db.seo.profiles.list_profiles("acct-1")] == ["mogra"]


# ── Router ──────────────────────────────────────────────────────────────────

def test_router_create_get_version(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        created = seo_router.create_profile(
            seo_router.ProfileIn(brand_key="mogra", name="Mogra", body=BODY_V1),
            acct="acct-1")
        got = seo_router.get_profile(created["id"], acct="acct-1")
        updated = seo_router.add_version(
            created["id"], seo_router.VersionIn(body={"entities": ["MOGRA"]}, note="trim"),
            acct="acct-1")
        versions = seo_router.list_versions(created["id"], acct="acct-1")
    assert got["current_version"] == 1
    assert updated["current_version"] == 2
    assert [v["version"] for v in versions["versions"]] == [2, 1]


def test_router_unknown_profile_is_404(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            seo_router.get_profile("nope", acct="acct-1")
    assert "404" in str(getattr(ei.value, "status_code", "")) + str(ei.value)


def test_router_duplicate_is_400(db):
    with mock.patch.object(seo_router, "get_northstar_db", return_value=db):
        seo_router.create_profile(seo_router.ProfileIn(brand_key="mogra"), acct="acct-1")
        with pytest.raises(Exception) as ei:
            seo_router.create_profile(seo_router.ProfileIn(brand_key="MOGRA"), acct="acct-1")
    assert "400" in str(getattr(ei.value, "status_code", "")) + str(ei.value)


# ── Chat tool hook (reachable from the Simple shell) ────────────────────────

def test_seo_profile_tool_renders_card(db):
    import chat_tools
    db.seo.profiles.create_profile({
        "account_id": "acct-1", "brand_key": "mogra",
        "body": {"keyword_clusters": {"head": ["turmeric powder"]}, "competitors": ["BrandX"]}})
    out = chat_tools.run_tool("seo_profile", {"brand_key": "mogra"},
                              {"db": db, "account_id": "acct-1"})
    assert out["ok"] is True
    card = out["data"]["card"]
    assert card["title"] == "Brand SEO profile"
    labels = [r["label"] for r in card["rows"]]
    assert "head terms" in labels and "competitors" in labels


def test_seo_profile_tool_lists_when_no_key(db):
    import chat_tools
    db.seo.profiles.create_profile({"account_id": "acct-1", "brand_key": "mogra"})
    out = chat_tools.run_tool("seo_profile", {}, {"db": db, "account_id": "acct-1"})
    assert out["ok"] is True
    assert out["data"]["profiles"][0]["brand_key"] == "mogra"


def test_seo_profile_tool_honest_without_store():
    import chat_tools
    out = chat_tools.run_tool("seo_profile", {}, {"db": None, "account_id": "acct-1"})
    assert out["ok"] is False
    assert "unavailable" in out["summary"]


def test_seo_profile_tool_registered_in_grow():
    import chat_tools
    import shell_focus
    assert "seo_profile" in chat_tools.TOOLS
    assert "seo_profile" in shell_focus.tools_for_focus("grow")

