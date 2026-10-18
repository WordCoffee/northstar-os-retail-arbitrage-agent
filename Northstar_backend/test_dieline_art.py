"""Dieline-art lane tests: panel grounds, content, reserved-zone layout, PDF."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_print as dp  # noqa: E402
import dieline_art as da  # noqa: E402

KRAFT = (213, 167, 122)


def _logo():
    img = Image.new("RGBA", (200, 160), (252, 252, 252, 255))
    ImageDraw.Draw(img).rectangle([70, 75, 130, 95], fill=(60, 40, 30, 255))
    return img


def _build():
    return dp.build_from_template("doypack", {"width_mm": 130, "height_mm": 210,
                                              "gusset_mm": 40, "weld_mm": 6,
                                              "top_weld_mm": 8, "zip_offset_mm": 25,
                                              "bleed_mm": 3})


def test_doypack_meta_has_panels():
    b = _build()
    p = b["meta"]["panels"]
    assert set(p) >= {"front", "gusset", "back", "zip_y"}
    for key in ("front", "gusset", "back"):
        x, y, w, h = p[key]
        assert w > 0 and h > 0 and x > 0 and y > 0


def test_art_ops_grounds_and_content():
    b = _build()
    sku = {"title": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)", "ground": KRAFT,
           "title_color": (245, 238, 226), "subtitle_color": (245, 238, 226),
           "gold": da.GOLD_A}
    ops = da.build_ops(b, sku, _logo(), (255, 255, 255))
    kinds = [o["kind"] for o in ops]
    assert kinds[:3] == ["panel_fill"] * 3, "panels must be printed (grounded) first"
    assert "image" in kinds and "icons" in kinds and "text_centered" in kinds

    img = da.render_png(b, ops, _logo(), (255, 255, 255), dpi=25)
    a = np.array(img)
    mm = 25 / 25.4
    fx, fy, fw, fh = b["meta"]["panels"]["front"]
    # front ground is kraft, not white
    cx = int((fx + fw / 2) * mm)
    top = int((fy + 4) * mm)
    assert abs(int(a[top, cx, 0]) - KRAFT[0]) < 12, f"front ground wrong: {a[top, cx]}"
    # title row has lighter-than-ground pixels at title height
    ty = int((fy + fh * 0.40) * mm)
    row = a[ty - 2:ty + 2, int((fx + fw * 0.2) * mm):int((fx + fw * 0.8) * mm)]
    assert (row[..., 0].astype(int) - KRAFT[0] > 18).sum() > 5, "title ink missing"


def test_motif_extraction_and_placement():
    # synthetic LINE ART (thin strokes, like an engraving) on light ground
    base = Image.new("RGB", (300, 220), (235, 230, 220))
    dr = ImageDraw.Draw(base)
    for x0 in (110, 130, 150, 170):
        dr.line([(x0, 60), (x0, 160)], fill=(40, 30, 25), width=6)
    motif = da.extract_ink_motif(base, [60, 30, 240, 190])
    m = np.array(motif)
    # stroke at original x=130 -> crop x=70; y centre 110 -> crop y=80
    assert m[80, 70, 3] > 128, "stroke ink missing from alpha"
    assert m[155, 5, 3] == 0 and m[10, 175, 3] == 0, "ground leaked into alpha"

    b = _build()
    sku = {"title": "X", "weight": "y", "ground": KRAFT, "motif": motif,
           "title_color": (245, 238, 226), "subtitle_color": (245, 238, 226)}
    ops = da.build_ops(b, sku, _logo(), (255, 255, 255))
    assert any(o["kind"] == "motif" for o in ops)
    img = da.render_png(b, ops, _logo(), (255, 255, 255), dpi=25)
    a = np.array(img)
    mm = 25 / 25.4
    fx, fy, fw, fh = b["meta"]["panels"]["front"]
    my = int((fy + fh * 0.615) * mm)
    mx = int((fx + fw / 2) * mm)
    patch = a[my - 4:my + 4, mx - 4:mx + 4].astype(int)
    assert patch.mean() < KRAFT[0] - 8, "motif ink not visible on the sheet"


def test_reserved_zones_do_not_overlap():
    b = _build()
    sku = {"title": "X", "weight": "y", "ground": KRAFT,
           "title_color": (245, 238, 226), "subtitle_color": (245, 238, 226)}
    ops = da.build_ops(b, sku, _logo(), (255, 255, 255))
    boxes = [o for o in ops if o["kind"] == "box"]
    # supplement facts block = the tall one on the right
    tall = max(boxes, key=lambda o: o["y1"] - o["y0"])
    qr_row = [o for o in boxes if o is not tall]
    assert all(o["y0"] >= tall["y1"] for o in qr_row), "QR/UPC must sit BELOW the facts block"


def test_render_pdf_bytes():
    b = _build()
    sku = {"title": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)", "ground": (245, 238, 226),
           "title_color": (37, 54, 40), "subtitle_color": (37, 54, 40)}
    ops = da.build_ops(b, sku, _logo(), (255, 255, 255))
    pdf = da.render_pdf(b, ops, _logo(), None, (255, 255, 255))
    assert pdf[:4] == b"%PDF" and len(pdf) > 20000
