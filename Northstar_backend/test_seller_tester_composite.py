"""The composite path: real product pixels, generated scene, measured verdict.

Everything here is CPU-only. The render lane is injected, so these tests prove the
wiring and the failure modes without a GPU, and the cutout tests run on synthetic
pictures with a known subject.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools"), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import product_cutout as pc  # noqa: E402
from tools.seller_tester import reference_check  # noqa: E402
from tools.seller_tester.briefs import (  # noqa: E402
    brief_fidelity,
    route_for_brief,
)
from tools.seller_tester.generators import (  # noqa: E402
    CompositeGenerator,
    GeneratorUnavailable,
)
from tools.seller_tester.harness import run_pass  # noqa: E402


# ---------------------------------------------------------------- fixtures
@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "renders" / "references").mkdir(parents=True)
    return tmp_path


def _product_png(path: Path, size=(600, 600), *, box=(160, 120, 440, 500)) -> Path:
    """A white upload with one opaque product: coverage is known exactly."""
    image = Image.new("RGB", size, (250, 250, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=(40, 80, 60))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _scene_bytes(size=(640, 640), colour=(214, 208, 196)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _brief(reference_path: str | None = None, *, fidelity: str | None = None,
           mode: str = "uploaded_reference", brief_id: str = "T-1") -> dict:
    brief = {
        "id": brief_id,
        "category": "supplement_pouch",
        "situation": "lifestyle",
        "difficulty": 1,
        "source_mode": mode,
        "placement": {"scale": 0.6, "anchor": [0.5, 0.6]},
        "constraints": {
            "dimensions": {"min_width": 200, "min_height": 200},
            "aspect": {"ratio": 1.0, "tolerance": 0.02},
            "background": {"value": 255, "tolerance": 6, "mode": "free"},
            "fill_pct": {"min": 5, "max": 95},
            "text_rule": "allowed",
            "matte": {"mode": "any"},
            "file_size": {"min_bytes": 100, "max_bytes": 12000000},
        },
        "pass_score": 60,
    }
    if fidelity is not None:
        brief["fidelity"] = fidelity
    if reference_path is not None:
        brief["reference"] = {
            "kind": "uploaded_file",
            "path": reference_path,
            "descriptor": {"filename": Path(reference_path).name,
                           "mime_type": "image/png", "subject": "a pouch"},
        }
    return brief


def _alpha_from_box(rgb: np.ndarray, box=(120, 90, 420, 380)) -> pc.Cutout:
    alpha = np.zeros(rgb.shape[:2], dtype=np.uint8)
    alpha[box[1]:box[3], box[0]:box[2]] = 255
    return pc.Cutout(method="injected", alpha=alpha, rgb=rgb, seconds=0.01,
                     working_side=max(rgb.shape[:2]))


# ---------------------------------------------------------------- routing
def test_exact_reference_routes_to_composite():
    brief = _brief("renders/references/a.png", fidelity="exact")
    assert brief_fidelity(brief) == "exact"
    assert route_for_brief(brief) == "composite"
    generator = CompositeGenerator(renderer=lambda b, m="scene": {"bytes": b""})
    assert generator.route(brief) == "composite"


def test_tolerant_brief_may_generate_fully():
    brief = _brief("renders/references/a.png", fidelity="tolerant")
    assert brief_fidelity(brief) == "tolerant"
    assert route_for_brief(brief) == "full_generation"


def test_prompt_only_is_always_full_generation():
    for fidelity in (None, "exact", "tolerant"):
        brief = _brief(None, fidelity=fidelity, mode="prompt_only")
        assert route_for_brief(brief) == "full_generation"
        assert brief_fidelity(brief) == "tolerant"


def test_reference_brief_without_fidelity_defaults_to_exact():
    assert brief_fidelity(_brief("renders/references/a.png")) == "exact"
    assert route_for_brief(_brief("renders/references/a.png")) == "composite"


# ---------------------------------------------------------------- honest failure
def test_refused_media_lane_is_a_failure_not_a_pass(repo: Path):
    upload = _product_png(repo / "renders" / "references" / "product.png")
    brief = _brief("renders/references/product.png")

    def refused(brief, mode="scene", inside_lane=None):
        raise GeneratorUnavailable("render lane unavailable: ComfyUI runtime not found")

    generator = CompositeGenerator(renderer=refused, out_dir=repo / "out",
                                   repo_root=repo,
                                   cutout_fn=lambda rgb: _alpha_from_box(rgb))
    with pytest.raises(GeneratorUnavailable, match="render lane unavailable"):
        generator.generate(brief)
    assert not (repo / "out" / f"{brief['id']}.png").exists()
    record = generator.record_for(brief["id"])
    assert record is not None and "render lane unavailable" in record["error"]
    assert record["artefact"] is None
    assert upload.is_file()


def test_a_refused_lane_stops_the_pass_instead_of_scoring_nothing(repo: Path):
    _product_png(repo / "renders" / "references" / "product.png")

    def refused(brief, mode="scene", inside_lane=None):
        raise GeneratorUnavailable("render lane unavailable: already running")

    generator = CompositeGenerator(renderer=refused, out_dir=repo / "out",
                                   repo_root=repo,
                                   cutout_fn=lambda rgb: _alpha_from_box(rgb))
    with pytest.raises(GeneratorUnavailable):
        run_pass(generator=generator, briefs=[_brief("renders/references/product.png")],
                 limit=1, gaps_path=repo / "gaps.json",
                 mirror_path=repo / "mirror.json",
                 escalation_path=repo / "escalations.json")


# ---------------------------------------------------------------- cutout
def test_cutout_on_a_synthetic_image_produces_a_sane_alpha():
    image = Image.new("RGB", (600, 600), (250, 250, 250))
    ImageDraw.Draw(image).rectangle((160, 120, 440, 500), fill=(40, 80, 60))
    rgb = np.asarray(image, dtype=np.uint8)
    expected = (440 - 160) * (500 - 120) / (600.0 * 600.0)
    for method in ("background_distance", "grabcut"):
        cut = pc.cutout(rgb, method)
        metrics = pc.alpha_metrics(cut.alpha, reference_coverage=expected)
        assert metrics["subject_px"] > 0, method
        assert abs(metrics["coverage"] - expected) <= 0.08, (method, metrics)
        assert metrics["border_contact"] == 0.0, method
        assert metrics["edge_gradient_px"] <= 8.0, method
        left, top, right, bottom = metrics["bbox"]
        assert 140 <= left <= 180 and 420 <= right <= 460, (method, metrics["bbox"])
        assert pc.coverage_plausible(metrics) is True
        assert pc.border_ok(metrics) is True


def test_cutout_refuses_an_uninstalled_method_instead_of_substituting_one():
    rgb = np.full((64, 64, 3), 255, dtype=np.uint8)
    with pytest.raises(pc.CutoutUnavailable, match="rembg"):
        pc.cutout(rgb, "rembg")
    with pytest.raises(pc.CutoutUnavailable, match="unknown cutout method"):
        pc.cutout(rgb, "magic_wand")


def test_full_bleed_reference_does_not_judge_coverage():
    metrics = {"coverage": 0.41, "reference_coverage": 0.85}
    assert pc.coverage_plausible(metrics) is None


# ---------------------------------------------------------------- composite
def test_composite_places_the_subject_inside_the_frame(repo: Path):
    _product_png(repo / "renders" / "references" / "product.png")
    brief = _brief("renders/references/product.png")
    generator = CompositeGenerator(
        renderer=lambda b, m="scene", inside_lane=None: {
            "bytes": _scene_bytes(), "source": "generated", "prompt": "scene",
            "image_path": None, "lane": {"stopped": {"ok": True}}},
        out_dir=repo / "out", repo_root=repo,
        cutout_fn=lambda rgb: _alpha_from_box(rgb, box=(200, 160, 400, 520)))
    path = generator.generate(brief)
    record = generator.record_for(brief["id"])
    assert path.is_file()
    assert record["route"] == "composite"
    assert record["scene"]["source"] == "generated"
    left, top, right, bottom = record["product_box"]
    assert 0 <= left < right <= 640 and 0 <= top < bottom <= 640
    assert 0.55 <= record["product_scale"] <= 0.65
    with Image.open(path) as produced:
        assert produced.size == (640, 640)
        # the product really is in the pixels: its centre is not the scene colour
        probe = produced.convert("RGB").getpixel(((left + right) // 2, (top + bottom) // 2))
    assert probe != (214, 208, 196)


def test_tolerant_brief_generates_instead_of_compositing(repo: Path):
    _product_png(repo / "renders" / "references" / "product.png")
    brief = _brief("renders/references/product.png", fidelity="tolerant")
    generator = CompositeGenerator(
        renderer=lambda b, m="scene", inside_lane=None: {
            "bytes": _scene_bytes((320, 320)), "source": "generated",
            "prompt": "full", "image_path": None, "lane": {"stopped": {"ok": True}}},
        out_dir=repo / "out", repo_root=repo,
        cutout_fn=lambda rgb: _alpha_from_box(rgb))
    generator.generate(brief)
    record = generator.record_for(brief["id"])
    assert record["route"] == "full_generation"
    assert record["cutout"] is None
    with Image.open(repo / "out" / f"{brief['id']}.png") as produced:
        assert produced.size == (320, 320)


# ---------------------------------------------------------------- reference check
def test_reference_check_decides_on_ocr_text_not_colour():
    produced = np.full((240, 240, 3), 20, dtype=np.uint8)   # dark, unlike the reference
    reference = np.full((240, 240, 3), 240, dtype=np.uint8)  # bright
    brief = _brief("renders/references/a.png")
    brief["reference"]["check"] = {"min_token_recall": 0.6, "min_embedding": 0.72}
    verdict = reference_check.check_reference_for_brief(
        produced, reference, brief,
        produced_text="MOGRA ORGANICS ORGANIC LION'S MANE MUSHROOM POWDER",
        reference_text="MOGRA ORGANICS ORGANIC LION'S MANE MUSHROOM POWDER",
        embedder=lambda text: [1.0, 0.0])
    assert verdict["ok"] is True
    assert verdict["decided_by"] == "printed_text"
    assert verdict["diagnostic"]["colour_gate"] is False
    assert verdict["text"]["recall"] == 1.0


def test_colour_agreement_cannot_rescue_missing_text():
    produced = np.full((240, 240, 3), 240, dtype=np.uint8)
    reference = np.full((240, 240, 3), 240, dtype=np.uint8)
    brief = _brief("renders/references/a.png")
    verdict = reference_check.check_reference_for_brief(
        produced, reference, brief,
        produced_text="A DIFFERENT BRAND",
        reference_text="MOGRA ORGANICS ORGANIC LION'S MANE",
        embedder=lambda text: [1.0, 0.0])
    assert verdict["ok"] is False
    assert verdict["decided_by"] == "printed_text"
    assert verdict["diagnostic"]["colour_gate"] is False


def test_reference_check_reads_text_with_ocr_when_no_text_is_supplied(monkeypatch):
    calls = {"n": 0}

    def fake_ocr(rgb):
        calls["n"] += 1
        return {"ok": True, "items": [], "text": "MOGRA ORGANICS ORGANIC LION'S MANE"}

    monkeypatch.setattr(reference_check, "ocr_text", fake_ocr)
    produced = np.full((240, 240, 3), 120, dtype=np.uint8)
    reference = np.full((240, 240, 3), 200, dtype=np.uint8)
    brief = _brief("renders/references/a.png")
    verdict = reference_check.check_reference_for_brief(
        produced, reference, brief, embedder=lambda text: [1.0, 0.0])
    assert calls["n"] == 2, "both pictures must be read, not just one"
    assert verdict["decided_by"] == "printed_text"
    assert verdict["ok"] is True


def test_blank_descriptions_are_not_an_embedding_match():
    verdict = reference_check.semantic_agreement("", "", embedder=lambda text: [1.0, 0.0])
    assert verdict["cannot_verify"] is True
    assert verdict["ok"] is False


def test_a_synthetic_scene_cannot_pass_even_when_the_checks_pass():
    from tools.seller_tester import scorers

    image = io.BytesIO()
    Image.new("RGB", (800, 800), (250, 250, 250)).save(image, format="PNG")
    brief = _brief(None, mode="prompt_only")
    brief["constraints"]["dimensions"] = {"min_width": 200, "min_height": 200}
    scored = scorers.score_image(image.getvalue(), brief, scene_source="synthetic")
    assert scored["cannot_verify"] is True
    assert scored["passed"] is False
    assert "synthetic backdrop" in scored["cannot_verify_reason"]


def test_harness_records_the_route_and_fidelity(repo: Path):
    _product_png(repo / "renders" / "references" / "product.png")
    brief = _brief("renders/references/product.png")
    generator = CompositeGenerator(
        renderer=lambda b, m="scene", inside_lane=None: {
            "bytes": _scene_bytes(), "source": "generated", "prompt": "scene",
            "image_path": None, "lane": {"stopped": {"ok": True}}},
        out_dir=repo / "out", repo_root=repo,
        cutout_fn=lambda rgb: _alpha_from_box(rgb, box=(200, 160, 400, 520)))
    summary = run_pass(generator=generator, briefs=[brief], limit=1,
                       gaps_path=repo / "gaps.json", mirror_path=repo / "mirror.json",
                       escalation_path=repo / "escalations.json")
    row = summary["results"][0]
    assert row["route"] == "composite"
    assert row["fidelity"] == "exact"
    assert (row.get("generation") or {}).get("method") is not None or \
        (row.get("generation") or {}).get("cutout_in_lane") is True
