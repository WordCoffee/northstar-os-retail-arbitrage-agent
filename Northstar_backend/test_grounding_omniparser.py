"""The OmniParser-class runner's pure parts: box selection, caption matching, normalisation.

The detector and captioner need a GPU and a multi-hundred-megabyte download, so they are not in a
unit test. What *is* tested is everything that decides whether a grounding trial counts as a hit —
because a benchmark whose scoring is wrong reports a number nobody should trust.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "vision"))

from vision import grounding  # noqa: E402
import grounding_omniparser as G  # noqa: E402


def test_a_point_is_normalised_to_the_frame_it_came_from():
    # a 200x100 frame, box at (50, 20) sized 40x20 -> centre (70, 30)
    point = G.point_of((50, 20, 40, 20), (200, 100))
    assert point == {"x": pytest.approx(0.35), "y": pytest.approx(0.30)}


def test_a_label_inside_a_caption_wins_over_a_clumsy_similarity():
    captions = [((0, 0, 10, 10), "a small grey icon"),
                ((100, 100, 40, 40), "Search box with a magnifier")]
    assert G.pick(captions, "Search") == (100, 100, 40, 40)


def test_a_caption_that_has_nothing_to_do_with_the_label_is_refused():
    captions = [((0, 0, 10, 10), "folders"), ((50, 50, 10, 10), "trash can")]
    assert G.pick(captions, "Search") is None


def test_an_empty_label_never_matches_everything():
    captions = [((0, 0, 10, 10), "anything at all")]
    assert G.pick(captions, "") is None


def test_the_hit_test_uses_the_recorded_box_and_the_frame_geometry():
    box = [900, 16, 1100, 54]  # the Search box in the 1280x800 grounding set
    inside = G.point_of((890, 10, 200, 50), (1280, 800))
    assert grounding.hit(box, inside) is True
    outside = G.point_of((10, 700, 60, 40), (1280, 800))
    assert grounding.hit(box, outside) is False


def test_the_adoption_bar_is_the_documented_one():
    # 61.7% baseline plus a 10-point margin: adopting below that would be a regression sold as a win
    assert G.BASELINE == 0.617
    assert G.ADOPT_MARGIN == 0.10
    assert round(G.BASELINE + G.ADOPT_MARGIN, 3) == 0.717


def test_the_run_refuses_rather_than_scores_when_a_model_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(G, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(G, "load", lambda: {"detector_ok": False, "captioner_ok": False,
                                            "detector_error": "no ultralytics",
                                            "captioner_error": "no transformers"})
    payload = G.run(limit=1, targets=1)
    assert payload["ok"] is False
    assert payload["decision"] == "keep UIA and DOM primary"
    assert "hit_rate" not in payload
