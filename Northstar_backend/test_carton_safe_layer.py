"""D-023: a carton dieline needs its safe-margin layer, or the app refuses its own file.

Found by the first packaging pass (`sel-04`). `package_readiness.REQUIRED_LAYERS` is
`("trim", "fold", "safe")`, and `build_carton` emits `bleed`, `trim`, `fold` and `info` but
never `safe` — so `assess_dieline` blocks every carton and sleeve the app prints, with
*dieline is missing its 'safe' layer*. Measured: 6 of 8 packaging briefs failed on exactly
that, while both doypacks (which do emit a safe boundary) scored 100.

The checks are written first:

* every carton template carries a `safe` layer and the margin it was built with;
* each safe rectangle lies **inside** the trim by at least that margin on every side;
* the margin is the brief's own number, not a hard-coded default;
* the app's readiness assessment no longer blocks the file for a missing layer;
* labels and doypacks still carry theirs (this is additive, not a rewrite).
"""
from __future__ import annotations

import pytest

import design_studio_print as dsp
import package_readiness as readiness

CARTONS = ("rsc_box", "tuck_end", "sleeve")
PARAMS = {
    "rsc_box": {"length_mm": 120, "width_mm": 80, "height_mm": 60, "flap_mm": 40,
                "glue_mm": 15, "bleed_mm": 3},
    "tuck_end": {"length_mm": 45, "width_mm": 45, "height_mm": 120, "bleed_mm": 3},
    "sleeve": {"length_mm": 75, "width_mm": 75, "height_mm": 160, "bleed_mm": 3},
}


def _build(template: str, **extra) -> dict:
    params = dict(PARAMS[template], **extra)
    return dsp.build_from_template(template, params)


def _layers(build: dict, kind: str) -> list:
    return [item for item in build.get("layers") or [] if item.get("layer") == kind]


@pytest.mark.parametrize("template", CARTONS)
def test_every_carton_carries_a_safe_layer(template):
    build = _build(template)
    assert _layers(build, "safe"), f"{template} has no safe layer"
    assert float(build["meta"].get("safe_mm") or 0) > 0


@pytest.mark.parametrize("template", CARTONS)
def test_the_safe_margin_is_the_brief_s_own_number(template):
    build = _build(template, safe_mm=6)
    assert float(build["meta"]["safe_mm"]) == 6.0, build["meta"]


@pytest.mark.parametrize("template", CARTONS)
def test_each_safe_rectangle_sits_inside_the_trim_by_the_margin(template):
    build = _build(template, safe_mm=4)
    margin = float(build["meta"]["safe_mm"])
    xs, ys = [], []
    for item in _layers(build, "trim"):
        if item.get("kind") == "rect":
            xs += [float(item["x"]), float(item["x"]) + float(item["w"])]
            ys += [float(item["y"]), float(item["y"]) + float(item["h"])]
        else:                                     # the outline is a polyline of lines
            xs += [float(item["x1"]), float(item["x2"])]
            ys += [float(item["y1"]), float(item["y2"])]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    safes = [item for item in _layers(build, "safe") if item.get("kind") == "rect"]
    assert safes, "no safe rectangles"
    for item in safes:
        x0, y0 = float(item["x"]), float(item["y"])
        x1, y1 = x0 + float(item["w"]), y0 + float(item["h"])
        assert left + margin - 0.01 <= x0 and x1 <= right - margin + 0.01, (
            item, left, right, margin)
        assert top + margin - 0.01 <= y0 and y1 <= bottom - margin + 0.01, (
            item, top, bottom, margin)


@pytest.mark.parametrize("template", CARTONS)
def test_readiness_no_longer_blocks_a_carton_for_its_layers(template):
    verdict = readiness.assess_dieline(_build(template))
    assert verdict["assessed"] is True
    assert not [b for b in verdict["blockers"] if "layer" in str(b).lower()], verdict


def test_labels_and_doypacks_keep_their_safe_boundary():
    label = dsp.build_from_template("label_rectangle", {"width_mm": 100, "height_mm": 70})
    pouch = dsp.build_from_template("doypack", {"width_mm": 140, "height_mm": 220,
                                                "gusset_mm": 40})
    for build in (label, pouch):
        assert _layers(build, "safe"), build.get("meta", {}).get("template")
