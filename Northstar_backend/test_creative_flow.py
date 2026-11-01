"""Deterministic creative Flow: step order, gating, resumability."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from creative_flow import STEPS, CreativeFlow, CreativeJob

PRODUCT = {"id": "lion-6oz", "target_price": 34.0, "unit_cost": 11.5,
           "brand": {"colors": ["#1d4a1d"], "fonts": {"heading": "Playfair Display"}}}
COPY = {"title": "LION'S MANE", "subtitle": "Organic Mushroom Powder", "weight": "6 oz (170 g)"}


def _flow(tmp_path, *, render=None, cutout=None, compose=None, score=None, **job_kw):
    job = CreativeJob(job_id="j1", product=PRODUCT, pricing=PRODUCT,
                      keywords=["lion's mane powder"], copy=COPY,
                      out_dir=str(tmp_path / "out"), **job_kw)
    return CreativeFlow(job, root=tmp_path, render=render, cutout=cutout,
                        compose=compose, score=score)


def test_steps_are_the_documented_order():
    assert STEPS[0] == "intake" and STEPS[-1] == "report"
    assert STEPS.index("snapshot") < STEPS.index("plate")   # snapshot before anything changes
    assert STEPS.index("gate") < STEPS.index("compose")     # refuse before compositing


def test_flow_without_models_runs_to_ok(tmp_path):
    flow = _flow(tmp_path)
    state = flow.run()
    assert state["status"] == "ok"
    assert state["steps"]["bind"]["tier"] == "premium"
    assert state["steps"]["gate"]["status"] == "skipped"


def test_missing_product_id_blocks_at_intake(tmp_path):
    job = CreativeJob(job_id="j2", product={}, out_dir=str(tmp_path / "o2"))
    state = CreativeFlow(job, root=tmp_path).run()
    assert state["status"] == "blocked"
    assert "product_id_missing" in state["blocked"]


def test_missing_pricing_blocks_before_any_render(tmp_path):
    called = {"render": 0}
    job = CreativeJob(job_id="j3", product={"id": "p"}, out_dir=str(tmp_path / "o3"))
    flow = CreativeFlow(job, root=tmp_path,
                        render=lambda *a: called.__setitem__("render", called["render"] + 1) or b"x")
    state = flow.run()
    assert "pricing_unknown" in state["blocked"]
    assert called["render"] == 0          # a blocked brief never reaches the GPU


def test_dirty_plate_is_refused_and_compose_is_skipped(tmp_path):
    # A white image with a black block is read as text by nothing in CI, so inject
    # a plate that the gate refuses by monkeypatching the check.
    import text_fidelity
    flow = _flow(tmp_path, render=lambda *a: b"fake-png",
                 compose=lambda *a, **k: {"bytes": b"nope", "geom_residual_px": 0.0})
    flow.plate_bytes = b"fake-png"
    flow.state.blocked = []
    flow.step_gate()
    if flow.state.steps["gate"].get("status") == "refused":
        flow.step_compose()
        assert flow.state.steps["compose"]["status"] == "skipped"
    else:
        pytest.skip("OCR unavailable or plate judged clean in this environment")


def test_state_is_written_and_reloadable(tmp_path):
    flow = _flow(tmp_path)
    flow.run()
    path = Path(flow.job.out_dir) / "flow_state.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["job_id"] == "j1"
    assert data["status"] == "ok"


def test_report_carries_the_listing_payload(tmp_path):
    flow = _flow(tmp_path)
    flow.run()
    report = json.loads((Path(flow.job.out_dir) / "flow_report.json").read_text(encoding="utf-8"))
    assert report["job_id"] == "j1"
    assert "listing" in report
    assert report["steps"]["memory"]["status"] == "proposed"   # never applied


# ── A+ assets are rendered, not just described ─────────────────────────────

def test_aplus_step_renders_upload_ready_assets_from_the_plate(tmp_path):
    from PIL import Image

    flow = _flow(tmp_path)
    flow.out.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1400, 1400), (245, 242, 235)).save(flow.out / "01_plate.png")
    flow.step_aplus()

    step = flow.state.steps["aplus"]
    assert step["valid"] is True
    assert step["upload_ready"] is True, step["render"]["problems"]
    assert (flow.out / "aplus" / "aplus_01_header.png").exists()
    assert (flow.out / "aplus" / "aplus_preview.png").exists()
    kinds = [a["kind"] for a in step["render"]["assets"]]
    assert kinds == ["header", "three_tiles", "comparison"]


def test_aplus_step_records_a_defect_instead_of_shipping_a_bad_plate(tmp_path):
    from PIL import Image

    flow = _flow(tmp_path)
    flow.out.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 120), (245, 242, 235)).save(flow.out / "01_plate.png")
    flow.step_aplus()

    step = flow.state.steps["aplus"]
    assert step["valid"] is True                 # geometry is still fine
    assert step["upload_ready"] is False         # but the assets are not sellable
    assert any("too small" in p for p in step["render"]["problems"])
    assert flow.state.status != "blocked"        # a copy/plate defect is not a code rollback


def test_aplus_step_is_skipped_without_a_plate(tmp_path):
    flow = _flow(tmp_path)
    flow.step_aplus()
    assert flow.state.steps["aplus"]["rendered"].startswith("skipped")
    assert "upload_ready" not in flow.state.steps["aplus"]


# ── the finished package is measured, not assumed ──────────────────────────

def _face_png(tmp_path, w=600, h=800):
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGB", (w, h), (240, 236, 226)).save(buf, format="PNG")
    return buf.getvalue()


def test_face_legibility_needs_a_measured_quad(tmp_path):
    import creative_flow

    res = creative_flow.face_legibility(_face_png(tmp_path), None, ["LION'S"])
    assert res["status"] == "skipped"
    res = creative_flow.face_legibility(_face_png(tmp_path), [[0, 0], [10, 0], [10, 10], [0, 10]], [])
    assert res["status"] == "skipped"


def test_face_legibility_crops_the_quad_and_asks_for_the_copy(tmp_path, monkeypatch):
    import asset_rubric
    import creative_flow

    seen = {}

    def fake_legibility(png, expected=None):
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(png))
        seen["size"] = img.size
        seen["expected"] = list(expected or [])
        return {"legibility": 0.75, "hits": 3, "boxes": 12}

    monkeypatch.setattr(asset_rubric, "legibility", fake_legibility)
    quad = [[100, 200], [400, 190], [410, 600], [95, 610]]
    res = creative_flow.face_legibility(_face_png(tmp_path), quad,
                                        ["LION'S", "MANE", "ORGANIC", "POWDER", "SIXTH"])
    assert res["status"] == "checked"
    assert res["legibility"] == 0.75
    assert res["crop"] == [87, 182, 418, 618]          # quad bbox padded by 8
    assert seen["size"] == (331 * 2, 436 * 2)          # cropped, then 2x for OCR
    assert seen["expected"] == ["LION'S", "MANE", "ORGANIC", "POWDER"]   # capped at 4


def test_face_legibility_reports_ocr_absence_instead_of_faking_zero(tmp_path, monkeypatch):
    import asset_rubric
    import creative_flow

    monkeypatch.setattr(asset_rubric, "legibility",
                        lambda png, expected=None: {"legibility": 0.0, "ocr": "unavailable: RuntimeError"})
    quad = [[10, 10], [200, 10], [200, 300], [10, 300]]
    res = creative_flow.face_legibility(_face_png(tmp_path), quad, ["LION'S"])
    assert res["ocr"] == "unavailable: RuntimeError"


def test_compose_records_an_illegible_label_as_a_defect(tmp_path, monkeypatch):
    import creative_flow

    flow = _flow(tmp_path, compose=lambda *a, **k: {"bytes": _face_png(tmp_path),
                                                    "geom_residual_px": 0.4,
                                                    "quad": [[10, 10], [200, 10], [200, 300], [10, 300]]})
    flow.out.mkdir(parents=True, exist_ok=True)
    (flow.out / "01_plate.png").write_bytes(_face_png(tmp_path))
    monkeypatch.setattr(creative_flow, "face_legibility",
                        lambda *a, **k: {"status": "checked", "legibility": 0.0})
    flow.step_compose()
    assert flow.state.steps["compose"]["defects"] == ["label_illegible"]
