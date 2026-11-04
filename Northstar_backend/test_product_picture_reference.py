"""Reference plates for product pictures: the pouch is the real one, the type is drawn."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import product_picture as pp  # noqa: E402


def test_a_single_reference_applies_to_every_face():
    assert pp._reference_for(b"ref", "front") == b"ref"
    assert pp._reference_for(b"ref", "back") == b"ref"


def test_a_mapping_is_per_face():
    refs = {"front": b"front-bytes", "back": b"back-bytes"}
    assert pp._reference_for(refs, "front") == b"front-bytes"
    assert pp._reference_for(refs, "back") == b"back-bytes"
    assert pp._reference_for(refs, "side") is None


def test_no_reference_returns_none():
    assert pp._reference_for(None, "front") is None


def test_a_reference_plate_uses_the_mi2i_generator(monkeypatch):
    import studio_generation as sg

    calls = {}

    def fake_reference(prompt, reference, **kwargs):
        calls["prompt"] = prompt
        calls["reference"] = reference
        return {"bytes": b"plate", "seed": 1, "model": "flux-3", "width": 1024,
                "height": 1536, "duration_seconds": None}

    monkeypatch.setattr(sg, "generate_reference", fake_reference)
    out = pp._guarded_plate("a blank pouch", width=1024, height=1536, tier="final",
                            seed=1, reference=b"photo")
    assert calls["reference"] == b"photo"
    assert out["mode"] == "reference"
    assert out["bytes"] == b"plate"
    assert out["contains_text"] is None


def test_a_text_plate_still_goes_through_the_text_safe_guard(monkeypatch):
    import studio_generation as sg
    import text_fidelity as tf

    called = {}

    def fake_guard(*, render_fn, brief, text_safe):
        called["text_safe"] = text_safe
        return {"out": {"bytes": b"plate", "seed": 2, "model": "flux-3",
                        "width": 1024, "height": 1536},
                "text_fidelity": {"check": {"contains_text": False}},
                "used_brief": brief}

    monkeypatch.setattr(tf, "render_with_text_guard", fake_guard)
    out = pp._guarded_plate("a blank pouch", width=1024, height=1536, tier="final",
                            seed=2, reference=None)
    assert called["text_safe"] is True
    assert out["mode"] == "text_safe"
    assert out["contains_text"] is False


def test_build_passes_the_reference_for_the_matching_face(monkeypatch, tmp_path):
    seen = {}

    def fake_plate(brief, *, width, height, tier, seed, reference=None):
        seen[brief] = reference
        return {"bytes": b"not-an-image", "seed": seed}

    monkeypatch.setattr(pp, "_guarded_plate", fake_plate)
    # stop before decoding: the point is what each face was given
    result = pp.build(faces=["front", "back"], width=512, height=512, tier="draft",
                      reference={"front": b"F", "back": b"B"},
                      out_dir=str(tmp_path), out_root=str(tmp_path))
    assert not result["ok"]  # the fake plate is not decodable, recorded as such
    assert seen[pp.plate_brief("front")] == b"F"
    assert seen[pp.plate_brief("back")] == b"B"
