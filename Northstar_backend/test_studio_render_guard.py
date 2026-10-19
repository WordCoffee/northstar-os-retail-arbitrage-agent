"""Render-guard tests: VRAM eviction verification + bounded OOM retry.

2026-10-16: renders OOM'd when the 27B brain reloaded mid-render (external
caller). The lane now (a) verifies brain eviction before rendering and
(b) retries exactly once on CUDA out-of-memory.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio_generation as sg  # noqa: E402


def test_oom_triggers_exactly_one_reeviction_and_retry(monkeypatch):
    calls = {"graph": 0, "unload": 0, "release": 0}
    sleeps = []

    def flaky_graph(graph, timeout_s, **kwargs):
        calls["graph"] += 1
        if calls["graph"] == 1:
            raise RuntimeError('execution failed: {"status_str": "error"} CUDA error: out of memory')
        return [{"filename": "ok.png"}]

    monkeypatch.setattr(sg, "_run_graph", flaky_graph)
    monkeypatch.setattr(sg, "unload_brain", lambda wait_s=45.0: calls.__setitem__("unload", calls["unload"] + 1) or True)
    monkeypatch.setattr(sg, "release_models", lambda: calls.__setitem__("release", calls["release"] + 1))
    monkeypatch.setattr(sg.time, "sleep", lambda s: sleeps.append(s))

    out = sg._run_graph_guarded({"1": {}}, timeout_s=10)
    assert out == [{"filename": "ok.png"}]
    assert calls["graph"] == 2, "exactly one retry"
    assert calls["unload"] == 1, "re-evict once before the retry"
    assert calls["release"] == 1, "free ComfyUI's crammed cache before the retry"
    assert sleeps == [5]


def test_generate_image_releases_models_on_failure(monkeypatch):
    """A failed render must never leave a crammed ComfyUI cache behind."""
    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    monkeypatch.setattr(sg, "unload_brain", lambda wait_s=45.0: True)
    released = {"n": 0}
    monkeypatch.setattr(sg, "release_models",
                        lambda: released.__setitem__("n", released["n"] + 1))

    def boom(*a, **k):
        raise RuntimeError("CUDA error: out of memory")

    monkeypatch.setattr(sg, "_run_graph_guarded", boom)
    with pytest.raises(RuntimeError):
        sg.generate_image(prompt="x")
    assert released["n"] >= 1


def test_non_oom_failures_propagate_without_retry(monkeypatch):
    calls = {"graph": 0}

    def bad_graph(graph, timeout_s, **kwargs):
        calls["graph"] += 1
        raise RuntimeError("prompt validation failed")

    monkeypatch.setattr(sg, "_run_graph", bad_graph)
    with pytest.raises(RuntimeError):
        sg._run_graph_guarded({"1": {}}, timeout_s=10)
    assert calls["graph"] == 1, "no retry for non-OOM errors"


def test_unload_brain_returns_true_when_ollama_unreachable(monkeypatch):
    """Verification unavailable must never block renders (best effort kept)."""
    import json as _json
    import urllib.request as _urlreq

    def fake_urlopen(req, timeout=0):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(_urlreq, "urlopen", fake_urlopen)
    assert sg.unload_brain(wait_s=1) is True
