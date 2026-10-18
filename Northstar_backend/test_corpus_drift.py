"""Embeddings drift engine tests (V4.1 §5.4): vector store, drift math, lane,
tools, router. Offline: in-memory SQLite + sqlite-vec + a fake embedding lane.
No Ollama, no network.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_tools  # noqa: E402
import corpus_drift  # noqa: E402
import corpus_router  # noqa: E402
import shell_focus  # noqa: E402

DIM = 4

pytest.importorskip("sqlite_vec", reason="sqlite-vec not installed")


class _FakeLane:
    """Deterministic local lane stand-in — returns a fixed vector, records calls."""

    def __init__(self, vec=None, fail=False):
        self.vec = list(vec) if vec is not None else [1.0, 0.0, 0.0, 0.0]
        self.fail = fail
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        if self.fail:
            raise corpus_drift.EmbeddingUnavailable("embedding lane unreachable: test")
        return list(self.vec)

    def available(self):
        return not self.fail


@pytest.fixture()
def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE corpus_records (id TEXT PRIMARY KEY, source TEXT, source_id TEXT, "
        "title TEXT, summary TEXT, content TEXT, url TEXT, license TEXT, kind TEXT, "
        "ingested_at TEXT)")
    conn.execute("CREATE TABLE search_query_performance (id TEXT PRIMARY KEY, query TEXT, asin TEXT)")
    return corpus_drift.VectorStore(conn, dim=DIM)


# ── Vector store ────────────────────────────────────────────────────────────

def test_upsert_and_search_orders_by_cosine_distance(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("r2", "corpus", "b", [0, 1, 0, 0])
    store.upsert("r3", "corpus", "c", [0.9, 0.1, 0, 0])
    hits = store.search([1, 0, 0, 0], limit=5)
    assert [h["record_id"] for h in hits] == ["r1", "r3", "r2"]
    assert hits[0]["distance"] == 0.0 and hits[0]["similarity"] == 1.0


def test_upsert_is_idempotent_and_replaces_vector(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("r1", "corpus", "a", [0, 0, 1, 0])  # replace
    assert store.count() == 1
    hits = store.search([0, 0, 1, 0], limit=1)
    assert hits[0]["record_id"] == "r1" and hits[0]["distance"] == 0.0


def test_search_threshold_and_source_filter(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("r2", "sqp", "q", [0, 1, 0, 0])
    assert [h["record_id"] for h in store.search([1, 0, 0, 0], limit=5, threshold=0.2)] == ["r1"]
    assert [h["record_id"] for h in store.search([1, 0, 0, 0], limit=5, source="sqp")] == ["r2"]


def test_upsert_rejects_dim_mismatch(store):
    with pytest.raises(ValueError):
        store.upsert("r1", "corpus", "a", [1, 0, 0])  # 3 != 4


def test_delete_and_has(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    assert store.has("r1") is True
    assert store.delete("r1") is True
    assert store.has("r1") is False and store.count() == 0
    assert store.delete("missing") is False


def test_stats_counts_by_source(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("r2", "corpus", "b", [0, 1, 0, 0])
    store.upsert("s1", "sqp", "q", [0, 0, 1, 0])
    st = store.stats()
    assert st["total"] == 3 and st["by_source"] == {"corpus": 2, "sqp": 1}
    assert st["metric"] == "cosine" and st["model"] == corpus_drift.EMBED_MODEL


def test_vectors_by_source_roundtrips(store):
    store.upsert("r1", "corpus", "a", [0.25, 0.5, 0.75, 1.0])
    vecs = store.vectors_by_source("corpus")
    assert len(vecs) == 1
    assert all(abs(a - b) < 1e-6 for a, b in zip(vecs[0], [0.25, 0.5, 0.75, 1.0]))


# ── Drift math (pure) ───────────────────────────────────────────────────────

def test_cosine_similarity_and_distance():
    assert corpus_drift.cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert corpus_drift.cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert corpus_drift.cosine_distance([1, 0], [0, 1]) == pytest.approx(1.0)
    assert corpus_drift.cosine_similarity([0, 0], [1, 0]) == 0.0  # zero vector guarded


def test_centroid_is_mean(store):
    c = corpus_drift.centroid([[1, 2], [3, 4]])
    assert c == [2.0, 3.0]


def test_compute_drift_insufficient_is_honest():
    rep = corpus_drift.compute_drift([], [[1, 0]])
    assert rep["available"] is False and "insufficient" in rep["reason"]
    assert rep["n_current"] == 0 and rep["n_historical"] == 1


def test_compute_drift_identical_is_zero():
    rep = corpus_drift.compute_drift([[1, 0]], [[1, 0]])
    assert rep["available"] is True and rep["drift"] == 0.0 and rep["similarity"] == 1.0


def test_compute_drift_orthogonal_is_one():
    rep = corpus_drift.compute_drift([[1, 0]], [[0, 1]])
    assert rep["drift"] == pytest.approx(1.0)


def test_record_and_list_snapshots(store):
    store.record_snapshot({"metric": "cosine-centroid", "drift": 0.3,
                           "similarity": 0.7, "n_current": 3, "n_historical": 2})
    snaps = store.list_snapshots()
    assert len(snaps) == 1 and snaps[0]["drift"] == pytest.approx(0.3)
    assert snaps[0]["n_current"] == 3


# ── Embedding lane (honest failure modes) ───────────────────────────────────

class _Resp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return json.dumps(self._p).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_lane_embed_success(monkeypatch):
    monkeypatch.setattr(corpus_drift.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp({"embedding": [0.1, 0.2, 0.3]}))
    lane = corpus_drift.EmbeddingLane()
    assert lane.embed("hi") == [0.1, 0.2, 0.3]
    assert lane.dim == 3 and lane.available() is True


def test_lane_unreachable_raises_honestly(monkeypatch):
    def boom(req, timeout=None):
        raise corpus_drift.urllib.error.URLError("connection refused")
    monkeypatch.setattr(corpus_drift.urllib.request, "urlopen", boom)
    lane = corpus_drift.EmbeddingLane()
    with pytest.raises(corpus_drift.EmbeddingUnavailable):
        lane.embed("hi")
    assert lane.available() is False


def test_lane_http_error_raises_honestly(monkeypatch):
    def boom(req, timeout=None):
        raise corpus_drift.urllib.error.HTTPError(
            "http://x", 500, "boom", {}, io.BytesIO(b"cudaMalloc failed"))
    monkeypatch.setattr(corpus_drift.urllib.request, "urlopen", boom)
    with pytest.raises(corpus_drift.EmbeddingUnavailable) as ei:
        corpus_drift.EmbeddingLane().embed("hi")
    assert "500" in str(ei.value)


def test_lane_empty_text_raises():
    with pytest.raises(corpus_drift.EmbeddingUnavailable):
        corpus_drift.EmbeddingLane().embed("   ")


# ── High-level surfaces ─────────────────────────────────────────────────────

def test_vector_search_returns_matches(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("r2", "corpus", "b", [0, 1, 0, 0])
    out = corpus_drift.vector_search("alpha", store=store, lane=_FakeLane([1, 0, 0, 0]))
    assert out["available"] is True and out["count"] == 2
    assert out["matches"][0]["record_id"] == "r1"


def test_vector_search_honest_when_lane_down(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    out = corpus_drift.vector_search("alpha", store=store, lane=_FakeLane(fail=True))
    assert out["available"] is False and out["matches"] == []
    assert "unreachable" in out["reason"]


def test_vector_search_needs_a_query(store):
    out = corpus_drift.vector_search("  ", store=store, lane=_FakeLane())
    assert out["available"] is False and "query" in out["reason"]


def test_drift_report_available_with_both_sources(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("s1", "sqp", "q", [1, 0, 0, 0])
    rep = corpus_drift.drift_report(store=store, persist=False)
    assert rep["available"] is True and rep["drift"] == 0.0 and rep["metric"] == "cosine-centroid"


def test_drift_report_honest_when_insufficient(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])  # no SQP vectors
    rep = corpus_drift.drift_report(store=store, persist=False)
    assert rep["available"] is False and rep["n_historical"] == 0


def test_embed_pending_corpus_counts(store):
    store.conn.execute("INSERT INTO corpus_records (id, source, source_id, title, summary) "
                       "VALUES ('c1','doc','d1','Title one','sum')")
    store.conn.commit()
    out = corpus_drift.embed_pending_corpus(store, _FakeLane(), limit=10)
    assert out["embedded"] == 1 and store.count("corpus") == 1
    # second pass embeds nothing new
    again = corpus_drift.embed_pending_corpus(store, _FakeLane(), limit=10)
    assert again["embedded"] == 0


def test_embed_pending_corpus_stops_honestly_when_lane_down(store):
    store.conn.execute("INSERT INTO corpus_records (id, source, source_id, title) "
                       "VALUES ('c1','doc','d1','Title')")
    store.conn.commit()
    out = corpus_drift.embed_pending_corpus(store, _FakeLane(fail=True), limit=10)
    assert out["embedded"] == 0 and out["errors"]


def test_embed_pending_sqp_is_idempotent(store):
    store.conn.execute("INSERT INTO search_query_performance (id, query) VALUES ('q1','ssg bomber')")
    store.conn.commit()
    lane = _FakeLane()
    out = corpus_drift.embed_pending_sqp(store, lane, limit=10)
    assert out["embedded"] == 1
    again = corpus_drift.embed_pending_sqp(store, lane, limit=10)
    assert again["embedded"] == 0


# ── Tools ───────────────────────────────────────────────────────────────────

def test_tools_registered_and_in_focus():
    for name in ("corpus_vector_search", "corpus_drift"):
        assert name in chat_tools.TOOLS
        assert name in shell_focus.tools_for_focus("research")
        assert name in shell_focus.tools_for_focus("grow")


def test_vector_tool_returns_matches(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    ctx = {"db": None, "account_id": "acct-1", "vector_store": store,
           "embed_lane": _FakeLane([1, 0, 0, 0])}
    out = chat_tools.run_tool("corpus_vector_search", {"query": "alpha"}, ctx)
    assert out["ok"] is True and out["data"]["card"]["title"] == "Corpus (semantic)"
    assert out["data"]["matches"][0]["record_id"] == "r1"


def test_vector_tool_honest_when_lane_down(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    ctx = {"db": None, "account_id": "acct-1", "vector_store": store,
           "embed_lane": _FakeLane(fail=True)}
    out = chat_tools.run_tool("corpus_vector_search", {"query": "alpha"}, ctx)
    assert out["ok"] is True and "unavailable" in out["summary"]
    assert out["data"]["matches"] == []


def test_vector_tool_needs_query(store):
    out = chat_tools.run_tool("corpus_vector_search", {"query": " "},
                              {"vector_store": store, "embed_lane": _FakeLane()})
    assert out["ok"] is False


def test_drift_tool_reports_measured_value(store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("s1", "sqp", "q", [0, 1, 0, 0])
    out = chat_tools.run_tool("corpus_drift", {}, {"vector_store": store})
    assert out["ok"] is True and out["data"]["card"]["title"] == "Embedding drift"
    assert out["data"]["drift"]["drift"] == pytest.approx(1.0)


def test_drift_tool_honest_when_insufficient(store):
    out = chat_tools.run_tool("corpus_drift", {}, {"vector_store": store})
    assert out["ok"] is True and "not measurable" in out["summary"]


# ── Router ──────────────────────────────────────────────────────────────────

def _patch_shared(monkeypatch, store, lane):
    monkeypatch.setattr(corpus_drift, "open_vector_store", lambda *a, **k: store)
    monkeypatch.setattr(corpus_drift, "EmbeddingLane", lambda *a, **k: lane)


def test_router_vector_search(monkeypatch, store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    _patch_shared(monkeypatch, store, _FakeLane([1, 0, 0, 0]))
    out = corpus_router.search_vector("alpha", limit=5, threshold=None, source=None, acct="acct-1")
    assert out["available"] is True and out["count"] == 1 and out["query"] == "alpha"


def test_router_vector_search_honest_when_lane_down(monkeypatch, store):
    _patch_shared(monkeypatch, store, _FakeLane(fail=True))
    out = corpus_router.search_vector("alpha", limit=5, threshold=None, source=None, acct="acct-1")
    assert out["available"] is False


def test_router_drift(monkeypatch, store):
    store.upsert("r1", "corpus", "a", [1, 0, 0, 0])
    store.upsert("s1", "sqp", "q", [1, 0, 0, 0])
    _patch_shared(monkeypatch, store, _FakeLane())
    out = corpus_router.drift(persist=False, acct="acct-1")
    assert out["available"] is True and out["drift"] == 0.0


def test_router_embed(monkeypatch, store):
    store.conn.execute("INSERT INTO corpus_records (id, source, source_id, title) "
                       "VALUES ('c1','doc','d1','Title')")
    store.conn.commit()
    _patch_shared(monkeypatch, store, _FakeLane())
    out = corpus_router.embed(limit=5, include_sqp=False, acct="acct-1")
    assert out["available"] is True and out["corpus"]["embedded"] == 1
