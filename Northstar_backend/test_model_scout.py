"""D16 Model Scout tests. No network, no Ollama, no GPU.

Everything here is the maths and the plans: eval parsing, scoring, the swap
rule, the leaderboard write and the restore plan. The measurement path is the
Director's GPU run (`model_scout.py --run`), which these tests never call.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import model_scout as ms  # noqa: E402


# ---------------------------------------------------------------- eval sets
def test_router_eval_has_18_unique_cases_and_known_lanes():
    data = ms.load_eval("router")
    assert len(data["cases"]) == 18
    assert data["items"] == 18
    assert len({case["id"] for case in data["cases"]}) == 18
    lanes = set(data["lane_definitions"])
    assert {case["expect"] for case in data["cases"]} <= lanes
    assert set(ms.LANE_ALIASES.values()) <= lanes
    assert data["sha256"]


def test_json_eval_has_10_cases_each_with_a_schema():
    data = ms.load_eval("json_adherence")
    assert len(data["cases"]) == 10
    assert all(isinstance(case["schema"], dict) for case in data["cases"])
    assert data["system"]


def test_eval_item_count_mismatch_is_an_error(tmp_path):
    path = tmp_path / "router.json"
    path.write_text(json.dumps({"name": "router", "items": 2,
                                "lane_definitions": {"coder": "x"},
                                "cases": [{"id": "a", "intent": "x", "expect": "coder"}]}))
    with pytest.raises(ValueError):
        _load_from(path)


def _load_from(path: Path):
    original = ms.eval_path
    ms.eval_path = lambda name: path
    try:
        return ms.load_eval("router")
    finally:
        ms.eval_path = original


# ---------------------------------------------------------------- lane parsing
@pytest.mark.parametrize("reply,expected", [
    ("coder", "coder"),
    ("The lane is coder.", "coder"),
    ('{"lane": "vision"}', "vision"),
    ('{"lane": "gui-grounding"}', "gui_grounding"),
    ("GUI_GROUNDING", "gui_grounding"),
    ("embeddings", "embeddings"),
    ("image", "image"),
    ("bojo", "bojo"),
    ("This needs a render", "image"),
    ("I do not know", None),
])
def test_parse_lane(reply, expected):
    assert ms.parse_lane(reply) == expected


def test_parse_lane_prefers_json_over_prose():
    assert ms.parse_lane('{"lane":"vision"} although coder sounds close') == "vision"


# ---------------------------------------------------------------- router maths
def test_router_scoring_counts_and_accuracy():
    data = ms.load_eval("router")
    replies = [case["expect"] for case in data["cases"]]
    result = ms.score(data, replies)
    assert (result["correct"], result["items"]) == (18, 18)
    assert result["accuracy"] == 1.0
    replies[0] = "no idea"
    result = ms.score(data, replies)
    assert result["correct"] == 17


def test_router_baseline_six_of_eighteen_is_reproducible():
    data = ms.load_eval("router")
    replies = [case["expect"] for case in data["cases"]]
    for index in range(12):
        replies[index] = "unknown"
    assert ms.score(data, replies)["correct"] == 6


# ---------------------------------------------------------------- json maths
VALID_JSON_REPLIES = [
    '{"lane":"coder","confidence":0.9}',
    '{"tool":"read","args":{"path":"a.py"}}',
    '["bojo","coder","vision"]',
    '{"ok":true,"count":3}',
    '{"status":"queued"}',
    '{"items":[{"id":1,"done":true},{"id":2,"done":false}]}',
    '{"role":"vision","model":"llava:7b","vram_gb":5.19}',
    '{"plan":{"steps":["open","read"]},"dry_run":true}',
    '{"error":null,"data":{"rows":[]}}',
    '{"score":88,"grade":"B"}',
]


def test_json_scoring_all_valid_is_ten_of_ten():
    data = ms.load_eval("json_adherence")
    result = ms.score(data, VALID_JSON_REPLIES)
    assert result["correct"] == 10
    assert result["strict"] == 10
    assert all(row["ok"] for row in result["rows"])


def test_json_prose_around_valid_json_is_not_adherent():
    data = ms.load_eval("json_adherence")
    replies = list(VALID_JSON_REPLIES)
    replies[0] = 'Sure, here is the object: {"lane":"coder","confidence":0.9}'
    result = ms.score(data, replies)
    assert result["correct"] == 9
    assert result["rows"][0]["strict"] is False


def test_json_extra_key_and_enum_fail():
    data = ms.load_eval("json_adherence")
    replies = list(VALID_JSON_REPLIES)
    replies[0] = '{"lane":"coder","confidence":0.9,"why":"because"}'
    replies[4] = '{"status":"blocked"}'
    result = ms.score(data, replies)
    assert result["correct"] == 8


def test_validate_reports_the_path_of_the_problem():
    schema = {"type": "object", "required": ["a"], "additionalProperties": False,
              "properties": {"a": {"type": "integer", "minimum": 2}}}
    problems = ms.validate({"a": 1}, schema)
    assert any("$.a" in problem for problem in problems)
    assert any("minimum" in problem for problem in problems)
    assert ms.validate({"a": 2}, schema) == []


def test_fenced_json_is_strict():
    value, strict, _note = ms.extract_json('```json\n{"ok": true}\n```')
    assert value == {"ok": True} and strict is True


# ---------------------------------------------------------------- swap rule
def _fits(vram=3.0, ram=5.0, budget=3.5):
    return ms.fit_check(budget, vram, ram)


def test_swap_requires_two_clear_items():
    fit = _fits()
    assert ms.decide(10, 12, 18, fit)["verdict"] == "replace"
    assert ms.decide(10, 11, 18, fit)["verdict"] == "keep-incumbent"
    assert ms.decide(10, 11, 18, fit)["delta"] == 1


def test_swap_refuses_a_candidate_over_its_budget():
    fit = _fits(vram=4.2, budget=3.5)
    decision = ms.decide(10, 14, 18, fit)
    assert decision["verdict"] == "keep-incumbent"
    assert "does not fit" in decision["reason"]


def test_swap_refuses_on_the_ram_floor():
    fit = _fits(vram=3.0, ram=1.5)
    assert fit["ok"] is False
    assert ms.decide(10, 14, 18, fit)["verdict"] == "keep-incumbent"


def test_unmeasured_incumbent_holds():
    decision = ms.decide(None, 14, 18, _fits())
    assert decision["verdict"] == "hold"


def test_fit_check_unknown_budget_is_a_refusal():
    assert ms.fit_check(None, 3.0, 5.0)["ok"] is False


def test_budget_constants_match_manager():
    import gpu_budget

    assert ms.ROLE_BUDGET_GB == gpu_budget.ROLE_BUDGET_GB
    assert ms.RESERVE_GB == gpu_budget.RESERVE_GB
    assert ms.RAM_FLOOR_GB == gpu_budget.RAM_FLOOR_GB


# ---------------------------------------------------------------- leaderboard
def test_build_leaderboard_records_eval_hash_and_unmeasured_roles():
    leaderboard = ms.build_leaderboard(ms.load_roles(), {})
    assert set(leaderboard["roles"]) >= {"bojo-router", "planner-coder", "vision"}
    assert leaderboard["eval_sets"]["router"]["items"] == 18
    assert leaderboard["eval_sets"]["json_adherence"]["items"] == 10
    assert leaderboard["roles"]["bojo-router"]["recommendation"]["verdict"] == "unmeasured"
    assert leaderboard["swap_rule"]["auto_swap"] is False


def test_write_leaderboard_writes_tracked_file_and_intel_mirror(tmp_path):
    leaderboard = ms.build_leaderboard(ms.load_roles(), {})
    path = tmp_path / "leaderboard.json"
    mirror = tmp_path / "intel" / "models.json"
    written = ms.write_leaderboard(leaderboard, path=path, mirror=mirror)
    assert json.loads(path.read_text())["schema"] == 1
    mirrored = json.loads(mirror.read_text())
    assert mirrored["source"].endswith("leaderboard.json")
    assert "bojo-router" in mirrored["roles"]
    assert set(written) == {"leaderboard", "mirror"}


def _measured(model, role, correct, vram=3.0, ram=5.0, items=18):
    return {"model": model, "role": role, "status": "measured", "correct": correct,
            "items": items, "accuracy": correct / items, "vram_gb": vram,
            "ram_free_gb": ram, "latency_ms": 100, "eval": "router"}


def test_recommendation_replaces_only_on_margin_and_fit():
    roles = ms.load_roles()
    measurements = {
        "bojo:latest": _measured("bojo:latest", "bojo-router", 9),
        "qwen3.5:4b": _measured("qwen3.5:4b", "bojo-router", 13, vram=3.3),
        "gemma3:4b": _measured("gemma3:4b", "bojo-router", 10, vram=3.4),
    }
    leaderboard = ms.build_leaderboard(roles, measurements)
    entry = leaderboard["roles"]["bojo-router"]
    assert entry["recommendation"]["verdict"] == "replace"
    assert entry["recommendation"]["model"] == "qwen3.5:4b"
    assert entry["quarantine"]["from"] == "bojo:latest"
    assert entry["quarantine"]["delete_original"] is False


def test_recommendation_keeps_incumbent_when_no_candidate_clears_margin():
    roles = ms.load_roles()
    measurements = {
        "bojo:latest": _measured("bojo:latest", "bojo-router", 12),
        "qwen3.5:4b": _measured("qwen3.5:4b", "bojo-router", 13),
    }
    leaderboard = ms.build_leaderboard(roles, measurements)
    assert leaderboard["roles"]["bojo-router"]["recommendation"]["verdict"] == "keep-incumbent"
    assert leaderboard["roles"]["bojo-router"]["quarantine"] is None


def test_not_installed_candidate_is_recorded_not_proposed():
    roles = ms.load_roles()
    measurements = {
        "bojo:latest": _measured("bojo:latest", "bojo-router", 12),
        "qwen9:99b": {"model": "qwen9:99b", "role": "bojo-router",
                      "status": "not_installed", "reason": "not in /api/tags"},
    }
    leaderboard = ms.build_leaderboard(roles, measurements)
    assert leaderboard["roles"]["bojo-router"]["recommendation"]["verdict"] == "keep-incumbent"
    assert leaderboard["roles"]["bojo-router"]["measurements"]["qwen9:99b"]["status"] == "not_installed"


# ---------------------------------------------------------------- restore
def test_quarantine_plan_copies_and_never_deletes():
    plan = ms.quarantine_plan("bojo:latest", now=datetime(2026, 11, 8, tzinfo=timezone.utc))
    assert plan["tag"] == "bojo:quarantine-20261108-000000"
    assert plan["delete_original"] is False
    assert plan["commands"][0] == "ollama cp bojo:latest bojo:quarantine-20261108-000000"


def test_restore_plan_returns_the_recorded_incumbent():
    roles = ms.load_roles()
    measurements = {"bojo:latest": _measured("bojo:latest", "bojo-router", 9),
                    "qwen3.5:4b": _measured("qwen3.5:4b", "bojo-router", 14)}
    leaderboard = ms.build_leaderboard(roles, measurements)
    tag = leaderboard["roles"]["bojo-router"]["quarantine"]["tag"]
    plan = ms.restore_plan("bojo-router", leaderboard)
    assert plan["model"] == "bojo:latest"
    assert plan["quarantine_tag"] == tag
    assert f"ollama cp {tag} bojo:latest" in plan["commands"]
    assert plan["dry_run"] is True and plan["apply"] is False


def test_restore_plan_for_unmeasured_role_still_verifies_the_tag():
    leaderboard = ms.build_leaderboard(ms.load_roles(), {})
    plan = ms.restore_plan("embeddings", leaderboard)
    assert plan["commands"] == ["ollama show qwen3-embedding:0.6b"]


def test_restore_unknown_role_is_an_error():
    with pytest.raises(KeyError):
        ms.restore_plan("nope", ms.build_leaderboard(ms.load_roles(), {}))


# ---------------------------------------------------------------- cli surface
def test_cli_exposes_run_and_restore():
    parser = ms.build_parser()
    args = parser.parse_args(["--run", "--role", "bojo-router", "--models", "qwen3.5:4b"])
    assert args.run is True and args.role == "bojo-router"
    assert parser.parse_args(["--restore", "bojo-router"]).restore == "bojo-router"
    assert parser.parse_args(["--plan"]).plan is True
