"""Phase A / A4 — data readiness runner tests (offline)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import readiness  # noqa: E402


def _stats(rows, fresh_rows=0):
    return {"live_rows": len(rows), "fresh_rows": fresh_rows, "pulls": len(rows), "rows": rows}


def _fresh_row(**over):
    base = {"asin": "B01", "title": "T", "amazon_price": 9.99,
            "fresh_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    base.update(over)
    return base


def test_load_requirements_has_services():
    reqs = readiness.load_requirements()
    assert "goldengoose" in reqs["services"]
    assert "amazon_search" in reqs["providers"]


def test_provider_key_presence(monkeypatch):
    monkeypatch.setenv("CHOCODATA_API_KEY", "x")
    monkeypatch.delenv("BRIGHTDATA_UNLOCKER_API_KEY", raising=False)
    pres = readiness.provider_key_presence("amazon_search")
    assert pres["chocodata"] is True
    assert pres["bright_data_web_unlocker"] is False


def test_check_service_no_data_required_is_ready():
    r = readiness.check_service("autothink", {"display": "AutothinK", "required_fields": []})
    assert r["ready"] is True and r["reason"] == "no_product_data_required"


def test_check_service_no_stock_fails():
    spec = {"display": "Prospector", "required_fields": ["asin", "title"], "min_freshness_hours": 24}
    r = readiness.check_service("sourcescout", spec, _stats([]))
    assert r["ready"] is False and r["reason"] == "no_stocked_live_rows"


def test_check_service_incomplete_coverage_fails():
    spec = {"display": "Golden Goose", "required_fields": ["asin", "title", "net_profit"], "min_freshness_hours": 24}
    rows = [_fresh_row(net_profit=None)]
    r = readiness.check_service("goldengoose", spec, _stats(rows))
    assert r["ready"] is False and r["reason"] == "field_coverage_incomplete"
    assert "net_profit" in r["missing_example"]


def test_check_service_stale_fails():
    spec = {"display": "Prospector", "required_fields": ["asin", "title"], "min_freshness_hours": 1}
    rows = [_fresh_row(fresh_until=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())]
    r = readiness.check_service("sourcescout", spec, _stats(rows))
    assert r["ready"] is False and r["reason"] == "stale_stock"


def test_check_service_ready_when_complete_and_fresh():
    spec = {"display": "Prospector", "required_fields": ["asin", "title", "amazon_price"], "min_freshness_hours": 24}
    r = readiness.check_service("sourcescout", spec, _stats([_fresh_row()], fresh_rows=1))
    assert r["ready"] is True and r["reason"] == "ok" and r["coverage"] == 1.0


def test_check_all_shape_offline():
    report = readiness.check_all(live=False)
    assert "ready" in report and "services" in report and "provider_keys" in report
    assert report["live_probe"] is False
    assert len(report["services"]) >= 8


def test_main_exit_code_matches_readiness(capsys):
    rc = readiness.main([])
    out = capsys.readouterr().out
    assert "READY:" in out
    assert rc in (0, 1)
