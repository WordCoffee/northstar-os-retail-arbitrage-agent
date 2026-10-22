"""Local vision QC tests — offline. The VRAM discipline is the point.

This box has one 16 GB GPU and the render lanes own it. These tests pin the
rules that keep the QC lane from ever competing with a render:
  * unknown or low free VRAM => CPU (`num_gpu: 0`)
  * every call sets `keep_alive: 0` so nothing lingers
  * the frame is downscaled before it becomes vision tokens
  * an unparseable reply is reported as `unparsed`, never invented
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import local_vision as lv  # noqa: E402


def _png(size=(64, 64)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 180, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _poster(reply: str, capture: list):
    def post(url, payload, timeout):
        capture.append(payload)
        return {"response": reply, "eval_count": 12}
    return post


# --- the mode decision: the safety rule -------------------------------------

def test_unknown_vram_falls_back_to_cpu():
    assert lv.choose_mode(None, None) == "cpu"


def test_low_free_vram_falls_back_to_cpu():
    assert lv.choose_mode(2598, None) == "cpu"
    assert lv.choose_mode(lv.GPU_HEADROOM_MB - 1, None) == "cpu"


def test_headroom_permits_gpu():
    assert lv.choose_mode(lv.GPU_HEADROOM_MB + 1, None) == "gpu"


def test_caller_can_force_either_device():
    assert lv.choose_mode(20000, False) == "cpu"
    assert lv.choose_mode(100, True) == "gpu"


# --- the payload contract ---------------------------------------------------

def test_cpu_mode_pins_num_gpu_zero_and_unloads_after():
    capture: list = []
    lv.qc_image(_png(), "a kraft pouch",
                poster=_poster(json.dumps({"matches_brief": True, "issues": []}), capture),
                vram_reader=lambda: 1000)
    payload = capture[0]
    assert payload["options"]["num_gpu"] == 0, "CPU mode must forbid GPU layers"
    assert payload["keep_alive"] == 0, "the QC model must never stay resident"
    assert payload["stream"] is False
    assert len(payload["images"]) == 1


def test_gpu_mode_does_not_pin_num_gpu():
    capture: list = []
    lv.qc_image(_png(), "brief", poster=_poster('{"matches_brief": true}', capture),
                vram_reader=lambda: 20000)
    assert "num_gpu" not in capture[0]["options"]


def test_frame_is_downscaled_before_it_becomes_tokens():
    from PIL import Image
    capture: list = []
    big = _png((2400, 1200))
    lv.qc_image(big, "brief", max_side=768,
                poster=_poster('{"matches_brief": true}', capture),
                vram_reader=lambda: 1000)
    sent = base64.b64decode(capture[0]["images"][0])
    with Image.open(io.BytesIO(sent)) as im:
        assert max(im.size) <= 768
        assert im.size == (768, 384)


# --- verdict parsing --------------------------------------------------------

def test_clean_json_reply_becomes_a_verdict():
    out = lv.qc_image(_png(), "a kraft pouch",
                      poster=_poster(json.dumps({
                          "matches_brief": False,
                          "issues": ["background is not white"],
                          "confidence": 0.8,
                          "description": "a pouch on a bone backdrop"}), []),
                      vram_reader=lambda: 1000)
    assert out["ok"] is True
    assert out["verdict"] == "ok"
    assert out["matches_brief"] is False
    assert out["issues"] == ["background is not white"]
    assert out["mode"] == "cpu"


def test_json_wrapped_in_prose_is_still_recovered():
    reply = 'Sure! {"matches_brief": true, "issues": [], "confidence": 0.9} hope that helps'
    out = lv.qc_image(_png(), "brief", poster=_poster(reply, []), vram_reader=lambda: 1000)
    assert out["verdict"] == "ok" and out["matches_brief"] is True


def test_unparseable_reply_is_reported_not_invented():
    out = lv.qc_image(_png(), "brief",
                      poster=_poster("I cannot see any image here.", []),
                      vram_reader=lambda: 1000)
    assert out["ok"] is False
    assert out["verdict"] == "unparsed"
    assert "cannot see" in out["raw"]


def test_transport_failure_reports_the_reason_and_the_mode():
    def dead(url, payload, timeout):
        raise ConnectionRefusedError("ollama down")

    out = lv.qc_image(_png(), "brief", poster=dead, vram_reader=lambda: 1000)
    assert out["ok"] is False
    assert "ollama down" in out["error"]
    assert out["mode"] == "cpu"
    assert out["vram_free_mb_before"] == 1000


def test_issues_given_as_a_string_are_normalised():
    reply = json.dumps({"matches_brief": False, "issues": "blurry text"})
    out = lv.qc_image(_png(), "brief", poster=_poster(reply, []), vram_reader=lambda: 1000)
    assert out["issues"] == ["blurry text"]


def test_empty_image_is_rejected():
    with pytest.raises(ValueError):
        lv.qc_image(b"", "brief")


# --- engine report ----------------------------------------------------------

def test_engines_reports_the_device_it_would_use(monkeypatch):
    monkeypatch.setattr(lv, "vram_free_mb", lambda: 1000)
    monkeypatch.setattr(lv.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(b'{"models":[{"name":"qwen2.5vl:7b"}]}'))
    info = lv.engines()
    assert info["available"] is True
    assert info["would_use"] == "cpu"
    assert info["keep_alive"] == 0
