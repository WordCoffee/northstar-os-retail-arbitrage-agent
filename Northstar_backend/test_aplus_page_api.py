"""A+ page endpoint: a plate in, six measured modules out."""
from __future__ import annotations

import base64
import io

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

import aplus_page_api as api


def _plate_url() -> str:
    img = Image.new("RGB", (1600, 1200), (235, 230, 219))
    d = ImageDraw.Draw(img)
    d.ellipse([500, 200, 1100, 1000], fill=(213, 167, 122))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _body(**over):
    data = dict(plate_data_url=_plate_url())
    data.update(over)
    return api.APlusPageIn(**data)


def test_the_page_endpoint_returns_six_measured_modules():
    out = api.create_page(_body(), acct="test")
    assert out["ok"] is True
    assert len(out["modules"]) == 6
    assert out["page"]["ok"] is True
    for module in out["modules"]:
        assert module["qa"]["ok"] is True, module
        assert module["data_url"].startswith("data:image/png;base64,")
    assert {m["kind"] for m in out["modules"]} == {
        "header", "three_tiles", "comparison", "banner",
        "premium_desktop", "logo"}


def test_a_prohibited_claim_is_refused_with_the_reason():
    with pytest.raises(HTTPException) as err:
        api.create_page(_body(claims=["cures disease"]), acct="test")
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "aplus_page_refused"


def test_a_bad_plate_is_refused():
    with pytest.raises(HTTPException) as err:
        api.create_page(_body(plate_data_url="data:image/png;base64," + "A" * 200),
                        acct="test")
    assert err.value.status_code == 422


def test_the_modules_endpoint_lists_the_page_order():
    out = api.modules(acct="test")
    assert [m["kind"] for m in out["modules"]] == list(api.ab.PAGE_MODULES)
