"""The improvement backlog: it must refuse an item it cannot trust.

The backlog feeds the continuous loop, and the loop executes whatever card it is
given. So the backlog's own checks are load-bearing: an item without evidence, a
'ready' item whose write path the supervisor would refuse, or a promotion that
creates an invalid card all have to fail here rather than at dispatch time.

These tests use a temporary backlog and never touch the real one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import improvement_backlog as bl  # noqa: E402


def _item(**overrides):
    base = {
        "id": "imp-example",
        "theme": "ui",
        "priority": "P2",
        "status": "ready",
        "title": "An example improvement",
        "problem": "something is wrong",
        "evidence": ["Northstar_backend/main.py:1 - the thing"],
        "proposed_change": "fix it",
        "write_paths": ["northstar-os-ui/src/pages/internal/Admin.jsx"],
        "verification": "npm run build is clean",
        "checks": [{"name": "build", "cwd": "northstar-os-ui", "cmd": ["npm", "run", "build"]}],
        "risk": "low",
        "blocked": "",
    }
    base.update(overrides)
    return base


def _data(*items):
    return {"schema": "northstar.improvement_backlog.v1", "items": list(items)}


def test_a_well_formed_backlog_has_no_problems():
    assert bl.check(_data(_item())) == []


def test_an_item_without_evidence_is_refused():
    problems = bl.check(_data(_item(evidence=[])))
    assert any("no evidence" in p for p in problems)


def test_a_ready_item_needs_a_write_path_and_a_verification():
    assert any("no write_paths" in p for p in bl.check(_data(_item(write_paths=[]))))
    assert any("no verification" in p for p in bl.check(_data(_item(verification=""))))


def test_a_ready_item_outside_the_commit_allowlist_is_refused():
    """The supervisor would refuse this card, so the backlog must refuse it first."""
    problems = bl.check(_data(_item(write_paths=["package.json"])))
    assert any("outside the commit allowlist" in p for p in problems)


def test_unknown_status_theme_and_priority_are_refused():
    assert any("status" in p for p in bl.check(_data(_item(status="maybe"))))
    assert any("theme" in p for p in bl.check(_data(_item(theme="vibes"))))
    assert any("priority" in p for p in bl.check(_data(_item(priority="P9"))))


def test_duplicate_ids_are_refused():
    problems = bl.check(_data(_item(), _item()))
    assert any("duplicate id" in p for p in problems)


def test_needs_author_without_a_reason_is_refused():
    problems = bl.check(_data(_item(status="needs-author", blocked="")))
    assert any("no blocked reason" in p for p in problems)


def test_a_card_is_only_built_from_a_named_check():
    """A verification sentence is not a command; promotion needs a real check."""
    item = _item()
    item.pop("checks")
    with pytest.raises(ValueError, match="must name checks"):
        bl._card(item)


def test_counts_report_every_status():
    counts = bl.counts(_data(_item(), _item(id="imp-two", status="blocked")))
    assert counts["total"] == 2
    assert counts["ready"] == 1
    assert counts["blocked"] == 1
    assert counts["done"] == 0


def test_promote_refuses_an_item_that_is_not_ready():
    data = _data(_item(status="needs-author", blocked="author must decide"))
    path = ROOT / "state" / "backlog" / "_test_backlog.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    original = bl.BACKLOG
    bl.BACKLOG = path
    try:
        with pytest.raises(ValueError, match="only 'ready' items may be promoted"):
            bl.promote("imp-example")
    finally:
        bl.BACKLOG = original
        path.unlink(missing_ok=True)
