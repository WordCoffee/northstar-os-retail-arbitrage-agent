"""Text-fidelity pipeline tests (RE build follow-up 2026-10-16).

FIX half: sanitize_brief_for_render strips typographic demands pre-render.
CHECK half: check_text_in_image runs real OCR (rapidocr, CPU, offline).

The OCR tests use a synthetic image drawn with PIL - deterministic, no assets.
"""

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import design_studio_api  # noqa: E402
import text_fidelity as tf  # noqa: E402
from main import app  # noqa: E402

MOGRA_LIKE = """# MOGRA ORGANICS - POUCH PACKAGING DESIGN BRIEF
## OBJECTIVE
Design print-ready packaging artwork for two Mogra Organics mushroom powder pouches.
- Bag type: matte stand-up pouch (doypack) with resealable zipper and bottom gusset
- Finish: full-coverage matte print, both sides
- Palette: black #171717, kraft #D5A77A, olive #9DBA8B, ivory #F5EEE2
- Illustration: engraved/line-art botanical mushroom illustration (lion's mane form)
## FRONT PANEL LAYOUT
1. Logo lockup centered top third - mortar-pestle icon + MOGRA ORGANICS + tagline
2. Product name large: "ORGANIC LION'S MANE" + "MUSHROOM POWDER" beneath
5. Bottom: "6 oz (170g)" + footer text
3. RESERVED ZONE - QR code + UPC barcode
4. Zipper icon + reseal note, barcode below
Typography: high-contrast serif for wordmark, clean sans serif for information text
"""


