"""B7 tests — Golden Goose export manifest + no-vendor-leakage contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder import export_manifest as em  # noqa: E402


def _manifest(**overrides):
    base = dict(
        export_id="exp_" + "a" * 32,
        job_id="job_" + "b" * 32,
        export_type="opportunities_json",
        row_count=3,
        columns=["rank", "amazon_asin", "brand", "tier", "net_profit_per_unit"],
        tiers={"HIGH": 1, "MEDIUM": 1, "LOW": 1, "REJECT": 0},
        filters={"roi_floor": 10.0, "min_monthly_sales": 1000, "category": None},
    )
    base.update(overrides)
    return em.build_manifest(**base)


def test_build_manifest_shape_and_version():
    m = _manifest()
    assert m["manifest_version"] == "goose-export/v1"
    assert m["service"] == "golden_goose"
    assert m["currency"] == "USD"
    assert m["export_type"] in em.EXPORT_TYPES
    assert "disclaimer" in m and m["disclaimer"] == em.DEFAULT_DISCLAIMER


def test_unknown_export_type_rejected():
    with pytest.raises(ValueError):
        _manifest(export_type="opportunities_parquet")


def test_valid_manifest_passes_leak_guard():
    assert em.assert_no_export_leakage(_manifest()) is not None


def test_forbidden_key_rejected_any_depth():
    m = _manifest()
    m["provider"] = "X"
    with pytest.raises(em.ExportLeakageError):
        em.assert_no_export_leakage(m)
    m2 = _manifest()
    m2["filters"]["report_path"] = "/srv/reports/x.json"
    with pytest.raises(em.ExportLeakageError):
        em.assert_no_export_leakage(m2)


def test_provider_value_token_rejected():
    m = _manifest()
    m["columns"].append("sourced_via_brightdata")
    with pytest.raises(em.ExportLeakageError):
        em.assert_no_export_leakage(m)


def test_absolute_path_and_secret_shapes_rejected():
    m = _manifest()
    m["notes"] = "C:\\Users\\T2Hol\\reports\\goose.json"
    with pytest.raises(em.ExportLeakageError):
        em.assert_no_export_leakage(m)
    m2 = _manifest()
    m2["notes"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdefghijklmnop"
    with pytest.raises(em.ExportLeakageError):
        em.assert_no_export_leakage(m2)


def test_manifest_has_no_internal_ids_by_default():
    text = str(_manifest()).lower()
    assert "scan_id" not in text
    assert "report_path" not in text
    for tok in ("brightdata", "chocodata", "easyparser", "openwebninja", "unwrangle"):
        assert tok not in text