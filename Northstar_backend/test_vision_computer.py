"""D14 computer mode: scope enforcement, grants, and PC mode that cannot switch itself on."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import computer, scope  # noqa: E402


def test_a_path_inside_the_project_is_allowed():
    verdict = scope.check("reports/ty/d8_control_browser.md")
    assert verdict["allow"] is True
    assert verdict["root"]


def test_a_path_outside_the_declared_roots_is_refused():
    verdict = scope.check("C:/Windows/system.ini")
    assert verdict["allow"] is False
    assert "GRANT" in verdict["reason"]


def test_dot_dot_cannot_walk_out_of_scope():
    verdict = scope.check("reports/../../Windows/system.ini")
    assert verdict["allow"] is False


def test_a_grant_naming_a_path_unlocks_it(tmp_path, monkeypatch):
    target = tmp_path / "outside.txt"
    grants = tmp_path / "grants.json"
    grants.write_text(json.dumps({"paths": [
        {"path": str(target), "granted": True, "why": "unit test"}]}), encoding="utf-8")
    # with no grant file at all the path is refused
    assert scope.check(str(target), path=tmp_path / "absent.json")["allow"] is False
    monkeypatch.setattr(scope, "GRANTS", grants)
    assert scope.check(str(target))["allow"] is True


def test_pc_mode_needs_both_the_flag_and_the_grant():
    off = scope.pc_mode_enabled(env={}, grant_data={})
    assert off["enabled"] is False
    flag_only = scope.pc_mode_enabled(env={"TY_PC_MODE": "1"}, grant_data={})
    assert flag_only["enabled"] is False
    grant_only = scope.pc_mode_enabled(env={}, grant_data={"pc_mode": {"granted": True}})
    assert grant_only["enabled"] is False
    both = scope.pc_mode_enabled(env={"TY_PC_MODE": "1"},
                                 grant_data={"pc_mode": {"granted": True}})
    assert both["enabled"] is True


def test_a_write_outside_scope_is_refused_and_leaves_no_file(tmp_path):
    target = tmp_path / "outside" / "file.txt"
    result = computer.write_text(str(target), "hello")
    assert result["ok"] is False and result["refused"] is True
    assert target.exists() is False


def test_a_write_inside_scope_lands(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "ROOT", tmp_path)
    monkeypatch.setattr(scope, "DECLARED_ROOTS", ("reports",))
    result = computer.write_text("reports/note.txt", "northstar")
    assert result["ok"] is True
    assert (tmp_path / "reports" / "note.txt").read_text(encoding="utf-8") == "northstar"


def test_reads_are_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "ROOT", tmp_path)
    monkeypatch.setattr(scope, "DECLARED_ROOTS", ("reports",))
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "secrets.txt").write_text(
        "api_key=abcdef123456 and a normal line", encoding="utf-8")
    result = computer.read_text("reports/secrets.txt")
    assert result["ok"] is True
    assert "abcdef123456" not in result["text"]
    assert "[redacted]" in result["text"]


def test_windows_are_filtered_by_the_privacy_blocklist(monkeypatch):
    monkeypatch.setattr(computer.capture, "windows", lambda: [
        {"title": "Amazon Seller Central", "process": "chrome.exe", "hwnd": 1},
        {"title": "Settings", "process": "SystemSettings.exe", "hwnd": 2},
    ])
    result = computer.windows()
    assert result["count"] == 1
    assert result["blocked"] == 1
    assert result["windows"][0]["title"] == "Settings"


def test_the_pc_mode_plan_is_documented_and_not_executed():
    assert computer.PC_MODE_PLAN["steps"]
    assert "not_executed" in computer.PC_MODE_PLAN
