"""P4-T3 data-rights register + enforcement tests."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation import data_rights as dr


def test_internal_allowed_but_external_blocked_for_sellersprite():
    assert dr.rights("sellersprite_historical_export", dr.USE_INTERNAL) == dr.ALLOWED
    assert dr.customer_display_allowed("sellersprite_historical_export") is False
    assert dr.export_allowed("sellersprite_historical_export") is False


def test_unknown_source_is_blocked():
    assert dr.customer_display_allowed("does_not_exist") is False
    assert dr.rights("does_not_exist", dr.USE_CUSTOMER) == dr.UNKNOWN


def test_manual_observed_capture_is_customer_ok():
    assert dr.customer_display_allowed("manual_observed_capture") is True
    assert dr.export_allowed("manual_observed_capture") is True


def test_customer_safe_rows_excludes_unpermitted_sources():
    rows = [
        {"id": 1, "source": "sellersprite_historical_export"},
        {"id": 2, "source": "manual_observed_capture"},
        {"id": 3, "source": "amazon_catalog_records"},
        {"id": 4, "source": "unknown_src"},
    ]
    kept = dr.customer_safe_rows(rows)
    assert [r["id"] for r in kept] == [2]
    # input not mutated
    assert len(rows) == 4


def test_export_safe_rows_excludes_unpermitted_sources():
    rows = [{"source": "sellersprite_historical_export"},
            {"source": "manual_observed_capture"}]
    assert [r["source"] for r in dr.export_safe_rows(rows)] == ["manual_observed_capture"]


def test_owner_test_mode_does_not_bypass_rights(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    rows = [{"source": "sellersprite_historical_export"}]
    assert dr.customer_safe_rows(rows) == []
    assert dr.customer_display_allowed("sellersprite_historical_export") is False


def test_assert_helpers_raise_typed_errors():
    with pytest.raises(dr.DataRightsError) as e1:
        dr.assert_customer_display("sellersprite_historical_export")
    assert e1.value.code == "customer_display_blocked"
    with pytest.raises(dr.DataRightsError) as e2:
        dr.assert_export("amazon_catalog_records")
    assert e2.value.code == "export_blocked"
    with pytest.raises(dr.DataRightsError) as e3:
        dr.assert_external_ai("manual_observed_capture")
    assert e3.value.code == "external_ai_blocked"


def test_planned_providers_are_not_integrated_and_blocked():
    for key in ("dataforseo", "brightdata", "keepa", "amazon_sp_api", "amazon_ads"):
        assert dr.SOURCES[key].status == dr.NOT_INTEGRATED
        assert dr.customer_display_allowed(key) is False


def test_internal_use_rights_do_not_imply_redistribution():
    # SellerSprite: internal ALLOWED but redistribution UNKNOWN -> blocked
    assert dr.rights("sellersprite_historical_export", dr.USE_INTERNAL) == dr.ALLOWED
    assert dr.external_use_allowed("sellersprite_historical_export", dr.USE_REDISTRIBUTE) is False