"""End-to-end chain test: compose -> cutout framing -> MAIN -> prepress -> readiness.

This is the integration guard. Each module is tested alone elsewhere; this proves
the SHAPES they hand each other still line up, on synthetic data only (no GPU, no
network). If an interface drifts, this test names the stage that broke.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_print as dp  # noqa: E402
import image_prep as ip  # noqa: E402
import mockup_compositor as mc  # noqa: E402
import package_readiness as pr  # noqa: E402
import prepress as pp  # noqa: E402


def _plate(tmp: Path) -> Path:
    """A cream plate with two dark pouch faces (the compositor's target)."""
    img = Image.new("RGB", (800, 500), (243, 234, 214))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([80, 120, 340, 460], radius=20, fill=(33, 56, 0))
    d.rounded_rectangle([420, 120, 700, 460], radius=20, fill=(23, 23, 23))
    p = tmp / "plate.png"
    img.save(p)
    return p


def _logo(tmp: Path) -> Path:
    img = Image.new("RGB", (300, 240), (240, 236, 220))
    ImageDraw.Draw(img).rectangle([70, 60, 230, 180], fill=(255, 255, 255))
    ImageDraw.Draw(img).rectangle([120, 100, 180, 130], fill=(60, 40, 30))
    p = tmp / "logo.png"
    img.save(p)
    return p


def _cutout(size=(400, 400), box=(150, 100, 250, 300)) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=(33, 56, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_chain_compose_then_main_then_readiness(tmp_path):
    # 1) compose deterministic type onto a plate
    out = tmp_path / "composed.png"
    res = mc.compose_mockup(
        template_id="mogra-forest-dusk",
        plate_path=_plate(tmp_path), logo_path=_logo(tmp_path), out_path=out,
        quads=[[[90, 130], [330, 128], [336, 450], [84, 452]],
               [[430, 128], [690, 130], [694, 452], [426, 450]]],
        skus=[{"title": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)",
               "gold": [196, 160, 74]},
              {"title": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)",
               "gold": [214, 158, 62]}],
        erases=[], glyph_box=None, shading=0.5,
    )
    assert out.is_file() and res["quads"] == 2
    # the realism record travels with the render
    assert res["realism"]["displacement_k"] > 0
    assert len(res["face_metrics"]) == 2

    # 2) frame a cutout for a MAIN slot
    framed = ip.frame_on_white_bytes(_cutout(), fill=0.88, size=2000)
    main_check = ip.check_main_compliance(framed["bytes"])
    assert main_check["verdict"] == "compliant", main_check["blockers"]

    # 3) send the composed artwork through prepress
    if not pp.available_cmyk_profiles():
        pre = {"assessed": False, "reason": "no CMYK profile"}
    else:
        pre = pr.assess_prepress(out.read_bytes())
        assert pre["assessed"] is True
        assert pre["profile"] and pre["ink"]["max_tac_pct"] > 0

    # 4) the one verdict, wired from the same artifacts
    dieline = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                                 "gusset_mm": 80, "fill_g": 250})
    verdict = pr.assess_package(artwork=out.read_bytes(), main_image=framed["bytes"],
                                dieline=dieline,
                                expected_terms=["MUSHROOM POWDER"])
    assert verdict["verdict"] in ("retail_ready", "needs_work", "not_assessed")
    ev = verdict["evidence"]
    assert set(ev) == {"prepress", "copy", "main", "dieline"}
    assert ev["main"]["verdict"] == "compliant"
    assert ev["dieline"]["assessed"] is True
    assert isinstance(verdict["blockers"], list) and isinstance(verdict["warnings"], list)


def test_chain_dieline_layers_survive_the_readiness_check():
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 80, "fill_g": 250})
    res = pr.assess_dieline(build)
    assert res["assessed"] and res["blockers"] == []
    # the build must carry the layers the check looks for
    kinds = {i["layer"] for i in build["layers"]}
    assert set(pr.REQUIRED_LAYERS) <= kinds


def test_chain_upscale_then_main_check():
    """Upscaled artwork must still pass the size rule (the common failure)."""
    small = ip.frame_on_white_bytes(_cutout(), fill=0.88, size=1000)
    assert ip.check_main_compliance(small["bytes"])["verdict"] == "blocked"
    up = ip.upscale_lanczos(small["bytes"], factor=2.0)
    rep = ip.check_main_compliance(up["bytes"])
    assert rep["verdict"] == "compliant", rep["blockers"]
