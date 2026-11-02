"""A+ packages: the page, its QA, and what OCR can actually read back."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aplus_manifest as am  # noqa: E402


def _module(tmp_path: Path, kind: str, texts, *, index=1, qa_ok=True,
            problems=None) -> dict:
    png = tmp_path / f"{kind}.png"
    Image.new("RGB", (64, 48), (240, 236, 226)).save(png, format="PNG")
    return {"index": index, "kind": kind, "path": str(png), "size": [64, 48],
            "copy_mode": "panel", "copy_texts": list(texts),
            "qa": {"ok": qa_ok, "problems": list(problems or []), "warnings": []}}


def _page(*modules) -> dict:
    return {"id": "aplus_test_page", "ok": all(m["qa"]["ok"] for m in modules),
            "problems": [], "modules": list(modules), "bytes_total": 1234}


@pytest.fixture()
def ocr(monkeypatch):
    def apply(contains_text=True, words=None):
        monkeypatch.setattr(am.tf, "check_text_in_image", lambda _b: {
            "engine": "rapidocr", "status": "ok",
            "contains_text": contains_text, "boxes": len(words or []),
            "words": list(words or []), "error": None})
    return apply


def test_a_readable_page_is_packaged(tmp_path, ocr):
    ocr(words=["LION MANE", "6 oz"])
    module = _module(tmp_path, "header", ["LION MANE", "6 oz"])
    out = am.package(_page(module), requested_kinds=["header"], out_root=tmp_path / "out")
    folder = Path(out["folder"])
    assert folder.is_dir()
    names = sorted(p.name for p in folder.iterdir())
    assert "manifest.json" in names and any(n.startswith("aplus_01_header") for n in names)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["quality"]["verdict"]["ok"] is True
    assert manifest["quality"]["verdict"]["score"] == "3/3"
    assert manifest["modules"][0]["coverage"]["coverage"] == 1.0


def test_the_manifest_carries_no_nulls(tmp_path, ocr):
    ocr(words=["LION MANE"])
    module = _module(tmp_path, "header", ["LION MANE"])
    out = am.package(_page(module), requested_kinds=["header"], out_root=tmp_path / "out")
    manifest = out["manifest"]

    def nulls(obj, path="manifest"):
        found = []
        if obj is None:
            found.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(nulls(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(nulls(v, f"{path}[{i}]"))
        return found

    assert nulls(manifest) == []


def test_a_failed_qa_module_blocks_and_writes_nothing(tmp_path, ocr):
    ocr(words=["LION MANE"])
    module = _module(tmp_path, "header", ["LION MANE"], qa_ok=False,
                     problems=["headline: contrast 2.1:1 below 4.5:1"])
    out = am.package(_page(module), requested_kinds=["header"], out_root=tmp_path / "out")
    assert out["folder"] is None
    assert out["verdict"]["ok"] is False
    assert out["verdict"]["reasons"][0]["reason"] == "layout_qa"
    assert not (tmp_path / "out" / "aplus_test_page").exists()


def test_copy_that_ocr_cannot_read_blocks(tmp_path, ocr):
    ocr(words=["SOMETHING ELSE"], contains_text=True)
    module = _module(tmp_path, "header", ["LION MANE", "6 oz"])
    out = am.package(_page(module), requested_kinds=["header"], out_root=tmp_path / "out")
    assert out["folder"] is None
    assert out["verdict"]["reasons"][0]["reason"] == "typography_unreadable"


def test_a_module_that_draws_no_copy_is_not_applicable(tmp_path, ocr):
    ocr(contains_text=False, words=[])
    module = _module(tmp_path, "three_tiles", [])
    out = am.package(_page(module), requested_kinds=["three_tiles"], out_root=tmp_path / "out")
    assert out["verdict"]["ok"] is True
    assert out["verdict"]["not_applicable"] == ["form", "typography"]
    assert out["verdict"]["score"] == "2/2"


def test_a_requested_module_that_is_missing_blocks(tmp_path, ocr):
    ocr(words=["LION MANE"])
    module = _module(tmp_path, "header", ["LION MANE"])
    out = am.package(_page(module), requested_kinds=["header", "comparison"],
                     out_root=tmp_path / "out")
    assert out["verdict"]["reasons"][0]["reason"] == "module_missing"


def test_ocr_unavailable_blocks_a_copied_module(tmp_path, monkeypatch):
    monkeypatch.setattr(am.tf, "check_text_in_image", lambda _b: {
        "engine": None, "status": "unavailable", "contains_text": None,
        "boxes": 0, "words": [], "error": "unavailable"})
    module = _module(tmp_path, "header", ["LION MANE"])
    out = am.package(_page(module), requested_kinds=["header"], out_root=tmp_path / "out")
    assert out["folder"] is None
    assert out["verdict"]["reasons"][0]["reason"] == "typography_unreadable"
