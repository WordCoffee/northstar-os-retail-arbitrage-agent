"""D-012: a bundle brief declares how many units the picture must show.

A `bundle_multipack` brief that declares no `units` is measured as one unit, so
the picture is captioned a bundle and shows one package — the same false picture
`sel-07` fixed for the two held-out briefs, still open on the catalog's six.

The fix has two halves, and both are checked here:

* the brief declares `units`, so `build(units=…)` asks for that many;
* the **plate brief** asks for that many, because a plate of one package measured
  against a three-unit request is refused (`units_not_found`) — the picture can
  only be a bundle if the photograph is one.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import brand_art as ba
import product_picture as pp

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ty" / "seller_briefs.json"


def _bundle_briefs():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [b for b in catalog["briefs"]
            if str(b.get("situation") or "") == "bundle_multipack"]


def test_every_bundle_brief_declares_its_units():
    bundles = _bundle_briefs()
    assert bundles, "the catalog must keep its bundle briefs"
    missing = [b["id"] for b in bundles if not b.get("units")]
    assert not missing, f"bundle briefs with no units: {missing}"


def test_a_bundle_brief_asks_for_at_least_two_units():
    for brief in _bundle_briefs():
        assert int(brief.get("units") or 0) >= 2, brief["id"]


def test_the_plate_brief_asks_for_the_units_the_picture_must_show():
    three = pp.plate_brief("front", ba.CYLINDER, ba.design_for("pine-paws-joint"),
                           units=3)
    assert "three" in three and "side by side" in three
    assert "supplement tub" in three
    one = pp.plate_brief("front", ba.CYLINDER, ba.design_for("pine-paws-joint"))
    assert "one blank unprinted" in one
    assert "side by side" not in one


def test_a_bundle_plate_brief_names_the_form_it_bundles():
    box = pp.plate_brief("front", ba.GIFT_BOX, ba.design_for("word-coffee"), units=3)
    assert "three" in box and "gift box" in box
    pouch = pp.plate_brief("front", ba.POUCH, None, units=2)
    assert "two" in pouch and "pouch" in pouch
