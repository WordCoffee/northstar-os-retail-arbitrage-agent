"""B3/B4/B5 — the three fixes B1 withheld until a cause was named.

B1 attributed the tail's *shape* from lane_telemetry (a zero-tool stall, one
degraded hour, ~95 s of per-render overhead) but could not name a root cause, so
it shipped nothing. These add the visibility that makes the next occurrence
explicable:

  B3  the RAM-heavy lanes refuse to run against a ComfyUI started WITHOUT
      --cache-none (the 2026-10-22 kill with no traceback);
  B4  a render records which models it evicted, and the turn says so;
  B5  the cross-process render lock counts its waits and timeouts.

Offline: no Ollama, no ComfyUI, no GPU.
"""

from __future__ import annotations

import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import studio_generation as sg  # noqa: E402


# ── B3 ──────────────────────────────────────────────────────────────────────

@pytest.fixture()
def marker(tmp_path, monkeypatch):
    path = tmp_path / "comfyui_launch.json"
    monkeypatch.setattr(sg, "CACHE_NONE_MARKER", path)
    return path


def test_marker_true_allows_and_false_refuses(marker):
    marker.write_text(json.dumps({"cache_none": True, "pid": 1}), encoding="utf-8")
    assert sg.comfyui_cache_none() is True
    sg.require_cache_none("edit")           # no raise

    marker.write_text(json.dumps({"cache_none": False, "pid": 1}), encoding="utf-8")
    assert sg.comfyui_cache_none() is False
    with pytest.raises(RuntimeError) as err:
        sg.require_cache_none("edit")
    assert "comfyui_cache_none_required" in str(err.value)


def test_an_absent_or_broken_marker_is_unknown_not_false(marker):
    assert sg.comfyui_cache_none() is None          # absent
    sg.require_cache_none("video")                  # unknown never blocks
    marker.write_text("{not json", encoding="utf-8")
    assert sg.comfyui_cache_none() is None
    sg.require_cache_none("video")


def test_the_edit_and_video_lanes_call_the_guard(monkeypatch, marker):
    marker.write_text(json.dumps({"cache_none": False}), encoding="utf-8")
    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    with pytest.raises(RuntimeError, match="comfyui_cache_none_required"):
        sg.generate_edit(b"x", "make it blue")
    with pytest.raises(RuntimeError, match="comfyui_cache_none_required"):
        sg.generate_video("a pouch")


# ── B4 ──────────────────────────────────────────────────────────────────────

def test_unload_brain_records_what_it_evicted(monkeypatch):
    calls = {"resident": [["qwen2.5vl:7b", "northstaros-qwen3.8:27b"], []]}
    monkeypatch.setattr(sg, "_resident_models", lambda: calls["resident"].pop(0)
                        if calls["resident"] else [])
    monkeypatch.setattr(sg, "_evict", lambda name: None)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)
    sg._LAST_EVICTION["models"] = []

    assert sg.unload_brain() is True
    recorded = sg.last_brain_eviction()
    assert "qwen2.5vl:7b" in recorded["models"]
    assert "northstaros-qwen3.8:27b" in recorded["models"]
    assert recorded["at"]


def test_unload_brain_with_nothing_resident_records_nothing(monkeypatch):
    monkeypatch.setattr(sg, "_resident_models", lambda: [])
    sg._LAST_EVICTION["models"] = []
    assert sg.unload_brain() is True
    assert sg.last_brain_eviction()["models"] == []


# ── B5 ──────────────────────────────────────────────────────────────────────

def test_render_lock_counts_attempts_and_waits(tmp_path, monkeypatch):
    lock_path = tmp_path / "render.lock"
    lock = sg._CrossProcessRenderLock(str(lock_path), max_seconds=30)
    before = sg.render_lock_stats()["attempts"]
    assert lock.acquire(timeout=2.0) is True
    lock.release()
    after = sg.render_lock_stats()
    assert after["attempts"] == before + 1
    assert after["last_wait_s"] >= 0.0

    # a second, concurrent owner must time out and be counted as one
    other = sg._CrossProcessRenderLock(str(lock_path), max_seconds=30)
    assert lock.acquire(timeout=1.0) is True
    try:
        t0 = time.perf_counter()
        got = other.acquire(timeout=0.4)
        waited = time.perf_counter() - t0
        assert got is False
        assert waited >= 0.35
        stats = sg.render_lock_stats()
        assert stats["timeouts"] >= 1
        assert stats["max_wait_s"] >= stats["last_wait_s"] - 1e-6
    finally:
        lock.release()
