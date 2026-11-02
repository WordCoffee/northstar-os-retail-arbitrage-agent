"""Deliverable packages: gate, folder, manifest — and no placeholder fields."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deliverables as dl


def _png(size=(64, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (210, 200, 180)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DELIVERABLES", tmp_path / "deliverables")
    return tmp_path / "deliverables"


def test_a_passing_verdict_writes_the_package(store):
    out = dl.write_deliverable("run-1", brief="a 6 oz pouch of mushroom powder",
                               final_png=_png(),
                               adherence={"ok": True, "requested": "pouch",
                                          "observed": "pouch", "model": "qwen3.5:4b"})
    folder = Path(out["folder"])
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["adherence.json", "brief.txt", "citations.json", "final.png",
                     "manifest.json"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-1"
    assert manifest["image_size"] == [64, 80]
    assert manifest["bytes"] == len(_png())
    assert manifest["adherence"]["ok"] is True
    assert manifest["citations"], "citations must be populated, not empty"
    # the manifest's own file list must include itself, or it under-reports the folder
    assert manifest["files"] == names


def test_the_manifest_holds_no_placeholders(store):
    out = dl.write_deliverable("run-2", brief="brief", final_png=_png(),
                               adherence={"ok": True, "requested": "box",
                                          "observed": "box"})
    raw = json.dumps(out["manifest"]).lower()
    for needle in ("todo", "tbd", "placeholder", "lorem", "xxx"):
        assert needle not in raw
    # unknown stays absent rather than null
    assert "seed" not in out["manifest"]


def test_unknown_extras_are_omitted_not_nulled(store):
    out = dl.write_deliverable("run-3", brief="b", final_png=_png(),
                               adherence={"ok": True, "requested": "pouch",
                                          "observed": "pouch"},
                               extra={"seed": None, "model": "flux"})
    assert out["manifest"]["model"] == "flux"
    assert "seed" not in out["manifest"]


def test_the_verdict_requires_a_vision_answer():
    verdict = dl.adherence_verdict("pouch", {"available": False, "reason": "offline"})
    assert verdict["ok"] is False and "unavailable" in verdict["reason"]


def test_the_verdict_fails_on_the_wrong_form():
    verdict = dl.adherence_verdict("bottle", {"available": True, "observed": "box",
                                              "answer": "box", "model": "m"})
    assert verdict["ok"] is False and verdict["observed"] == "box"


def test_the_verdict_passes_on_the_right_form():
    verdict = dl.adherence_verdict("tube", {"available": True, "observed": "tube",
                                            "answer": "squeeze tube", "model": "m"})
    assert verdict["ok"] is True


def test_listing_returns_newest_first(store):
    dl.write_deliverable("a", brief="1", final_png=_png(),
                         adherence={"ok": True, "requested": "pouch", "observed": "pouch"})
    dl.write_deliverable("b", brief="2", final_png=_png(),
                         adherence={"ok": True, "requested": "pouch", "observed": "pouch"})
    rows = dl.list_deliverables()
    assert [r["run_id"] for r in rows] == ["b", "a"]


def test_read_final_returns_the_packaged_render(store):
    dl.write_deliverable("run-9", brief="b", final_png=_png(),
                         adherence={"ok": True, "requested": "pouch", "observed": "pouch"})
    assert dl.read_final("run-9") == _png()


def test_read_final_refuses_unknown_runs_and_escapes(store):
    dl.write_deliverable("run-10", brief="b", final_png=_png(),
                         adherence={"ok": True, "requested": "pouch", "observed": "pouch"})
    assert dl.read_final("no-such-run") is None
    assert dl.read_final("../test_deliverables") is None
    assert dl.read_final("..") is None


def test_a_folder_without_a_manifest_is_ignored(store):
    (store / "broken").mkdir(parents=True)
    (store / "broken" / "final.png").write_bytes(_png())
    assert dl.list_deliverables() == []
