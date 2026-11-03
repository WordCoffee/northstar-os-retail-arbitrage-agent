"""Social frame endpoint: decode, render, check, save (or refuse)."""
from __future__ import annotations

import base64
import io

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

import social_frames as sf
import social_frames_api as sfa


def _product_data_url() -> str:
    img = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(150, 80), (450, 80), (470, 820), (130, 820)], fill=(213, 167, 122, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _body(**over):
    data = dict(product_data_url=_product_data_url(), placement="meta-feed",
                headline="LION'S MANE", subline="MUSHROOM POWDER", cta="SHOP NOW")
    data.update(over)
    return sfa.SocialFrameIn(**data)


def test_a_frame_is_rendered_checked_and_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(sfa, "OUT_DIR", tmp_path)
    out = sfa.render_frame(_body(), acct="test")
    assert out["ok"] is True
    assert all(out["checks"].values()), out["checks"]
    assert (tmp_path / (out["file"].split("\\")[-1])).is_file()
    assert out["data_url"].startswith("data:image/png;base64,")
    assert out["canvas"] == [1024, 1024]


def test_a_no_text_placement_refuses_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(sfa, "OUT_DIR", tmp_path)
    with pytest.raises(HTTPException) as err:
        sfa.render_frame(_body(placement="amazon-main"), acct="test")
    assert err.value.status_code == 422
    assert "placement_refuses_copy" in str(err.value.detail)


def test_an_unknown_placement_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(sfa, "OUT_DIR", tmp_path)
    with pytest.raises(HTTPException) as err:
        sfa.render_frame(_body(placement="myspace"), acct="test")
    assert err.value.status_code == 422
    assert "placement_unknown" in str(err.value.detail)


def test_a_failed_check_is_a_422_with_the_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(sfa, "OUT_DIR", tmp_path)
    monkeypatch.setattr(sf, "check_frame", lambda *a, **k: {
        "ok": False, "reason": "frame_contract_failed: headline_read",
        "checks": {"headline_read": False}, "words": []})
    with pytest.raises(HTTPException) as err:
        sfa.render_frame(_body(), acct="test")
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "frame_refused"
    assert "candidate" in err.value.detail


def test_the_placements_endpoint_lists_all_eight():
    out = sfa.placements(acct="test")
    assert len(out["placements"]) == 8
    assert all("safe_zones" in p and "canvas" in p for p in out["placements"])
