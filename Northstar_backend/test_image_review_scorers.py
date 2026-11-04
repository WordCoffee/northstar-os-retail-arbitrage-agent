"""The installed scorers: PickScore (adherence) and HPSv2 (preference).

These run the real models on CPU in a child process (~25 s for both). They are
skipped, not faked, when the runtime or the weights are missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import image_review_scorers as irs  # noqa: E402

READY = irs.available()


def _png() -> bytes:
    img = Image.new("RGB", (768, 1024), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.rectangle([90, 90, 678, 930], fill=(247, 243, 235))
    d.rectangle([120, 140, 300, 220], fill=(120, 96, 64))
    d.text((130, 600), "MOGRA", fill=(23, 23, 23))
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_availability_reports_every_dependency_and_file():
    assert set(READY["deps"]) == {"torch", "transformers", "open_clip"}
    assert set(READY["files"]) == {"pickscore", "hpsv2"}
    assert isinstance(READY["detail"], str) and READY["detail"]


def test_unknown_axis_is_refused_without_loading_a_model():
    result = irs.score("nonsense", _png(), "anything")
    assert result["ok"] is False
    assert "unknown_axis" in result["error"]


@pytest.mark.skipif(not READY["ok"], reason=f"scorers unavailable: {READY['detail']}")
def test_both_axes_score_a_real_image():
    png = _png()
    text = "a product photograph of a kraft stand-up coffee pouch with a cream label"
    adherence = irs.score("adherence", png, text)
    assert adherence["ok"] is True, adherence
    assert 0.0 < adherence["score"] < 40.0, adherence
    assert adherence["model"] == "pickscore"

    preference = irs.score("preference", png, text)
    assert preference["ok"] is True, preference
    assert -1.0 < preference["score"] < 1.0, preference
    assert preference["model"] == "hpsv2"
