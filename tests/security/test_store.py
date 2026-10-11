"""Phase 4 tests: snapshot store, retail gates, tenant isolation, Scrapling tiers."""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from northstar.gateway.scrapling_policy import (
    ALLOWED_TIERS,
    FORBIDDEN_FEATURES,
    assert_scrapling_feature,
    assert_scrapling_tier,
    healed_selector_record,
)
from northstar.policy import PolicyDenied
from northstar.store import SnapshotStore, StoreValidationError

BASE = dict(
    source="lightpanda-connect",
    url="http://allowed.example/page",
    observed_at="2026-10-11T00:00:00Z",
    data_class="live-verified",
)


def _store() -> SnapshotStore:
    return SnapshotStore(":memory:")


class TestSnapshots:
    def test_roundtrip_and_null_first(self):
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        record = store.get_snapshot(sid, tenant_id="tenant-a")
        assert record["snapshot_id"] == sid
        assert record["confidence"] is None  # unknown stays NULL
        assert record["freshness_status"] == "UNKNOWN"  # never coerced
        assert record["content_hash"] is None
        assert record["limitations"] is None

    def test_simulated_can_never_be_written(self):
        store = _store()
        with pytest.raises(PolicyDenied):
            store.put_snapshot(
                tenant_id="tenant-a", **{**BASE, "data_class": "SIMULATED"}
            )

    def test_unknown_data_class_rejected(self):
        store = _store()
        with pytest.raises(StoreValidationError):
            store.put_snapshot(
                tenant_id="tenant-a", **{**BASE, "data_class": "made-up"}
            )

    def test_confidence_range_enforced_not_coerced(self):
        store = _store()
        with pytest.raises(StoreValidationError):
            store.put_snapshot(tenant_id="tenant-a", confidence=1.5, **BASE)
        sid = store.put_snapshot(tenant_id="tenant-a", confidence=0.7, **BASE)
        assert store.get_snapshot(sid, tenant_id="tenant-a")["confidence"] == 0.7

    def test_required_fields_rejected(self):
        store = _store()
        with pytest.raises(StoreValidationError):
            store.put_snapshot(tenant_id="", **BASE)
        with pytest.raises(StoreValidationError):
            store.put_snapshot(
                tenant_id="tenant-a",
                source="",
                url="http://x/",
                observed_at="t",
                data_class="cached",
            )

    def test_tenant_isolation_reads(self):
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        assert store.get_snapshot(sid, tenant_id="tenant-b") is None
        assert store.list_snapshots(tenant_id="tenant-b") == []
        assert [r["snapshot_id"] for r in store.list_snapshots(tenant_id="tenant-a")] == [sid]

    def test_zero_outbound_on_reads(self, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("outbound network attempted from the store")

        monkeypatch.setattr(socket, "getaddrinfo", boom)
        monkeypatch.setattr(socket, "create_connection", boom)
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        assert store.get_snapshot(sid, tenant_id="tenant-a") is not None
        assert store.list_snapshots(tenant_id="tenant-a")


class TestRetailGates:
    def test_gates_roundtrip_and_never_purchase_authorized(self):
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        gates = store.put_retail_gates(
            sid,
            tenant_id="tenant-a",
            resale_eligibility="discovery-only",
            exact_pack_match=None,
            cost_fee_basis=None,
            invoice_path=None,
            operator_approval=None,
        )
        assert gates["purchase_authorized"] == 0
        assert gates["resale_eligibility"] == "discovery-only"
        assert gates["exact_pack_match"] is None  # null-first
        store.assert_not_purchase_authorized(sid, tenant_id="tenant-a")  # no raise

    def test_gates_tenant_isolation(self):
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        assert (
            store.put_retail_gates(sid, tenant_id="tenant-b", resale_eligibility="x")
            is None
        )
        assert store.get_retail_gates(sid, tenant_id="tenant-b") is None

    def test_unknown_gate_field_rejected(self):
        store = _store()
        sid = store.put_snapshot(tenant_id="tenant-a", **BASE)
        with pytest.raises(StoreValidationError):
            store.put_retail_gates(sid, tenant_id="tenant-a", purchase_authorized=1)


class TestScraplingPolicy:
    def test_forbidden_features_refused(self):
        for feature in FORBIDDEN_FEATURES:
            with pytest.raises(PolicyDenied):
                assert_scrapling_feature(feature)
        assert_scrapling_feature("Fetcher") is None  # allowed tier → no raise

    def test_tier_guard(self):
        for tier in ALLOWED_TIERS:
            assert_scrapling_tier(tier)
        with pytest.raises(PolicyDenied):
            assert_scrapling_tier("stealthy")
        with pytest.raises(PolicyDenied):
            assert_scrapling_tier("dynamic")

    def test_our_sources_never_reference_forbidden_features(self):
        root = Path(__file__).resolve().parents[2] / "northstar"
        for path in root.rglob("*.py"):
            if path.name == "scrapling_policy.py":
                continue  # the guard names them by design
            text = path.read_text(encoding="utf-8")
            for feature in (
                "StealthyFetcher",
                "DynamicFetcher",
                "StealthySession",
                "DynamicSession",
            ):
                assert feature not in text, f"{path} references {feature}"
            assert "import scrapling" not in text, f"{path} imports scrapling"

    def test_healed_selectors_never_verified(self):
        record = healed_selector_record(
            selector="div:nth-of-type(3) > a", match_confidence=1.0, url="http://allowed.example/"
        )
        assert record["verified"] is False
        assert record["flagged_for_review"] is True
        bad = healed_selector_record(
            selector="x", match_confidence="nonsense", url="http://allowed.example/"
        )
        assert bad["match_confidence"] == 0.0
        assert bad["verified"] is False
