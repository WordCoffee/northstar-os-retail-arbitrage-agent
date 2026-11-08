"""The Watch — real monitoring surface tests (gap-b).

The Watch has exactly one real HTTP surface in this repo:
``GET /api/monitoring/error-alerts`` (main.app). The endpoint reads the live
``error_alerts.tracker`` singleton and composes an alert payload; it never
delivers anything. A middleware in ``main.py`` feeds that same singleton with
the status of every ``/api/`` response *after* the response is sent, so a test
must account for exactly one extra sample per request it makes.

These tests feed the real singleton with real timestamps and assert the real
response body, so the wiring — not a stub — is what is being proven.

Not tested here because it does not exist: watchlist CRUD, thresholds, signal
feed, snapshot history, alert acknowledgement (see reports/ty/d12_gap_b.md).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Northstar_backend"))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from error_alerts import tracker  # noqa: E402

client = TestClient(main.app)


@pytest.fixture()
def clean_tracker():
    """Empty the real singleton before/after each test, then restore it."""
    saved = list(tracker._samples)
    tracker._samples.clear()
    try:
        yield tracker
    finally:
        tracker._samples.clear()
        tracker._samples.extend(saved)


def _feed(statuses, *, at):
    for status in statuses:
        tracker.record(status, at=at)


def test_monitoring_envelope_and_empty_summary_shape(clean_tracker):
    resp = client.get("/api/monitoring/error-alerts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1"
    assert body["request_id"].startswith("req_")
    assert len(body["request_id"]) == 4 + 32  # "req_" + token_hex(16)
    assert body["status"] == "ok"
    assert body["error"] is None
    assert body["meta"] == {"service": "monitoring", "version": "v1"}

    summary = body["data"]["summary"]
    assert summary == {
        "window_seconds": 300.0,
        "total_requests": 0,
        "five_xx": 0,
        "five_xx_rate": None,
        "threshold": 0.05,
        "min_requests": 10,
        "breached": False,
    }

    alert = body["data"]["alert"]
    assert alert["code"] == "ok"
    assert alert["severity"] == "info"
    assert alert["message"] == "Error rate within threshold."
    assert alert["retryable"] is False
    assert alert["channel"] is None  # nothing is ever delivered by this code


def test_monitoring_endpoint_reads_live_tracker_and_raises_breach(clean_tracker):
    now = time.time()
    _feed([500] * 10 + [200] * 10, at=now - 60.0)  # 50% 5xx over 20 samples

    body = client.get("/api/monitoring/error-alerts").json()
    summary = body["data"]["summary"]
    assert summary["total_requests"] == 20
    assert summary["five_xx"] == 10
    assert summary["five_xx_rate"] == 0.5
    assert summary["breached"] is True

    alert = body["data"]["alert"]
    assert alert["code"] == "error_rate_breached"
    assert alert["severity"] == "critical"
    assert "50.0%" in alert["message"]
    assert "exceeds the 5.0% threshold" in alert["message"]
    assert alert["channel"] is None

    # The singleton is the source of truth: good traffic inside the same window
    # dilutes the rate below threshold. The +1 is the middleware sample recorded
    # for the request above.
    _feed([200] * 400, at=now - 50.0)
    cleared = client.get("/api/monitoring/error-alerts").json()["data"]["summary"]
    assert cleared["total_requests"] == 421
    assert cleared["five_xx"] == 10
    assert cleared["five_xx_rate"] == 0.0238
    assert cleared["breached"] is False


def test_monitoring_counts_5xx_only(clean_tracker):
    _feed([404, 422, 301] * 10, at=time.time() - 60.0)  # 30 samples, zero 5xx

    summary = client.get("/api/monitoring/error-alerts").json()["data"]["summary"]
    assert summary["total_requests"] == 30
    assert summary["five_xx"] == 0
    assert summary["five_xx_rate"] == 0.0
    assert summary["breached"] is False


def test_monitoring_min_sample_floor_suppresses_breach(clean_tracker):
    _feed([500] * 9, at=time.time() - 60.0)  # 100% 5xx, below min_requests=10

    summary = client.get("/api/monitoring/error-alerts").json()["data"]["summary"]
    assert summary["total_requests"] == 9
    assert summary["five_xx"] == 9
    assert summary["five_xx_rate"] == 1.0
    assert summary["breached"] is False


def test_monitoring_rejects_post_with_405_and_advertises_get(clean_tracker):
    resp = client.post("/api/monitoring/error-alerts")

    assert resp.status_code == 405
    assert resp.headers["allow"] == "GET"


def test_monitoring_unknown_subpath_is_404(clean_tracker):
    resp = client.get("/api/monitoring/error-alerts/extra")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"
