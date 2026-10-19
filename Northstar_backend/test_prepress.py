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


# -- gamut mapping assistant: the blocker comes with a fix ---------------------

@needs_profile
def test_map_colors_passes_in_gamut_and_suggests_for_out_of_gamut():
    out = pp.map_colors([(243, 234, 214), (0, 255, 0), (196, 160, 74)])
    assert out["status"] == "ok" and out["profile"]
    by_hex = {c["hex"]: c for c in out["colors"]}
    cream = by_hex["#F3EAD6"]
    assert cream["in_gamut"] is True
    assert "suggested_hex" not in cream, "an in-gamut colour needs no suggestion"

    green = by_hex["#00FF00"]
    assert green["in_gamut"] is False
    assert green["dE76"] > 20
    assert green["suggested_hex"] and green["suggested_srgb"]
    assert green["suggested_hex"] != green["hex"]
    assert out["out_of_gamut"] == 1


@needs_profile
def test_map_colors_suggestion_is_itself_in_gamut():
    """The suggested value must survive a second trip, or it is not a fix."""
    first = pp.map_colors([(0, 255, 0)])
    suggested = tuple(first["colors"][0]["suggested_srgb"])
    second = pp.map_colors([suggested])
    assert second["colors"][0]["in_gamut"] is True, second["colors"][0]
    assert second["colors"][0]["dE76"] <= first["colors"][0]["dE76"]


@needs_profile
def test_map_colors_handles_an_empty_palette():
    out = pp.map_colors([])
    assert out["colors"] == [] and out["out_of_gamut"] == 0
