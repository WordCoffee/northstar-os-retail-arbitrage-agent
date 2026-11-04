"""Listing image pipeline: text-safe render -> matching gate."""
from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

import listing_render
import listing_image_api as api
import social_frames as sf


def _image(bg=(255, 255, 255), margin=72) -> Image.Image:
    img = Image.new("RGB", (1024, 1024), bg)
    ImageDraw.Draw(img).rectangle([margin, margin, 1024 - margin, 1024 - margin],
                                  fill=(213, 167, 122))
    return img


def _bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render(img):
    def inner(prompt, *, width, height, tier):
        return _bytes(img)
    return inner


def test_a_white_background_main_image_passes():
    out = listing_render.generate("white-bg", "a kraft pouch", render=_render(_image()))
    assert out["ok"] is True, out
    assert out["main_image"] is True
    assert out["gate"]["checks"]["text_free"] is True
    assert out["gate"]["checks"]["listing_rubric_pass"] is True


def test_a_grey_background_is_normalised_to_pure_white():
    """The main-image pass crops the subject onto white; the gate then passes."""
    out = listing_render.generate("white-bg", render=_render(_image(bg=(200, 200, 200))))
    assert out["ok"] is True, out
    assert out["gate"]["score"]["metrics"]["background_purity"] >= 0.90


def test_a_blank_render_is_refused():
    blank = Image.new("RGB", (1024, 1024), (255, 255, 255))
    out = listing_render.generate("white-bg", render=_render(blank))
    assert out["ok"] is False
    assert "listing_rubric_pass" in out["reason"]


def test_fit_main_image_hits_the_fill_band():
    small = Image.new("RGB", (1024, 1024), (255, 255, 255))
    ImageDraw.Draw(small).rectangle([110, 110, 914, 914], fill=(213, 167, 122))
    fitted = listing_render.fit_main_image(_bytes(small))
    gate = sf.listing_gate(fitted, main_image=True)
    assert gate["ok"] is True, gate
    assert 0.80 <= gate["score"]["metrics"]["fill"] <= 0.92


def test_a_secondary_style_uses_the_hook_rubric():
    out = listing_render.generate("lifestyle", "a pouch on a counter",
                                 render=_render(_image()))
    assert out["main_image"] is False
    assert out["gate"]["checks"]["text_free"] is True


def test_an_unknown_style_raises():
    with pytest.raises(ValueError, match="listing_style_unknown"):
        listing_render.generate("billboard", render=_render(_image()))


def test_the_api_saves_a_passing_image(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUT_DIR", tmp_path)

    def fake(style, brief, **kw):
        return {"ok": True, "style": style, "main_image": True,
                "prompt": "p", "used_brief": "p", "text_fidelity": {"verdict": "text_free"},
                "bytes": _bytes(_image()), "gate": {"ok": True, "checks": {}},
                "reason": ""}

    monkeypatch.setattr(listing_render, "generate", fake)
    out = api.create_listing_image(api.ListingImageIn(style="white-bg"), acct="test")
    assert out["ok"] is True
    assert out["size"] == [1024, 1024]
    assert out["data_url"].startswith("data:image/png;base64,")


def test_the_api_saves_a_rejected_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUT_DIR", tmp_path)

    def fake(style, brief, **kw):
        return {"ok": False, "style": style, "main_image": True,
                "prompt": "p", "used_brief": "p", "text_fidelity": {},
                "bytes": _bytes(_image(bg=(200, 200, 200))),
                "gate": {"ok": False, "checks": {"listing_rubric_pass": False}},
                "reason": "listing_image_refused: listing_rubric_pass"}

    monkeypatch.setattr(listing_render, "generate", fake)
    with pytest.raises(HTTPException) as err:
        api.create_listing_image(api.ListingImageIn(style="white-bg"), acct="test")
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "listing_image_refused"
    assert "candidate" in err.value.detail


def test_the_styles_endpoint_returns_the_pack():
    out = api.styles(acct="test")
    assert len(out["styles"]) == 5
