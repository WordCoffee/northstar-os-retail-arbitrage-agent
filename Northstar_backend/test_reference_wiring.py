"""Reference plumbing end to end: adapter -> gateway client -> ComfyUI graph.

No engine is started. The gateway graph is asserted structurally; the client and
the adapter are driven with fakes so a dropped reference cannot pass silently.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))

import flux3_gateway as gw  # noqa: E402
import tys_assistant as tys  # noqa: E402
from tys_ops import graphics  # noqa: E402


# ---------------------------------------------------------------------------
# the gateway graph
# ---------------------------------------------------------------------------

def test_gateway_graph_attaches_a_reference_when_named():
    graph = gw._graph("a pouch", 1024, 1024, 16, 5, reference_name="ref-5.png")
    assert graph["110"]["class_type"] == "LoadImage"
    assert graph["110"]["inputs"]["image"] == "ref-5.png"
    assert graph["111"]["class_type"] == "VAEEncode"
    assert graph["112"]["class_type"] == "ReferenceLatent"
    assert graph["107"]["inputs"]["positive"] == ["112", 0]


def test_gateway_graph_without_a_reference_is_text_to_image():
    graph = gw._graph("a pouch", 1024, 1024, 16, 5)
    classes = {node["class_type"] for node in graph.values()}
    assert "ReferenceLatent" not in classes
    assert graph["107"]["inputs"]["positive"] == ["104", 0]


# ---------------------------------------------------------------------------
# the client sends the reference
# ---------------------------------------------------------------------------

def test_graphics_client_sends_the_reference_as_base64(monkeypatch):
    sent = {}

    def _post(path, payload, timeout):
        sent.update(payload)
        return {"images": ["C:/tmp/out.png"]}

    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": True, "detail": "ok"})
    monkeypatch.setattr(graphics, "_post", _post)
    out = graphics.generate("a pouch", reference_image=b"\x89PNG-reference")
    assert base64.b64decode(sent["reference_image"]) == b"\x89PNG-reference"
    assert out["mode"] == "reference"


def test_graphics_client_without_a_reference_sends_no_field(monkeypatch):
    sent = {}
    monkeypatch.setattr(graphics, "status", lambda: {"available": True, "detail": "ok"})
    monkeypatch.setattr(graphics, "_post",
                        lambda path, payload, timeout: sent.update(payload) or {
                            "images": ["C:/tmp/out.png"]})
    out = graphics.generate("a pouch")
    assert "reference_image" not in sent
    assert out["mode"] == "text"


# ---------------------------------------------------------------------------
# the adapter reads the reference file and passes its bytes
# ---------------------------------------------------------------------------

def _adapter_env(monkeypatch, reference_path, captured):
    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": True, "detail": "ok", "model": "flux-3"})
    monkeypatch.setattr(graphics, "suspend_competing_engines", lambda: {})

    class Lock:
        def acquire(self, timeout=None):
            return True

        def release(self):
            pass

    monkeypatch.setattr(graphics, "gpu_lock", lambda: Lock())

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return {"artifacts": [str(reference_path)], "model": "flux-3",
                "width": 1024, "height": 1024, "steps": 28,
                "seed": kwargs.get("seed")}

    monkeypatch.setattr(graphics, "generate", fake_generate)
    monkeypatch.setattr(tys.GraphicsAdapter, "_ship_gate",
                        lambda self, out, params, prompt: ({"status": "passed", "axes": {}}, {}))


def test_graphics_adapter_passes_the_reference_bytes(monkeypatch, tmp_path):
    reference = tmp_path / "product.png"
    reference.write_bytes(b"\x89PNG-product-photo")
    captured = {}
    _adapter_env(monkeypatch, reference, captured)

    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "render the pouch",
         "params": {"prompt": "the pouch", "reference": str(reference)}}, {})
    assert result.ok is True
    assert captured["reference_image"] == b"\x89PNG-product-photo"
    assert result.evidence["mode"] == "reference"


def test_graphics_adapter_refuses_a_missing_reference(monkeypatch, tmp_path):
    captured = {}
    _adapter_env(monkeypatch, tmp_path / "missing.png", captured)
    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "render the pouch",
         "params": {"prompt": "the pouch",
                    "reference": str(tmp_path / "missing.png")}}, {})
    assert result.ok is False
    assert result.blocked is True
    assert captured == {}
