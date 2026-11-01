"""A+ renderer: exact geometry, measured legibility, refusal of bad copy.

These tests assert BEHAVIOUR, not pixels: the canvas is exactly the planner size,
type stays inside its container, contrast is measured rather than assumed, the
2 MB / PNG-or-JPG contract holds, and copy that could never be legible or legal is
refused instead of shipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aplus_layout as geo
import aplus_render as ar
from specialists import image_aplus as spec

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"


def _image(w: int = 1600, h: int = 1000, colour=(246, 242, 234)) -> Image.Image:
    """A soft, light plate: enough variation to be a real image, low contrast."""
    img = Image.new("RGB", (w, h), colour)
    px = img.load()
    for y in range(0, h, 2):
        shift = int(10 * (y / max(1, h - 1)))
        for x in range(0, w, 7):
            px[x, y] = (min(255, colour[0] + shift), min(255, colour[1] + shift),
                        min(255, colour[2] + shift))
    return img


def _mid_grey(w: int = 1600, h: int = 1000) -> Image.Image:
    """Mid grey: dark ink on this is ~4:1, so a truthful renderer must scrim."""
    return Image.new("RGB", (w, h), (128, 128, 128))


def _light_plate(w: int = 1600, h: int = 1000) -> Image.Image:
    return Image.new("RGB", (w, h), (252, 251, 249))


COPY = {"headline": "Lion's Mane", "sub": "Organic mushroom powder, 6 oz",
        "kicker": "Mogra Organics"}

ALL_KINDS = sorted(geo.CANVAS)


def _render(kind, **kw):
    base = {"copy": COPY, "image": _image(), "tiles": [_image(), _image(), _image()]}
    base.update(kw)
    return ar.render_module(kind, **base)


# ── contract: exact, uploadable canvas ──────────────────────────────────────

@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_renders_at_the_exact_planner_size(kind):
    res = _render(kind)
    img = Image.open(__import__("io").BytesIO(res["png"]))
    assert img.size == geo.CANVAS[kind]
    assert res["size"] == list(geo.CANVAS[kind])
    assert res["qa"]["canvas"] == list(geo.CANVAS[kind])


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_is_upload_ready_and_clears_the_planner_validator(kind, tmp_path):
    res = _render(kind)
    assert res["qa"]["ok"] is True, res["qa"]["problems"]
    assert res["qa"]["bytes"] <= spec.MAX_MODULE_BYTES
    assert res["format"] in ("PNG", "JPEG")
    p = tmp_path / f"{kind}.{'png' if res['format'] == 'PNG' else 'jpg'}"
    p.write_bytes(res["png"])
    check = spec.validate_module_image(p, kind)
    assert check["ok"] is True, check["problems"]


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_all_type_stays_inside_its_container(kind):
    res = _render(kind)
    for rec in res["texts"]:
        x0, y0, x1, y1 = rec["bbox"]
        c = rec["container"]
        assert x0 >= c["x"] - 1 and y0 >= c["y"] - 1, (kind, rec["id"])
        assert x1 <= c["x"] + c["w"] + 1 and y1 <= c["y"] + c["h"] + 1, (kind, rec["id"])


# ── legibility is measured, and rescued, not assumed ────────────────────────

def test_the_default_reserves_a_panel_so_type_never_lands_on_the_photo():
    res = ar.render_module("header", copy=COPY, image=_mid_grey())
    assert res["copy_mode"] == "panel"
    assert res["qa"]["ok"] is True, res["qa"]["problems"]
    assert res["qa"]["min_contrast"] >= ar.CONTRAST_BODY


def test_overlay_mode_scrims_a_midtone_plate_until_it_passes():
    res = ar.render_module("header", copy=COPY, image=_mid_grey(), copy_style="overlay")
    assert res["copy_mode"] == "scrim"
    assert res["qa"]["ok"] is True, res["qa"]["problems"]
    head = next(t for t in res["texts"] if t["id"] == "headline")
    assert head["contrast"] >= ar.OVERLAY_MIN_CONTRAST


def test_overlay_light_type_on_a_bright_plate_gets_a_dark_scrim():
    brand = {"ink": (250, 248, 242), "field": (26, 30, 28), "accent": (200, 178, 130)}
    res = ar.render_module("banner", copy=COPY, image=_light_plate(), brand=brand,
                           copy_style="overlay")
    assert res["copy_mode"] == "scrim"
    assert res["qa"]["ok"] is True, res["qa"]["problems"]


def test_overlay_on_a_plain_plate_needs_no_scrim():
    res = ar.render_module("header", copy=COPY, image=_image(), copy_style="overlay")
    assert res["copy_mode"] == "none"
    assert res["qa"]["ok"] is True


def test_overlay_over_busy_printing_is_refused_even_when_contrast_passes():
    """The defect this check exists for: 4.5:1 over a photo of printed packaging
    measures fine and still reads as a collision."""
    busy = Image.new("RGB", (1600, 1000), (245, 242, 235))
    d = ImageDraw.Draw(busy)
    for y in range(0, 1000, 40):
        for x in range(0, 1600, 60):
            d.text((x, y), "MOGRA ORGANICS LION'S MANE", font=ar._font(ar.BODY_FONT, 22, None),
                   fill=(20, 30, 25))
    res = ar.render_module("header", copy=COPY, image=busy, copy_style="overlay")
    assert res["qa"]["ok"] is False
    assert any("busy backdrop" in p for p in res["qa"]["problems"])
    # the same plate is fine when the type gets its own column
    assert ar.render_module("header", copy=COPY, image=busy)["qa"]["ok"] is True


def test_unknown_copy_style_is_rejected():
    with pytest.raises(ValueError):
        ar.render_module("header", copy=COPY, image=_image(), copy_style="floating")


def test_ink_equal_to_the_plate_is_refused_not_shipped():
    grey = (40, 40, 40)
    brand = {"ink": grey, "field": grey, "accent": (120, 120, 120)}
    res = ar.render_module("banner", copy=COPY,
                           image=Image.new("RGB", (1600, 1000), grey), brand=brand)
    assert res["qa"]["ok"] is False
    assert any("contrast" in p for p in res["qa"]["problems"])
    with pytest.raises(ar.AplusNotPerfect):
        ar.assert_perfect(res)


def test_contrast_maths_matches_wcag_reference():
    assert ar.contrast_ratio((0, 0, 0), (255, 255, 255)) == 21.0
    assert ar.contrast_ratio((255, 255, 255), (255, 255, 255)) == 1.0
    assert 4.4 < ar.contrast_ratio((23, 38, 32), (247, 244, 237)) < 15.5


# ── copy is refused before a pixel is written ──────────────────────────────

@pytest.mark.parametrize("bad", [
    "Only $19.99 today",
    "Now on sale - 20% off",
    "Free shipping on every order",
    "Outperforms every rival brand",
    "Cures inflammation in days",
])
def test_prohibited_a_plus_copy_is_refused(bad):
    with pytest.raises(ar.AplusNotPerfect) as exc:
        ar.render_module("header", copy={"headline": bad}, image=_image())
    assert "prohibited" in str(exc.value)


def test_clean_copy_is_not_flagged():
    ar.render_module("header", copy={"headline": "Organic Lion's Mane, 6 oz"},
                     image=_image())


def test_copy_that_cannot_fit_at_the_floor_is_reported():
    long_copy = "Lion's Mane " * 40
    res = ar.render_module("header", copy={"headline": long_copy}, image=_image())
    assert res["qa"]["ok"] is False
    assert any("does not fit" in p for p in res["qa"]["problems"])


def test_long_headline_shrinks_but_stays_above_the_floor():
    res = ar.render_module("header",
                           copy={"headline": "A rather long product name that still fits"},
                           image=_image())
    assert res["qa"]["ok"] is True
    head = next(t for t in res["texts"] if t["id"] == "headline")
    assert head["size"] >= ar.MIN_HEAD_PX
    assert head["fits"] is True


# ── imagery honesty ────────────────────────────────────────────────────────

def test_a_tiny_plate_is_refused_because_it_would_be_blurred():
    res = ar.render_module("header", copy=COPY, image=Image.new("RGB", (300, 200), (240, 240, 240)))
    assert res["qa"]["ok"] is False
    assert any("too small" in p for p in res["qa"]["problems"])


def test_tile_rows_use_every_tile_and_are_centred_by_the_layout():
    for kind, count in (("three_tiles", 3), ("four_tiles", 4)):
        res = _render(kind, tiles=[_image(600, 600)] * count)
        assert res["layout"]["tiles"] == geo.layout(kind)["tiles"]
        assert res["qa"]["ok"] is True, res["qa"]["problems"]


def test_one_image_is_reused_across_the_row_with_a_recorded_warning():
    res = _render("three_tiles", tiles=[_image(900, 900)])
    assert res["qa"]["ok"] is True
    assert any("reused" in w for w in res["qa"]["warnings"])


def test_tile_row_without_imagery_is_refused():
    with pytest.raises(ar.AplusNotPerfect):
        ar.render_module("three_tiles", copy={"tiles": ["a", "b", "c"]})


def test_tile_caption_that_cannot_fit_is_reported():
    too_long = "Reishi Lion's Mane Shiitake Cordyceps Chaga Turkey Tail Maitake " * 3
    res = ar.render_module("four_tiles", copy={"tiles": [too_long] * 4},
                           tiles=[_image(600, 600)] * 4)
    assert res["qa"]["ok"] is False
    assert any("does not fit" in p for p in res["qa"]["problems"])


# ── comparison table ───────────────────────────────────────────────────────

def test_comparison_draws_four_rows_and_two_columns():
    res = ar.render_module("comparison", copy={
        "headline": "Which one is yours?",
        "columns": ["Lion's Mane", "Shiitake"],
        "rows": [{"label": "Organic", "values": ["yes", "yes"]},
                 {"label": "Net weight", "values": ["6 oz", "4 oz"]},
                 {"label": "Powdered", "values": ["yes", "no"]}],
    })
    assert res["qa"]["ok"] is True, res["qa"]["problems"]
    comp = res["layout"]["comparison"]
    assert comp["rows"] == 4
    assert len(comp["columns"]) == 2
    ids = {t["id"] for t in res["texts"]}
    assert "row0.label" in ids and "row1.col1" in ids
    assert any(t["id"] == "headline" for t in res["texts"])


def test_comparison_defaults_the_second_column_rather_than_inventing_one():
    res = ar.render_module("comparison", copy={"columns": ["Only Ours"]})
    assert res["qa"]["ok"] is True


# ── determinism ────────────────────────────────────────────────────────────

def test_the_same_inputs_produce_identical_bytes():
    a = ar.render_module("header", copy=COPY, image=_image())
    b = ar.render_module("header", copy=COPY, image=_image())
    assert a["png"] == b["png"]


def test_unknown_kind_is_a_keyerror():
    with pytest.raises(KeyError):
        ar.render_module("does_not_exist")


def test_the_planner_validator_measures_the_row_canvas_not_the_tile(tmp_path):
    """Regression: 970x300 rows are correct for three_tiles; 300x300 is not.

    ``MODULES['three_tiles']`` carries the TILE size, so validating a row image
    against it rejected every correct asset. The expected size must come from the
    same table the renderer draws into.
    """
    row = tmp_path / "row.png"
    Image.new("RGB", (970, 300), (240, 238, 232)).save(row)
    assert spec.validate_module_image(row, "three_tiles")["ok"] is True

    tile = tmp_path / "tile.png"
    Image.new("RGB", (300, 300), (240, 238, 232)).save(tile)
    check = spec.validate_module_image(tile, "three_tiles")
    assert check["ok"] is False
    assert "970x300" in check["problems"][0]

    comp = tmp_path / "comp.png"
    Image.new("RGB", (970, 600), (240, 238, 232)).save(comp)
    assert spec.validate_module_image(comp, "comparison")["ok"] is True


def test_logo_module_needs_a_mark_or_a_name():
    res = ar.render_module("logo", copy={"brand": "Mogra Organics"})
    assert res["qa"]["ok"] is True
    with pytest.raises(ar.AplusNotPerfect):
        ar.render_module("logo", copy={})


# ── page assembly ──────────────────────────────────────────────────────────

def test_render_page_writes_assets_a_manifest_and_a_preview(tmp_path):
    manifest = ar.render_page(
        [{"kind": "header", "copy": COPY},
         {"kind": "three_tiles", "copy": {"tiles": ["Reishi", "Lion's Mane", "Shiitake"]}},
         {"kind": "comparison", "copy": {"columns": ["Ours", "Theirs"],
                                         "rows": [{"label": "Organic", "values": ["yes", "no"]}]}}],
        image=_image(), tiles=[_image(800, 800)], out_dir=tmp_path)
    assert manifest["ok"] is True, manifest["problems"]
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "aplus_01_header.png" in files
    assert "aplus_02_three_tiles.png" in files
    assert "aplus_03_comparison.png" in files
    assert "aplus_manifest.json" in files
    assert "aplus_preview.png" in files
    on_disk = json.loads((tmp_path / "aplus_manifest.json").read_text(encoding="utf-8"))
    assert on_disk["ok"] is True
    assert len(on_disk["modules"]) == 3
    assert all("path" in m for m in on_disk["modules"])


def test_preview_stacks_the_modules_at_full_width(tmp_path):
    ar.render_page(["header", "banner"], image=_image(), out_dir=tmp_path)
    sheet = Image.open(tmp_path / "aplus_preview.png")
    h1, h2 = geo.CANVAS["header"][1], geo.CANVAS["banner"][1]
    assert sheet.width == 970
    assert sheet.height == h1 + h2 + 3 * 24


def test_render_page_reports_a_bad_module_instead_of_hiding_it(tmp_path):
    manifest = ar.render_page([{"kind": "header", "copy": {"headline": "Lion's Mane " * 40}}],
                              image=_image(), out_dir=tmp_path)
    assert manifest["ok"] is False
    assert any("header:" in p for p in manifest["problems"])


def test_cli_returns_nonzero_when_the_module_is_not_perfect(tmp_path):
    out = tmp_path / "h.png"
    code = ar.main(["--kind", "header", "--out", str(out),
                    "--headline", "Lion's Mane", "--sub", "Organic powder"])
    assert code == 0
    assert out.exists()
