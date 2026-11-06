"""The guard must allow new tests and block disappearing ones."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_regression as cr  # noqa: E402


def _junit(tmp_path, rows):
    cases = []
    for cls, name, status in rows:
        inner = ""
        if status == "failed":
            inner = "<failure message='boom'>trace</failure>"
        elif status == "error":
            inner = "<error message='err'>trace</error>"
        elif status == "skipped":
            inner = "<skipped/>"
        cases.append(f'<testcase classname="{cls}" name="{name}">{inner}</testcase>')
    xml = f'<?xml version="1.0"?><testsuites><testsuite>{"".join(cases)}</testsuite></testsuites>'
    path = tmp_path / "run.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_collect_output_is_parsed_without_parametrised_suffixes():
    text = (
        "tests/test_a.py::test_one\n"
        "tests/test_a.py::test_two[case-1]\n"
        "tests/test_a.py::test_two[case-2]\n"
        "\n=== 3 tests collected in 0.10s ===\n"
    )
    ids = cr._ids_from_collect(text)
    assert ids == {"tests/test_a.py::test_one", "tests/test_a.py::test_two"}


def test_new_tests_are_allowed(tmp_path):
    xml = _junit(tmp_path, [("t", "old", "passed"), ("t", "new", "passed")])
    result = cr.compare(cr._from_junit(xml), {"t::old"})
    assert result["added"] == ["t::new"]
    assert result["ok"] is True


def test_a_disappearing_test_is_a_regression(tmp_path):
    xml = _junit(tmp_path, [("t", "kept", "passed")])
    result = cr.compare(cr._from_junit(xml), {"t::kept", "t::gone"})
    assert result["removed"] == ["t::gone"]
    assert result["ok"] is False


def test_a_failing_test_blocks_by_name(tmp_path):
    xml = _junit(tmp_path, [("t", "a", "passed"), ("t", "b", "failed")])
    result = cr.compare(cr._from_junit(xml), {"t::a", "t::b"})
    assert result["failed"] == ["t::b"]
    assert result["ok"] is False


def test_errors_count_as_failures_and_skips_do_not(tmp_path):
    xml = _junit(tmp_path, [("t", "e", "error"), ("t", "s", "skipped")])
    result = cr.compare(cr._from_junit(xml), {"t::e", "t::s"})
    assert result["failed"] == ["t::e"]
    assert result["skipped"] == ["t::s"]
    assert result["ok"] is False


def test_write_then_check_round_trip(tmp_path, monkeypatch):
    baseline = tmp_path / "BASELINE_TESTS.json"
    monkeypatch.setattr(cr, "BASELINE", baseline)
    cr.write_baseline({"t::a", "t::b"})
    assert json.loads(baseline.read_text(encoding="utf-8"))["count"] == 2
    xml = _junit(tmp_path, [("t", "a", "passed"), ("t", "b", "passed"), ("t", "c", "passed")])
    ids = set(json.loads(baseline.read_text(encoding="utf-8"))["tests"])
    result = cr.compare(cr._from_junit(xml), ids)
    assert result["ok"] is True
    assert len(result["added"]) == 1


def test_a_subset_run_is_refused_rather_than_reported_as_6039_removals(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / "BASELINE_TESTS.json"
    monkeypatch.setattr(cr, "BASELINE", baseline)
    cr.write_baseline({f"t::x{n}" for n in range(100)})
    xml = _junit(tmp_path, [("t", "x1", "passed")])
    assert cr.main(["--junit", str(xml)]) == 2
    assert "subset run" in capsys.readouterr().err
