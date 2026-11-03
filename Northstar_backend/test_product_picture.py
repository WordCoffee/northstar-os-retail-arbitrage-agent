"""Product-picture contracts: measure, compose, gate — no engine required.

The FLUX plate is injected, so these tests exercise the half that decides whether
a picture is deliverable: face measurement, panel warp and the OCR gate.
"""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image, ImageDraw

import mogra_label_art as art
import mockup_quality as mq
import product_picture as pp


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pouch_plate(width=1024, height=1536, box=(330, 360, 700, 1240)) -> Image.Image:
    plate = Image.new("RGB", (width, height), (232, 230, 226))
    d = ImageDraw.Draw(plate)
    d.polygon([(box[0], box[1]), (box[2], box[1]), (box[2] + 8, box[3]),
               (box[0] - 8, box[3])], fill=(213, 167, 122))
    # a soft top weld and base shadow, so the measurement has real edges to find
    d.rectangle([box[0], box[1], box[2], box[1] + 26], fill=(196, 152, 110))
    return plate


def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "fake-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


def test_a_synthetic_pouch_plate_yields_a_gated_picture(tmp_path):
    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path), generator=_generator(_pouch_plate()))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    for face in ("front", "back"):
        path = tmp_path / f"product_{face}.png"
        assert path.is_file() and path.stat().st_size > 10_000
    assert (tmp_path / "product_picture_manifest.json").is_file()
    manifest = json.loads((tmp_path / "product_picture_manifest.json").read_text())
    assert manifest["checks"]["legible"] is True
    assert manifest["checks"]["plate_face_measured"] is True


def test_a_plate_with_no_package_is_refused_not_composited(tmp_path):
    flat = Image.new("RGB", (1024, 1536), (236, 233, 227))
    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path), generator=_generator(flat))
    assert result["ok"] is False
    reasons = [r["reason"] for r in result["faces"]]
    assert reasons and all("plate_face_not_found" in r for r in reasons)
    assert not (tmp_path / "product_front.png").exists()


def test_copy_too_small_to_read_is_refused(tmp_path):
    # A 400 px plate with a 120 px-wide face: the wordmark lands under 10 px.
    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path), generator=_generator(_pouch_plate(
        width=400, height=1000, box=(140, 300, 260, 700))))
    assert result["ok"] is False
    reasons = " ".join(r.get("reason", "") for r in result["faces"])
    assert "small" in reasons or "no_text" in reasons or "wordmark" in reasons


def test_an_engine_failure_is_named_and_written_as_a_refusal(tmp_path):
    def down(brief, *, width, height, tier, seed):
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")

    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path), generator=down)
    assert result["ok"] is False
    assert all(r["reason"].startswith("image_lane_unavailable")
               for r in result["faces"])
    assert result["engine"]["armed"] in (True, False, None)


def test_a_plate_with_invented_lettering_is_refused(tmp_path):
    def lettered(brief, *, width, height, tier, seed):
        return {"bytes": _png(_pouch_plate()), "contains_text": True,
                "seed": seed, "model": "fake-plate", "used_brief": brief,
                "text_fidelity": {"check": {"contains_text": True, "words": ["GLYCERIN"]}}}

    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path), generator=lettered)
    assert result["ok"] is False
    assert all("plate_has_lettering" in r["reason"] for r in result["faces"])


def test_out_dir_cannot_escape_renders():
    with pytest.raises(ValueError):
        pp.resolve_out_dir("C:\\Windows\\Temp\\northstar")
    with pytest.raises(ValueError):
        pp.resolve_out_dir("renders/../../elsewhere")
    assert pp.resolve_out_dir("renders/example").name == "example"


def test_the_back_panel_carries_a_readable_net_weight():
    gate = mq.assert_legible(art.back_panel(), wordmark="MOGRA", net_weight="6 oz")
    assert gate["ok"] is True, gate


def test_the_front_panel_carries_the_wordmark_and_weight():
    gate = mq.assert_legible(art.front_panel(), wordmark="MOGRA", net_weight="6 oz")
    assert gate["ok"] is True, gate
