"""The GPU lock manager owns residency, and refuses what does not fit.

Measured facts these tests encode (reports/ty/d7_coexistence.md):
  * Bojo + embeddings together are 5.15 GB VRAM with 5.40 GB RAM free - the resident set.
  * The 27B is 14.32 GB VRAM and leaves 0.04 GB of RAM free - a lease, never a resident.
  * ComfyUI keeps 4.25 GB after a render and reloads on demand, so it can be evicted.

The Ollama and ComfyUI calls are injected; nothing here starts a model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gpu_budget as G  # noqa: E402


@pytest.fixture()
def world(tmp_path, monkeypatch):
    state = {"loaded": ["bojo:latest", "qwen3-embedding:0.6b"], "loads": [], "unloads": []}

    monkeypatch.setattr(G, "STATE", tmp_path / "state" / "gpu")
    monkeypatch.setattr(G, "LOCK", tmp_path / "state" / "gpu" / "lock.json")
    monkeypatch.setattr(G, "ps", lambda: [{"name": name, "processor": "100% GPU"}
                                          for name in state["loaded"]])
    monkeypatch.setattr(G, "unload", lambda model: (
        state["unloads"].append(model),
        state.__setitem__("loaded", [n for n in state["loaded"] if n != model]),
        {"ok": True})[-1])
    monkeypatch.setattr(G, "load", lambda model, role="", keep_alive="10m": (
        state["loads"].append(model),
        state["loaded"].append(model),
        {"ok": True, "loaded": True, "problems": []})[-1])
    monkeypatch.setattr(G, "_warm", lambda model, role, keep_alive="2m": (
        state["loaded"].append(model), {"ok": True})[-1])
    monkeypatch.setattr(G, "fits", lambda role, size: {"ok": True})
    monkeypatch.setattr(G, "free_comfy", lambda: {"ok": True})
    return state


def test_the_resident_set_is_bojo_and_embeddings(world):
    policy = G.residency()["policy"]
    assert policy == sorted([G.ROLE_MODELS["bojo"], G.ROLE_MODELS["embeddings"]])


def test_enforce_unloads_everything_outside_the_keep_set(world):
    world["loaded"] = ["bojo:latest", "qwen3:8b", "qwen3-embedding:0.6b"]

    out = G.enforce(keep=("bojo",))

    assert out["unloaded"] == ["qwen3:8b", "qwen3-embedding:0.6b"]
    assert world["loaded"] == ["bojo:latest"]


def test_an_exclusive_role_drains_everything_first(world, tmp_path, monkeypatch):
    # Hermetic: a lease left on disk by an earlier run must not decide this test.
    monkeypatch.setattr(G, "HEAVY_LEASE_PATH", tmp_path / "heavy_leases.json")
    # The 27B is off by default (WORK ORDER 3, folded fix 4): it needs a stated lease first.
    refused = G.acquire("27b")
    assert refused["ok"] is False and refused["reason"] == "heavy_role_not_leased"
    assert G.heavy_lease("27b", reason="unit test: local reasoning job")["ok"] is True

    out = G.acquire("27b")

    assert out["ok"] is True and out["exclusive"] is True
    assert world["loaded"] == []                       # nothing resident for the 27B
    assert "start-northstar-llm.ps1" in out["action"]  # the manager returns the starter


def test_a_shared_role_keeps_the_resident_pair(world):
    out = G.acquire("coder")

    assert out["ok"] is True and out["exclusive"] is False
    assert "bojo:latest" in world["loaded"]
    assert "qwen3-embedding:0.6b" in world["loaded"]
    assert G.ROLE_MODELS["coder"] in world["loaded"]


def test_a_role_that_does_not_fit_evicts_comfyui_before_refusing(world, monkeypatch):
    calls = {"fits": 0, "comfy": 0}

    def fits(role, size):
        calls["fits"] += 1
        return {"ok": calls["fits"] > 1}          # fails until ComfyUI is freed

    monkeypatch.setattr(G, "fits", fits)
    monkeypatch.setattr(G, "free_comfy", lambda: (calls.__setitem__("comfy", calls["comfy"] + 1),
                                                  {"ok": True})[-1])

    out = G.acquire("vision")

    assert calls["comfy"] == 1, "ComfyUI must be asked to release VRAM before giving up"
    assert out["ok"] is True


def test_release_restores_the_resident_pair(world):
    world["loaded"] = ["bojo:latest", "qwen3-embedding:0.6b", G.ROLE_MODELS["coder"]]

    out = G.release("coder")

    assert out["unloaded"] == G.ROLE_MODELS["coder"]
    assert set(out["restored"]) == {"bojo", "embeddings"}
    assert set(world["loaded"]) >= {"bojo:latest", "qwen3-embedding:0.6b"}


def test_budgets_come_from_the_measurement(world):
    assert G.ROLE_BUDGET_GB["27b"] == 14.5
    assert G.ROLE_BUDGET_GB["vision"] == 8.0     # budget keeps the 7B-class headroom
    assert G.ROLE_BUDGET_GB["image_flux"] == 11.0
    assert G.ROLE_SIZE_GB["vision"] == 5.19      # measured, 7B-class
    # corrected 2026-11-08: qwen2.5vl:7b on a clean server beats llava on correctness
    assert G.ROLE_MODELS["vision"] == "qwen2.5vl:7b"
