"""ComfyUI client helpers — offline (no network, no generation)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Northstar_backend import comfyui_client as cc


def test_join_builds_url():
    assert cc._join("http://127.0.0.1:8188/", "/prompt") == "http://127.0.0.1:8188/prompt"


def test_extract_images_from_history():
    entry = {"outputs": {"9": {"images": [{"filename": "a.png"}, {"filename": "b.png"}]},
                         "10": {"videos": [{"filename": "c.mp4"}]}}}
    assert cc.extract_images(entry) == ["a.png", "b.png", "c.mp4"]
    assert cc.extract_images({}) == []


def test_reachable_bad_url_is_unknown():
    assert cc.reachable("not a url") == "unknown"


def test_reachable_closed_port_is_unreachable():
    assert cc.reachable("http://127.0.0.1:1", timeout=0.2) == "unreachable"


def test_load_template_roundtrip(tmp_path: Path):
    p = tmp_path / "wf.json"
    p.write_text(json.dumps({"1": {"class_type": "SaveImage"}}), encoding="utf-8")
    assert cc.load_template(p)["1"]["class_type"] == "SaveImage"


def test_load_template_missing_raises(tmp_path: Path):
    with pytest.raises(cc.ComfyUIError):
        cc.load_template(tmp_path / "nope.json")


def test_client_defaults_are_localhost():
    c = cc.ComfyUIClient()
    assert c.base.startswith("http://127.0.0.1")
