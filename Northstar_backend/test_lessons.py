"""Tests for the build-lesson store (learn-from-the-build loop)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specialists import lessons  # noqa: E402


def test_seed_contains_the_three_applied_lessons_from_the_real_build(tmp_path, monkeypatch):
    monkeypatch.setattr(lessons, "STORE", tmp_path / "lessons.json")
    items = lessons.ensure_seeded()
    applied = [l for l in items if l["status"] == "APPLIED"]
    assert len(applied) == 3
    assert {l["id"] for l in applied} == {"L1", "L2", "L3"}


def test_a_lesson_without_a_code_location_is_only_proposed(tmp_path, monkeypatch):
    monkeypatch.setattr(lessons, "STORE", tmp_path / "lessons.json")
    lessons.ensure_seeded()
    entry = lessons.record("side strips should carry the side panel", area="compositing")
    assert entry["status"] == "PROPOSED"
    assert entry["applied_in"] is None


def test_a_lesson_naming_its_code_is_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(lessons, "STORE", tmp_path / "lessons.json")
    lessons.ensure_seeded()
    entry = lessons.record("use the side panel for gussets", area="compositing",
                           applied_in="pouch_label.py::_wrap_panel")
    assert entry["status"] == "APPLIED"


def test_prompt_notes_only_carry_applied_lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(lessons, "STORE", tmp_path / "lessons.json")
    lessons.ensure_seeded()
    lessons.record("a proposed idea", area="geometry")
    notes = lessons.notes_for_prompt("geometry")
    assert "L1" in notes or "L2" in notes
    assert "a proposed idea" not in notes


def test_active_filters_by_area(tmp_path, monkeypatch):
    monkeypatch.setattr(lessons, "STORE", tmp_path / "lessons.json")
    lessons.ensure_seeded()
    assert all(l["area"] == "compositing" for l in lessons.active("compositing"))
