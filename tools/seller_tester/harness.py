"""Harness orchestration: brief -> generator -> scorers -> gap/escalation.

`run_pass` is one seller-testing session. It pairs briefs with artefacts from an
injectable generator, scores each image, files failures as gaps, and escalates
the brief after every pass. Nothing here is model-dependent; the judge is
optional and off unless enabled.

The circuit breaker rule applies: a generator that cannot produce an artefact
raises `GeneratorUnavailable` and the pass stops. Failures are never silently
skipped and nothing is retried automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .briefs import DEFAULT_CATALOG_PATH, load_catalog
from .escalate import DEFAULT_ESCALATION_PATH, EscalationLog, escalate
from .gaps import DEFAULT_GAPS_PATH, DEFAULT_MIRROR_PATH, build_gap, file_gap, read_gaps
from .judge import get_judge
from .scorers import score_image

REPO_ROOT = Path(__file__).resolve().parents[2]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _relative(path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return str(path)


def _briefs_from(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("briefs")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("briefs must be a catalog dict or a list of briefs")
    return [row for row in rows if isinstance(row, dict)]


def run_pass(*, generator: Any, briefs: Any = None, limit: int = 20,
             judge: Optional[Callable[[bytes, Dict[str, Any]], Dict[str, Any]]] = None,
             gaps_path: str | Path = DEFAULT_GAPS_PATH,
             mirror_path: str | Path | None = DEFAULT_MIRROR_PATH,
             escalation_path: str | Path | None = DEFAULT_ESCALATION_PATH,
             now: Optional[str] = None,
             progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
    """Run one pass. Returns a summary suitable for a report."""
    catalog = _briefs_from(briefs if briefs is not None else load_catalog(DEFAULT_CATALOG_PATH))
    if not catalog:
        raise ValueError("no briefs to run")
    active_judge = judge if judge is not None else get_judge()

    pairs = generator.pair(catalog, limit=int(limit))
    if not pairs:
        raise RuntimeError("generator produced no (brief, artefact) pairs")

    log = EscalationLog(escalation_path)
    results: List[Dict[str, Any]] = []
    gaps_filed = 0
    used_categories = {str(row.get("category")) for row in catalog}

    for index, (brief, artefact) in enumerate(pairs):
        data = Path(artefact).read_bytes()
        scored = score_image(data, brief, judge=active_judge)
        rel = _relative(artefact)
        result_row = {
            "brief_id": scored.get("brief_id"),
            "category": scored.get("category"),
            "situation": scored.get("situation"),
            "difficulty": scored.get("difficulty"),
            "artefact_path": rel,
            "width": scored.get("width"),
            "height": scored.get("height"),
            "score": scored.get("score"),
            "passed": bool(scored.get("passed")),
            "failed_checks": list(scored.get("failed_checks") or []),
            "checks": {
                name: {"ok": check.get("ok"),
                       "skipped": bool(check.get("skipped")),
                       "detail": str(check.get("detail", ""))[:400]}
                for name, check in (scored.get("checks") or {}).items()
            },
        }
        if scored.get("error"):
            result_row["error"] = scored["error"]
        results.append(result_row)

        if scored.get("passed"):
            step = escalate(brief, catalog, used_categories=used_categories)
            log.record(brief, step, score=scored.get("score"), artefact_path=rel, at=now)
            used_categories.add(str(step.get("brief", {}).get("category")))
        else:
            gap = build_gap(str(brief.get("id")), scored, artefact, at=now)
            file_gap(gap, path=gaps_path, mirror=mirror_path)
            gaps_filed += 1

        if progress is not None:
            progress(index + 1, len(pairs))

    log.save()
    all_gaps = read_gaps(gaps_path)
    passed = sum(1 for row in results if row["passed"])
    scores = [float(row["score"] or 0.0) for row in results]
    summary = {
        "generated_at": now or _now(),
        "generator": getattr(generator, "name", type(generator).__name__),
        "judge_enabled": active_judge is not None,
        "catalog_briefs": len(catalog),
        "artefacts_available": len(generator) if hasattr(generator, "__len__") else None,
        "scored": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(100.0 * passed / len(results), 1) if results else 0.0,
        "mean_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "gaps_filed": gaps_filed,
        "gaps_in_file": len(all_gaps),
        "gaps_path": _relative(gaps_path),
        "mirror_path": None if mirror_path is None else _relative(mirror_path),
        "escalations": list(log.entries),
        "results": results,
    }
    summary["by_situation"] = _by_situation(results)
    summary["by_category"] = _by_category(results)
    return summary


def _group(results: Sequence[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in results:
        name = str(row.get(key) or "unknown")
        bucket = out.setdefault(name, {"scored": 0, "passed": 0, "scores": []})
        bucket["scored"] += 1
        bucket["passed"] += 1 if row.get("passed") else 0
        bucket["scores"].append(float(row.get("score") or 0.0))
    for bucket in out.values():
        bucket["mean_score"] = round(sum(bucket["scores"]) / len(bucket["scores"]), 1)
        bucket.pop("scores", None)
    return dict(sorted(out.items()))


def _by_situation(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _group(results, "situation")


def _by_category(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _group(results, "category")


__all__ = ["run_pass", "score_image"]
