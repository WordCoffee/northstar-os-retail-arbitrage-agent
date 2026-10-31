"""Deterministic local model routing: intent, preferred lane, explicit fallback."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lane_policy as mr


def test_classify_code_edit_by_path_and_code_fence():
    assert mr.classify("please refactor this file", path="pkg/mod.py") == "code_edit"
    assert mr.classify("```python\ndef f(): pass\n```") == "code_edit"


def test_classify_reasoning():
    assert mr.classify("why does this fail? give me the root cause") == "reasoning"
    assert mr.classify("prove the algorithm is O(n log n)") == "reasoning"


def test_classify_orchestration():
    assert mr.classify("plan the multi-step workflow and delegate to agents") == "orchestration"


def test_classify_defaults_to_the_interactive_coder():
    assert mr.classify("hello") == "code_edit"


def test_route_uses_the_preferred_lane_when_installed():
    out = mr.route("reasoning", available={"northstaros-reasoner": True,
                                           "northstaros-27b-coder": True})
    assert out["lane"] == "northstaros-reasoner"
    assert out["fallback"] is False


def test_route_records_a_fallback_instead_of_pretending():
    out = mr.route("reasoning", available={"northstaros-27b-coder": True})
    assert out["lane"] == "northstaros-27b-coder"
    assert out["requested_lane"] == "northstaros-reasoner"
    assert out["fallback"] is True
    assert "not_installed" in out["reason"]


def test_route_refuses_when_nothing_is_installed():
    with pytest.raises(mr.NoModelAvailable):
        mr.route("code_edit", available={})


def test_route_uses_classification_when_intent_is_omitted():
    out = mr.route(None, "add a method to this class", path="x.py",
                   available={"northstaros-27b-coder": True})
    assert out["intent"] == "code_edit"
    assert out["lane"] == "northstaros-27b-coder"


def test_describe_reports_missing_policy_lanes():
    d = mr.describe(available={"northstaros-27b-coder": True})
    assert "northstaros-27b-coder" in d["installed"]
    assert "northstaros-reasoner" in d["missing"]
    assert d["routes"]["reasoning"] == "northstaros-reasoner"


def test_installed_lanes_sees_the_local_coder_file():
    lanes = mr.installed_lanes()
    assert lanes.get("northstaros-27b-coder") is True
