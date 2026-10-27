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
    monkeypatch.setattr(sg, "ensure_system_ram", lambda **kw: {"ok": True, "stopped": [], "free_mb_before": 8192.0, "free_mb_after": 8192.0, "needed_mb": 4096, "refusal": None})
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


# --- 2026-10-22: eviction must drain EVERY resident model -------------------
#
# The old implementation evicted one hard-coded id and then checked only that
# id. A vision model loaded by an earlier call (qwen2.5vl:7b, 6.4 GB) stayed
# resident while unload_brain reported success, and the next render died.

def test_unload_brain_evicts_every_resident_model(monkeypatch):
    state = {"resident": ["northstaros-qwen3.8:27b", "qwen2.5vl:7b"], "evicted": []}

    def fake_resident():
        return list(state["resident"])

    def fake_evict(name):
        state["evicted"].append(name)
        if name in state["resident"]:
            state["resident"].remove(name)

    monkeypatch.setattr(sg, "_resident_models", fake_resident)
    monkeypatch.setattr(sg, "_evict", fake_evict)
    monkeypatch.delenv("NORTHSTAR_BRAIN_MODEL", raising=False)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)

    assert sg.unload_brain(wait_s=0) is True
    assert set(state["evicted"]) == {"northstaros-qwen3.8:27b", "qwen2.5vl:7b"}
    assert state["resident"] == []


def test_unload_brain_is_false_when_a_model_will_not_leave(monkeypatch):
    monkeypatch.setattr(sg, "_resident_models", lambda: ["stuck:1b"])
    monkeypatch.setattr(sg, "_evict", lambda name: None)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)
    assert sg.unload_brain(wait_s=0) is False


def test_unload_brain_honours_explicit_brain_model(monkeypatch):
    """NORTHSTAR_BRAIN_MODEL still pins eviction to one id when the operator wants that."""
    evicted = []
    monkeypatch.setenv("NORTHSTAR_BRAIN_MODEL", "northstaros-qwen3.8:27b")
    monkeypatch.setattr(sg, "_resident_models",
                        lambda: ["northstaros-qwen3.8:27b", "qwen2.5vl:7b"])
    monkeypatch.setattr(sg, "_evict", lambda name: evicted.append(name))
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)
    sg.unload_brain(wait_s=0)
    assert evicted == ["northstaros-qwen3.8:27b"]

