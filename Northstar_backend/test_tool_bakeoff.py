"""D17 bake-off tests. No subprocess, no network.

The run path is exercised by `python tools/tool_bakeoff.py --run`; these tests
cover the parts that decide the verdict: evidence gating, fact accuracy, detail
counting, normalisation, winner selection and the provenance rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import tool_bakeoff as tb  # noqa: E402


TARGET = tb.TARGETS[0]


def _run(**overrides):
    run = {"tool": "rea", "target": TARGET["id"], "status": "ran", "exit_code": 0,
           "seconds": 2.0, "bytes": 4000, "artefact": "state/bakeoff/out/x.json",
           "command_line": "rea analyze-javascript-application ..."}
    run.update(overrides)
    return run


# ---------------------------------------------------------------- evidence gate
def test_non_zero_exit_is_not_a_result():
    scored = tb.score_cell(_run(exit_code=2), TARGET, artefact_text='{"ok":true}')
    assert scored["status"] == "did-not-run"
    assert "exit code 2" in scored["reason"]


def test_blocked_is_not_a_result():
    scored = tb.score_cell({"tool": "craft-anything", "target": TARGET["id"],
                            "status": "blocked", "reason": "binary not found"},
                           TARGET, artefact_text="{}")
    assert scored["status"] == "did-not-run"
    assert scored["reason"] == "binary not found"


def test_missing_artefact_is_not_a_result():
    scored = tb.score_cell(_run(artefact="state/bakeoff/out/does-not-exist.json"), TARGET)
    assert scored["status"] == "did-not-run"
    assert "artefact" in scored["reason"]


def test_error_payload_is_not_a_result():
    payload = json.dumps({"error": {"code": "feature_missing", "message": "clean room"}})
    scored = tb.score_cell(_run(), TARGET, artefact_text=payload)
    assert scored["status"] == "did-not-run"
    assert "error" in scored["reason"]


def test_unparsable_artefact_is_not_a_result():
    scored = tb.score_cell(_run(), TARGET, artefact_text="not json at all")
    assert scored["status"] == "did-not-run"


# ---------------------------------------------------------------- scoring
def test_accuracy_counts_ground_truth_facts():
    payload = json.dumps({"modules": ["Controller", "Model", "View"]})
    scored = tb.score_cell(_run(), TARGET, artefact_text=payload)
    assert scored["status"] == "ran"
    assert scored["facts_found"] == 3
    assert scored["facts_total"] == 10
    assert scored["accuracy"] == 0.3
    assert "Store" in scored["facts_missing"]


def test_detail_ignores_hash_lists():
    hashes = {"ids": [f"jsrg_unknown_{index:064x}" for index in range(500)]}
    names = {"modules": ["Controller", "Model", "View", "Store"]}
    assert tb.detail_count(hashes) == 0
    assert tb.detail_count(names) == 4


def test_detail_is_capped_at_one():
    payload = json.dumps({"names": [f"name-{index}" for index in range(2000)]})
    scored = tb.score_cell(_run(), TARGET, artefact_text=payload)
    assert scored["detail"] == 1.0


def test_token_estimate_is_bytes_over_four():
    scored = tb.score_cell(_run(bytes=4000), TARGET,
                           artefact_text=json.dumps({"Controller": 1}))
    assert scored["tokens_est"] == 1000


# ---------------------------------------------------------------- composites
def _scored(tool, accuracy, detail, seconds, tokens):
    return {"tool": tool, "target": TARGET["id"], "status": "ran",
            "accuracy": accuracy, "facts_found": int(accuracy * 10), "facts_total": 10,
            "detail": detail, "seconds": seconds, "tokens_est": tokens,
            "bytes": tokens * 4, "reliability": 1.0}


def test_composite_rewards_speed_and_tokens_when_accuracy_ties():
    rows = tb.add_composites([_scored("rea", 1.0, 1.0, 10.0, 2_000_000),
                              _scored("craft-anything", 1.0, 1.0, 0.1, 20_000)])
    by_tool = {row["tool"]: row for row in rows}
    assert by_tool["craft-anything"]["composite"] > by_tool["rea"]["composite"]
    assert by_tool["rea"]["speed_norm"] == 0.01
    assert by_tool["craft-anything"]["speed_norm"] == 1.0


def test_composite_keeps_accuracy_dominant():
    rows = tb.add_composites([_scored("rea", 1.0, 1.0, 10.0, 2_000_000),
                              _scored("craft-anything", 0.1, 0.1, 0.1, 20_000)])
    assert {row["tool"]: row["composite"] for row in rows}["rea"] > 0.4


def test_did_not_run_rows_have_no_composite():
    rows = tb.add_composites([{"tool": "rea", "target": TARGET["id"],
                               "status": "did-not-run", "reason": "exit code 1"}])
    assert rows[0]["composite"] is None


# ---------------------------------------------------------------- decision
def test_decide_picks_highest_composite_and_second_as_backup():
    rows = [{"tool": "rea", "status": "ran", "composite": 0.7, "seconds": 9.0,
             "accuracy": 1.0, "facts_found": 10, "facts_total": 10},
            {"tool": "craft-anything", "status": "ran", "composite": 0.86, "seconds": 0.1,
             "accuracy": 0.9, "facts_found": 9, "facts_total": 10}]
    decision = tb.decide_target(TARGET, rows)
    assert decision["default"] == "craft-anything"
    assert decision["backup"] == "rea"
    assert decision["target"] == TARGET["id"]


def test_decide_reports_no_result_when_neither_ran():
    decision = tb.decide_target(TARGET, [{"tool": "rea", "status": "did-not-run",
                                          "composite": None}])
    assert decision["verdict"] == "no-result"
    assert decision["default"] is None


# ---------------------------------------------------------------- provenance
def test_provenance_rows_match_the_csv_header():
    rows = tb.provenance_rows()
    assert len(rows) == 2
    assert tb.provenance_csv(rows).splitlines()[0] == (
        "component,status,source,license,reviewer,notes")
    assert any("MIT" in row["license"] for row in rows)
    assert any("Apache" in row["license"] for row in rows)


def test_amazon_is_not_a_target():
    for target in tb.TARGETS:
        assert target.get("url") is None or "amazon" not in target["url"].lower()
        assert "amazon" not in (target.get("path") or "").lower()


def test_commands_are_explicit_about_deep_mode_and_format():
    command = tb.build_command("rea", TARGET)
    assert command[1] == "analyze-javascript-application"
    assert "--format" in command and command[command.index("--format") + 1] == "json"
    if tb.tool_binary("craft-anything"):
        craft = tb.build_command("craft-anything", TARGET)
        assert "--deep" in craft
        assert craft[craft.index("--output-format") + 1] == "json"


def test_parser_defaults_to_score_only():
    args = tb.build_parser().parse_args([])
    assert args.run is False
    assert args.score_only is False  # no --run means sweep(run=False)


def test_weights_sum_to_one():
    assert round(sum(tb.WEIGHTS.values()), 6) == 1.0
