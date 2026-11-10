"""Tests for the Bojo competitor tool (`watch_competitor`).

Offline: no network, no database, no disk. The snapshot store is the one
injectable dependency and is faked here — the tool only reads what the store
already persisted, so the fake is a faithful stand-in.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import competitors  # noqa: E402
from bojo_tools.competitors import TOOLS, watch_competitor  # noqa: E402

SNAPSHOT = {
    "asin": "B000000001",
    "title": "Tide Pods 30 ct",
    "data_status": "available",
    "observed_at": "2026-11-01T00:00:00+00:00",
    "fetched_at": "2026-11-01T00:00:00+00:00",
    "buy_box": {"available": True, "price": 24.99, "fulfillment": "FBA"},
    "seller_counts": {"observed_total": 6, "claimed_total": 8, "fba_observed": 4},
    "offers_returned": 6,
    "offers_complete": False,
    "stages": {"detail": "done", "offers": "partial", "sales": "not_requested"},
    "data_gaps": ["offers_returned_count < offer_count"],
    "last_error": None,
}


class FakeStore:
    def __init__(self, snapshots=None, freshness=None, fresh=None, error=None):
        self.snapshots = snapshots or {}
        self.freshness = freshness or {}
        self.fresh = fresh or {}
        self.error = error
        self.calls = []

    def get_snapshot(self, asin):
        self.calls.append(asin)
        if self.error is not None:
            raise self.error
        return self.snapshots.get(asin)

    def snapshot_freshness_status(self, snapshot, stage="offers"):
        return self.freshness.get(snapshot.get("asin"), "unknown")

    def is_fresh_success(self, snapshot):
        return bool(self.fresh.get(snapshot.get("asin"), False))


def test_tools_registry_exports_watch_competitor():
    assert set(TOOLS) == {"watch_competitor"}
    assert TOOLS["watch_competitor"] is watch_competitor


def test_watch_competitor_reports_stored_observations():
    store = FakeStore(
        snapshots={
            "B000000001": dict(SNAPSHOT),
            "B000000002": dict(SNAPSHOT, asin="B000000002"),
        },
        freshness={"B000000001": "fresh", "B000000002": "stale"},
        fresh={"B000000001": True},
    )

    result = watch_competitor(
        ["B000000001", "B000000002", "B000000003"], store=store
    )

    assert result["ok"] is True
    assert result["tool"] == "watch_competitor"
    data = result["data"]
    assert data["stage"] == "offers"
    assert data["watched"] == 3
    assert data["found"] == 2
    assert data["fresh"] == 1
    assert data["stale"] == 1
    assert data["missing"] == ["B000000003"]
    first = data["observations"][0]
    assert first["data_status"] == "available"
    assert first["seller_counts"]["observed_total"] == 6
    assert first["offers_complete"] is False
    assert first["fresh_success"] is True
    assert first["data_gaps"] == ["offers_returned_count < offer_count"]
    json.dumps(result)


def test_watch_competitor_accepts_a_single_asin_and_a_stage():
    store = FakeStore(
        snapshots={"B000000001": dict(SNAPSHOT)},
        freshness={"B000000001": "fresh"},
    )

    result = watch_competitor("B000000001", stage="sales", store=store)

    assert result["ok"] is True
    assert result["data"]["stage"] == "sales"
    assert store.calls == ["B000000001"]


def test_watch_competitor_with_nothing_stored_is_a_business_failure():
    store = FakeStore(snapshots={})

    result = watch_competitor(["B000000001", "not-an-asin"], store=store)

    assert result["ok"] is False
    assert result["tool"] == "watch_competitor"
    assert result["reason"] == (
        "no stored competitor observation for B000000001, not-an-asin"
    )


def test_watch_competitor_store_error_is_reported_not_raised():
    store = FakeStore(error=RuntimeError("snapshot store is corrupt"))

    result = watch_competitor("B000000001", store=store)

    assert result["ok"] is False
    assert result["reason"].startswith(
        "competitor snapshot read failed for B000000001: RuntimeError"
    )


def test_watch_competitor_programmer_errors_raise():
    with pytest.raises(TypeError):
        watch_competitor(5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        watch_competitor([5])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        watch_competitor("B000000001", stage=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        watch_competitor("B000000001", stage="buybox")


def test_default_store_is_the_real_snapshot_store():
    import market_snapshot_store

    assert competitors._default_store() is market_snapshot_store
    assert watch_competitor.__defaults__[-1] is None
