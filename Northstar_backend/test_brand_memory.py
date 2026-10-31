"""Brand memory sync (Phase 3, item 3) - proposals only, never silent writes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brand_memory import (MAX_COLORS, MAX_PROMPTS, STATUS, atoms, extract, merge,
                          propose)

PROFILE = {
    "brand": {
        "colors": ["#1D4A1D", "#fff", "#1d4a1d", "not-a-colour", "#c4941a"],
        "fonts": {"heading": "  Playfair Display ", "body": "Inter", "junk": 42},
        "logo": {"ref": "/assets/logo.png", "placement": "TOP-LEFT"},
        "prompts": ["  matte kraft pouch, soft studio light ",
                    "matte kraft pouch, soft studio light", "ceramic mug, 85mm"],
    }
}


def test_colours_are_validated_expanded_and_deduped():
    b = extract(PROFILE)
    assert b["colors"] == ["#1d4a1d", "#ffffff", "#c4941a"]


def test_fonts_are_trimmed_and_only_known_roles_survive():
    b = extract(PROFILE)
    assert b["fonts"] == {"heading": "Playfair Display", "body": "Inter"}


def test_logo_ref_is_kept_and_placement_lowered():
    b = extract(PROFILE)
    assert b["logo"] == {"ref": "/assets/logo.png", "placement": "top-left"}


def test_prompts_are_deduped_and_trimmed():
    b = extract(PROFILE)
    assert b["prompts"] == ["matte kraft pouch, soft studio light", "ceramic mug, 85mm"]


def test_colour_cap():
    b = extract({"brand": {"colors": [f"#00000{i}" for i in range(12)]}})
    assert len(b["colors"]) <= MAX_COLORS


def test_prompt_cap():
    b = extract({"brand": {"prompts": [f"p{i}" for i in range(40)]}})
    assert len(b["prompts"]) == MAX_PROMPTS


def test_empty_profile_extracts_nothing_and_invents_nothing():
    b = extract({})
    assert b == {"colors": [], "fonts": {}, "logo": {}, "prompts": []}
    assert extract(None)["colors"] == []


def test_atoms_have_stable_keys_and_proposed_status():
    recs = atoms(extract(PROFILE), "acct-1")
    keys = [r["key"] for r in recs]
    assert "brand.color.0" in keys
    assert "brand.font.heading" in keys
    assert "brand.logo.ref" in keys
    assert "brand.prompt.0" in keys
    assert all(r["status"] == STATUS for r in recs)
    assert all(r["account_id"] == "acct-1" for r in recs)


def test_propose_never_claims_applied_without_a_store():
    doc = propose(extract(PROFILE), account_id="acct-1")
    assert doc["status"] == "proposed"
    assert doc["persisted"] is False
    assert doc["reason"] == "no_store_supplied"
    assert doc["count"] == len(doc["atoms"])


def test_propose_writes_only_through_the_injected_store():
    captured = {}
    def store(records):
        captured["records"] = records
    doc = propose(extract(PROFILE), account_id="acct-2", store=store)
    assert doc["persisted"] is True
    assert len(captured["records"]) == doc["count"]
    assert all(r["status"] == "proposed" for r in captured["records"])


def test_a_failing_store_is_reported_not_swallowed():
    def store(_records):
        raise RuntimeError("db down")
    doc = propose(extract(PROFILE), account_id="acct-3", store=store)
    assert doc["persisted"] is False
    assert "RuntimeError" in doc["reason"]


def test_merge_incoming_wins_on_the_same_key():
    merged = merge(
        [{"key": "brand.color.0", "value": "#111111"}],
        [{"key": "brand.color.0", "value": "#222222"}, {"key": "brand.font.body", "value": "Inter"}],
    )
    assert merged[0] == {"key": "brand.color.0", "value": "#222222"}
    assert merged[1]["key"] == "brand.font.body"


def test_no_atom_has_an_empty_key():
    assert all(r["key"] for r in atoms(extract(PROFILE), "a"))
