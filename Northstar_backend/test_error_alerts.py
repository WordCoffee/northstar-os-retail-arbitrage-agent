"""Phase F/S4 — error-rate alerting logic tests.

Pure + offline: no network, no alert delivery (channel wiring is
operator-side later, per MONITORING_SETUP.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from error_alerts import (  # noqa: E402
    ErrorRateTracker,
    ProviderErrorBudget,
    compose_alert,
)


def _feed(tracker, statuses, base=1_000_000.0):
    for i, s in enumerate(statuses):
        tracker.record(s, at=base + i)


def test_empty_tracker_no_breach():
    t = ErrorRateTracker(window_seconds=300)
    assert t.rate() is None and t.breached() is False
    assert t.summary()["total_requests"] == 0


def test_breach_above_threshold():
    t = ErrorRateTracker(window_seconds=300, min_requests=10)
    _feed(t, [200] * 10 + [500] * 10)   # 10/20 = 50% 5xx > 5%
    assert t.rate() == 0.5
    assert t.breached() is True


def test_no_breach_below_threshold():
    t = ErrorRateTracker(window_seconds=300, min_requests=10)
    _feed(t, [200] * 100 + [500] * 4)   # 4/104 ≈ 3.8% < 5%
    assert t.breached() is False


def test_min_requests_guard():
    t = ErrorRateTracker(window_seconds=300, min_requests=10)
    _feed(t, [500, 500])               # 100% 5xx but sample < min_requests
    assert t.breached() is False


def test_window_eviction_drops_old_samples():
    t = ErrorRateTracker(window_seconds=300, min_requests=5)
    _feed(t, [500] * 5, base=1_000_000.0)
    assert t.breached() is True
    # move far beyond window → old samples evicted
    _feed(t, [200], base=1_000_000.0 + 900.0)
    assert t.window()[0] == 1
    assert t.breached() is False


def test_alert_payload_no_network():
    t = ErrorRateTracker(window_seconds=300, min_requests=10)
    _feed(t, [500] * 5 + [200] * 5)
    p = compose_alert(t.summary())
    assert p["code"] == "error_rate_breached" and p["severity"] == "critical"
    assert p["channel"] is None                  # never delivered by code
    assert "5xx rate" in p["message"]


def test_alert_payload_ok():
    t = ErrorRateTracker(window_seconds=300, min_requests=10)
    _feed(t, [200] * 20)
    p = compose_alert(t.summary())
    assert p["code"] == "ok" and p["severity"] == "info"


def test_endpoint_returns_envelope():
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    resp = c.get("/api/monitoring/error-alerts")
    assert resp.status_code == 200
    b = resp.json()
    assert b["contract"] == "bff/v1" and b["status"] == "ok"
    assert "summary" in b["data"] and "alert" in b["data"]


# ---------------------------------------------------------------------------
# FIXES_50 #26b — per-provider error budget (Phase G)
# ---------------------------------------------------------------------------


def test_error_budget_burn_and_warn():
    b = ProviderErrorBudget(monthly_budget=100, warn_fraction=0.8)
    for _ in range(80):
        b.charge("brightdata", code="TIMEOUT")
    assert b.burn("brightdata") == 80 and b.warned("brightdata") is True
    assert b.exhausted("brightdata") is False


def test_error_budget_exhaustion():
    b = ProviderErrorBudget(monthly_budget=20)
    for _ in range(10):
        b.charge("chocodata", code="PROVIDER_ERROR", weight=2)
    assert b.exhausted("chocodata") is True and b.remaining("chocodata") == 0


def test_error_budget_severity_weights():
    b = ProviderErrorBudget(monthly_budget=100)
    b.charge("firecrawl", code="AUTH")          # weight 2
    b.charge("firecrawl", code="RATE_LIMIT")    # weight 1
    assert b.burn("firecrawl") == 3


def test_error_budget_summary_excludes_untouched_providers():
    b = ProviderErrorBudget(monthly_budget=100)
    b.charge("costco", code="PROVIDER_ERROR")
    s = b.summary()
    assert list(s["providers"].keys()) == ["costco"]
    assert s["providers"]["costco"]["burn"] == 2