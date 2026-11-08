"""Harness orchestration: brief -> generator -> scorers -> gap/escalation.

`run_pass` is one seller-testing session. It pairs briefs with artefacts from an
injectable generator, scores each image, files failures as gaps, and escalates
the brief after every pass. Nothing here is model-dependent; the judge is
optional and off unless enabled.

Three things make the pass honest about the service's three inputs
(ty/MANDATE.md):

* every result carries the brief's `source_mode`, and the summary is grouped by
  mode with the three known modes always present (`scored: 0` is shown, never
  hidden);
* a limited pass samples across modes by round-robin, so `--limit 40` cannot
  silently score one input mode and call it coverage;
* reference-mode briefs run the reference-subject check, which fails when the
  produced picture does not measurably contain the reference subject — or when
  it cannot be verified at all.

The circuit breaker rule applies: a generator that cannot produce an artefact
raises `GeneratorUnavailable` and the pass stops. Failures are never silently
skipped and nothing is retried automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .briefs import (
    DEFAULT_CATALOG_PATH,
    SOURCE_MODES,
    brief_mode,
    load_catalog,
    mode_counts,
)
from .escalate import DEFAULT_ESCALATION_PATH, EscalationLog, escalate
from .gaps import DEFAULT_GAPS_PATH, DEFAULT_MIRROR_PATH, build_gap, file_gap, read_gaps
from .judge import get_judge
from .reference_check import reference_check_for_brief
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


def select_briefs(catalog: Sequence[Dict[str, Any]], limit: Optional[int] = None,
                  mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Deterministic, mode-balanced selection from the catalog.

    Briefs are taken round-robin across input modes, in catalog order within a
    mode. A limit therefore samples all three inputs instead of exhausting one
    and reporting it as full coverage. `mode` restricts the pass to one input.
    """
    if mode is not None and mode not in SOURCE_MODES:
        raise ValueError(f"unknown source_mode {mode!r}; must be one of {SOURCE_MODES}")
    rows = [row for row in catalog
            if mode is None or brief_mode(row) == mode]
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(brief_mode(row), []).append(row)
    order = [name for name in SOURCE_MODES if buckets.get(name)]
    order += sorted(name for name in buckets if name not in SOURCE_MODES)
    cursors = {name: 0 for name in order}
    selected: List[Dict[str, Any]] = []
    while True:
        progressed = False
        for name in order:
            if cursors[name] >= len(buckets[name]):
                continue
            selected.append(buckets[name][cursors[name]])
            cursors[name] += 1
            progressed = True
            if limit is not None and len(selected) >= max(0, int(limit)):
                return selected
        if not progressed:
            return selected


def run_pass(*, generator: Any, briefs: Any = None, limit: int = 20,
             mode: Optional[str] = None,
             judge: Optional[Callable[[bytes, Dict[str, Any]], Dict[str, Any]]] = None,
             gaps_path: str | Path = DEFAULT_GAPS_PATH,
             mirror_path: str | Path | None = DEFAULT_MIRROR_PATH,
             escalation_path: str | Path | None = DEFAULT_ESCALATION_PATH,
             now: Optional[str] = None,
             progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
    """Run one pass. Returns a summary suitable for a report."""
    payload = briefs if briefs is not None else load_catalog(DEFAULT_CATALOG_PATH)
    catalog = _briefs_from(payload)
    if not catalog:
        raise ValueError("no briefs to run")
    active_judge = judge if judge is not None else get_judge()

    selected = select_briefs(catalog, limit=int(limit), mode=mode)
    if not selected:
        raise ValueError(f"no briefs selected for mode {mode!r}")

    pairs = generator.pair(selected, limit=int(limit))
    if not pairs:
        raise RuntimeError("generator produced no (brief, artefact) pairs")

    log = EscalationLog(escalation_path)
    results: List[Dict[str, Any]] = []
    gaps_filed = 0
    used_categories = {str(row.get("category")) for row in catalog}

    for index, (brief, artefact) in enumerate(pairs):
        data = Path(artefact).read_bytes()
        current_mode = brief_mode(brief)
        scored = score_image(
            data, brief, judge=active_judge,
            reference_check=lambda rgb, b=brief: reference_check_for_brief(rgb, b),
        )
        rel = _relative(artefact)
        result_row = {
            "brief_id": scored.get("brief_id"),
            "category": scored.get("category"),
            "situation": scored.get("situation"),
            "difficulty": scored.get("difficulty"),
            "source_mode": scored.get("source_mode") or current_mode,
            "artefact_path": rel,
            "width": scored.get("width"),
            "height": scored.get("height"),
            "score": scored.get("score"),
            "passed": bool(scored.get("passed")),
            "failed_checks": list(scored.get("failed_checks") or []),
            "checks": {
                name: {"ok": check.get("ok"),
                       "skipped": bool(check.get("skipped")),
                       "cannot_verify": bool(check.get("cannot_verify")),
                       "detail": str(check.get("detail", ""))[:400]}
                for name, check in (scored.get("checks") or {}).items()
            },
        }
        reference = brief.get("reference")
        if isinstance(reference, dict):
            result_row["reference"] = {
                "kind": reference.get("kind"),
                "path": reference.get("path"),
            }
        if scored.get("error"):
            result_row["error"] = scored["error"]
        results.append(result_row)

        if scored.get("passed"):
            step = escalate(brief, catalog, used_categories=used_categories,
                            source_mode=current_mode)
            log.record(brief, step, score=scored.get("score"), artefact_path=rel,
                       at=now, source_mode=current_mode)
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
        "mode_filter": mode,
        "catalog_briefs": len(catalog),
        "catalog_by_mode": mode_counts({"briefs": catalog}),
        "selected": len(selected),
        "artefacts_available": len(generator) if hasattr(generator, "__len__") else None,
        "scored": len(results),
        "not_scored": len(selected) - len(results),
        "not_scored_reason": (
            None if len(results) == len(selected)
            else "the generator had fewer artefacts than the pass selected"
        ),
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
    summary["by_mode"] = _by_mode(results)
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
        bucket["failed"] = bucket["scored"] - bucket["passed"]
        bucket["pass_rate"] = round(100.0 * bucket["passed"] / bucket["scored"], 1)
        bucket["mean_score"] = round(sum(bucket["scores"]) / len(bucket["scores"]), 1)
        bucket.pop("scores", None)
    return dict(sorted(out.items()))


def _empty_bucket() -> Dict[str, Any]:
    return {"scored": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "mean_score": 0.0}


def _by_mode(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group by input mode, keeping the three known modes visible at zero."""
    grouped = _group(results, "source_mode")
    out: Dict[str, Dict[str, Any]] = {name: _empty_bucket() for name in SOURCE_MODES}
    for name, bucket in grouped.items():
        out[name] = bucket
    return out


def _by_situation(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _group(results, "situation")


def _by_category(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _group(results, "category")


__all__ = ["run_pass", "score_image", "select_briefs"]
