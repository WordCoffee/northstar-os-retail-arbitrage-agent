"""Lane selection: the task's own model, or an honest refusal.

2026-11-03, a real campaign (campaign-20261103T191733Z) dispatched one task, then
refused the next with:

    refused dispatch task=ty-feather-sigma-guard reason=profile_mismatch
    lane=qwen3-embedding:0.6b task=qwen3.5:4b

The first task had loaded qwen3.5:4b, free RAM fell below the estimate+headroom,
the requested model no longer "fit", and resolve_lane fell back to the smallest
thing that did: an EMBEDDING model that cannot run a single tool call. The
campaign ended on that substitution. These tests pin the three rules that fix it.

Offline: tags, free RAM and the resident set are injected.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "continuous_loop_lane", ROOT / "scripts" / "continuous_loop.py")
cl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cl)

TAGS = {"ok": True, "models": [
    {"name": "qwen3.5:4b", "size_gb": 3.1},
    {"name": "qwen3.5:2b", "size_gb": 2.5},
    {"name": "bojo", "size_gb": 2.5},
    {"name": "qwen3-embedding:0.6b", "size_gb": 0.6},
]}


def _ty(model="qwen3.5:4b"):
    return {"id": "t", "execution": "ty", "model": model}


def test_the_requested_model_is_chosen_when_it_fits():
    lane = cl.resolve_lane(_ty(), tags=TAGS, free_ram_gb=8.0, resident=[])
    assert lane["ok"] is True
    assert lane["model"] == "qwen3.5:4b"


def test_a_requested_model_that_does_not_fit_is_refused_not_substituted():
    lane = cl.resolve_lane(_ty(), tags=TAGS, free_ram_gb=1.5, resident=[])
    assert lane["ok"] is False, "it must not quietly pick a smaller model"
    assert "does not fit" in lane["reason"]
    assert "qwen3-embedding" not in (lane.get("model") or "")


def test_an_embedding_model_is_never_a_candidate():
    # Free RAM only holds the embedding model: the lane must refuse, not use it.
    lane = cl.resolve_lane(_ty(), tags=TAGS, free_ram_gb=0.8, resident=[])
    assert lane["ok"] is False
    assert all("embed" not in (c["model"] or "") for c in lane["installed"])


def test_a_resident_model_fits_without_extra_ram():
    # The campaign case: the same model is already loaded, so no new RAM is needed.
    lane = cl.resolve_lane(_ty(), tags=TAGS, free_ram_gb=0.5,
                           resident=["qwen3.5:4b"])
    assert lane["ok"] is True
    assert lane["model"] == "qwen3.5:4b"
    row = next(c for c in lane["installed"] if c["model"] == "qwen3.5:4b")
    assert row["resident"] is True and row["fits"] is True


def test_without_a_request_the_best_ranked_lane_that_fits_wins():
    task = {"id": "t", "execution": "ty"}
    lane = cl.resolve_lane(task, tags=TAGS, free_ram_gb=8.0, resident=[])
    assert lane["ok"] is True
    assert lane["model"] == "bojo", "bojo is the proven tool-loop lane"


def test_a_prebuilt_task_needs_no_model():
    lane = cl.resolve_lane({"id": "p", "execution": "prebuilt"}, tags=TAGS,
                           free_ram_gb=0.1, resident=[])
    assert lane["ok"] is True and lane["model"] == ""
