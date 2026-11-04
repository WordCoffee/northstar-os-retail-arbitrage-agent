"""Reference conditioning: the render must be YOUR product, not a stranger.

The graph is asserted offline (node types and links), and the generator is run
with the engine faked, so no GPU and no ComfyUI are needed. The live graph is
the FLUX 3 Klein ``mi2i`` template: LoadImage -> VAEEncode -> ReferenceLatent on
the positive conditioning.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import studio_generation as sg  # noqa: E402


def _png(size=(2048, 1024), mode="RGB") -> bytes:
    img = Image.new(mode, size, (200, 180, 140) if mode == "RGB" else (200, 180, 140, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# graph shape
# ---------------------------------------------------------------------------

def test_reference_graph_attaches_the_reference_to_the_positive_conditioning():
    graph = sg._flux3_reference_graph("a pouch on marble", "ns-ref-1.png", 1024, 1024, 16, 7)
    classes = {node["class_type"] for node in graph.values()}
    assert {"LoadImage", "VAEEncode", "ReferenceLatent", "KSampler"} <= classes

    ref = next(n for n in graph.values() if n["class_type"] == "ReferenceLatent")
    assert ref["inputs"]["latent"] == ["7", 0]
    assert graph["6"]["class_type"] == "LoadImage"
    assert graph["6"]["inputs"]["image"] == "ns-ref-1.png"

    sampler = next(n for n in graph.values() if n["class_type"] == "KSampler")
    assert sampler["inputs"]["positive"] == ["8", 0]
    assert sampler["inputs"]["negative"] == ["5", 0]
    assert sampler["inputs"]["denoise"] == 1.0


def test_reference_prompt_carries_the_identity_clause():
    graph = sg._flux3_reference_graph("a pouch", "ref.png", 512, 512, 16, 1)
    text = graph["4"]["inputs"]["text"]
    assert "reference image" in text and "identical label" in text


def test_text_to_image_graph_has_no_reference_nodes():
    graph = sg._flux3_klein_graph("a pouch", 1024, 1024, 16, 1)
    classes = {node["class_type"] for node in graph.values()}
    assert "ReferenceLatent" not in classes and "LoadImage" not in classes


# ---------------------------------------------------------------------------
# reference preparation
# ---------------------------------------------------------------------------

def test_reference_is_bounded_and_flattened_onto_white():
    out = sg.prepare_reference(_png((2048, 1024)))
    with Image.open(io.BytesIO(out)) as img:
        assert max(img.size) <= 1024
        assert img.mode == "RGB"
    rgba = sg.prepare_reference(_png((400, 400), mode="RGBA"))
    with Image.open(io.BytesIO(rgba)) as img:
        assert img.mode == "RGB"
        assert img.getpixel((0, 0)) == (255, 255, 255)


# ---------------------------------------------------------------------------
# generator behaviour (faked engine)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_engine(monkeypatch):
    calls = {"upload": [], "graph": None}

    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    monkeypatch.setattr(sg, "unload_brain", lambda: True)
    monkeypatch.setattr(sg, "release_models", lambda: None)
    monkeypatch.setattr(sg, "last_brain_eviction", lambda: {"models": []})

    def _upload(data, filename="upload.png", mime="image/png"):
        calls["upload"].append((len(data), filename))
        return filename

    monkeypatch.setattr(sg, "upload_image", _upload)

    def _run(graph, *, on_progress=None, timeout_s=1800):
        calls["graph"] = graph
        return [{"filename": "out.png"}], {"ok": True}

    monkeypatch.setattr(sg, "_run_image_session", _run)
    monkeypatch.setattr(sg, "_fetch_output", lambda item: _png((1024, 1024)))
    return calls


def test_generate_reference_uploads_the_reference_and_uses_the_mi2i_graph(fake_engine):
    out = sg.generate_reference("a pouch on marble", _png((2048, 1024)),
                                width=1024, height=1024, seed=11)
    assert out["mode"] == "reference"
    assert out["reference"].endswith(".png")
    assert fake_engine["upload"] and fake_engine["upload"][0][1].endswith("ns-ref-11.png")
    classes = {n["class_type"] for n in fake_engine["graph"].values()}
    assert "ReferenceLatent" in classes


def test_generate_reference_refuses_without_a_reference_image(fake_engine):
    with pytest.raises(ValueError):
        sg.generate_reference("a pouch", b"")


def test_generate_reference_refuses_when_the_engine_is_not_armed(monkeypatch):
    monkeypatch.setattr(sg, "media_live_armed", lambda: False)
    with pytest.raises(RuntimeError, match="media_generation_disarmed"):
        sg.generate_reference("a pouch", _png((64, 64)))


def test_generate_image_still_uses_the_text_to_image_graph(fake_engine):
    out = sg.generate_image("a pouch", width=1024, height=1024, seed=3)
    assert out["mode"] if "mode" in out else True
    classes = {n["class_type"] for n in fake_engine["graph"].values()}
    assert "ReferenceLatent" not in classes
    assert fake_engine["upload"] == []
