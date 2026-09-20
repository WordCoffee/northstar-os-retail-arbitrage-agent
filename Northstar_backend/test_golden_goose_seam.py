"""B2/C5 tests — Golden Goose seam (bff/v1 envelope, entitlement, dry-run).

Uses the finder's real contract via /api/golden-goose/* with a fixture report
only (no provider calls, no network). Aligned to docs/contracts/BFF_CONTRACT_v1.md
and GOLDEN_GOOSE_SEAM_v1.md.

Run: python -m pytest Northstar_backend/test_golden_goose_seam.py -q
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
import agents.golden_goose_finder.main as gg_main  # noqa: E402
import auth  # noqa: E402

FIXTURE = _BACKEND / "fixtures" / "golden_goose" / "goose_scan_fixture_00000000_000000.json"

SPA_CONSUMED_KEYS = [
    "rank", "amazon_asin", "brand", "wholesale_title", "net_profit_per_unit",
    "roi_per_unit", "composite_score", "tier", "source_store", "pack_count",
    "monthly_sales_estimate", "fba_sellers", "price_gap_score",
    "ad_feasibility_score", "opportunity_tags",
]


def token_for(plan: str = "foundation", role: str = "owner") -> str:
    return auth.create_access_token("acct1", "o@x.com", plan, role=role)


@pytest.fixture
def client(tmp_path, monkeypatch):
    report_dir = tmp_path / "golden-goose-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, report_dir / "goose_scan_fixture_00000000_000000.json")
    monkeypatch.setattr(gg_main, "REPORT_DIR", report_dir)
    return TestClient(app)


def _data(resp):
    return resp.json()["data"]


def test_opportunities_endpoint_returns_envelope_and_contract(client):
    resp = client.get("/api/golden-goose/opportunities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1"
    assert body["status"] == "ok"
    assert body["error"] is None
    assert body["request_id"].startswith("req_")
    items = _data(resp)["items"]
    assert isinstance(items, list) and len(items) == 3
    assert _data(resp)["summary"]["high_tier_count"] == 1


def test_opportunity_shape_covers_spa_seam_keys(client):
    for o in _data(client.get("/api/golden-goose/opportunities"))["items"]:
        for key in SPA_CONSUMED_KEYS:
            assert key in o, "opportunity missing SPA-consumed key: %s" % key


def test_tiers_present_in_fixture(client):
    opps = _data(client.get("/api/golden-goose/opportunities"))["items"]
    assert {o["tier"] for o in opps} == {"HIGH", "MEDIUM", "LOW"}
    assert opps[0]["tier"] == "HIGH"


def test_opportunities_filter_by_tier(client):
    data = _data(client.get("/api/golden-goose/opportunities", params={"tier": "HIGH"}))
    assert len(data["items"]) == 1 and data["items"][0]["tier"] == "HIGH"


def test_report_meta_is_leak_free(client):
    """report_path / scan_manifest_path must NOT be served (B1 no-leak)."""
    data = _data(client.get("/api/golden-goose/opportunities"))
    meta = data.get("report_meta", {})
    assert "report_path" not in meta
    assert "scan_manifest_path" not in meta
    text = json.dumps(data).lower()
    assert "report_path" not in text
    for tok in ("brightdata", "chocodata", "easyparser", "openwebninja"):
        assert tok not in text


def test_response_carries_opaque_job(client):
    data = _data(client.get("/api/golden-goose/opportunities"))
    job = data.get("job", {})
    assert job.get("job_id", "").startswith("job_")
    assert job.get("state") == "done"
    assert job.get("result_ref", "").startswith("res_")
    assert "scan_id" not in job
    assert "scan_id" not in json.dumps(job)


def test_scan_endpoint_stays_403_gated(client, monkeypatch):
    monkeypatch.delenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", raising=False)
    resp = client.post("/api/golden-goose/scan")
    assert resp.status_code == 403
    assert "approval" in resp.json()["detail"].lower()


def test_dry_run_endpoint_envelope_and_estimates(client):
    resp = client.get("/api/golden-goose/dry-run", params={"categories": "vitamins_supplements"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["contract"] == "bff/v1"
    est = _data(resp)["estimate"]
    assert est["dry_run"] is True
    assert est["estimated_credits"] > 0
    assert est["estimated_time_seconds"] >= 0
    assert est["estimated_opportunities"] > 0
    assert "no provider call" in est["note"]
    # dry-run must never WRITE a new report (fixture set unchanged)
    names_before = {p.name for p in gg_main.REPORT_DIR.glob("goose_scan_*.json")}
    _data(client.get("/api/golden-goose/dry-run"))
    names_after = {p.name for p in gg_main.REPORT_DIR.glob("goose_scan_*.json")}
    assert names_after == names_before


def test_entitlements_demo_foundation_has_none(client):
    body = _data(client.get("/api/golden-goose/entitlements"))
    assert body["plan"] == "foundation"
    assert body["categories"] == [] and body["exports"] == []


def test_entitlements_autothink_unlocks_all(client):
    token = token_for("autothink")
    body = _data(client.get("/api/golden-goose/entitlements",
                            headers={"Authorization": "Bearer " + token}))
    assert body["plan"] == "autothink"
    assert "pet" in body["categories"]
    assert "export_manifest_json" in body["exports"]


def test_category_filter_gated_by_plan(client):
    # foundation cannot filter a category not entitled -> 403 entitlement_required
    resp = client.get("/api/golden-goose/opportunities", params={"category": "pet"})
    assert resp.status_code == 403
    assert resp.json()["status"] == "error"
    assert resp.json()["error"]["code"] == "entitlement_required"

    # autothink can
    token = token_for("autothink")
    resp = client.get("/api/golden-goose/opportunities", params={"category": "pet"},
                      headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 200

    # scout can filter an entitled category
    token = token_for("scout")
    resp = client.get("/api/golden-goose/opportunities", params={"category": "vitamins_supplements"},
                      headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 200


def test_categories_and_health_are_envelopes(client):
    for path in ("/api/golden-goose/categories", "/api/golden-goose/health"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.json()["contract"] == "bff/v1"
        assert resp.json()["status"] == "ok"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))