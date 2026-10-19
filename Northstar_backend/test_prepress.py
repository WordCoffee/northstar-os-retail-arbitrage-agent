"""Prepress tests — ICC conversion, gamut check, ink limit, verdict.

Uses the CMYK profile Windows ships (RSWOP.icm). If a machine genuinely has no
CMYK profile the suite SKIPS with an explicit reason — it never fakes a pass.
All offline, synthetic images only.
"""

from __future__ import annotations

import io
import os
import sys

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prepress as pp  # noqa: E402


def _png(rgb=(243, 234, 214), size=(64, 64)) -> bytes:
    img = Image.new("RGB", size, rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _have_profile() -> bool:
    try:
        return bool(pp.available_cmyk_profiles())
    except Exception:  # noqa: BLE001
        return False


needs_profile = pytest.mark.skipif(not _have_profile(),
                                   reason="no CMYK ICC profile on this machine")


def test_profiles_list_is_honest():
    profs = pp.available_cmyk_profiles()
    for p in profs:
        assert p.path.lower().endswith((".icc", ".icm"))
        assert os.path.isfile(p.path)


def test_unknown_profile_is_rejected_with_the_available_list():
    if not _have_profile():
        pytest.skip("no CMYK ICC profile on this machine")
    with pytest.raises(RuntimeError) as exc:
        pp.to_cmyk(_png(), profile="definitely-not-a-profile")
    assert "not found" in str(exc.value)
    assert ".ic" in str(exc.value)  # the available list is echoed back


@needs_profile
def test_to_cmyk_returns_a_real_cmyk_tiff():
    out = pp.to_cmyk(_png())
    assert out["mode"] == "CMYK" and out["format"] == "tiff"
    img = Image.open(io.BytesIO(out["bytes"]))
    assert img.mode == "CMYK"
    assert out["profile"].lower().endswith((".icc", ".icm"))
    assert "littlecms" in out["engine"]


@needs_profile
def test_soft_proof_returns_a_png():
    out = pp.soft_proof(_png())
    img = Image.open(io.BytesIO(out["bytes"]))
    assert img.mode == "RGB" and img.size == (64, 64)


@needs_profile
def test_gamut_flags_pure_green_but_not_brand_cream():
    green = pp.gamut_check(_png((0, 255, 0)))
    cream = pp.gamut_check(_png((243, 234, 214)))
    assert green["out_of_gamut_pct"] > 90.0, green
    assert green["max_dE76"] > 20.0
    assert cream["out_of_gamut_pct"] == 0.0, cream
    # white is the profile's white point: it must round trip exactly
    white = pp.gamut_check(_png((255, 255, 255)))
    assert white["max_dE76"] < 0.5


@needs_profile
def test_ink_limit_reports_counts_and_a_clear_verdict():
    ok = pp.ink_limit(_png((243, 234, 214)))
    assert ok["verdict"] == "within_limit"
    assert ok["max_tac_pct"] > 0
    # an artificially low cap must flip the verdict - proves the check is live
    tight = pp.ink_limit(_png((128, 128, 128)), limit_pct=20.0)
    assert tight["verdict"] == "over_limit"
    assert tight["pixels_over_limit_pct"] > 90.0


@needs_profile
def test_prepress_report_blocks_on_gamut_and_passes_cream():
    blocked = pp.prepress_report(_png((0, 255, 0)))
    assert blocked["verdict"] == "blocked"
    assert any("dE" in b for b in blocked["blockers"])

    clean = pp.prepress_report(_png((243, 234, 214)))
    assert clean["verdict"] == "printable"
    assert clean["blockers"] == []
    assert clean["profile"]


@needs_profile
def test_report_names_the_profile_it_actually_used():
    rep = pp.prepress_report(_png())
    used = rep["profile"]
    assert used in rep["profiles_available"]
    assert rep["gamut"]["profile"] == used and rep["ink"]["profile"] == used


@needs_profile
def test_report_handles_a_multi_colour_dieline_sheet():
    img = Image.new("RGB", (300, 300), (243, 234, 214))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 280, 80], fill=(196, 160, 74))     # brand gold
    d.rectangle([20, 120, 280, 180], fill=(0, 255, 0))      # out of gamut
    d.rectangle([20, 220, 280, 280], fill=(23, 23, 23))     # film black
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    rep = pp.prepress_report(buf.getvalue())
    assert rep["verdict"] == "blocked"
    assert rep["gamut"]["out_of_gamut_pct"] > 0
    assert rep["gamut"]["worst_colors"], "worst offenders must be named"
    assert rep["gamut"]["worst_colors"][0]["hex"].startswith("#")
