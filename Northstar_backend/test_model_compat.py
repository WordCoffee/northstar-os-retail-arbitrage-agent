"""Model compatibility tests after the FLUX 3 migration.

FLUX 2 Klein and its text-correcting vision models were deleted on 2026-10-29.
What matters now:

* the configured image model is FLUX 3 and its encoder exists;
* the FLUX 3 graph uses the official nodes (UNETLoader, CLIPLoader type
  ``flux3``, ``EmptyFlux2LatentImage``, ``ModelSamplingFlux``, CFG 1.0);
* asking for an encoder that is not on disk fails **before** dispatch.

The old 4B/9B pairing rules remain in the module for any Klein weights an
operator might add later, but they are no longer the production path.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio_generation as sg  # noqa: E402


def test_default_image_model_is_flux3():
    model = sg.IMAGE_MODEL_FILE.lower()
    assert "flux3" in model or "flux-3" in model
    assert "qwen3vl" in sg.TEXT_ENCODER_FILE.lower()


def test_configured_pairing_is_valid_on_this_host():
    report = sg.validate_configured_pairing()
    assert report["ok"] is True, report
    assert "flux3" in str(report["model"]).lower() or \
        "flux-3" in str(report["model"]).lower()


def test_unknown_family_requires_the_encoder_on_disk(monkeypatch):
    monkeypatch.setattr(sg, "_any_model_on_disk", lambda name: False)
    with pytest.raises(ValueError) as exc:
        sg.resolve_text_encoder("flux3-image-klein-int8-convrot.safetensors")
    assert "encoder_not_installed" in str(exc.value)


def test_flux3_graph_is_the_official_graph():
    graph = sg._flux3_klein_graph("a matte stand-up pouch", 1024, 1024, 16, 7)
    assert graph["1"]["class_type"] in ("UNETLoader", "UnetLoaderGGUF")
    assert graph["2"]["class_type"] == "CLIPLoader"
    assert graph["2"]["inputs"]["type"] == "flux3"
    assert graph["6"]["class_type"] == "EmptyFlux2LatentImage"
    assert graph["7"]["class_type"] == "ModelSamplingFlux"
    assert graph["8"]["inputs"]["cfg"] == 1.0
    assert graph["8"]["inputs"]["steps"] == 16
    assert graph["8"]["inputs"]["sampler_name"] == "euler"


def test_flux3_graph_has_no_flux2_scheduler():
    graph = sg._flux3_klein_graph("pouch", 512, 512, 8, 1)
    classes = {node["class_type"] for node in graph.values()}
    assert "Flux2Scheduler" not in classes
    assert "CFGGuider" not in classes
    assert graph["3"]["inputs"]["vae_name"] == sg.FLUX3_VAE_FILE


def test_edit_lane_is_removed_with_the_text_models(monkeypatch):
    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    with pytest.raises(RuntimeError) as exc:
        sg.generate_edit(b"\x89PNG\r\n\x1a\n", "make it warmer")
    assert "edit_lane_removed" in str(exc.value)


@pytest.mark.parametrize("name,expected", [
    ("flux-2-klein-4b-Q8_0.gguf", "qwen_3_4b"),
    ("Flux-2-Klein-9B-KV-Q8_0.gguf", "qwen_3_8b"),
])
def test_legacy_klein_pairing_rules_are_still_enforced(name, expected, monkeypatch):
    """If Klein weights are ever re-added, the pairing guard still applies."""
    monkeypatch.setattr(sg, "_encoder_on_disk", lambda _: True)
    assert expected in sg.resolve_text_encoder(name)
    with pytest.raises(ValueError):
        sg.resolve_text_encoder(
            name,
            "qwen_3_8b_fp8mixed.safetensors" if "4b" in name
            else "qwen_3_4b_fp8_mixed.safetensors")
