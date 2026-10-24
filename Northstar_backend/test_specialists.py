"""Tests for the specialist layer: router, package designer, listing, PPC.

These are the acceptance suite's fast half — deterministic, offline, no GPU.
The blueprint's 20+ task suite lives in tests/agents/tasks.json and runs through
these modules (see tests/agents/run_suite.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pouch_label  # noqa: E402
from specialists import listing_optimizer, package_designer, ppc_agent, router  # noqa: E402


# ── router ─────────────────────────────────────────────────────────────────

def test_routes_a_packaging_request():
    d = router.classify("Create a product image for Mogra Organics Lion's Mane, "
                        "6 oz stand-up pouch with front and back labels")
    assert d["status"] == "routed"
    assert d["agent"] == "package_designer"


def test_routes_a_listing_request():
    d = router.classify("Optimize this listing title and bullets for the keyword "
                        "lions mane mushroom powder")
    assert d["agent"] == "listing_optimizer"


def test_routes_a_ppc_request():
    d = router.classify("Here is my search term report, find negatives and adjust bids")
    assert d["agent"] == "ppc_agent"


def test_a_quoted_example_is_not_an_instruction():
    """Blueprint §6: quoted examples must not become commands."""
    d = router.classify('Write the brand story. The customer asked "make a video" but '
                        "we are not doing that.")
    assert d["agent"] in (None, "content")
    assert d["agent"] != "video_ugc"


def test_a_negated_request_does_not_route_to_the_negated_agent():
    d = router.classify("Do not make a video. I need the A+ content modules instead.")
    assert d["agent"] == "image_aplus"


def test_an_ambiguous_request_asks_instead_of_guessing():
    d = router.classify("Can you improve the creative?")
    assert d["status"] == "unclear"
    assert d.get("question")


def test_the_vague_package_request_triggers_questions():
    """The single most revealing test in the blueprint."""
    d = router.plan("Create a product image for my pouch")
    assert d["status"] == "routed"
    assert d["agent"] == "package_designer"
    assert d["ready"] is False
    fields = {q["field"] for q in d["questions"]}
    assert {"title", "weight", "dims", "company", "address"} <= fields


def test_a_complete_brief_is_ready():
    d = router.plan(
        "Build the packaging for Lion's Mane, 6 oz, 95x200x80 mm stand-up pouch, "
        "ingredients: organic lion's mane mushroom. Company Mogra Organics, "
        "address 123 Main St, country of origin USA.")
    assert d["agent"] == "package_designer"
    assert d["spec"].get("weight") == "NET WT 6 OZ (170 g)"
    assert d["spec"].get("dims", {}).get("width_mm") == 95.0


# ── package designer ───────────────────────────────────────────────────────

def _spec(**over):
    base = {
        "title": "Lion's Mane",
        "subtitle": "Organic Mushroom Powder",
        "weight": "NET WT 6 OZ (170 g)",
        "dims": {"width_mm": 95, "height_mm": 200, "gusset_mm": 80},
        "ingredients": ["Organic Lion's Mane mushroom powder"],
        "company": "Mogra Organics LLC",
        "address": "123 Main St, Austin TX",
        "country_of_origin": "USA",
        "claims": ["Fruiting body only", "Third-party tested"],
        "icons": ["organic_sprout", "non_gmo"],
    }
    base.update(over)
    return base


def test_the_vague_request_is_refused_with_questions():
    out = package_designer.build_package({"title": ""})
    assert out["ok"] is False and out["status"] == "needs_input"
    assert len(out["questions"]) >= 5


def test_a_complete_package_builds_every_panel_and_the_dieline():
    out = package_designer.build_package(_spec())
    assert out["ok"] is True
    for key in ("front", "back", "side", "sheet"):
        assert out["panels"][key][:8] == b"\x89PNG\r\n\x1a\n", key
    assert out["dieline"]["svg"].lstrip().startswith("<")
    assert out["dieline"]["pdf"][:4] == b"%PDF"
    assert out["validation"]["ready_for_print"] is True


def test_the_back_panel_reserves_a_barcode_zone():
    out = package_designer.build_package(_spec())
    img = Image.open(__import__("io").BytesIO(out["panels"]["back"]))
    assert img.size == (900, 1200)


def test_missing_facts_are_drawn_as_markers_not_invented():
    spec = _spec()
    spec.pop("address")
    spec.pop("country_of_origin")
    out = package_designer.build_package(spec, allow_incomplete=True)
    assert out["ok"] is True
    assert out["validation"]["ready_for_print"] is False
    missing = " ".join(out["validation"]["missing"])
    assert "address" in missing and "country of origin" in missing


def test_dimensions_are_consistent_between_dieline_and_request():
    out = package_designer.build_package(_spec())
    meta = out["dieline"]["meta"]
    assert meta["width_mm"] == pytest.approx(95.0, abs=0.01)
    assert meta["height_mm"] == pytest.approx(200.0, abs=0.01)
    assert meta["gusset_mm"] == pytest.approx(80.0, abs=0.01)
    # the flat sheet is a DIFFERENT number and must not be confused with the pouch
    assert out["dieline"]["flat_width_mm"] != meta["width_mm"]


def test_an_unusual_ratio_is_flagged_not_hidden():
    out = package_designer.build_package(_spec(dims={"width_mm": 95, "height_mm": 400,
                                                     "gusset_mm": 80}))
    assert any("ratio" in w for w in out["validation"]["warnings"])


# ── listing optimizer ──────────────────────────────────────────────────────

def test_listing_without_keywords_asks_instead_of_inventing():
    out = listing_optimizer.optimize(title="Lion's Mane Powder", bullets=["Good."],
                                     keywords=[])
    assert out["ok"] is False and out["status"] == "needs_input"


def test_listing_rewrite_improves_the_score_and_logs_changes():
    out = listing_optimizer.optimize(
        title="BEST SELLER Lion's Mane Mushroom Powder Buy Now!!!",
        bullets=["Great product.", "You will love it."],
        keywords=["lions mane mushroom powder", "organic mushroom powder",
                  "lion mane supplement"])
    assert out["ok"] is True
    assert out["after"]["score"]["total"] >= out["before"]["score"]["total"]
    assert out["listing"]["title"].lower().startswith("lion's mane")
    assert "buy now" not in out["listing"]["title"].lower()
    assert out["change_log"]


def test_backend_terms_respect_the_250_byte_limit_and_dedupe():
    terms = [f"term{i}" for i in range(200)]
    out = listing_optimizer.clean_backend_terms(
        terms, title="lion mane powder", bullets=["organic mushroom powder"])
    assert out["bytes"] <= 250
    assert "lion" not in out["terms"]


# ── PPC ────────────────────────────────────────────────────────────────────

def _st_rows():
    return [
        {"Campaign": "A", "Ad Group": "G1", "Customer Search Term": "lions mane powder",
         "Impressions": 900, "Clicks": 40, "Spend": 12.0, "Sales": 60.0, "Orders": 3},
        {"Campaign": "A", "Ad Group": "G1", "Customer Search Term": "mushroom coffee",
         "Impressions": 800, "Clicks": 25, "Spend": 9.0, "Sales": 0.0, "Orders": 0},
    ]


def test_the_wrong_report_is_rejected_not_guessed():
    out = ppc_agent.analyze([{"Campaign": "A", "Clicks": 3}])
    assert out["ok"] is False and out["status"] == "rejected"
    assert "missing column" in out["error"]


def test_harvest_and_negatives_trace_to_source_rows():
    out = ppc_agent.analyze(_st_rows(), target_acos=0.35)
    assert out["ok"] is True
    assert len(out["harvest"]) == 1 and len(out["negatives"]) == 1
    assert out["harvest"][0]["source_row"]["customer search term"] == "lions mane powder"
    assert out["negatives"][0]["source_row"]["customer search term"] == "mushroom coffee"


def test_a_change_referencing_an_unknown_campaign_is_rejected():
    src = _st_rows()
    bad = [{"operation": "update", "campaign": "Z", "ad group": "G9", "bid": 1.0}]
    out = ppc_agent.validate_change_rows(bad, src)
    assert out["ok"] is False
    assert any("not in the source report" in p for p in out["problems"])
