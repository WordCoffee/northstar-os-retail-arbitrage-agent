"""Tests for the remaining creative-adjacent rooms: Listing Guardian (local
listing-health audit) and Competitor Monitor (local watch desk + deltas).

Offline, deterministic, isolated index.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative import competitor_monitor, listing_guardian  # noqa: E402
from creative.service_routes import competitor_router, guardian_router  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    monkeypatch.setenv("NORTHSTAR_COMPETITORS_INDEX", str(tmp_path / "competitors.json"))
    monkeypatch.delenv("NORTHSTAR_MEDIA_DIR", raising=False)
    return tmp_path


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(guardian_router)
    app.include_router(competitor_router)
    return TestClient(app)


GOOD = {
    "product": {"brand": "Mogra Organics", "title": "Organic Turmeric Powder"},
    "title": "Mogra Organics Organic Turmeric Powder 5 lb | Golden & Earthy",
    "bullets": [
        "Premium organic turmeric powder sourced from single-origin farms",
        "Earthy, golden flavor that brightens curries, soups and smoothies",
        "Resealable 5 lb pouch keeps the powder fresh for months",
        "No fillers, no additives, just pure ground turmeric",
    ],
    "description": "Mogra Organics Organic Turmeric Powder is a golden, earthy spice for daily cooking.",
    "keywords": ["organic turmeric powder", "golden spice"],
}


# ---------------------------------------------------------------------------
# Listing Guardian
# ---------------------------------------------------------------------------

def test_audit_healthy_listing():
    r = listing_guardian.audit(GOOD)
    assert r["ok"] is True
    assert r["status"] == "healthy"
    assert r["passed"] == r["total"]
    assert all(c["ok"] for c in r["checks"])
    assert "no live Amazon" in r["basis"]


def test_audit_flags_weak_listing():
    weak = {"product": {"brand": "Mogra"}, "title": "Short",
            "bullets": [], "description": "", "keywords": []}
    r = listing_guardian.audit(weak)
    assert r["status"] in ("attention", "needs_work")
    failed = {c["check"] for c in r["checks"] if not c["ok"]}
    assert "bullet_count" in failed and "description_present" in failed


def test_audit_flags_compliance_violation():
    bad = {**GOOD, "title": "USDA certified miracle turmeric that cures everything"}
    r = listing_guardian.audit(bad)
    assert r["compliance"]["ok"] is False
    assert any(c["check"] == "compliance" and not c["ok"] for c in r["checks"])


def test_audit_route(client):
    r = client.post("/api/listing-guardian/audit", json={"listing": GOOD})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Competitor Monitor
# ---------------------------------------------------------------------------

def test_watch_add_list_remove():
    e = competitor_monitor.add("Rival Turmeric", asin="B0RIVAL", url="https://x")
    assert e["id"].startswith("CM-")
    assert len(competitor_monitor.list_watch()) == 1
    assert competitor_monitor.remove(e["id"]) is True
    assert competitor_monitor.list_watch() == []


def test_snapshot_and_deltas():
    e = competitor_monitor.add("Rival")
    competitor_monitor.snapshot(e["id"], {"price": 24.99, "rank": 120, "in_stock": True})
    competitor_monitor.snapshot(e["id"], {"price": 21.99, "rank": 88, "in_stock": True})
    d = competitor_monitor.deltas(e["id"])
    assert d["count"] == 2
    fields = {c["field"]: c for c in d["changes"]}
    assert fields["price"]["delta"] == -3.0
    assert fields["rank"]["delta"] == -32


def test_deltas_need_two_snapshots():
    e = competitor_monitor.add("Rival")
    competitor_monitor.snapshot(e["id"], {"price": 10})
    d = competitor_monitor.deltas(e["id"])
    assert d["count"] == 0 and "two snapshots" in d["note"]


def test_overview_reports_change_counts():
    e = competitor_monitor.add("Rival")
    competitor_monitor.snapshot(e["id"], {"price": 10})
    competitor_monitor.snapshot(e["id"], {"price": 12})
    ov = competitor_monitor.overview()
    assert ov[0]["snapshots"] == 2 and ov[0]["changes"] == 1


def test_competitor_routes(client):
    c = client.post("/api/competitor-monitor/watchlist", json={"name": "Rival", "asin": "B1"})
    assert c.status_code == 200, c.text
    wid = c.json()["entry"]["id"]

    s = client.post(f"/api/competitor-monitor/watchlist/{wid}/snapshot", json={"price": 30, "rank": 50})
    assert s.status_code == 200 and s.json()["snapshot"]["price"] == 30
    client.post(f"/api/competitor-monitor/watchlist/{wid}/snapshot", json={"price": 27})

    d = client.get(f"/api/competitor-monitor/watchlist/{wid}/deltas")
    assert d.status_code == 200 and d.json()["count"] == 1
    assert "rank" in d.json()["not_reported"]

    lst = client.get("/api/competitor-monitor/watchlist")
    assert lst.status_code == 200 and lst.json()["overview"][0]["changes"] == 1

    assert client.delete(f"/api/competitor-monitor/watchlist/{wid}").json()["removed"] is True


def test_competitor_routes_validation(client):
    assert client.post("/api/competitor-monitor/watchlist", json={}).status_code == 400
    assert client.get("/api/competitor-monitor/watchlist/CM-NOPE/deltas").status_code == 404
    assert client.post("/api/competitor-monitor/watchlist/CM-NOPE/snapshot", json={"price": 1}).status_code == 404
