"""The disposable screen must score a broken candidate, never crash on it."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import screen_lane as sl


def test_a_correct_result_passes():
    ok, detail = sl.summarise_verdict({"approved": 2, "denied": 1, "skipped": 3, "total": 3})
    assert ok is True and detail["skipped"] == 3


def test_a_none_result_is_a_failure_not_a_crash():
    ok, detail = sl.summarise_verdict(None)
    assert ok is False and "NoneType" in detail["reason"]


def test_a_partial_result_fails():
    ok, _ = sl.summarise_verdict({"approved": 2, "denied": 1})
    assert ok is False


def test_the_acceptance_reports_a_raising_module(tmp_path):
    mod = tmp_path / "limits.py"
    mod.write_text("def summarise(rows):\n    raise RuntimeError('boom')\n", encoding="utf-8")
    ok, detail = sl._accept(mod)()
    assert ok is False and "RuntimeError" in detail


def test_the_acceptance_scores_a_none_return(tmp_path):
    mod = tmp_path / "limits.py"
    mod.write_text("def summarise(rows):\n    pass\n", encoding="utf-8")
    ok, detail = sl._accept(mod)()
    assert ok is False and "expected dict" in detail
