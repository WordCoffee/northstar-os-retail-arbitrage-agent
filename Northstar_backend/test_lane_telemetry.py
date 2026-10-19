"""Lane telemetry — measured percentiles and a policy that refuses before data."""
from __future__ import annotations

import sqlite3

import pytest

import lane_telemetry as lt


@pytest.fixture()
def db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "northstar.db"))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def seed(db, lane, values, ok=True, task_class=None):
    for v in values:
        lt.record(db, lane, latency_ms=v, ok=ok, task_class=task_class)


# ── recording ────────────────────────────────────────────────────────────────

def test_record_validates_its_input(db):
    assert lt.record(db, "", latency_ms=10)["ok"] is False
    assert lt.record(db, "local", latency_ms=-1)["ok"] is False
    assert lt.record(db, "local", latency_ms=12.5)["ok"] is True


def test_ensure_table_works_with_a_datalayer_that_has_no_executescript(tmp_path):
    """Regression: the project DataLayer exposes execute/commit only.

    A db.executescript(...) call raised AttributeError, which the caller's error
    handling swallowed — telemetry would have been silently dead in production.
    """
    class DataLayerLike:
        """Mimics data_layer.DataLayer: execute/commit, no executescript."""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            return self._conn.execute(sql, params)

        def commit(self):
            self._conn.commit()

    conn = sqlite3.connect(str(tmp_path / "northstar.db"))
    conn.row_factory = sqlite3.Row
    dl = DataLayerLike(conn)

    assert lt.record(dl, "chat:model", latency_ms=120.0, ok=True, tool_calls=2)["ok"] is True
    out = lt.summary(dl)["lanes"]["chat:model"]
    assert out["samples"] == 1
    assert out["p50_latency_ms"] == 120.0
    conn.close()


def test_ensure_table_works_with_a_northstar_db_container(tmp_path):
    """Regression: the chat turn path passes data_layer.NorthstarDB, a CONTAINER.

    NorthstarDB has no execute() — the raw layer is on ._layer. Calling
    db.execute() raised AttributeError, which the turn path's error handling
    swallowed, leaving the producer silently dead in production.
    """
    class ContainerLike:
        """Mimics data_layer.NorthstarDB: table repositories + ._layer."""

        def __init__(self, layer):
            self._layer = layer

    conn = sqlite3.connect(str(tmp_path / "northstar.db"))
    conn.row_factory = sqlite3.Row

    class LayerLike:
        def execute(self, sql, params=()):
            return conn.execute(sql, params)

        def commit(self):
            conn.commit()

    container = ContainerLike(LayerLike())
    assert lt.record(container, "chat:qwen", latency_ms=2600.0, ok=True, tool_calls=0)["ok"] is True
    got = lt.summary(container)["lanes"]["chat:qwen"]
    assert got["samples"] == 1 and got["p50_latency_ms"] == 2600.0
    conn.close()


def test_an_unusable_handle_is_reported_not_raised():
    out = lt.record(object(), "chat:x", latency_ms=10)
    assert out["ok"] is False
    assert "unsupported db handle" in out["error"]
    assert lt.summary(object())["lanes"] == {}


def test_ensure_table_is_idempotent(db):
    lt.ensure_table(db)
    lt.ensure_table(db)
    assert lt.summary(db)["lanes"] == {}


# ── percentiles are measured, not modelled ───────────────────────────────────

def test_summary_uses_nearest_rank_over_recorded_rows(db):
    seed(db, "local", list(range(1, 41)))          # 1..40
    out = lt.summary(db)["lanes"]["local"]
    assert out["samples"] == 40
    assert out["p50_latency_ms"] == 20.0
    assert out["p95_latency_ms"] == 38.0
    assert out["success_rate"] == 1.0
    assert out["measured"] is True                 # 40 >= MIN_SAMPLES


def test_a_lane_below_the_sample_floor_is_not_reported_as_measured(db):
    seed(db, "local", list(range(10)))
    out = lt.summary(db)["lanes"]["local"]
    assert out["samples"] == 10
    assert out["measured"] is False


def test_success_rate_reflects_failures(db):
    seed(db, "cloud", [100, 110, 120, 130], ok=True)
    lt.record(db, "cloud", latency_ms=900, ok=False)
    out = lt.summary(db)["lanes"]["cloud"]
    assert out["samples"] == 5
    assert out["success_rate"] == 0.8


def test_a_lane_that_never_ran_has_no_entry(db):
    seed(db, "local", [10])
    assert "cloud" not in lt.summary(db)["lanes"]


# ── no policy before data ────────────────────────────────────────────────────

def test_recommend_refuses_when_a_candidate_has_never_run(db):
    seed(db, "local", list(range(30)))
    out = lt.recommend(db, ["local", "cloud"])
    assert out["available"] is False
    assert "never run: cloud" in out["reason"]
    assert "no routing policy is emitted before there is evidence" in out["reason"].lower()


def test_recommend_refuses_when_samples_are_too_thin(db):
    seed(db, "local", list(range(31)))
    seed(db, "cloud", list(range(5)))
    out = lt.recommend(db, ["local", "cloud"])
    assert out["available"] is False
    assert "too few samples" in out["reason"]
    assert out["min_samples"] == lt.MIN_SAMPLES


def test_recommend_chooses_on_measured_evidence_once_there_is_enough(db):
    seed(db, "local", [100] * 30, ok=True)
    seed(db, "cloud", [50] * 30, ok=True)
    for _ in range(5):                             # cloud is faster but flakier
        lt.record(db, "cloud", latency_ms=50, ok=False)
    out = lt.recommend(db, ["cloud", "local"])
    assert out["available"] is True
    assert out["chosen"] == "local"                # success rate wins over latency
    assert out["ranked"] == ["local", "cloud"]
    assert "measured success rate first" in out["basis"]


def test_recommend_breaks_a_success_tie_on_latency(db):
    seed(db, "a", [400] * 30, ok=True)
    seed(db, "b", [120] * 30, ok=True)
    out = lt.recommend(db, ["a", "b"])
    assert out["available"] is True and out["chosen"] == "b"


def test_recommend_needs_candidates(db):
    out = lt.recommend(db, [])
    assert out["available"] is False
    assert "no candidate lanes" in out["reason"]
