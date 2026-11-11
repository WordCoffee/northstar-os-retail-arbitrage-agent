"""Every unit tag must have a restore point — enforced, not remembered.

Measured 2026-11-11: four units shipped with no `rollback/pre-*` tag (block3, block4, block5,
the UI defects) and a previous verifier had already caught the same omission for D-026/D-027.
The rule is in the work order (§2, §7); a rule enforced by memory is not enforced, so
`tools/release/check_rollback_tags.py` checks it and this test runs the check.

The check is by **commit**, not by name: several restore points are named after a defect
(`rollback/pre-d020-20261111`) rather than the unit they cover, and name-matching reported 39
of 41 units as unprotected when the real number was 23.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.release import check_rollback_tags as check  # noqa: E402


def test_every_unit_tag_has_a_restore_point():
    result = check.check()
    if result.get("skipped"):
        pytest.skip(str(result["skipped"]))
    gaps = [row for row in result.get("units") or [] if row.get("status") != "ok"]
    assert gaps == [], (
        "unit tag(s) with no rollback point at the pre-unit tree: "
        + ", ".join(str(row.get("tag")) for row in gaps)
        + " — create one with tools/release/check_rollback_tags.py as the judge")


def test_the_check_reads_commits_not_names(tmp_path):
    """Guards the fix itself: a name-matching check reported a 39/41 gap that was 23/41."""
    source = (ROOT / "tools" / "release" / "check_rollback_tags.py").read_text(encoding="utf-8")
    assert "covered.get(parent" in source, "the check must match on the parent commit"
    assert "unit in name" not in source, "the check must not fall back to name matching"
