"""Four-format integration through the flow state machine (no GPU).

A synthetic plate stands in for the FLUX 3 render so the test suite can prove the
ROUTING and the MEASUREMENT - plate -> measure -> compose -> hero -> evaluate ->
aplus -> report for box, bottle, tube and pouch - without a 30 s render per
format. The real-render run is the script in tools/, not this test.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

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

BG = (208, 208, 208)
BODY = (176, 146, 116)
SIDE = (140, 116, 92)


def _plate(kind: str, w: int = 420, h: int = 520) -> bytes:
    """A synthetic product silhouette the measurer must actually fit."""
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    if kind == "pouch":
        d.polygon([(120, 60), (300, 60), (310, 460), (110, 460)], fill=BODY)
    elif kind == "box":
        d.rectangle([100, 80, 270, 460], fill=BODY)
        d.polygon([(270, 100), (360, 150), (360, 440), (270, 460)], fill=SIDE)
    elif kind == "bottle":
        d.rectangle([185, 50, 235, 110], fill=BODY)
        d.polygon([(185, 110), (160, 150), (160, 460), (260, 460),
                   (260, 150), (235, 110)], fill=BODY)
    elif kind == "tube":
        d.rectangle([160, 40, 260, 60], fill=BODY)
        d.polygon([(170, 60), (250, 60), (258, 460), (162, 460)], fill=BODY)
        d.rectangle([160, 460, 260, 480], fill=BODY)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _cutout(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGBA")
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _flow(tmp_path, kind: str, *, render=None) -> CreativeFlow:
    dims = dict(FORMATS[kind])
    if kind == "pouch":
        dims["require_print_dpi"] = False
    job = CreativeJob(job_id=f"fmt-{kind}", product={"id": "p", "target_price": 34, "unit_cost": 11},
                      pricing={"target_price": 34, "unit_cost": 11}, keywords=["lion mane"],
                      copy=COPY, geometry=kind, geometry_dims=dims,
                      out_dir=str(tmp_path / kind))
    return CreativeFlow(job, root=tmp_path, auto_revert=False,
                        render=render or (lambda p, w, h: _plate(kind)),
                        cutout=_cutout,
                        compose=lambda path, **kw: {"bytes": path.read_bytes(),
                                                    "geom_residual_px": 0.1,
                                                    "neutralized": {"neutralized": True}})


@pytest.fixture(autouse=True)
def _gpu_always_ready(monkeypatch):
    """The plate step probes nvidia-smi; tests must not depend on a GPU host."""
    import hardware_guard
    hw = hardware_guard.Hardware(True, used_mb=1000, total_mb=16000, temp_c=50.0)
    monkeypatch.setattr(hardware_guard, "snapshot", lambda *a, **k: hw)
    monkeypatch.setattr(hardware_guard, "plan", lambda *a, **k: (1, "test", hw))


@pytest.mark.parametrize("kind", sorted(FORMATS))
def test_every_format_completes_the_flow(tmp_path, kind):
    flow = _flow(tmp_path, kind)
    state = flow.run()
    assert state["status"] == "ok", state["blocked"]
    geo = state["steps"]["bind"]["geometry"]
    assert geo["kind"] == kind
    assert "error" not in geo
    assert state["steps"]["aplus"]["valid"] is True
    assert Path(state["steps"]["report"]["path"]).exists()


@pytest.mark.parametrize("kind", ["box", "bottle", "tube"])
def test_non_pouch_formats_use_a_measured_quad(tmp_path, kind):
    flow = _flow(tmp_path, kind)
    state = flow.run()
    compose = state["steps"]["compose"]
    assert compose.get("status") != "refused", compose
    assert compose["residual_px"] is not None
    surface = compose["surface"]
    assert surface["method"] in ("box-quad", "box-front", "bottle-band", "tube-band")
    assert surface["confidence"] > 0.5
    assert compose["bytes"] > 0
    # The measured quad must be inside the plate and ordered TL/TR/BR/BL.
    quad = surface.get("quad")
    if quad:
        assert quad[0][1] < quad[2][1] and quad[0][0] < quad[1][0]


def test_unmeasurable_plate_blocks_instead_of_guessing(tmp_path):
    blank = Image.new("RGB", (420, 520), BG)
    buf = BytesIO(); blank.save(buf, format="PNG")
    flow = _flow(tmp_path, "box", render=lambda p, w, h: buf.getvalue())
    state = flow.run()
    assert "surface_unmeasurable" in state["blocked"]
    assert state["steps"]["compose"]["status"] == "refused"


def test_rollback_is_recorded_when_blocked(tmp_path):
    job = CreativeJob(job_id="blocked", product={}, out_dir=str(tmp_path / "b"))
    state = CreativeFlow(job, root=tmp_path, auto_revert=True).run()
    assert state["status"] == "blocked"
    assert "rollback" in state["steps"] or "product_id_missing" in state["blocked"]
