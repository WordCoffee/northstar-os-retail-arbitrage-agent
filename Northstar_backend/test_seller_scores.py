"""Seller-Tester output scores feed the scorecard (owner instruction 2026-11-08)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import seller_scores  # noqa: E402


BRIEFS = {"briefs": [
    {"id": "ST-001", "category": "supplement_pouch"},
    {"id": "ST-002", "category": "mug", "service": "listings"},
]}


def summary(rows):
    return {"generated_at": "2026-11-08T00:00:00+00:00", "scored": len(rows),
            "passed": sum(1 for row in rows if row.get("passed")), "results": rows}


def test_a_brief_without_a_service_belongs_to_design_studio():
    mapping = seller_scores.brief_services(BRIEFS)
    assert mapping["ST-001"] == "design-studio"
    assert mapping["ST-002"] == "listings"


def test_scores_are_averaged_per_service():
    data = summary([
        {"brief_id": "ST-001", "score": 20, "passed": False},
        {"brief_id": "ST-001", "score": 40, "passed": True},
        {"brief_id": "ST-002", "score": 90, "passed": True},
    ])
    built = seller_scores.build(summary=data, briefs=BRIEFS)
    assert built["services"]["design-studio"]["mean"] == 30.0
    assert built["services"]["design-studio"]["scored"] == 2
    assert built["services"]["listings"]["mean"] == 90.0


def test_a_service_without_output_scores_zero_with_a_reason():
    verdict = seller_scores.score_for("hub", data={"services": {}})
    assert verdict["score"] == 0.0
    assert "no Seller-Tester output" in verdict["evidence"]


def test_a_thin_sample_is_not_a_score():
    data = {"services": {"design-studio": {"mean": 95.0, "scored": 2, "passed": 2}}}
    verdict = seller_scores.score_for("design-studio", data=data)
    assert verdict["score"] == 0.0
    assert "only 2" in verdict["evidence"]


def test_a_full_sample_is_the_measured_mean():
    data = {"services": {"design-studio": {"mean": 41.5, "scored": 30, "passed": 3}}}
    verdict = seller_scores.score_for("design-studio", data=data)
    assert verdict["score"] == 41.5
    assert "30 Seller-Tester outputs" in verdict["evidence"]


def test_no_pass_on_disk_is_an_empty_result_not_a_crash():
    built = seller_scores.build(summary=None, briefs=BRIEFS)
    # None means "read from disk"; with no file the build reports the reason
    assert isinstance(built, dict)
    assert "services" in built


def test_the_live_file_matches_the_registry_shape():
    data = seller_scores._read(seller_scores.OUT)
    if not data:
        pytest.skip("no seller_scores.json in this checkout")
    assert "services" in data
    for service, row in data["services"].items():
        assert isinstance(service, str)
        assert 0.0 <= float(row["mean"]) <= 100.0
        assert int(row["scored"]) >= 1
