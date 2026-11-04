"""Best-of-N for image renders.

Quality is a number only if more than one candidate is measured. This module
renders N candidates, reviews each with `ship_gate.review_image` and keeps the
winner; every rejected candidate is written next to it with its scores, so a
refusal can be audited instead of argued about.

Selection order, deterministic:

1. a candidate the gate passed beats one it did not;
2. then the higher HPSv2 preference score;
3. then the higher PickScore adherence score;
4. then the earlier attempt.

A render or review error is recorded against that candidate and never silently
dropped; if every attempt fails, the result says so and has no winner. There is
no retry loop inside: the caller decides whether another batch is worth the GPU.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

RenderFn = Callable[[int], Dict[str, Any]]
ReviewFn = Callable[[bytes], Dict[str, Any]]


def candidate_key(candidate: Dict[str, Any]) -> tuple:
    report = candidate.get("report") or {}
    axes = report.get("axes") or {}
    preference = (axes.get("preference") or {}).get("score")
    adherence = (axes.get("adherence") or {}).get("score")
    return (
        1 if report.get("status") == "passed" else 0,
        float(preference) if isinstance(preference, (int, float)) else -1.0,
        float(adherence) if isinstance(adherence, (int, float)) else -1.0,
        -int(candidate.get("index") or 0),
    )


def _has_output(candidate: Dict[str, Any]) -> bool:
    out = candidate.get("out") or {}
    return bool(out.get("bytes") or out.get("artifacts"))


def pick(candidates: Sequence[Dict[str, Any]]) -> Optional[int]:
    """Index of the winning candidate, or None when nothing could be rendered."""
    usable = [i for i, c in enumerate(candidates) if _has_output(c)]
    if not usable:
        return None
    return max(usable, key=lambda i: candidate_key(candidates[i]))


def _seeds(count: int, base: Optional[int]) -> List[int]:
    if base is None:
        return [int(time.time() * 1000) % (2 ** 31) + i * 7919 for i in range(count)]
    base = int(base)
    return [base + i * 7919 for i in range(count)]


def run(render_fn: RenderFn, review_fn: Optional[ReviewFn], *, attempts: int = 3,
        seed: Optional[int] = None, out_dir: Optional[Path] = None,
        prefix: str = "candidate", brief: str = "") -> Dict[str, Any]:
    """Render ``attempts`` candidates, review them, keep the winner.

    ``render_fn(seed)`` returns a dict with at least ``bytes``.
    ``review_fn(png_bytes)`` returns a ship-gate report; ``None`` records the
    candidates unreviewed and picks the first.
    """
    count = max(1, min(int(attempts), 5))
    seeds = _seeds(count, seed)
    candidates: List[Dict[str, Any]] = []
    for index, one_seed in enumerate(seeds):
        candidate: Dict[str, Any] = {"index": index, "seed": one_seed}
        try:
            out = render_fn(one_seed)
        except Exception as exc:  # noqa: BLE001 - one failed attempt is not the batch
            candidate.update({"error": f"{type(exc).__name__}: {exc}"})
            candidates.append(candidate)
            continue
        candidate["out"] = out
        if review_fn is not None:
            try:
                candidate["report"] = review_fn(out["bytes"])
            except Exception as exc:  # noqa: BLE001 - an error is not a verdict
                candidate["report"] = {"status": "error", "ok": False,
                                       "reasons": [f"{type(exc).__name__}: {exc}"]}
        candidates.append(candidate)

    winner = pick(candidates)
    manifest = {
        "attempts": count,
        "brief": brief,
        "winner_index": winner,
        "passed_on": (candidates[winner]["index"]
                      if winner is not None
                      and (candidates[winner].get("report") or {}).get("status") == "passed"
                      else None),
        "candidates": [_record(c) for c in candidates],
    }
    if out_dir is not None and winner is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for c in candidates:
            data = (c.get("out") or {}).get("bytes")
            if not data:
                continue
            name = (f"{prefix}.png" if c["index"] == winner
                    else f"rejected_{prefix}_{c['index']}.png")
            (out_dir / name).write_bytes(data)
            c["path"] = str(out_dir / name)
        manifest["winner_path"] = candidates[winner].get("path")
        (out_dir / f"{prefix}_best_of.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(out_dir / f"{prefix}_best_of.json")
    return {"winner": candidates[winner] if winner is not None else None,
            "candidates": candidates, "manifest": manifest}


def _record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    report = candidate.get("report") or {}
    return {
        "index": candidate.get("index"),
        "seed": candidate.get("seed"),
        "status": report.get("status"),
        "reasons": list(report.get("reasons") or []),
        "preference": ((report.get("axes") or {}).get("preference") or {}).get("score"),
        "adherence": ((report.get("axes") or {}).get("adherence") or {}).get("score"),
        "error": candidate.get("error"),
    }


def summarise(candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_record(c) for c in candidates]


__all__ = ["run", "pick", "candidate_key", "summarise"]
