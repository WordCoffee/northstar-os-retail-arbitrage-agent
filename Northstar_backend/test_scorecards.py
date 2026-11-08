"""D4 - scorecards: measured, not asserted.

The pass rule is the point of these tests: a service is at the bar only when **every**
dimension clears 85, so a strong average cannot hide a dimension nobody measures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import scorecards as S  # noqa: E402


@pytest.fixture()
def world(tmp_path, monkeypatch):
    registry = tmp_path / "services.json"
    registry.write_text(json.dumps({"services": [
        {"id": "alpha", "label": "Alpha", "group": "Create", "kind": "studio",
         "route": "/alpha", "tools": ["make_thing"]},
        {"id": "beta", "label": "Beta", "group": "Sourcing", "kind": "workspace",
         "route": "/beta", "tools": []},
    ]}), encoding="utf-8")
    idlist = tmp_path / "ids.json"
    idlist.write_text(json.dumps({"ids": [
        "test_alpha_api.py::test_alpha_renders",
        "test_alpha_api.py::test_alpha_saves",
        "test_zulu.py::test_unrelated",
    ]}), encoding="utf-8")
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"findings": [
        {"check": "img-no-alt", "severity": "medium", "file": "src/rooms/alpha/Panel.jsx"},
        {"check": "dead-module", "severity": "medium", "file": "src/lib/serviceGate.js"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(S, "REGISTRY", registry)
    monkeypatch.setattr(S, "IDLIST", idlist)
    monkeypatch.setattr(S, "SCAN", scan)
    monkeypatch.setattr(S, "SCORES", tmp_path / "scorecards.json")
    monkeypatch.setattr(S, "SPEC", tmp_path / "TARGET_SPEC.md")
    monkeypatch.setattr(S, "SERVICE_TESTS", {"alpha": ["test_alpha"], "beta": []})
    monkeypatch.setattr(S, "_HAYSTACK", None)
    monkeypatch.setattr(S, "_backend_text", lambda: "def make_thing(): pass")
    return tmp_path


def test_a_service_with_its_own_test_ids_scores_works(world):
    result = S.measure()
    alpha = next(row for row in result["services"] if row["id"] == "alpha")

    assert alpha["dimensions"]["works"]["score"] == 100.0
    assert "2 test id" in alpha["dimensions"]["works"]["evidence"]


def test_a_service_with_no_test_ids_scores_zero_and_says_why(world):
    result = S.measure()
    beta = next(row for row in result["services"] if row["id"] == "beta")

    assert beta["dimensions"]["works"]["score"] == 0.0
    assert beta["dimensions"]["works"]["evidence"] == "no test id maps to this service"


def test_a_declared_tool_that_is_not_wired_scores_zero(world):
    result = S.measure()
    beta = next(row for row in result["services"] if row["id"] == "beta")
    assert beta["dimensions"]["complete"]["score"] == 0.0
    assert "no Bojo tool declared" in beta["dimensions"]["complete"]["evidence"]


def test_a_finding_about_the_service_lowers_usable_but_a_repo_wide_one_does_not(world):
    result = S.measure()
    alpha = next(row for row in result["services"] if row["id"] == "alpha")
    beta = next(row for row in result["services"] if row["id"] == "beta")

    assert alpha["dimensions"]["usable"]["score"] == 90.0
    assert beta["dimensions"]["usable"]["score"] == 100.0
    # The dead module belongs to nobody, so it is reported once, globally.
    assert [f["check"] for f in result["global_findings"]] == ["dead-module"]


def test_the_bar_is_per_dimension_not_an_average(world):
    """Alpha has 100 on two dimensions and 0 on `measured` and `seller`; not at the bar."""
    result = S.measure()
    alpha = next(row for row in result["services"] if row["id"] == "alpha")

    assert alpha["score"] > 40          # the average still looks plausible
    assert alpha["meets_bar"] is False  # and the weakest dimension still fails
    assert "seller" in alpha["dimensions"]
    assert alpha["dimensions"]["seller"]["score"] == 0.0
    assert "no Seller-Tester output" in alpha["dimensions"]["seller"]["evidence"]
    assert result["at_bar"] == []


def test_artefacts_alone_cannot_reach_the_bar(world):
    """A service whose only evidence is passing tests scores 60 on `correct`, not 100."""
    result = S.measure()
    alpha = next(row for row in result["services"] if row["id"] == "alpha")
    assert alpha["dimensions"]["correct"]["score"] == 60.0
    assert "Seller-Tester" in alpha["dimensions"]["correct"]["evidence"]


def test_the_gap_is_impact_times_the_distance_to_the_bar(world):
    result = S.measure()
    for row in result["services"]:
        expected = round(row["impact"] * max(0.0, S.BAR - row["score"]), 1)
        assert row["gap"] == expected


def test_the_spec_is_written_from_the_measurement(world):
    S.main([])
    text = S.SPEC.read_text(encoding="utf-8")
    assert "Bar: **85 on every dimension**" in text
    assert "Scores are measured, never asserted" in text
    assert "At the bar today: **0 of 2**" in text
    assert "Repo-wide findings (not charged to any service)" in text
