"""Input flexibility paths — guided interview, creative discovery, bulk ingest.

These tests pin the HONESTY of the three paths: questions are only asked about
slots that are provably absent, discovery is deterministic and invents no facts,
and the bulk report never advertises an ingest lane the repository lacks.
"""
from __future__ import annotations

import input_paths as ip


# ── classification ───────────────────────────────────────────────────────────

def test_classifies_a_listing_request():
    info = ip.classify("Rewrite the Amazon title and bullets for our mushroom powder")
    assert info["family"] == "listing"
    assert info["matched"], "the listing family matched on nothing"
    assert set(info["matched"]) <= {"list", "listing", "title", "asin", "seo", "keywords", "bullet"}
    # "amazon" is not a family keyword — it is the marketplace SLOT, and it must be
    # understood there (that is the behaviour that matters).
    guided = ip.guided("Rewrite the Amazon title and bullets for our 8 oz mushroom powder")
    assert "marketplace" in guided["answered"]


def test_classifies_design_and_sourcing_and_research():
    assert ip.classify("Build a dieline for a stand-up pouch")["family"] == "design"
    assert ip.classify("Is this Costco supplier worth buying from at 22% ROI")["family"] == "sourcing"
    assert ip.classify("Research competitor pricing in the supplement market")["family"] == "research"


def test_unknown_request_has_no_family():
    assert ip.classify("hello there")["family"] is None


# ── guided interview ─────────────────────────────────────────────────────────

def test_guided_asks_only_about_slots_that_are_missing():
    req = "Make the Amazon listing better"          # has marketplace, lacks product/objective
    out = ip.guided(req)
    assert out["family"] == "listing"
    assert "marketplace" in out["answered"]
    assert "marketplace" not in out["missing"]
    asked = [q["slot"] for q in out["questions"]]
    assert "product" in asked and "objective" in asked
    for q in out["questions"]:
        assert q["question"] and q["why"]


def test_guided_never_exceeds_the_question_cap():
    out = ip.guided("design a pouch", max_questions=99)
    assert len(out["questions"]) <= ip.MAX_QUESTIONS


def test_guided_declines_honestly_when_no_family_matches():
    out = ip.guided("hello there")
    assert out["questions"] == []
    assert out["missing"] == []
    assert "no slot can be proven missing" in out["summary"]


def test_guided_flags_vague_markers_without_using_them_as_questions():
    out = ip.guided("make it better, something about the packaging")
    assert "make it better" in out["vague_markers"]
    assert all("make it better" not in q["question"] for q in out["questions"])


def test_guided_says_so_when_nothing_is_missing():
    req = ("Rewrite the Amazon listing for our 8 oz Lion's Mane mushroom powder "
           "to improve conversion")
    out = ip.guided(req)
    assert out["missing"] == []
    assert out["questions"] == []
    assert "already present" in out["summary"]


# ── creative discovery ───────────────────────────────────────────────────────

def test_discovery_is_deterministic_for_a_seed():
    a = ip.discovery("premium mushroom packaging", n=4, seed=7)
    b = ip.discovery("premium mushroom packaging", n=4, seed=7)
    assert [m["id"] for m in a["moves"]] == [m["id"] for m in b["moves"]]


def test_discovery_honours_n_and_fills_every_template():
    out = ip.discovery("mushroom packaging launch", n=3, seed=1)
    assert len(out["moves"]) == 3
    for m in out["moves"]:
        assert m["name"] and m["prompt"]
        assert "{" not in m["prompt"]                 # template fully applied
        assert m["prompt"] != m["name"]


def test_discovery_invents_no_facts():
    out = ip.discovery("mushroom packaging", n=8, seed=3)
    blob = " ".join(m["prompt"] for m in out["moves"]).lower()
    for word in ("certified", "organic", "usda", "fda", "guaranteed", "$"):
        assert word not in blob, f"discovery invented '{word}'"
    assert "not generated answers" in out["caveat"]


# ── bulk ingest ──────────────────────────────────────────────────────────────

def test_bulk_reports_implemented_and_queued_lanes_truthfully():
    out = ip.bulk()
    kinds = {b["kind"]: b["state"] for b in out["implemented"] + out["queued"]}
    assert kinds["text"] == "implemented"
    assert kinds["voice"] == "implemented"
    assert kinds["pdf"] == "queued"          # must not be advertised as working
    assert kinds["logs"] == "queued"
    assert "not advertisements" in out["summary"] or "not advertised" in out["summary"].lower()
    assert "not implemented" in out["caveat"]


# ── the combined entry point ─────────────────────────────────────────────────

def test_paths_returns_all_three_paths():
    out = ip.paths("research Costco club pricing for paper towels", seed=2)
    assert set(out) == {"request", "guided", "discovery", "bulk"}
    assert out["guided"]["family"] == "research"
    assert out["discovery"]["moves"]
    assert out["bulk"]["implemented"]
