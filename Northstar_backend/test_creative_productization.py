"""Tests for the creative productization pass: bundled brand fonts, deterministic
label-zone alignment, and the optional Edit-2511 blank-panel prep stage.

All offline and deterministic: no ComfyUI, no network.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from creative import comfy_client, label_zone, mogra_mockup, presets
from creative.exact_text import brand_fonts, font_source, load_font


# ---------------------------------------------------------------------------
# Brand fonts
# ---------------------------------------------------------------------------

def test_brand_fonts_are_bundled_and_of_license():
    info = brand_fonts()
    assert info["bundled"] is True, "brand fonts must ship with the lane"
    assert info["serif"] == "LibreBaskerville-VF.ttf"
    assert info["sans"] == "DMSans-VF.ttf"
    assert "Open Font License" in info["license"]


def test_compositor_uses_brand_fonts():
    assert font_source(True, True) == "brand"    # serif bold
    assert font_source(False, False) == "brand"  # sans regular
    f = load_font(48, serif=True, bold=True)
    assert f.getlength("Mogra Organics") > 0


def test_brand_font_weights_differ():
    regular = load_font(40, serif=True, bold=False)
    bold = load_font(40, serif=True, bold=True)
    # A real variable-font weight change changes the rendered width.
    assert regular.getlength("Mogra Organics") != bold.getlength("Mogra Organics")


# ---------------------------------------------------------------------------
# Label-zone detection
# ---------------------------------------------------------------------------

def _panel_image(w=400, h=400, x0=0.3, y0=0.3, x1=0.7, y1=0.7):
    im = Image.new("RGB", (w, h), (34, 78, 46))  # saturated background
    d = ImageDraw.Draw(im)
    d.rectangle([int(w * x0), int(h * y0), int(w * x1), int(h * y1)],
                fill=(250, 249, 245))            # bright, low-sat panel
    return im


def test_detect_finds_centered_panel():
    zone = label_zone.detect_label_zone(_panel_image())
    assert zone is not None
    xs = [p[0] for p in zone["quad_norm"]]
    ys = [p[1] for p in zone["quad_norm"]]
    assert 0.2 <= min(xs) <= 0.35
    assert 0.65 <= max(xs) <= 0.8
    assert 0.2 <= min(ys) <= 0.35
    assert 0.65 <= max(ys) <= 0.8
    assert zone["confidence"] >= 0.25


def test_detect_returns_none_for_border_touching_region():
    # A fully bright image is all "border" background — not a panel.
    im = Image.new("RGB", (200, 200), (252, 251, 248))
    assert label_zone.detect_label_zone(im) is None


def test_detect_returns_none_for_flat_colour():
    im = Image.new("RGB", (200, 200), (30, 60, 40))
    assert label_zone.detect_label_zone(im) is None


def test_detect_ignores_tiny_specks():
    im = Image.new("RGB", (400, 400), (34, 78, 46))
    ImageDraw.Draw(im).rectangle([198, 198, 204, 204], fill=(252, 252, 250))
    assert label_zone.detect_label_zone(im) is None  # below min area


def test_detect_result_serialisable():
    import json
    zone = label_zone.detect_label_zone(_panel_image())
    json.dumps(zone)


def test_detect_does_not_merge_adjacent_bright_window():
    # A bright label sits directly above a bright but textured product window with
    # a crisp edge between them: detection must stop at that edge.
    import random
    im = Image.new("RGB", (400, 600), (30, 70, 45))
    d = ImageDraw.Draw(im)
    d.rectangle([80, 120, 320, 300], fill=(250, 249, 245))   # smooth label
    d.rectangle([80, 305, 320, 470], fill=(243, 238, 225))   # bright window
    rnd = random.Random(1)
    for _ in range(6000):                                    # texture the window
        im.putpixel((rnd.randint(81, 319), rnd.randint(306, 469)),
                    (rnd.randint(190, 255), rnd.randint(180, 245), rnd.randint(160, 230)))
    zone = label_zone.detect_label_zone(im)
    assert zone is not None
    ys = [p[1] for p in zone["quad_norm"]]
    assert max(ys) < 0.56, f"panel bled into the window: {zone['quad_norm']}"


def test_detect_snaps_out_to_shaded_panel_edge():
    # Panel whose right side is shaded below threshold, ending at a crisp edge:
    # the box should extend to that edge, not stop at the bright core.
    im = Image.new("RGB", (400, 400), (30, 70, 45))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 120, 240, 280], fill=(250, 249, 245))  # bright core
    for x in range(241, 300):                                # soft shading ramp
        v = int(245 - (245 - 150) * (x - 241) / 59.0)
        d.line([(x, 120), (x, 280)], fill=(v, v, v - 6))
    zone = label_zone.detect_label_zone(im)
    assert zone is not None
    xs = [p[0] for p in zone["quad_norm"]]
    assert max(xs) > 0.72, f"box did not snap to the shaded edge: {zone['quad_norm']}"


# ---------------------------------------------------------------------------
# Pipeline: alignment
# ---------------------------------------------------------------------------

def test_build_mockup_align_auto_detects(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    _panel_image(500, 500).save(src)
    res = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, align="auto", out_path=tmp_path / "out.png")
    assert res["align"]["source"] == "detected"
    assert res["align"]["confidence"] >= 0.25


def test_build_mockup_align_preset_uses_preset(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    _panel_image(500, 500).save(src)
    res = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, align="preset", out_path=tmp_path / "out.png")
    assert res["align"]["source"] == "preset"


def test_build_mockup_align_auto_falls_back_without_panel(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    Image.new("RGB", (400, 400), (30, 60, 40)).save(src)
    res = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, align="auto", out_path=tmp_path / "out.png")
    assert res["align"]["source"] == "preset_fallback"


# ---------------------------------------------------------------------------
# Pipeline: blank-panel prep stage (ComfyUI mocked out)
# ---------------------------------------------------------------------------

def test_blank_panel_uses_panel_preserving_prompt(monkeypatch, tmp_path):
    seen = {}

    def fake_edit(prompt, source_path, out_path, **kw):
        seen["prompt"] = prompt
        return {"lane": "qwen-image-edit-2511", "output": str(out_path)}

    monkeypatch.setattr(comfy_client, "edit_scene", fake_edit)
    comfy_client.blank_panel("in.png", tmp_path / "out.png")
    assert "do not remove" in seen["prompt"].lower()
    assert "no text" in seen["prompt"].lower()


def test_build_mockup_rejects_unknown_panel_prep(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    _panel_image(300, 300).save(src)
    with pytest.raises(ValueError):
        mogra_mockup.build_mockup(
            product="organic_turmeric_powder", source_image=src,
            panel_prep="bogus", out_path=tmp_path / "out.png")


def test_build_mockup_panel_prep_then_align(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    src = tmp_path / "base.png"
    _panel_image(500, 500).save(src)

    def fake_blanks(source_path, out_path, **kw):
        _panel_image(500, 500).save(out_path)  # pretend Edit-2511 blanked it
        return {"lane": "qwen-image-edit-2511", "output": str(out_path)}

    monkeypatch.setattr(comfy_client, "blank_panel", fake_blanks)
    res = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, panel_prep="edit_blank", align="auto",
        out_path=tmp_path / "out.png")
    assert res["panel_prep"]["applied"] is True
    assert "qwen-image-edit-2511" in res["lane"]
    assert res["align"]["source"] == "detected"


# ---------------------------------------------------------------------------
# Scene prompt still forbids text even with prep
# ---------------------------------------------------------------------------

def test_prep_prompt_forbids_text():
    p = comfy_client.PANEL_PREP_PROMPT.lower()
    assert "no text" in p and "logos" in p


def test_presets_unchanged_by_productization():
    assert presets.MOGRA_BRAND["name"] == "Mogra Organics"
    assert len(presets.CONTAINER_PRESETS) == 3
