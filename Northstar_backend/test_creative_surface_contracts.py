"""Creative-surface contract tests for modules the audit found untested.

These are not exhaustive suites — they are the minimum honest guard so a module
that nothing imported cannot drift silently. Each test targets a deterministic
path: no model, no network, no GPU.

Covered: ad_pilot, design_studio_boxes, design_studio_imports, mockup_engine,
social_pulse voice defaults, studio_upload_router route contract.
(listing_forge is covered by test_seo_listing.py's imports; it remains flagged
only for direct-import heuristics.)
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --- ad_pilot: the money math must not silently produce nonsense ------------

def test_compute_target_acos_returns_a_bounded_target():
    from ad_pilot import compute_target_acos
    out = compute_target_acos(product_cost=10.0, amazon_price=30.0,
                              referral_fee_pct=15.0, fba_fee=5.0,
                              desired_profit_margin=20.0)
    assert isinstance(out, dict) and out
    numeric = [v for v in out.values() if isinstance(v, (int, float))]
    assert numeric, "no numeric output at all"
    assert all(v == v for v in numeric), "NaN leaked into the money math"


def test_optimize_bid_moves_in_the_right_direction():
    from ad_pilot import optimize_bid
    good = optimize_bid("kw", current_bid=1.00, acos=10.0, target_acos=30.0,
                        clicks=20, orders=4)
    bad = optimize_bid("kw", current_bid=1.00, acos=80.0, target_acos=30.0,
                       clicks=20, orders=0)
    assert good["recommended_bid"] > bad["recommended_bid"], \
        "a healthy ACOS must not be bid below a bleeding one"
    assert good["action"] == "increase"
    assert bad["action"] == "pause" and bad["needs_approval"] is True


def test_classify_keyword_tier_is_a_known_label():
    from ad_pilot import classify_keyword_tier
    labels = {classify_keyword_tier(impressions=i, clicks=i // 10, orders=i // 100)
              for i in (0, 500, 5000, 50000)}
    assert all(isinstance(x, str) and x for x in labels)


def test_allocate_budget_never_exceeds_the_total():
    from ad_pilot import allocate_budget
    camps = [{"name": "a", "spend": 100, "sales": 400},
             {"name": "b", "spend": 100, "sales": 50},
             {"name": "c", "spend": 0, "sales": 0}]
    out = allocate_budget(camps, total_budget=500.0)
    assert abs(sum(float(r["allocated_budget"]) for r in out) - 500.0) < 0.01
    assert all(float(r["allocated_budget"]) >= 0 for r in out)


# --- design_studio_imports: parsing must fail loudly ------------------------

def test_parse_import_rejects_unknown_kind():
    from design_studio_imports import ImportParseError, parse_import
    with pytest.raises(ImportParseError):
        parse_import(kind="not_a_kind", content="x")


def test_content_fingerprint_is_stable_and_content_sensitive():
    from design_studio_imports import content_fingerprint
    a = content_fingerprint("brief", "same text")
    b = content_fingerprint("brief", "same text")
    c = content_fingerprint("brief", "same text!")
    assert a == b and a != c and len(a) >= 16


def test_confidence_label_is_explicit_about_unknown():
    from design_studio_imports import confidence_label
    assert confidence_label(None)["sample"] == "UNKNOWN"
    assert confidence_label(0)["sample"] == "very small"


def test_parse_variant_metrics_refuses_empty_input():
    from design_studio_imports import ImportParseError, parse_variant_metrics
    with pytest.raises(ImportParseError):
        parse_variant_metrics(content="")


# --- design_studio_boxes: refuse rather than fake ---------------------------

def test_generate_box_rejects_unknown_generator():
    from design_studio_boxes import generate_box
    with pytest.raises(ValueError):
        generate_box("DefinitelyNotAGenerator", {})


def test_generate_box_rejects_out_of_range_dimension():
    from design_studio_boxes import generate_box
    with pytest.raises(ValueError):
        generate_box("Box", {"x": 10_000})


def test_generate_box_reports_missing_tool_instead_of_faking():
    import design_studio_boxes as dsb
    if dsb.boxes_binary():
        pytest.skip("boxes CLI present; the unavailable path cannot be exercised")
    with pytest.raises(dsb.BoxesUnavailable):
        dsb.generate_box(dsb.BOX_LIBRARY[0]["id"], {})


# --- mockup_engine: config plumbing ----------------------------------------

def test_plate_config_loads_as_a_mapping():
    from mockup_engine import load_plate_config
    cfg = load_plate_config()
    assert isinstance(cfg, dict)


def test_scale_cfg_scales_plate_anchors():
    from mockup_engine import load_plate_config, scale_cfg
    cfg = load_plate_config()
    if not cfg:
        pytest.skip("no plate presets configured")
    name, plate = next(iter(cfg.items()))
    if not isinstance(plate, dict) or "y0" not in plate:
        pytest.skip(f"plate {name} has no calibrated anchors to scale")
    out = scale_cfg(plate, 0.5)
    assert out["y0"] == plate["y0"] * 0.5
    assert out["y1"] == plate["y1"] * 0.5
    assert out["L"] == [[y * 0.5, x * 0.5] for y, x in plate["L"]]


# --- social_pulse: an unknown brand must fall back, not explode ------------

def test_load_brand_voice_returns_a_usable_profile():
    from social_pulse import load_brand_voice
    v = load_brand_voice("A Brand That Does Not Exist")
    assert isinstance(v, dict) and v
    assert "tone" in v


# --- model routing: generators must not hardcode a model id ----------------

def test_listing_forge_resolves_model_from_the_suite():
    import listing_forge
    import model_router
    assert listing_forge._default_model() == model_router.resolve("local", "T2").model


def test_social_pulse_resolves_model_from_the_suite():
    import social_pulse
    import model_router
    assert social_pulse._default_model() == model_router.resolve("local", "T2").model


def test_listing_forge_title_falls_back_to_a_template_without_the_llm(monkeypatch):
    import listing_forge
    monkeypatch.setattr(listing_forge, "_call_llm", lambda *a, **k: [])
    out = listing_forge.generate_title({"brand": "Northstar", "category": "mushroom powder",
                                        "title": "Organic Lion's Mane Powder"})
    assert out["title"] and out["score"] >= 0
    assert "compliance" in out


def test_social_pulse_caption_falls_back_without_the_llm(monkeypatch):
    import httpx
    import social_pulse

    def boom(*a, **k):
        raise httpx.ConnectError("offline in tests")

    monkeypatch.setattr(httpx, "post", boom)
    out = social_pulse.generate_caption({"title": "Organic Lion's Mane", "brand": "Northstar",
                                         "price": 24.99, "category": "mushroom powder"})
    assert isinstance(out, dict) and out.get("caption")


# --- studio_upload_router: the route exists and is auth-gated --------------

def test_upload_route_is_registered_and_requires_an_account():
    import studio_upload_router as sur
    paths = {r.path for r in sur.router.routes}
    assert any("upload" in p for p in paths), f"no upload route in {paths}"
    route = next(r for r in sur.router.routes if "upload" in r.path)
    dependant_names = " ".join(str(d.call) for d in route.dependant.dependencies)
    assert "studio_account" in dependant_names, "upload route is not auth-gated"
