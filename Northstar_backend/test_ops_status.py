"""Operational status (N-2) — the trust surface.

The contract worth protecting: every number is measured, and anything that cannot
be measured is an explicit null with a reason — never a fabricated zero, and never
a silent "healthy".
"""
from __future__ import annotations

import sqlite3
from collections import namedtuple

import pytest

import lane_telemetry as lt
import ops_status as ops

Usage = namedtuple("Usage", "total used free")


# ── disk ─────────────────────────────────────────────────────────────────────

def test_disk_is_measured_with_a_headroom_verdict():
    out = ops.disk_status(".", probe=lambda p: Usage(100 * 1024**3, 10 * 1024**3, 19 * 1024**3))
    assert out["available"] is True
    assert out["free_gb"] == pytest.approx(19.0, abs=0.01)
    assert out["verdict"] == "ok"                    # >= 5 GB
    assert out["thresholds"] == {"warn_gb": 5.0, "crit_gb": 1.0}


def test_disk_verdict_thresholds():
    warn = ops.disk_status(".", probe=lambda p: Usage(100 * 1024**3, 0, 3 * 1024**3))
    crit = ops.disk_status(".", probe=lambda p: Usage(100 * 1024**3, 0, 0))
    assert warn["verdict"] == "warn"
    assert crit["verdict"] == "critical"


def test_disk_probe_failure_is_reported_not_guessed():
    def boom(_p):
        raise OSError("no such device")

    out = ops.disk_status(".", probe=boom)
    assert out["available"] is False
    assert out["free_gb"] is None
    assert "no such device" in out["reason"]


# ── database ─────────────────────────────────────────────────────────────────

def test_missing_database_is_explicit(tmp_path):
    out = ops.db_status(str(tmp_path / "nope.db"))
    assert out["available"] is False
    assert out["reason"] == "database file absent"


def test_database_integrity_and_table_count_are_measured(tmp_path):
    path = tmp_path / "n.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (id TEXT)")
    conn.commit()
    conn.close()
    out = ops.db_status(str(path))
    assert out["available"] is True
    assert out["tables"] == 1
    assert out["integrity"] == "ok"
    assert out["verdict"] == "ok"
    assert out["size_bytes"] > 0
    assert out["size_mb"] >= 0.0


def test_database_integrity_failure_is_critical(tmp_path):
    path = tmp_path / "n.db"
    path.write_bytes(b"")
    out = ops.db_status(str(path), integrity_probe=lambda p: "malformed")
    assert out["verdict"] == "critical"
    assert out["integrity"] == "malformed"


# ── lanes ────────────────────────────────────────────────────────────────────

def test_lanes_reuse_the_one_telemetry_store(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "n.db"))
    conn.row_factory = sqlite3.Row
    for i in range(4):
        lt.record(conn, "chat:qwen", latency_ms=100 + i, ok=True)
    out = ops.lane_status(conn)
    assert out["available"] is True
    assert out["lanes"]["chat:qwen"]["samples"] == 4
    assert out["lanes"]["chat:qwen"]["p50_latency_ms"] == 101.0


def test_lane_status_reports_an_unusable_handle():
    out = ops.lane_status(object())
    assert out["available"] is False and out["lanes"] == {}
    assert out["reason"]


# ── models ───────────────────────────────────────────────────────────────────

def test_resident_models_are_listed():
    payload = {"models": [
        {"name": "northstaros-qwen3.8:27b", "size_vram": 12 * 1024**3},
        {"name": "qwen3-embedding:0.6b", "size": 639 * 1024**2},
    ]}
    out = ops.model_status(ps_probe=lambda: payload)
    assert out["available"] is True
    assert [m["name"] for m in out["resident"]] == ["northstaros-qwen3.8:27b", "qwen3-embedding:0.6b"]
    assert out["vram_used_mb"] > 12000
    assert out["reason"] is None


def test_no_resident_model_is_a_reason_not_a_zero():
    out = ops.model_status(ps_probe=lambda: {"models": []})
    assert out["available"] is True
    assert out["resident"] == []
    assert out["reason"] == "no model is currently resident"
    assert out["vram_used_mb"] is None


def test_unreachable_ollama_is_reported():
    def boom():
        raise ConnectionError("ollama down")

    out = ops.model_status(ps_probe=boom)
    assert out["available"] is False
    assert "ollama down" in out["reason"]


# ── verdict ──────────────────────────────────────────────────────────────────

def test_verdict_levels():
    assert ops.verdict({"a": {"verdict": "ok"}})["status"] == "healthy"
    assert ops.verdict({"a": {"verdict": "warn"}})["status"] == "degraded"
    assert ops.verdict({"a": {"verdict": "critical"}})["status"] == "critical"


def test_unknown_never_reads_as_healthy():
    v = ops.verdict({"gpu": {"available": False, "reason": "not measured"}})
    assert v["status"] == "degraded"
    assert any("gpu" in r and "unknown" in r for r in v["reasons"])


def test_a_delegated_component_does_not_degrade_the_verdict():
    """The GPU is reported by /api/shell/hardware; pointing at it is not a fault."""
    v = ops.verdict({"disk": {"verdict": "ok"},
                     "gpu": {"available": False, "delegated": True, "reason": "see /api/shell/hardware"}})
    assert v["status"] == "healthy"
    assert v["reasons"] == []


# ── aggregate ────────────────────────────────────────────────────────────────

def test_collect_is_fully_injectable_and_returns_the_shape(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "n.db"))
    conn.row_factory = sqlite3.Row
    out = ops.collect(
        db_path=str(tmp_path / "n.db"), db=conn,
        disk_probe=lambda p: Usage(100 * 1024**3, 0, 10 * 1024**3),
        ps_probe=lambda: {"models": [{"name": "m", "size_vram": 1024**3}]},
    )
    assert out["ok"] is True
    assert set(out["components"]) == {"disk", "database", "lanes", "models", "gpu"}
    assert out["status"] in ("healthy", "degraded", "critical")
    assert "measured at call time" in out["note"]
    # GPU is not duplicated here; the pointer is explicit.
    assert out["components"]["gpu"]["available"] is False
    assert "/api/shell/hardware" in out["components"]["gpu"]["reason"]


# ── D4: no NEW debug forks (the safe resolution of the owner decision) ──────

def test_no_new_debug_fork_files():
    """D4: three *_dbg forks of main.py exist historically and are untracked.

    They are NOT deleted here (unfamiliar files are treated as potential operator
    work). What this test prevents is a FOURTH one appearing unnoticed.
    """
    import glob
    import os

    backend = os.path.dirname(os.path.abspath(__file__))
    known = {"_main_dbg.py", "_main_dbg2.py", "_main_dbg3.py"}
    found = {os.path.basename(p) for p in glob.glob(os.path.join(backend, "*_dbg*.py"))}
    assert found <= known, (
        f"new debug fork(s) appeared: {sorted(found - known)} — archive them outside the "
        "tree rather than letting them accumulate")
