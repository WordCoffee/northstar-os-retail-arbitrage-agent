"""The review gate in front of every presented image.

A render is not a deliverable until it has been measured. These tests pin the
four statuses and the one behavior that matters operationally: the graphics lane
refuses a render the gate refuses, and it labels an unscored/unavailable render
a candidate instead of a finished asset.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

import ship_gate as sg  # noqa: E402
import tys_assistant as tys  # noqa: E402


def _label(blur: bool = False) -> Image.Image:
    img = Image.new("RGB", (900, 1200), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 820, 1120], fill=(247, 243, 235))
    d.text((140, 200), "MOGRA", font=ImageFont.truetype(
        r"C:\Windows\Fonts\georgiab.ttf", 110), fill=(23, 23, 23))
    d.text((140, 900), "6 oz (170 g)", font=ImageFont.truetype(
        r"C:\Windows\Fonts\segoeuib.ttf", 58), fill=(23, 23, 23))
    return img.filter(ImageFilter.GaussianBlur(6)) if blur else img


def _reference() -> Image.Image:
    """A different picture: dark ground with a pale shape."""
    img = Image.new("RGB", (900, 1200), (18, 22, 28))
    d = ImageDraw.Draw(img)
    d.ellipse([120, 260, 780, 940], fill=(226, 190, 96))
    return img


# ---------------------------------------------------------------------------
# the four statuses
# ---------------------------------------------------------------------------

def test_sharp_label_with_wordmark_and_weight_passes():
    report = sg.review_image(_label(), wordmark="MOGRA", net_weight="6 oz")
    assert report["status"] == "passed" and report["deliverable"] is True
    assert report["axes"]["legibility"]["status"] == "pass"
    assert "MOGRA" in " ".join(report["axes"]["legibility"]["words"]).upper()


def test_blurred_label_is_refused_with_a_named_reason():
    report = sg.review_image(_label(blur=True), wordmark="MOGRA", net_weight="6 oz")
    assert report["status"] == "refused" and report["deliverable"] is False
    assert any(r.startswith("legibility") for r in report["reasons"])


def test_a_picture_with_no_measurable_axis_is_unscored_never_passed():
    report = sg.review_image(Image.new("RGB", (640, 640), (40, 40, 40)))
    assert report["status"] == "unscored"
    assert report["ok"] is False and report["candidate"] is True


def test_a_required_scorer_that_is_not_configured_needs_review():
    report = sg.review_image(_label(), wordmark="MOGRA", net_weight="6 oz",
                             require_preference=True, use_default_scorers=False)
    assert report["status"] == "needs_review"
    assert report["ok"] is False
    assert report["required_unavailable"] == ["preference"]


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def test_identity_passes_against_the_same_picture():
    ref = _reference()
    report = sg.review_image(ref, reference=ref)
    assert report["status"] == "passed"
    assert report["axes"]["identity"]["phash_distance"] == 0


def test_identity_refuses_a_render_that_is_not_the_product():
    report = sg.review_image(_label(), reference=_reference())
    assert report["status"] == "refused"
    assert "identity" in report["failed_axes"]
    assert report["axes"]["identity"]["phash_distance"] > 0


# ---------------------------------------------------------------------------
# injected scorers
# ---------------------------------------------------------------------------

def test_injected_scorer_below_its_floor_refuses():
    report = sg.review_image(_label(), wordmark="MOGRA", net_weight="6 oz",
                             require_preference=True, use_default_scorers=False,
                             preference_floor=0.22,
                             preference_scorer=lambda png, brief: 0.05)
    assert report["status"] == "refused"
    assert "preference" in report["failed_axes"]


def test_injected_scorer_above_its_floor_passes_and_is_recorded():
    report = sg.review_image(_label(), wordmark="MOGRA", net_weight="6 oz",
                             require_preference=True, use_default_scorers=False,
                             preference_floor=0.22,
                             preference_scorer=lambda png, brief: 0.41)
    assert report["status"] == "passed"
    assert report["axes"]["preference"]["score"] == 0.41


def test_manifest_block_is_compact_and_keeps_the_verdict():
    block = sg.manifest_block(sg.review_image(_label(blur=True), wordmark="MOGRA",
                                              net_weight="6 oz"))
    assert block["status"] == "refused"
    assert "legibility" in block["axes"]
    assert block["axes"]["legibility"]["status"] == "fail"


# ---------------------------------------------------------------------------
# the graphics lane cannot present what the gate refuses
# ---------------------------------------------------------------------------

def _adapter(monkeypatch, rendered: Path):
    from tys_ops import graphics

    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": True, "detail": "ok",
                                 "model": "flux-3-image-klein"})
    monkeypatch.setattr(graphics, "suspend_competing_engines", lambda: {})

    class Lock:
        def acquire(self, timeout=None):
            return True

        def release(self):
            pass

    monkeypatch.setattr(graphics, "gpu_lock", lambda: Lock())
    monkeypatch.setattr(
        graphics, "generate",
        lambda prompt, **kw: {"artifacts": [str(rendered)],
                              "model": "flux-3-image-klein",
                              "width": 900, "height": 1200,
                              "steps": 28, "seed": 1})
    return tys.GraphicsAdapter()


def test_graphics_lane_refuses_a_render_the_gate_refuses(monkeypatch, tmp_path):
    rendered = tmp_path / "render.png"
    _label(blur=True).save(rendered)
    result = _adapter(monkeypatch, rendered).run_step(
        {"lane": "graphics", "objective": "render the pouch",
         "params": {"prompt": "the pouch", "wordmark": "MOGRA",
                    "net_weight": "6 oz"}}, {})
    assert result.ok is False
    assert "ship gate" in result.summary
    assert result.evidence["ship_gate"]["status"] == "refused"


def test_graphics_lane_presents_a_passing_render_as_a_deliverable(monkeypatch, tmp_path):
    rendered = tmp_path / "render.png"
    _label().save(rendered)
    result = _adapter(monkeypatch, rendered).run_step(
        {"lane": "graphics", "objective": "render the pouch",
         "params": {"prompt": "the pouch", "wordmark": "MOGRA",
                    "net_weight": "6 oz"}}, {})
    assert result.ok is True
    assert result.evidence["ship_gate"]["status"] == "passed"
    assert result.artifacts == [str(rendered)]


def test_graphics_lane_labels_an_unmeasured_render_a_candidate(monkeypatch, tmp_path):
    rendered = tmp_path / "render.png"
    Image.new("RGB", (640, 640), (40, 40, 40)).save(rendered)
    result = _adapter(monkeypatch, rendered).run_step(
        {"lane": "graphics", "objective": "render a hero",
         "params": {"prompt": "hero"}}, {})
    assert result.ok is True
    assert "candidate" in result.summary
    assert result.evidence["ship_gate"]["status"] == "unscored"

# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

def test_product_picture_surface_requires_both_scorers_from_config():
    policy = sg.surface_policy("product_picture")
    assert policy["require_scorers"] is True
    assert policy["preference_floor"] == 0.2
    assert policy["adherence_floor"] == 18.0


def test_social_frames_record_but_do_not_block():
    policy = sg.surface_policy("social_frame")
    assert policy["require_scorers"] is False


def test_configured_surface_without_scorers_is_needs_review():
    report = sg.review_image(_label(), wordmark="MOGRA", net_weight="6 oz",
                             surface="product_picture", use_default_scorers=False)
    assert report["status"] == "needs_review"
    assert set(report["required_unavailable"]) == {"adherence", "preference"}


def test_a_recorded_only_score_does_not_make_an_image_deliverable():
    report = sg.review_image(_label(), preference_scorer=lambda png, brief: 0.9)
    assert report["status"] == "unscored"
    assert report["axes"]["preference"]["status"] == "pass"
