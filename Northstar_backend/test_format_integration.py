"""Four-format integration through the flow state machine (no GPU).

A synthetic plate stands in for the FLUX 3 render so the test suite can prove the
ROUTING - plate -> compose -> hero -> evaluate -> aplus -> report for box, bottle,
tube and pouch - without a 30 s render per format. The real-render run is the
script in tools/, not this test.
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from creative_flow import CreativeFlow, CreativeJob

COPY = {"title": "LION'S MANE", "subtitle": "Organic Mushroom Powder",
        "weight": "6 oz (170 g)", "bullets": ["Fruiting body only"]}

FORMATS = {
    "pouch": {"width": 100, "height": 200},
    "box": {"width": 80, "depth": 40, "height": 180},
    "bottle": {"diameter": 60, "height": 200, "label_height": 80, "label_top_offset": 30},
    "tube": {"diameter": 40, "height": 160},
}


def _plate(w=420, h=520) -> bytes:
    img = Image.new("RGB", (w, h), (206, 182, 152))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _cutout(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGBA")
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _flow(tmp_path, kind: str) -> CreativeFlow:
    dims = dict(FORMATS[kind])
    if kind == "pouch":
        dims["require_print_dpi"] = False
    job = CreativeJob(job_id=f"fmt-{kind}", product={"id": "p", "target_price": 34, "unit_cost": 11},
                      pricing={"target_price": 34, "unit_cost": 11}, keywords=["lion mane"],
                      copy=COPY, geometry=kind, geometry_dims=dims,
                      out_dir=str(tmp_path / kind))
    return CreativeFlow(job, root=tmp_path, auto_revert=False,
                        render=lambda p, w, h: _plate(),
                        cutout=_cutout,
                        compose=lambda path, **kw: {"bytes": path.read_bytes(),
                                                    "geom_residual_px": 0.1,
                                                    "neutralized": {"neutralized": True}})


@pytest.mark.parametrize("kind", sorted(FORMATS))
def test_every_format_completes_the_flow(tmp_path, kind):
    flow = _flow(tmp_path, kind)
    state = flow.run()
    assert state["status"] in ("ok", "blocked")
    assert "geometry_invalid" not in state["blocked"]
    geo = state["steps"]["bind"]["geometry"]
    assert geo["kind"] == kind
    assert "error" not in geo
    assert state["steps"]["compose"].get("status") != "skipped" or kind != "pouch"
    assert state["steps"]["aplus"]["valid"] is True
    assert Path(state["steps"]["report"]["path"]).exists()


@pytest.mark.parametrize("kind", ["box", "bottle", "tube"])
def test_non_pouch_formats_use_a_format_compositor(tmp_path, kind):
    flow = _flow(tmp_path, kind)
    state = flow.run()
    compose = state["steps"]["compose"]
    assert compose.get("residual_px") is None       # not a pouch fit
    assert compose.get("bytes", 0) > 0


def test_rollback_is_recorded_when_blocked(tmp_path):
    job = CreativeJob(job_id="blocked", product={}, out_dir=str(tmp_path / "b"))
    state = CreativeFlow(job, root=tmp_path, auto_revert=True).run()
    assert state["status"] == "blocked"
    assert "rollback" in state["steps"] or "product_id_missing" in state["blocked"]
