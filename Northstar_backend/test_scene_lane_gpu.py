"""The image lane owns the GPU and proves what it found and what it left.

Every test here injects the measurements, so no GPU and no Ollama call is made.
The behaviour under test is the bookkeeping that makes a render safe to run beside
resident models: unload only what is resident, reload it from `finally`, refuse a
budget that does not fit with the real numbers, and record both snapshots.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import comfy_lane  # noqa: E402

GPU = {"ok": True, "total_mb": 16303, "used_mb": 3072, "free_mb": 13231,
       "free_gb": 12.92, "used_gb": 3.0, "util_pct": 3}
GPU_CLEAN = {**GPU, "used_mb": 0, "free_mb": 16303, "free_gb": 15.92,
             "used_gb": 0.0}


@pytest.fixture()
def journal(monkeypatch):
    rows = []
    monkeypatch.setattr(comfy_lane, "_log", rows.append)
    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: False)
    return rows


def _ps(*names):
    return {"ok": True, "resident": list(names),
            "models": [{"name": name, "size_vram_gb": 3.0} for name in names]}


def _run(*, resident=(), snapshots=None, needed=6.0, journal=None, work=None,
         unload=None, reload=None, stop_after=None):
    """Drive one lane with fake measurements and return the lane row."""
    state = {"resident": list(resident), "snap": 0,
             "unloaded": [], "reloaded": []}
    snaps = list(snapshots or [GPU, GPU, GPU, GPU, GPU, GPU, GPU])

    def snapshot():
        idx = min(state["snap"], len(snaps) - 1)
        state["snap"] += 1
        return snaps[idx]

    def ps():
        return _ps(*state["resident"])

    def do_unload(tag):
        state["unloaded"].append(tag)
        state["resident"] = [name for name in state["resident"] if name != tag]
        return {"tag": tag, "api_ok": True, "verified": tag not in state["resident"]}

    def do_reload(tag):
        state["reloaded"].append(tag)
        state["resident"].append(tag)
        return {"tag": tag, "api_ok": True, "verified": True}

    def start():
        return {"ok": True, "pid": 4242}

    def stop(pid):
        return {"ok": True, "pid": pid, "stopped": True}

    outcome = comfy_lane.lane(
        work or (lambda: {"rendered": True}),
        start=start, ready=lambda: {"ok": True}, stop=stop,
        snapshot=snapshot, ps=ps, unload=unload or do_unload, reload=reload or do_reload,
        needed_gb=needed, watchlist=list(comfy_lane.OLLAMA_WATCHLIST))
    return outcome, state


def test_a_resident_watched_model_is_unloaded_and_reloaded(journal):
    outcome, state = _run(resident=["bojo:latest"])
    assert outcome["ok"] is True
    assert state["unloaded"] == ["bojo:latest"]
    assert state["reloaded"] == ["bojo:latest"]
    row = outcome["lane"]
    assert row["unloaded"][0]["verified"] is True
    assert row["reload_verified"] == {"bojo:latest": True}
    assert row["resident_before"] == ["bojo:latest"]
    assert row["ollama_ps_after"]["resident"] == ["bojo:latest"]


def test_an_absent_model_is_not_unloaded_or_reloaded(journal):
    outcome, state = _run(resident=[])
    assert outcome["ok"] is True
    assert state["unloaded"] == [] and state["reloaded"] == []
    assert outcome["lane"]["unloaded"] == []


def test_both_watched_models_are_restored_from_finally_when_work_raises(journal):
    def boom():
        raise RuntimeError("render died")

    with pytest.raises(RuntimeError):
        _run(resident=["bojo:latest", "qwen3-embedding:0.6b"], work=boom)
    assert journal, "the lane must still write its row"
    row = journal[-1]
    assert row["event"] == "lane"
    assert [item["tag"] for item in row["unloaded"]] == ["bojo:latest",
                                                         "qwen3-embedding:0.6b"]
    assert row["reload_verified"] == {"bojo:latest": True,
                                      "qwen3-embedding:0.6b": True}
    assert row["stopped"]["stopped"] is True
    assert row["work_ok"] is False


def test_a_budget_that_does_not_fit_names_the_numbers_and_never_starts(journal):
    started = {"called": False}

    def snapshot():
        return {"ok": True, "total_mb": 16303, "used_mb": 10240, "free_mb": 6144,
                "free_gb": 6.0, "used_gb": 10.0, "util_pct": 1}

    result = comfy_lane.lane(lambda: None,
                             start=lambda: started.update({"called": True}) or {"ok": True, "pid": 1},
                             ready=lambda: {"ok": True}, stop=lambda pid: {"ok": True},
                             snapshot=snapshot, ps=lambda: _ps(),
                             unload=lambda tag: {"tag": tag, "verified": True},
                             reload=lambda tag: {"tag": tag, "verified": True},
                             needed_gb=8.0, watchlist=[])
    assert result["ok"] is False and result["refused"] is True
    assert "6.0 GB free - 8.0 GB needed = -2.0 GB" in result["reason"]
    assert "1.0 GB reserve" in result["reason"]
    assert started["called"] is False
    assert result["lane"]["budget"]["headroom_gb"] == -2.0


def test_the_lane_records_before_and_after_snapshots(journal):
    outcome, state = _run(
        resident=["bojo:latest"],
        snapshots=[GPU, GPU_CLEAN, GPU_CLEAN, GPU_CLEAN, GPU_CLEAN, GPU, GPU])
    row = outcome["lane"]
    for key in ("gpu_before", "gpu_ready", "gpu_before_work", "gpu_after_work",
                "gpu_after", "gpu_after_reload"):
        assert row.get(key), key
    assert row["gpu_before"]["used_mb"] == 3072
    assert row["gpu_ready"]["used_mb"] == 0
    assert row["budget"]["checked"] is True
    assert row["budget"]["ok"] is True
    assert row["seconds"] >= 0


def test_an_unload_that_does_not_take_is_a_refusal(journal):
    def stuck(tag):
        return {"tag": tag, "api_ok": True, "verified": False}

    state = {"resident": ["bojo:latest"]}
    result = comfy_lane.lane(
        lambda: None, start=lambda: {"ok": True, "pid": 1},
        ready=lambda: {"ok": True}, stop=lambda pid: {"ok": True},
        snapshot=lambda: GPU_CLEAN,
        ps=lambda: _ps(*state["resident"]),
        unload=stuck, reload=lambda tag: {"tag": tag, "verified": True},
        needed_gb=4.0, watchlist=["bojo:latest"])
    assert result["ok"] is False and result["refused"] is True
    assert "could not unload" in result["reason"]
