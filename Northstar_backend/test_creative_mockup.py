"""Tests for the reusable Northstar image/text workflow (creative.exact_text,
creative.presets, creative.comfy_client, creative.mogra_mockup).

All offline and deterministic: no ComfyUI, no network, no GPU.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from creative import comfy_client, mogra_mockup, presets
from creative.exact_text import (
    BrandContentError,
    LabelSpec,
    check_brand_content,
    compose_exact_text,
    quad_homography,
    render_label_layer,
    warp_to_quad,
)


# ---------------------------------------------------------------------------
# Presets / brand rules
# ---------------------------------------------------------------------------

def test_brand_copy_is_exact():
    assert presets.MOGRA_BRAND["name"] == "Mogra Organics"
    assert presets.MOGRA_BRAND["tagline"] == "Fuel Your Focus."


def test_required_presets_present():
    assert set(presets.CONTAINER_PRESETS) == {
        "mogra_5lb_clear_handled_pet_jar",
        "mogra_32oz_standup_pouch",
        "mogra_4oz_window_pouch",
    }
    assert set(presets.PRODUCT_PRESETS) == {
        "organic_black_peppercorns",
        "organic_white_onion_powder",
        "organic_turmeric_powder",
    }
    # Generic reusable surface zones.
    for key in ("plain_rectangle", "angled_product_face", "card_banner_hero",
                "ui_screenshot_annotation"):
        assert key in presets.SURFACE_PRESETS


def test_product_preset_copy_exact():
    p = presets.get_product("organic_turmeric_powder")
    assert p["product_name"] == "Organic Turmeric Powder"
    assert p["descriptor"] == "Earthy \u2022 Golden \u2022 Vibrant"
    assert p["net_weight"] == "NET WT. 5 LB (2.27 kg)"
    assert p["brand"] == "Mogra Organics"


def test_quads_are_four_normalized_points():
    for group in (presets.CONTAINER_PRESETS, presets.SURFACE_PRESETS):
        for key, v in group.items():
            q = v["quad_norm"]
            assert len(q) == 4, key
            for x, y in q:
                assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0, key


@pytest.mark.parametrize("bad", ["USDA Organic", "Nutrition Facts",
                                 "UPC 012345678901", "Supplement Facts",
                                 "Lot Code AB-12", "Manufactured by Acme"])
def test_brand_guard_rejects_invented_compliance(bad):
    spec = LabelSpec(brand="Mogra Organics", product_name="Organic Turmeric Powder",
                     extra_lines=[bad])
    with pytest.raises(BrandContentError):
        check_brand_content(spec)


def test_brand_guard_allows_clean_copy():
    spec = LabelSpec(brand="Mogra Organics", tagline="Fuel Your Focus.",
                     product_name="Organic Turmeric Powder",
                     descriptor="Earthy \u2022 Golden \u2022 Vibrant",
                     net_weight="NET WT. 5 LB (2.27 kg)")
    check_brand_content(spec)  # must not raise


# ---------------------------------------------------------------------------
# Label rendering
# ---------------------------------------------------------------------------

def test_render_label_layer_draws_ink():
    spec = mogra_mockup.build_spec("organic_black_peppercorns")
    layer = render_label_layer(spec, (600, 400), presets.get_style("mogra_label_panel"))
    assert layer.size == (600, 400)
    assert layer.mode == "RGBA"
    lo, hi = layer.getchannel("A").getextrema()
    assert hi > 0                       # something was drawn
    assert lo == 0                      # and it is not a full opaque fill


def test_label_text_fits_within_layer():
    # A long product name on a portrait label must shrink, never clip.
    spec = mogra_mockup.build_spec("organic_turmeric_powder")
    layer = render_label_layer(spec, (612, 864), presets.get_style("mogra_text_only"))
    a = layer.getchannel("A")
    assert a.crop((0, 0, 4, 864)).getextrema()[1] == 0      # no ink on left edge
    assert a.crop((608, 0, 612, 864)).getextrema()[1] == 0  # no ink on right edge


def test_build_spec_overrides():
    spec = mogra_mockup.build_spec("organic_turmeric_powder",
                                   product_name="Custom Blend", net_weight="NET WT. 2 OZ")
    assert spec.product_name == "Custom Blend"
    assert spec.net_weight == "NET WT. 2 OZ"
    assert spec.brand == "Mogra Organics"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def test_homography_reproduces_corners():
    dst = [(10.0, 12.0), (210.0, 30.0), (190.0, 180.0), (5.0, 160.0)]
    src = [(0.0, 0.0), (100.0, 0.0), (100.0, 80.0), (0.0, 80.0)]
    a, b, c, d, e, f, g, h = quad_homography(dst, src)
    for (x, y), (u, v) in zip(dst, src):
        denom = g * x + h * y + 1.0
        uu = (a * x + b * y + c) / denom
        vv = (d * x + e * y + f) / denom
        assert abs(uu - u) < 1e-6
        assert abs(vv - v) < 1e-6


def test_warp_places_center_marker_in_quad():
    layer = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(40, 60):
        for y in range(40, 60):
            layer.putpixel((x, y), (255, 0, 0, 255))
    quad = [(50.0, 20.0), (250.0, 40.0), (230.0, 200.0), (30.0, 180.0)]
    warped = warp_to_quad(layer, (300, 240), quad, 0.0)
    cx = sum(p[0] for p in quad) / 4
    cy = sum(p[1] for p in quad) / 4
    r, g, b, a = warped.getpixel((int(cx), int(cy)))
    assert a > 0 and r > 120 and g < 120 and b < 120


def test_compose_preserves_size_and_leaves_outside_untouched():
    src = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
    spec = mogra_mockup.build_spec("organic_turmeric_powder")
    surface = {"rect_norm": [0.25, 0.25, 0.75, 0.75], "curvature": 0.0}
    out = compose_exact_text(src, spec, surface, presets.get_style("mogra_label_panel"))
    assert out.size == (400, 400)
    assert out.getpixel((5, 5))[:3] == (255, 255, 255)     # outside the quad
    changed = any(out.getpixel((x, y))[:3] != (255, 255, 255)
                  for x in range(150, 250) for y in range(150, 250))
    assert changed                                            # text/panel drawn


def test_compose_return_params_round_trips():
    src = Image.new("RGBA", (300, 300), (255, 255, 255, 255))
    spec = mogra_mockup.build_spec("organic_white_onion_powder")
    surface = presets.get_surface("angled_product_face")
    out, params = compose_exact_text(src, spec, surface, surface["style"],
                                     return_params=True)
    assert out.size == (300, 300)
    assert len(params["quad_norm"]) == 4
    assert params["spec"]["brand"] == "Mogra Organics"
    json.dumps(params)  # must be serialisable


def test_curvature_changes_output():
    src = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
    spec = mogra_mockup.build_spec("organic_black_peppercorns")
    flat = compose_exact_text(src, spec, {"rect_norm": [0.2, 0.2, 0.8, 0.8],
                                          "curvature": 0.0},
                              presets.get_style("mogra_label_panel"))
    curved = compose_exact_text(src, spec, {"rect_norm": [0.2, 0.2, 0.8, 0.8],
                                            "curvature": 0.15},
                                presets.get_style("mogra_label_panel"))
    assert list(flat.tobytes()) != list(curved.tobytes())


def test_curvature_does_not_smear_the_label():
    src = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
    spec = mogra_mockup.build_spec("organic_black_peppercorns")

    def ink_count(img):
        return sum(1 for x in range(120, 280) for y in range(120, 280)
                   if img.getpixel((x, y))[:3] != (255, 255, 255))

    surface = {"rect_norm": [0.2, 0.2, 0.8, 0.8]}
    flat = compose_exact_text(src, spec, dict(surface, curvature=0.0),
                              presets.get_style("mogra_label_panel"))
    curved = compose_exact_text(src, spec, dict(surface, curvature=0.25),
                                presets.get_style("mogra_label_panel"))
    f, c = ink_count(flat), ink_count(curved)
    assert f > 0
    assert c > 0.6 * f          # content survives the wrap, not smeared away


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def _assert_valid_graph(wf):
    for nid, node in wf.items():
        assert "class_type" in node and "inputs" in node, nid
        for value in node["inputs"].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                assert value[0] in wf, f"{nid} links to missing node {value[0]}"


def test_qwen_t2i_graph_is_valid_and_uses_gguf():
    wf = comfy_client.qwen_t2i_workflow("a clean spice jar, no text", width=768, height=768)
    _assert_valid_graph(wf)
    types = {n["class_type"] for n in wf.values()}
    assert {"CLIPLoader", "VAELoader", "UnetLoaderGGUF", "ModelSamplingAuraFlow",
            "EmptySD3LatentImage", "KSampler", "VAEDecode", "SaveImage"} <= types
    assert wf["1"]["inputs"]["type"] == "qwen_image"
    assert wf["7"]["inputs"]["width"] == 768


def test_qwen_edit_graph_is_valid():
    wf = comfy_client.qwen_edit_workflow("swap container to premium jar",
                                         "source.png")
    _assert_valid_graph(wf)
    types = {n["class_type"] for n in wf.values()}
    assert {"UnetLoaderGGUF", "TextEncodeQwenImageEditPlus", "VAEEncode",
            "FluxKontextImageScale", "KSampler"} <= types


def test_flux_fallback_graph_is_valid():
    wf = comfy_client.flux_t2i_workflow("clean product scene, no text")
    _assert_valid_graph(wf)
    assert wf["1"]["class_type"] == "DualCLIPLoader"


def test_scene_prompt_forbids_text():
    prompt = comfy_client.build_scene_prompt(
        container=presets.get_container("mogra_5lb_clear_handled_pet_jar"),
        product=presets.get_product("organic_turmeric_powder"))
    assert "no text" in prompt.lower()
    assert "Mogra Organics" in prompt


# ---------------------------------------------------------------------------
# Model resolution (offline)
# ---------------------------------------------------------------------------

def test_resolve_models_offline_reads_disk(tmp_path, monkeypatch):
    comfy = tmp_path / "ComfyUI"
    (comfy / "models" / "text_encoders").mkdir(parents=True)
    (comfy / "models" / "vae").mkdir(parents=True)
    (comfy / "models" / "unet").mkdir(parents=True)
    (comfy / "models" / "text_encoders" / comfy_client.QWEN_CLIP_DEFAULT).write_bytes(b"x")
    (comfy / "models" / "vae" / comfy_client.QWEN_VAE_DEFAULT).write_bytes(b"x")
    (comfy / "models" / "unet" / comfy_client.QWEN_T2I_UNET_DEFAULT).write_bytes(b"x")
    monkeypatch.setenv("COMFYUI_DIR", str(comfy))
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")  # nothing there
    models = comfy_client.resolve_models()
    assert models["comfy_up"] is False
    assert models["source"] == "disk"
    assert models["qwen_ready"] is True
    assert models["qwen_edit_ready"] is False


def test_generate_scene_without_comfy_is_honest(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
    with pytest.raises(comfy_client.ComfyUIError):
        comfy_client.generate_scene("x", "unused.png")


# ---------------------------------------------------------------------------
# Full pipeline (offline compose path)
# ---------------------------------------------------------------------------

def test_build_mockup_offline_compose(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    Image.new("RGB", (512, 512), (240, 235, 228)).save(src)
    out = tmp_path / "final.png"
    result = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, out_path=out)
    assert Path(result["output"]).exists()
    assert result["lane"] == "composited_only"
    assert Path(result["sidecar"]).exists()
    with Image.open(out) as im:
        assert im.size == (512, 512)


def test_build_mockup_requires_source_or_generate(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    with pytest.raises(ValueError):
        mogra_mockup.build_mockup(product="organic_turmeric_powder",
                                  out_path=tmp_path / "x.png")
