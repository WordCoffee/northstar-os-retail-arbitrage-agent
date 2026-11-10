"""Reference checks: a real description or `cannot_verify`, and the product-region rule.

Offline only. The VLM describer is switched off for this module and every embedding is a
callable injected here, so nothing hits Ollama or the network. What is tested is the rule the
owner set on 2026-11-08:

* a description produces a measured cosine;
* a blank description is `cannot_verify`, never a perfect match;
* a describer that raises is `cannot_verify`, with the error recorded;
* a composite whose product region cannot be verified **fails**, even when its printed text
  passes — `cannot_verify` is a fail.

Run: python -m pytest Northstar_backend/test_reference_checks.py -q
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seller_tester import composite_check as C  # noqa: E402
from tools.seller_tester import reference_check as R  # noqa: E402
from tools.seller_tester import scorers  # noqa: E402


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_VLM_DESCRIBE", "0")


# ------------------------------------------------------------------ fixtures
def png_bytes(rgb: np.ndarray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(rgb).save(buffer, format="PNG")
    return buffer.getvalue()


def pouch(colour=(30, 100, 65), size=(240, 320)):
    """A textured block: real products have structure, and a flat block has none."""
    rgb = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    rgb[:, :] = colour
    ramp = np.linspace(-30, 30, size[1]).astype(np.int16)[:, None, None]
    rgb = np.clip(rgb.astype(np.int16) + ramp, 0, 255).astype(np.uint8)
    return rgb


def cutout_rgba(size=(120, 120), colour=(30, 120, 70)):
    image = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    image[:, :] = (255, 255, 255, 0)
    inner = size[0] // 6
    box = image[inner:size[1] - inner, inner:size[0] - inner]
    ramp = np.linspace(-26, 26, box.shape[0]).astype(np.int16)[:, None]
    texture = np.clip(np.array(colour, dtype=np.int16)[None, None, :] + ramp[:, :, None],
                      0, 255)
    box[:, :, :3] = texture.astype(np.uint8)
    box[:, :, 3] = 255
    return image


def brief_with_reference(tmp_path: Path, *, route: str | None = None,
                         printed: bool = False) -> dict:
    folder = tmp_path / "renders"
    folder.mkdir(parents=True, exist_ok=True)
    reference = folder / "ref.png"
    Image.fromarray(pouch()).save(reference)
    brief = {
        "id": "T-001",
        "category": "supplement_pouch",
        "situation": "lifestyle",
        "source_mode": "stored_reference",
        "reference": {"kind": "stored_asset", "path": "renders/ref.png"},
        "constraints": {"dimensions": {"min_width": 8, "min_height": 8}},
        "critical": ["dimensions"],
        "pass_score": 70,
    }
    if route is not None:
        brief["route"] = route
    if printed:
        brief["reference"]["check"] = {"min_token_recall": 0.6, "min_embedding": 0.72}
    return brief


def fake_embedder(text: str):
    """A deterministic two-number vector. The test is that a cosine is measured, not its size."""
    seed = sum(ord(ch) for ch in str(text))
    return [float(1 + seed % 7), float(1 + (seed * 3) % 5)]


def composite_brief(route: str | None = "composite") -> dict:
    brief = {
        "id": "T-C01",
        "category": "supplement_pouch",
        "situation": "white_background_main",
        "source_mode": "stored_reference",
        "reference": {"kind": "stored_asset", "path": "renders/ref.png"},
        "constraints": {"dimensions": {"min_width": 8, "min_height": 8}},
        "critical": ["dimensions"],
        "pass_score": 70,
    }
    if route is not None:
        brief["route"] = route
    return brief


# ------------------------------------------------------------------ descriptions
def test_a_description_produces_a_measured_similarity(tmp_path):
    brief = brief_with_reference(tmp_path)
    verdict = R.reference_check_for_brief(
        pouch(), brief, repo_root=tmp_path,
        describe=lambda _rgb: "a green stand-up pouch of organic mushroom powder",
        embedder=fake_embedder,
    )
    assert verdict["decided_by"] == "embedding", verdict
    assert verdict["cannot_verify"] is False
    assert verdict["meaning"]["similarity"] is not None
    assert 0.0 <= verdict["meaning"]["similarity"] <= 1.0
    assert verdict["description"]["produced"] is True
    assert verdict["description"]["reference"] is True


def test_a_blank_description_is_cannot_verify_not_a_perfect_match(tmp_path):
    brief = brief_with_reference(tmp_path)
    verdict = R.reference_check_for_brief(
        pouch(), brief, repo_root=tmp_path,
        describe=lambda _rgb: "", embedder=fake_embedder,
    )
    assert verdict["cannot_verify"] is True, verdict
    assert verdict["ok"] is False
    assert verdict["meaning"]["cannot_verify"] is True
    assert "similarity" not in verdict["meaning"]
    assert verdict["description"]["produced"] is False


def test_a_describer_that_raises_is_cannot_verify_and_records_the_error(tmp_path):
    brief = brief_with_reference(tmp_path)

    def explode(_rgb):
        raise RuntimeError("model not resident")

    verdict = R.reference_check_for_brief(
        pouch(), brief, repo_root=tmp_path, describe=explode, embedder=fake_embedder)
    assert verdict["cannot_verify"] is True
    assert verdict["ok"] is False
    assert "model not resident" in verdict["description"]["produced_error"]


def test_printed_text_does_not_turn_a_blank_description_into_agreement(tmp_path):
    """Text may decide fidelity, but the embedding must still report that it could not."""
    brief = brief_with_reference(tmp_path)
    verdict = R.check_reference_for_brief(
        pouch(), pouch(), brief,
        produced_text="MOGRA ORGANICS ORGANIC LION'S MANE",
        reference_text="MOGRA ORGANICS ORGANIC LION'S MANE",
        produced_desc="", reference_desc="", embedder=fake_embedder,
    )
    assert verdict["decided_by"] == "printed_text"
    assert verdict["ok"] is True
    assert verdict["meaning"]["cannot_verify"] is True
    assert "similarity" not in verdict["meaning"]


def test_semantic_agreement_refuses_a_blank_on_either_side():
    for produced, reference in (("", "a pouch"), ("a pouch", ""), ("", "")):
        verdict = R.semantic_agreement(produced, reference, embedder=fake_embedder)
        assert verdict["cannot_verify"] is True
        assert verdict["ok"] is False


def test_a_description_is_off_when_the_environment_disables_it(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_VLM_DESCRIBE", raising=False)
    assert R.describe_enabled() is True
    monkeypatch.setenv("NORTHSTAR_VLM_DESCRIBE", "0")
    assert R.describe_enabled() is False
    # Disabled means an honest empty description, never a fabricated one.
    assert R.describe_picture(pouch()) == ""


# ------------------------------------------------------------------ the product-region rule
def test_a_composite_without_a_cutout_fails_with_the_reason():
    scored = scorers.score_image(png_bytes(pouch(size=(900, 900))), composite_brief(),
                                 composite_route=True)
    assert scored["passed"] is False
    assert scored["cannot_verify"] is True
    region = scored["checks"]["product_region"]
    assert region["ok"] is False
    assert region["cannot_verify"] is True
    assert region["detail"].startswith("product region cannot be verified:")
    assert "product_region" in scored["failed_checks"]
    assert "product_region" in scored["critical_failed"]


def test_a_brief_that_declares_route_composite_is_checked_without_the_flag():
    scored = scorers.score_image(png_bytes(pouch(size=(900, 900))), composite_brief())
    assert "product_region" in scored["checks"]
    assert scored["passed"] is False


def test_a_full_generation_brief_does_not_run_the_region_check():
    brief = composite_brief(route=None)
    scored = scorers.score_image(png_bytes(pouch(size=(900, 900))), brief)
    # It is present but skipped with a reason, so the absence of a comparison is visible
    # rather than indistinguishable from a silent pass.
    region = scored["checks"]["product_region"]
    assert region["skipped"] is True
    assert "composite route" in region["detail"]


def test_a_composite_with_a_saved_cutout_verifies(tmp_path):
    cutout = cutout_rgba()
    frame = np.zeros((400, 400, 3), dtype=np.uint8)
    frame[:, :] = (245, 242, 235)
    region = frame[30:30 + cutout.shape[0], 40:40 + cutout.shape[1]]
    alpha = cutout[:, :, 3:4].astype(np.float32) / 255.0
    blended = cutout[:, :, :3].astype(np.float32) * alpha + region.astype(np.float32) * (1 - alpha)
    region[:] = blended.astype(np.uint8)

    scored = scorers.score_image(
        png_bytes(frame), composite_brief(), composite_route=True,
        cutout=cutout, placement=[40, 30, 120, 120])
    region_check = scored["checks"]["product_region"]
    assert region_check["ok"] is True, region_check
    assert region_check["similarity"] >= 0.99
    assert "product_region" not in scored["failed_checks"]


def test_the_missing_cutout_verdict_names_the_product_region():
    verdict = C.missing_cutout_verdict("nothing was saved")
    assert verdict["ok"] is False
    assert verdict["cannot_verify"] is True
    assert verdict["check"] == "product_region"
    assert verdict["detail"] == "product region cannot be verified: nothing was saved"


# ------------------------------------------------------------------ rewriting the proof
def test_a_passing_composite_becomes_provisional_and_keeps_its_old_score():
    from tools import composite_audit

    brief = composite_brief()
    result = {
        "brief_id": "MG-C02", "passed": True, "score": 75.0,
        "checks": {
            "dimensions": {"ok": True, "skipped": False},
            "aspect": {"ok": True, "skipped": False},
            "background": {"ok": True, "skipped": True},
            "subject_fill": {"ok": False, "skipped": False},
            "file_size": {"ok": True, "skipped": False},
            "reference_subject": {"ok": True, "skipped": False},
        },
    }
    verdict = {"ok": False, "cannot_verify": True,
               "detail": "product region cannot be verified: no cutout was saved"}
    updated = composite_audit.apply_region_to_row(result, brief, verdict)
    assert updated["provisional"] is True
    assert updated["provisional_score"] == 75.0
    assert updated["provisional_passed"] is True
    assert updated["passed"] is False
    assert "product_region" in updated["failed_checks"]
    assert updated["score"] < 75.0
    assert updated["failed_reason"].startswith("product region cannot be verified:")


def test_an_already_failing_composite_is_not_called_provisional():
    from tools import composite_audit

    brief = composite_brief()
    result = {"brief_id": "MG-C01", "passed": False, "score": 60.0,
              "checks": {"dimensions": {"ok": True, "skipped": False},
                         "aspect": {"ok": True, "skipped": False},
                         "background": {"ok": False, "skipped": False},
                         "reference_subject": {"ok": True, "skipped": False}}}
    updated = composite_audit.apply_region_to_row(
        result, brief, {"ok": False, "cannot_verify": True, "detail": "no cutout"})
    assert updated["provisional"] is False
    assert "provisional_score" not in updated
    assert updated["score"] < 60.0
    assert "product_region" in updated["failed_checks"]


# ------------------------------------------------------------------ the harness wires it
class ReplayGenerator:
    """One artefact on disk with a recorded composite generation."""

    name = "composite"

    def __init__(self, artefact: Path, brief_id: str, cutout: Path | None):
        self.artefact = artefact
        self.brief_id = brief_id
        if cutout is not None:
            artefact.with_suffix(".cutout.png").write_bytes(cutout.read_bytes())
        self._record = {"brief_id": brief_id, "route": "composite",
                        "scene": {"source": "generated"},
                        "product_box": [40, 30, 120, 120]}

    def pair(self, briefs, limit=None):
        return [(briefs[0], str(self.artefact))]

    def record_for(self, brief_id):
        return self._record

    def route(self, brief):
        return "composite"


def _run_harness(tmp_path, cutout_path):
    from tools.seller_tester.harness import run_pass

    artefact = tmp_path / "MG-C99.png"
    artefact.write_bytes(png_bytes(pouch(size=(900, 900))))
    brief = composite_brief()
    brief["id"] = "MG-C99"
    brief["reference"]["path"] = "renders/ref.png"
    (tmp_path / "renders").mkdir(parents=True, exist_ok=True)
    Image.fromarray(pouch()).save(tmp_path / "renders" / "ref.png")
    generator = ReplayGenerator(artefact, "MG-C99", cutout_path)
    return run_pass(
        generator=generator, briefs={"briefs": [brief]}, limit=1,
        describe=lambda _rgb: "",
        gaps_path=tmp_path / "gaps.json", mirror_path=None,
        escalation_path=None, now="2026-11-09T00:00:00+00:00",
    )


def test_the_harness_fails_a_composite_with_no_saved_cutout(tmp_path):
    summary = _run_harness(tmp_path, cutout_path=None)
    row = summary["results"][0]
    assert row["passed"] is False
    assert row["cannot_verify"] is True
    assert row["checks"]["product_region"]["cannot_verify"] is True


def test_the_harness_verifies_a_composite_that_saved_its_cutout(tmp_path):
    saved = tmp_path / "cutout.png"
    Image.fromarray(cutout_rgba()).save(saved)
    summary = _run_harness(tmp_path, cutout_path=saved)
    row = summary["results"][0]
    region = row["checks"]["product_region"]
    assert region["ok"] is True, region
    # The detail names the region it actually compared and the score it got; the exact box is the
    # harness fixture's geometry, so the assertion is on the shape of the evidence, not the number.
    detail = row["checks"]["product_region"]["detail"]
    assert detail.startswith("product region "), detail
    assert "structure" in detail and "opaque pixels" in detail, detail
