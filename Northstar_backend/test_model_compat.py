"""Model / text-encoder compatibility tests.

A FLUX.2 Klein 4B UNet must use the 4B Qwen3 encoder; a 9B UNet must use the
8B encoder. Pairing them the other way fails at dispatch with a shape mismatch
(512x12288 vs 7680x3072). These tests reject an incompatible pairing *before*
any graph is submitted.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio_generation as sg  # noqa: E402


@pytest.fixture(autouse=True)
def _pretend_installed(monkeypatch):
    # Unit tests do not depend on the host's model directory layout.
    monkeypatch.setattr(sg, "_encoder_on_disk", lambda name: True)


def test_4b_model_accepts_4b_encoder():
    assert sg.resolve_text_encoder(
        "flux-2-klein-4b-Q8_0.gguf", "qwen_3_4b_fp8_mixed.safetensors"
    ) == "qwen_3_4b_fp8_mixed.safetensors"


def test_4b_model_defaults_to_4b_encoder():
    assert sg.resolve_text_encoder("flux-2-klein-4b-Q8_0.gguf") == \
        "qwen_3_4b_fp8_mixed.safetensors"


def test_9b_model_accepts_8b_encoder():
    assert sg.resolve_text_encoder(
        "Flux-2-Klein-9B-KV-Q8_0.gguf", "qwen_3_8b_fp8mixed.safetensors"
    ) == "qwen_3_8b_fp8mixed.safetensors"


def test_9b_model_defaults_to_8b_encoder():
    assert sg.resolve_text_encoder("Flux-2-Klein-9B-KV-Q8_0.gguf") == \
        "qwen_3_8b_fp8mixed.safetensors"


def test_4b_model_rejects_8b_encoder():
    with pytest.raises(ValueError) as exc:
        sg.resolve_text_encoder(
            "flux-2-klein-4b-Q8_0.gguf", "qwen_3_8b_fp8mixed.safetensors")
    assert "incompatible_encoder_pairing" in str(exc.value)


def test_9b_model_rejects_4b_encoder():
    with pytest.raises(ValueError) as exc:
        sg.resolve_text_encoder(
            "Flux-2-Klein-9B-KV-Q8_0.gguf", "qwen_3_4b_fp8_mixed.safetensors")
    assert "incompatible_encoder_pairing" in str(exc.value)


def test_missing_encoder_is_rejected(monkeypatch):
    monkeypatch.setattr(sg, "_encoder_on_disk", lambda name: False)
    with pytest.raises(ValueError) as exc:
        sg.resolve_text_encoder("flux-2-klein-4b-Q8_0.gguf")
    assert "encoder_not_installed" in str(exc.value)


def test_unknown_model_family_is_passed_through():
    # FLUX 3 and other families have no size token; do not block them here.
    assert sg.resolve_text_encoder("flux3-klein.safetensors", "qwen3vl.safetensors") == \
        "qwen3vl.safetensors"


def test_klein_graph_uses_resolved_encoder(monkeypatch):
    monkeypatch.setattr(sg, "IMAGE_MODEL_FILE", "flux-2-klein-4b-Q8_0.gguf")
    monkeypatch.setattr(sg, "TEXT_ENCODER_FILE", "qwen_3_4b_fp8_mixed.safetensors")
    graph = sg._klein_graph("a matte stand-up pouch", 512, 512, 4, 1234)
    assert graph["2"]["inputs"]["clip_name"] == "qwen_3_4b_fp8_mixed.safetensors"


def test_klein_graph_rejects_bad_pairing_before_dispatch(monkeypatch):
    monkeypatch.setattr(sg, "IMAGE_MODEL_FILE", "flux-2-klein-4b-Q8_0.gguf")
    monkeypatch.setattr(sg, "TEXT_ENCODER_FILE", "qwen_3_8b_fp8mixed.safetensors")
    with pytest.raises(ValueError) as exc:
        sg._klein_graph("a matte stand-up pouch", 512, 512, 4, 1234)
    assert "incompatible_encoder_pairing" in str(exc.value)


def test_configured_pairing_is_valid_on_this_host():
    """The production configuration must be a supported pairing."""
    report = sg.validate_configured_pairing()
    assert report["ok"] is True, report
    assert "klein-4b" in str(report["model"]).lower() or \
        "klein-9b" in str(report["model"]).lower()
