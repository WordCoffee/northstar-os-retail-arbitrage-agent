"""Phase F/S11c — observability toolkit tests (offline)."""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.gg_observability import (  # noqa: E402
    CostTracker,
    DebugStore,
    LatencyTracker,
    MetricsStore,
    StructuredLogger,
    percentile,
    project_scans,
)


def test_percentiles():
    assert percentile([], 95) is None
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)
    assert percentile([1.0, 2.0, 3.0, 4.0], 100) == pytest.approx(4.0)


def test_latency_summary():
    t = LatencyTracker()
    for i in range(20):
        t.record(float(i))
    s = t.summary()
    assert s["count"] == 20 and s["p95"] is not None and s["p99"] is not None


def test_metrics_store_appends(tmp_path):
    ms = MetricsStore(tmp_path / "metrics.jsonl")
    ms.emit({"scan_id": "s1", "opp_count": 3})
    ms.emit({"scan_id": "s2", "opp_count": 5})
    lines = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["opp_count"] == 5


def test_structured_log_json_line():
    line = StructuredLogger.line(level="WARNING", event="timeout", scan_id="s1", asin="B0X", ms=120)
    d = json.loads(line)
    assert d["level"] == "WARNING" and d["scan_id"] == "s1" and d["ms"] == 120


def test_debug_store_gzip_roundtrip_when_enabled(tmp_path):
    store = DebugStore(tmp_path, debug=True)
    p = store.save_raw("raw", {"asin": "B0X", "html_len": 100})
    assert p and p.exists()
    assert gzip.open(p, "rt").read()
    assert store.load_for_replay("raw")["asin"] == "B0X"


def test_debug_store_off_skips_writes(tmp_path):
    store = DebugStore(tmp_path, debug=False)
    assert store.save_raw("raw", {"x": 1}) is None
    assert store.load_for_replay("raw") is None


def test_debug_env_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLDEN_GOOSE_DEBUG", "1")
    store = DebugStore(tmp_path)
    assert store.debug is True


def test_debug_purge_expired(tmp_path):
    store = DebugStore(tmp_path, debug=True)
    store.save_raw("a", {"x": 1})
    store.save_raw("b", {"x": 2})
    now = time.time()
    # back-date one file beyond TTL
    p = tmp_path / "a.json.gz"
    os.utime(p, (now - 8 * 86400, now - 8 * 86400))
    assert store.purge(now) == 1
    assert not p.exists() and (tmp_path / "b.json.gz").exists()


def test_cost_tracker():
    ct = CostTracker()
    ct.charge("brightdata", 12)
    ct.charge("brightdata", 3)
    ct.charge("chocodata", 5)
    assert ct.totals() == {"brightdata": 15, "chocodata": 5}
    assert ct.total() == 20


def test_quota_projection():
    r = project_scans(monthly_limit=1000, spent=250, avg_credits_per_scan=50)
    assert r["projected_scans_remaining"] == 15
    assert project_scans(1000, 1000, 50)["projected_scans_remaining"] == 0
    assert project_scans(100, 0, 0)["projected_scans_remaining"] == 0