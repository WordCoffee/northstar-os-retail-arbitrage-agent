"""Bojo's project-plan tool: visible plan, validated, never auto-executed."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chat_tools


def test_plan_project_returns_a_valid_visible_plan():
    res = chat_tools.run_tool("plan_project", {
        "goal": "Build a pouch label",
        "lanes": ["inspect", "creative"],
        "steps": [{"lane": "inspect", "objective": "measure the plate"},
                  {"lane": "creative", "objective": "compose the label"}],
    }, {})
    assert res["ok"] is True, res.get("error")
    assert res["data"]["errors"] == []
    assert "plan" in res["data"] and len(res["data"]["plan"]["nodes"]) == 2
    rows = res["data"]["card"]["rows"]
    assert [r["label"] for r in rows] == ["measure the plate", "compose the label"]
    assert "not an execution" in res["data"]["note"].lower()


def test_plan_project_refuses_an_empty_goal():
    res = chat_tools.run_tool("plan_project", {"goal": "  "}, {})
    assert res["ok"] is False
    assert "goal" in res["summary"].lower()


def test_plan_project_refuses_a_step_outside_scope():
    res = chat_tools.run_tool("plan_project", {
        "goal": "x", "lanes": ["inspect"],
        "steps": [{"lane": "coding", "objective": "write"}],
    }, {})
    assert res["ok"] is False
    assert "outside scope" in (res.get("error") or "").lower()


def test_plan_project_is_registered_and_offered():
    assert "plan_project" in chat_tools.TOOLS
    names = [t["function"]["name"] for t in chat_tools.ollama_tool_schemas()]
    assert "plan_project" in names
    system = next(s for s in chat_tools.SERVICES if s["id"] == "system")
    assert "plan_project" in system["tools"]
