"""FLUX 3 lane, current contract: fail closed, never a silent fallback.

Replaces the 2026-10-25 version of this file, which asserted an automatic
fallback to FLUX.2 Klein. FLUX.2 was deliberately removed from this machine on
2026-10-29 (53 GB freed, see 00_STATE flux3_install_20261029), so a test that
"verifies the fallback" was verifying a model that no longer exists - and it
could only pass by keeping a second image stack alive. What matters now is the
opposite property: an unarmed or model-less lane must refuse, out loud, and must
never substitute a different model behind the operator's back.

Offline: nothing here contacts ComfyUI.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Northstar_backend"))

import studio_generation as sg  # noqa: E402


def test_disarmed_lane_refuses_before_touching_the_gpu(monkeypatch):
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    called = []

    def boom(*a, **k):  # any ComfyUI call would land here
        called.append(1)
        raise AssertionError("the lane must not reach ComfyUI while disarmed")

    monkeypatch.setattr(sg, "_run_graph_guarded", boom)
    try:
        sg.generate_image("a matte kraft pouch on white", 512, 512, seed=1)
    except RuntimeError as exc:
        assert "media_generation_disarmed" in str(exc)
    else:
        raise AssertionError("an unarmed lane must raise, not render")
    assert called == []


def test_engine_status_says_unarmed_rather_than_guessing(monkeypatch):
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    st = sg.engine_status()
    assert st["gate"] is False
    assert st["armed"] is False
    assert "Unarmed" in st["note"]
    # The declared image model is always named, armed or not: the operator has to
    # be able to see WHAT would run before arming it.
    assert st["models"]["image"] == sg.IMAGE_MODEL_FILE


def test_only_flux3_is_on_the_wire(monkeypatch):
    graph = sg._flux3_klein_graph("a tin on white", 1024, 1024, 16, 7)
    classes = {node["class_type"] for node in graph.values()}
    assert "UNETLoader" in classes or "UnetLoaderGGUF" in classes
    joined = " ".join(str(v) for node in graph.values() for v in node["inputs"].values())
    assert "flux3" in joined.lower()
    for forbidden in ("Flux-2", "flux2-klein", "Q8_0.gguf"):
        assert forbidden not in joined, f"{forbidden} must not be reachable from the FLUX 3 graph"


def test_a_missing_model_is_a_refusal_not_a_substitution(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDIO_FLUX3_MODEL", "not-installed.safetensors")
    import importlib
    importlib.reload(sg)
    try:
        sg.validate_configured_pairing()
        missing = sg.models_present() if hasattr(sg, "models_present") else None
        if missing is not None:
            assert missing["present"] is False
    finally:
        monkeypatch.delenv("STUDIO_FLUX3_MODEL", raising=False)
        importlib.reload(sg)
