"""The V3 graduation gate: AST, tests, vision and E2E, each fail-closed."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import v3_graduation as gate  # noqa: E402


def _module(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mod.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_ast_audit_flags_duplicate_symbols_and_placeholders(tmp_path):
    path = _module(tmp_path, "def run():\n    pass\n\ndef run():\n    # TODO fix\n    pass\n")
    report = gate.audit_symbols(path)
    assert report["ok"] is False
    assert report["duplicates"] == ["run"]
    assert report["placeholders"]


def test_ast_audit_accepts_a_clean_module(tmp_path):
    path = _module(tmp_path, "def run():\n    return 1\n\nclass Box:\n    pass\n")
    report = gate.audit_symbols(path)
    assert report["ok"] is True
    assert report["symbols"] == 2


def test_command_failure_is_not_a_pass():
    report = gate.run_command(["python", "-c", "raise SystemExit(1)"])
    assert report["ok"] is False and report["exit"] == 1


def test_grade_passes_only_with_all_three_stages(tmp_path):
    module = _module(tmp_path, "def run():\n    return 1\n")
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"png")
    report = gate.grade(
        module=module, tests_cmd=["python", "-c", "raise SystemExit(0)"],
        screenshot=screenshot, constraint="a pouch",
        e2e_cmd=["python", "-c", "raise SystemExit(0)"],
        vision_caller=lambda image, constraint: '{"pass": true, "reasons": [], '
                                                '"confidence": 0.9}')
    assert report["ok"] is True
    assert report["stage2"]["status"] == "passed"


def test_grade_fails_closed_without_a_screenshot(tmp_path):
    module = _module(tmp_path, "def run():\n    return 1\n")
    report = gate.grade(module=module,
                        tests_cmd=["python", "-c", "raise SystemExit(0)"],
                        screenshot=None, constraint="a pouch",
                        e2e_cmd=["python", "-c", "raise SystemExit(0)"])
    assert report["ok"] is False
    assert report["stage2"]["status"] == "not_verified"


def test_grade_fails_when_vision_refuses(tmp_path):
    module = _module(tmp_path, "def run():\n    return 1\n")
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"png")
    report = gate.grade(
        module=module, tests_cmd=["python", "-c", "raise SystemExit(0)"],
        screenshot=screenshot, constraint="a pouch",
        e2e_cmd=["python", "-c", "raise SystemExit(0)"],
        vision_caller=lambda image, constraint: '{"pass": false, '
                                                '"reasons": ["no pouch"], '
                                                '"confidence": 0.8}')
    assert report["ok"] is False
    assert report["stage2"]["status"] == "failed"