def _img_with_text(text: str) -> bytes:
    img = Image.new("RGB", (640, 320), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=56)
    d.text((30, 120), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _img_plain() -> bytes:
    img = Image.new("RGB", (320, 320), "#D5A77A")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── FIX half ────────────────────────────────────────────────────────────────

def test_sanitize_strips_typographic_demands_and_keeps_art():
    r = tf.sanitize_brief_for_render(MOGRA_LIKE)
    p = r["render_prompt"]
    # the negative phrase legitimately names these things; scan the body only
    body = p.replace(tf.SUPPRESSION_PHRASE, "")
    for banned in ("MOGRA", "ORGANIC LION", "wordmark", "serif", "barcode", "QR code",
                   "6 oz", "170g", "tagline", "footer text"):
        assert banned.lower() not in body.lower(), banned
    # art direction survives
    assert "matte stand-up pouch" in p
    assert "kraft #D5A77A" in p
    assert "engraved/line-art botanical mushroom illustration" in p
    # suppression phrase + honest accounting
    assert tf.SUPPRESSION_PHRASE in p
    assert r["suppressed_count"] >= 5
    assert r["kept_count"] >= 4
    assert "MOGRA ORGANICS" in r["expected_terms"] or any("MOGRA" in t for t in r["expected_terms"])


def test_sanitize_survives_empty_and_junk_briefs():
    r = tf.sanitize_brief_for_render("")
    assert r["render_prompt"] == tf.SUPPRESSION_PHRASE
    r2 = tf.sanitize_brief_for_render("text text text")
    assert tf.SUPPRESSION_PHRASE in r2["render_prompt"]


def test_prepare_render_brief_passthrough_when_not_text_safe():
    prep = tf.prepare_render_brief("keep me exactly", False)
    assert prep == {"brief": "keep me exactly", "text_fidelity": None}
    prep2 = tf.prepare_render_brief(MOGRA_LIKE, True)
    assert prep2["text_fidelity"]["mode"] == "text_safe"
    assert len(prep2["brief"]) > 50


# ── CHECK half (real OCR) ───────────────────────────────────────────────────

def test_ocr_detects_text_and_passes_clean_render():
    with_text = tf.check_text_in_image(_img_with_text("MOGRA ORGANICS"))
    if with_text["status"] == "unavailable":
        import pytest
        pytest.skip(f"OCR engine unavailable: {with_text['error']}")
    assert with_text["status"] == "ok"
    assert with_text["contains_text"] is True
    assert with_text["boxes"] >= 1
    assert any("MOGRA" in w.upper() for w in with_text["words"])

    clean = tf.check_text_in_image(_img_plain())
    assert clean["status"] == "ok"
    assert clean["contains_text"] is False


def test_verify_asset_verdicts():
    v = tf.verify_asset_text(_img_plain(), brief=MOGRA_LIKE, text_safe=True)
    if v["check"]["status"] == "unavailable":
        import pytest
        pytest.skip("OCR engine unavailable")
    assert v["verdict"] == "text_free"

    v2 = tf.verify_asset_text(_img_with_text("MOGRA ORGANICS"), brief=MOGRA_LIKE, text_safe=True)
    assert v2["verdict"] in ("text_present", "text_present_matches_expected")
    assert "MOGRA ORGANICS" in v2["expected_terms"]


def test_hard_sanitize_strips_capitals_and_digits_but_keeps_hex_and_lowercase_art():
    r = tf.sanitize_brief_for_render(MOGRA_LIKE, hard=True)
    body = r["render_prompt"].replace(tf.SUPPRESSION_PHRASE, "")
    import re as _re
    stripped = _re.sub(r"#[0-9A-Fa-f]{3,8}", "", body)  # palette hex may keep digits/caps
    assert not _re.search(r"[A-Z]", stripped), stripped[:200]
    assert not _re.search(r"\d", stripped), stripped[:200]
    assert "#D5A77A" in body
    assert "matte stand-up pouch" in body
    assert r["hard"] is True


def test_render_with_text_guard_auto_reruns_once_when_text_found():
    calls = []

    def fake_render(prompt, **_):
        calls.append(prompt)
        img = _img_with_text("GARBLED TEXT") if len(calls) == 1 else _img_plain()
        return {"bytes": img, "ext": "png", "mime": "image/png", "model": "fake", "seed": 1}

    g = tf.render_with_text_guard(render_fn=fake_render, brief=MOGRA_LIKE, text_safe=True)
    if g["text_fidelity"]["check"]["status"] == "unavailable":
        import pytest
        pytest.skip("OCR engine unavailable")
    assert len(calls) == 2, "exactly one bounded auto-rerun"
    assert g["text_fidelity"]["retried"] is True
    assert g["text_fidelity"]["verdict"] == "text_free"
    assert len(g["text_fidelity"]["attempts"]) == 2
    assert g["text_fidelity"]["attempts"][0]["contains_text"] is True
    assert "render_prompt" in g["text_fidelity"]

    calls.clear()
    g2 = tf.render_with_text_guard(render_fn=fake_render, brief=MOGRA_LIKE, text_safe=False)
    assert len(calls) == 1 and g2["text_fidelity"] is None


def test_clean_text_regions_clears_and_rechecks():
    res = tf.clean_text_regions(_img_with_text("MOGRA ORGANICS"))
    if res["status"] != "ok":
        pytest.skip("OCR unavailable")
    assert res["cleared"] >= 1
    after = tf.check_text_in_image(res["image"])
    assert after["contains_text"] is False


def test_clean_text_regions_noop_on_clean_image():
    img = _img_plain()
    res = tf.clean_text_regions(img)
    assert res["status"] == "ok" and res["cleared"] == 0
    assert res["image"] == img


def test_guard_cleans_when_model_keeps_painting():
    calls = []

    def always_text(prompt, **_):
        calls.append(prompt)
        return {"bytes": _img_with_text("GARBLED GLYPHS"), "ext": "png",
                "mime": "image/png", "model": "fake", "seed": 1}

    g = tf.render_with_text_guard(render_fn=always_text, brief=MOGRA_LIKE, text_safe=True)
    if g["text_fidelity"]["check"]["status"] != "ok":
        pytest.skip("OCR unavailable")
    assert len(calls) == 2  # retry ran
    assert g["text_fidelity"].get("text_cleanup", {}).get("cleared", 0) >= 1
    assert g["text_fidelity"]["verdict"] in ("text_cleared", "text_reduced")


# ── endpoint ────────────────────────────────────────────────────────────────

def test_text_check_endpoint_auth_and_404():
    r = TestClient(app).post("/api/design-studio/text-check/whatever")
    assert r.status_code == 401

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-tf"
    try:
        r = TestClient(app).post("/api/design-studio/text-check/no-such-asset")
        assert r.status_code == 404
    finally:
        app.dependency_overrides = {}
