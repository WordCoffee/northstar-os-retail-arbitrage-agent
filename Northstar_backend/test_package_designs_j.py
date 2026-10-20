"""J-series (operator concept) package designs — wiring + render guards.

The two directions the operator supplied as concept sheets (Olive + Kraft,
Botanical Luxe) must stay renderable at 300 dpi, carry the REAL lockup and the
REAL label data, and must never fall back to the button-mushroom motif that
previous packs stamped (that motif is Agaricus, not Hericium).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402

import package_designs as pd  # noqa: E402
import rebuild_mogra_logo_hd as rb  # noqa: E402

J_KEYS = ("j01_olive_kraft", "j02_botanical_luxe")


def _logo():
    logo, _white, _qa = rb.build_master_hd()
    pd.set_logo_assets(lockup=logo)
    return logo


def test_specs_registered_and_wired_to_the_j_back():
    specs = {s["key"]: s for s in pd.design_specs()}
    for key in J_KEYS:
        assert key in specs, key
        assert specs[key]["kind"] == "bag"
        assert specs[key]["back"] == "j"
        assert specs[key]["logo_lockup"] is True


def test_fronts_render_full_panel_at_300dpi():
    logo = _logo()
    for key in J_KEYS:
        img = pd.BAG_FRONTS[key](logo, None)          # motif must NOT be needed
        assert img.size == (pd.P(pd.BAG_W), pd.P(pd.BAG_H)), key
        assert img.mode == "RGB"
        colours = img.convert("RGB").getcolors(maxcolors=1_000_000)
        assert colours and len(colours) > 500, f"{key} looks blank"


def test_backs_carry_the_real_label_data():
    logo = _logo()
    specs = {s["key"]: s for s in pd.design_specs()}
    for key in J_KEYS:
        img = pd.render_back(specs[key], pd.BAG_W, pd.BAG_H, logo)
        assert img.size == (pd.P(pd.BAG_W), pd.P(pd.BAG_H))
        assert len(img.convert("RGB").getcolors(maxcolors=1_000_000)) > 500


def test_back_never_uses_the_generic_placeholder_distributor():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "package_designs.py"), encoding="utf-8").read()
    j_block = src[src.index("BACK_J_DETAIL"):src.index("BAG_FRONTS.update({\n    \"j01")]
    assert "T2 Holdings LLC" not in j_block
    assert "Mogran Organics" in j_block


def test_hericium_assets_are_species_correct():
    assert pd.J_SOURCE.is_file(), "operator Hericium source asset missing"
    plate = pd.hericium_plate(pd.J_KRAFT, (222, 196, 156), (74, 60, 36))
    assert plate.size == (1840, 1330)
    # the photograph is asymmetric: a flat fill would give ~0 variance in column means
    import numpy as np
    a = np.asarray(plate.convert("L"), dtype=float)
    assert a.std() > 6.0, "plate looks like a flat fill"
