"""Semantic memory: real embeddings when the local runner answers, hashed fallback when it does not."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import pytest  # noqa: E402

from tys_ops import memory  # noqa: E402


def _fake_embed(text: str):
    vector = [0.0] * memory.SEMANTIC_DIM
    low = (text or "").lower()
    if "gpu" in low:
        vector[0] = 1.0
    elif "video" in low:
        vector[1] = 1.0
    else:
        vector[2] = 1.0
    return vector


def test_default_is_the_hashed_index(monkeypatch, tmp_path):
    monkeypatch.delenv("NORTHSTAR_MEMORY_SEMANTIC", raising=False)
    index = memory.MemoryIndex(str(tmp_path / "m.db"))
    assert index.semantic is False
    index.remember_text("a", "The render lane takes the GPU lock.")
    hits = index.search("a", "GPU lock")
    assert hits and hits[0]["semantic"] is False
    index.close()


def test_semantic_search_ranks_the_matching_text(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, "embed_semantic", _fake_embed)
    index = memory.MemoryIndex(str(tmp_path / "m.db"), semantic=True)
    assert index.semantic is True
    index.remember_text("a", "The render lane takes the GPU lock.")
    index.remember_text("a", "Free tier keeps no video.")
    index.remember_text("a", "The A+ header is 970 by 600.")
    hits = index.search("a", "gpu", k=1)
    assert len(hits) == 1
    assert "GPU lock" in hits[0]["text"]
    assert hits[0]["semantic"] is True
    index.close()


def test_an_embedder_failure_falls_back_and_never_raises(monkeypatch, tmp_path):
    def _boom(text):
        raise memory.EmbeddingError("runner down")

    monkeypatch.setattr(memory, "embed_semantic", _boom)
    index = memory.MemoryIndex(str(tmp_path / "m.db"), semantic=True)
    index.remember_text("a", "The render lane takes the GPU lock.")
    assert index.semantic is False
    assert "runner down" in index.semantic_reason
    hits = index.search("a", "GPU lock")
    assert hits and hits[0]["semantic"] is False
    index.close()

def test_old_hashed_chunks_are_backfilled_on_first_semantic_search(monkeypatch, tmp_path):
    path = str(tmp_path / "m.db")
    legacy = memory.MemoryIndex(path)
    legacy.remember_text("a", "The render lane takes the GPU lock.")
    legacy.close()

    monkeypatch.setattr(memory, "embed_semantic", _fake_embed)
    index = memory.MemoryIndex(path, semantic=True)
    hits = index.search("a", "gpu", k=1)
    assert hits and "GPU lock" in hits[0]["text"]
    assert hits[0]["semantic"] is True
    index.close()
