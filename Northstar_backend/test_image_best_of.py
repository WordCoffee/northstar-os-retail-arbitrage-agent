"""Best-of-N: the winner is measured, and every reject keeps its score."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import image_best_of as bo  # noqa: E402
import tys_assistant as tys  # noqa: E402


def _report(status="passed", preference=None, adherence=None):
    return {"status": status, "ok": status == "passed", "reasons": [],
            "axes": {"preference": {"score": preference},
                     "adherence": {"score": adherence}}}


def _render(seed):
    return {"bytes": f"png-{seed}".encode(), "seed": seed}


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def test_a_passed_candidate_beats_higher_scores_that_did_not_pass():
    candidates = [
        {"index": 0, "out": {"bytes": b"a"}, "report": _report("refused", 0.9, 25)},
        {"index": 1, "out": {"bytes": b"b"}, "report": _report("passed", 0.2, 19)},
    ]
    assert bo.pick(candidates) == 1


def test_higher_preference_wins_when_nothing_passed():
    candidates = [
        {"index": 0, "out": {"bytes": b"a"}, "report": _report("unscored", 0.15, 18)},
        {"index": 1, "out": {"bytes": b"b"}, "report": _report("unscored", 0.24, 20)},
        {"index": 2, "out": {"bytes": b"c"}, "report": _report("unscored", 0.20, 22)},
    ]
    assert bo.pick(candidates) == 1


def test_a_render_error_is_recorded_and_does_not_win():
    candidates = [
        {"index": 0, "out": None, "error": "boom"},
        {"index": 1, "out": {"bytes": b"b"}, "report": _report("passed")},
    ]
    assert bo.pick(candidates) == 1


def test_all_failures_leave_no_winner():
    assert bo.pick([{"index": 0, "out": None}, {"index": 1, "out": None}]) is None


# ---------------------------------------------------------------------------
# the batch
# ---------------------------------------------------------------------------

def test_run_renders_n_candidates_and_keeps_the_best(tmp_path):
    reports = [_report("unscored", 0.10, 18),
               _report("passed", 0.21, 20),
               _report("unscored", 0.30, 24)]
    seeds = []
    calls = {"n": 0}

    def render(seed):
        seeds.append(seed)
        index = calls["n"]
        calls["n"] += 1
        return {"bytes": f"png-{index}".encode(), "seed": seed}

    result = bo.run(render, lambda png: reports[int(png.decode().split('-')[1])],
                    attempts=3, seed=101, out_dir=tmp_path, prefix="hero")
    assert len(seeds) == 3
    assert seeds[1] - seeds[0] == seeds[2] - seeds[1] == 7919
    assert result["winner"]["report"]["status"] == "passed"
    assert result["manifest"]["passed_on"] == 1
    assert (tmp_path / "hero.png").is_file()
    assert (tmp_path / "rejected_hero_0.png").is_file()
    saved = json.loads((tmp_path / "hero_best_of.json").read_text(encoding="utf-8"))
    assert [c["status"] for c in saved["candidates"]] == ["unscored", "passed", "unscored"]


def test_a_review_error_is_recorded_against_that_candidate():
    def render(seed):
        return {"bytes": b"x"}

    def review(png):
        raise RuntimeError("scorer down")

    result = bo.run(render, review, attempts=1, seed=5)
    assert result["winner"]["report"]["status"] == "error"
    assert "scorer down" in result["winner"]["report"]["reasons"][0]


# ---------------------------------------------------------------------------
# the graphics lane uses it when the work order asks for variants
# ---------------------------------------------------------------------------

def test_graphics_lane_runs_best_of_when_attempts_is_set(monkeypatch, tmp_path):
    from tys_ops import graphics

    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": True, "detail": "ok", "model": "flux-3"})
    monkeypatch.setattr(graphics, "suspend_competing_engines", lambda: {})

    class Lock:
        def acquire(self, timeout=None):
            return True

        def release(self):
            pass

    monkeypatch.setattr(graphics, "gpu_lock", lambda: Lock())
    rendered = []
    for i in range(3):
        path = tmp_path / f"c{i}.png"
        path.write_bytes(b"png")
        rendered.append(path)

    def fake_generate(prompt, **kwargs):
        index = len([r for r in rendered if r.exists()]) - 1
        return {"artifacts": [str(rendered[index])], "model": "flux-3",
                "width": 1024, "height": 1024, "steps": 28,
                "seed": kwargs.get("seed")}

    monkeypatch.setattr(graphics, "generate", fake_generate)
    reports = [_report("refused", 0.9, 25), _report("passed", 0.21, 20),
               _report("unscored", 0.3, 24)]
    monkeypatch.setattr(tys.GraphicsAdapter, "_ship_gate",
                        lambda self, out, params, prompt: (reports.pop(0), {}))

    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "render the pouch",
         "params": {"prompt": "the pouch", "attempts": 3, "seed": 10}}, {})
    assert result.ok is True
    assert "best of 3" in result.summary
    assert result.evidence["best_of"]["winner_index"] == 1
    assert len(result.evidence["best_of"]["candidates"]) == 3
