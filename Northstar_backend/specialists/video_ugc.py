"""Video & UGC — script, storyboard and a duration check that cannot be faked.

The blueprint is explicit: "A still image, animated preview, script, storyboard,
or queued job is not the requested completed video", and the duration must be
verified "against five seconds with a declared frame/timebase tolerance, not a
hardcoded badge".

So this agent produces the plan AND the arithmetic that later proves the result:

    duration_seconds = frame_count / fps

and `validate_duration` refuses a clip whose measured length is outside the
declared tolerance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

FPS_DEFAULT = 24
#: A declared tolerance, not a guess: one frame either side of the target.
DEFAULT_TOLERANCE_FRAMES = 1

SUPPORTED_DURATIONS = (5, 10, 15, 30)

HOOKS = {
    "problem": "Open on the problem the product solves.",
    "result": "Open on the finished result, then explain.",
    "proof": "Open on the proof (test, comparison, before/after).",
}


def missing_inputs(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    gaps: List[Dict[str, str]] = []
    if not spec.get("product"):
        gaps.append({"field": "product", "question": "which product is the video for?"})
    if not spec.get("duration_seconds"):
        gaps.append({"field": "duration_seconds",
                     "question": "how long should it be? (5, 10, 15 or 30 seconds)"})
    return gaps


def storyboard(*, duration_seconds: int, hook: str = "problem",
               beats: Sequence[str] | None = None) -> List[Dict[str, Any]]:
    """Split a duration into scene beats. Never invents product facts."""
    total = float(duration_seconds)
    default_beats = ["hook", "problem", "product", "proof", "cta"]
    names = list(beats or default_beats)
    if total <= 6:
        names = ["hook", "product", "cta"]
    elif total <= 12:
        names = ["hook", "problem", "product", "cta"]
    share = total / len(names)
    scenes: List[Dict[str, Any]] = []
    cursor = 0.0
    for i, name in enumerate(names):
        length = round(share, 2) if i < len(names) - 1 else round(total - cursor, 2)
        scenes.append({
            "scene": i + 1,
            "beat": name,
            "start_s": round(cursor, 2),
            "end_s": round(cursor + length, 2),
            "seconds": length,
            "direction": _direction(name, hook),
        })
        cursor += length
    return scenes


def _direction(beat: str, hook: str) -> str:
    return {
        "hook": HOOKS.get(hook, HOOKS["problem"]),
        "problem": "Show the friction the product removes.",
        "product": "Clean product hero; label legible; no invented claims.",
        "proof": "Demonstrate the benefit with something observable.",
        "cta": "Short call to action; brand end-card.",
    }.get(beat, "Continue the story.")


def plan(*, spec: Dict[str, Any], allow_incomplete: bool = False) -> Dict[str, Any]:
    gaps = missing_inputs(spec)
    if gaps and not allow_incomplete:
        return {"ok": False, "status": "needs_input",
                "summary": f"{len(gaps)} thing(s) first.", "questions": gaps, "assets": []}

    seconds = int(spec.get("duration_seconds") or 0)
    if seconds not in SUPPORTED_DURATIONS:
        return {"ok": False, "status": "rejected",
                "summary": (f"{seconds}s is not one of the durations this lane supports "
                            f"({', '.join(str(d) for d in SUPPORTED_DURATIONS)}s). "
                            f"Nothing was generated."),
                "error": "unsupported duration", "assets": []}

    fps = int(spec.get("fps") or FPS_DEFAULT)
    frames = int(round(seconds * fps))
    scenes = storyboard(duration_seconds=seconds, hook=str(spec.get("hook") or "problem"))
    return {
        "ok": True,
        "status": "planned",
        "summary": (f"{seconds}s storyboard: {len(scenes)} scenes at {fps} fps "
                    f"= {frames} frames. Generate, then validate the length."),
        "duration_seconds": seconds,
        "fps": fps,
        "frames": frames,
        "scenes": scenes,
        "validation_plan": {
            "expected_seconds": seconds,
            "tolerance_frames": DEFAULT_TOLERANCE_FRAMES,
            "tolerance_seconds": round(DEFAULT_TOLERANCE_FRAMES / fps, 4),
            "measured_as": "frame_count / fps",
        },
        "claims_check": _claim_words(spec.get("script") or ""),
        "assets": [],
    }


def _claim_words(script: str) -> List[Dict[str, str]]:
    import re
    bad = re.compile(r"\b(cures?|treats?|prevents?|reverses?|guaranteed)\b", re.I)
    return [{"match": m.group(0)} for m in bad.finditer(str(script or ""))]


def validate_duration(*, frame_count: int, fps: int, expected_seconds: int,
                      tolerance_frames: int = DEFAULT_TOLERANCE_FRAMES) -> Dict[str, Any]:
    """Prove the clip is the requested length, from frames and fps."""
    if fps <= 0:
        return {"ok": False, "problems": ["fps must be positive"], "measured_seconds": None}
    measured = frame_count / float(fps)
    tolerance = tolerance_frames / float(fps)
    ok = abs(measured - expected_seconds) <= tolerance + 1e-9
    return {
        "ok": ok,
        "measured_seconds": round(measured, 4),
        "expected_seconds": expected_seconds,
        "tolerance_seconds": round(tolerance, 4),
        "delta_seconds": round(measured - expected_seconds, 4),
        "problems": [] if ok else [
            f"measured {measured:.3f}s from {frame_count} frames at {fps} fps; "
            f"expected {expected_seconds}s +/- {tolerance:.3f}s"],
    }
