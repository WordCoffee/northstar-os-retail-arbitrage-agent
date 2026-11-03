"""FLUX 3 lane, current contract: the model/encoder pairing and the box fit.

Replaces the 2026-10-25 version, which imported `_USE_FLUX2`, `FLUX2_MODEL_FILE`
and `_get_flux3_model_file` - all removed when FLUX.2 was taken off this machine
on 2026-10-29. The file could not even import, so it protected nothing. These
tests cover the parts that can still be wrong on a real render: a mismatched
text encoder, a model that is configured but not installed, and a requested size
that would exceed what the graph can do.

Offline, no ComfyUI, no GPU.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Northstar_backend"))

import studio_generation as sg  # noqa: E402


def test_the_configured_pairing_is_valid_on_this_machine():
    report = sg.validate_configured_pairing()
    assert report["ok"] is True, report["error"]
    assert report["model"] == sg.IMAGE_MODEL_FILE
    assert report["encoder"] == sg.TEXT_ENCODER_FILE


def test_a_mismatched_encoder_is_rejected_before_a_graph_is_built():
    # The 4b/9b Klein families have encoder-size rules; FLUX 3 (no size token)
    # only requires the file to exist. Both paths must refuse BEFORE dispatch.
    try:
        sg.resolve_text_encoder("flux-2-klein-4b-Q8_0.gguf", "qwen3vl_4b_int8_convrot.safetensors")
    except ValueError as exc:
        assert "incompatible_encoder_pairing" in str(exc) or "encoder_not_installed" in str(exc)
    else:
        raise AssertionError("a 4b Klein model must not accept a non-4b encoder")


def test_a_configured_model_that_is_not_installed_is_named_as_such():
    try:
        sg.resolve_text_encoder("flux3-image-klein-nvfp4.safetensors", "not-on-this-disk.safetensors")
    except ValueError as exc:
        assert "encoder_not_installed" in str(exc)
        assert "not-on-this-disk" in str(exc)
    else:
        raise AssertionError("an encoder that is not on disk must be refused")


def test_requested_sizes_fit_the_graph_box():
    # _fit_box keeps the graph on supported multiples while preserving ratio.
    for w, h in ((1024, 1024), (1464, 600), (2000, 2000), (390, 844)):
        fw, fh = sg._fit_box(w, h)
        assert fw % 8 == 0 and fh % 8 == 0, (w, h, fw, fh)
        assert abs((fw / fh) - (w / h)) < 0.05, (w, h, fw, fh)
        assert fw * fh <= 4_200_000, (w, h, fw, fh)
