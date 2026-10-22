"""Bulk fact import — parsing, validation and the shipped corpus."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import import_facts  # noqa: E402
import knowledge_pack as kp  # noqa: E402


def test_parse_builds_a_valid_atom(tmp_path):
    path = tmp_path / "facts.psv"
    path.write_text(
        "listing|title.smoke|Lead with the brand and the product|Bury the brand|"
        "Buyers scan brand first|Seller Central - titles|high|pl,reseller\n",
        encoding="utf-8")
    rows = import_facts.parse_psv(path)
    assert len(rows) == 1
    atom = rows[0][1]
    assert atom["id"] == "listing.title.smoke"
    assert atom["applies_to"] == ["pl", "reseller"]
    assert atom["needs_verification"] is True
    assert kp.validate_atom(atom, known_domains=kp.domains()) == []


def test_malformed_row_is_flagged_not_crashed(tmp_path):
    path = tmp_path / "bad.psv"
    path.write_text("listing|only|three|fields\n", encoding="utf-8")
    rows = import_facts.parse_psv(path)
    assert rows and "_error" in rows[0][1]


def test_comments_and_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "ignored.psv"
    path.write_text("# comment\n\n", encoding="utf-8")
    assert import_facts.parse_psv(path) == []


def test_shipped_corpus_is_valid():
    files = sorted(import_facts.FACTS_DIR.glob("*.psv"))
    assert files, "no fact files shipped"
    total = 0
    for path in files:
        for _lineno, atom in import_facts.parse_psv(path):
            assert "_error" not in atom, atom
            assert kp.validate_atom(atom, known_domains=kp.domains()) == [], atom["id"]
            total += 1
    assert total >= 50


def test_imported_atoms_are_present_in_the_packs():
    ids = {a.get("id") for a in kp.all_atoms()}
    for _lineno, atom in import_facts.parse_psv(import_facts.FACTS_DIR / "packs.psv"):
        assert atom["id"] in ids, f"not imported: {atom['id']}"
