"""Seller-Tester output scores, per service, split by population.

The owner's instruction (2026-11-08): *add seller-tester output scores to the scorecards so
artefacts alone can't raise them.* Tests prove that a code path runs; they do not prove that
what comes out is worth selling. This module turns a real Seller-Tester pass into a number a
scorecard can use, and a service with no scored output gets 0 with that reason.

**Two populations, never mixed.** A pass has two kinds of row:

* ``generated`` — the pipeline made the picture (composite, scene render, full generation);
  its row carries a generator record and says so;
* ``replay`` — `StoredGenerator` paired a brief with whatever image happened to be on disk
  (screenshots, crops, earlier renders). Useful context, but it is not this pipeline's
  output, so it is reported and never averaged into the published score.

The published mean is the generated/composite population. The replay population is kept in
the record with its count and mean, so a bad replay cannot be dropped silently and a good
one cannot flatter the service.

Attribution is declared, never guessed: a brief belongs to a service only through the
`service` field in `ty/seller_briefs.json` (default: the product-picture service, Design
Studio, because every brief in the catalogue today is a product picture).

    python -m tools.seller_tester run --limit 30     # the replay pass (context)
    python -m tools.seller_tester composite --limit 3  # a real generated pass
    python tools/seller_scores.py --write            # the scores the scorecard reads
    python tools/seller_scores.py --ceiling          # how many briefs can be judged at all
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "ty" / "seller_scores.json"
SUMMARY = ROOT / "state" / "seller" / "last_run.json"
COMPOSITE = ROOT / "state" / "seller" / "composite_proof.json"
MIN_SCORED = 5

POPULATIONS = ("generated", "replay")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _brief_rows(briefs: Any = None) -> List[Dict[str, Any]]:
    payload = briefs if briefs is not None else (_read(BRIEFS) or {})
    items = payload.get("briefs") if isinstance(payload, dict) else payload
    return [row for row in (items or []) if isinstance(row, dict)]


def brief_services(briefs: Any = None) -> Dict[str, str]:
    """brief id -> service. Declared in the brief, defaulting to design-studio."""
    out: Dict[str, str] = {}
    for brief in _brief_rows(briefs):
        if not brief.get("id"):
            continue
        out[str(brief["id"])] = str(brief.get("service") or "design-studio")
    return out


def population_of(row: Dict[str, Any], generator: Optional[str] = None) -> str:
    """Which population one result row belongs to, from its own record.

    The row's own `population` wins (the harness writes it). Next, a generator record with
    a route means the picture was made. Only an explicit stored/replay generator, or a row
    with neither, is replayed. An unknown generator is treated as generated: a summary that
    declares nothing is a caller's direct input, not a disk replay.
    """
    declared = str(row.get("population") or "").lower()
    if declared in POPULATIONS:
        return declared
    generation = row.get("generation")
    if isinstance(generation, dict) and generation.get("route"):
        return "generated"
    name = str(generator or row.get("generator") or "").lower()
    if name in ("stored", "replay", "stored_generator"):
        return "replay"
    return "generated"


def _sources(summary: Any = None, composite: Any = None) -> List[Tuple[Dict[str, Any], str]]:
    """The passes to aggregate: an injected summary, or the two on disk."""
    if summary is not None:
        out = [(summary, str(summary.get("generator") or ""))] if isinstance(summary, dict) else []
        if isinstance(composite, dict):
            out.append((composite, str(composite.get("generator") or "composite")))
        return out
    out = []
    primary = _read(SUMMARY)
    if isinstance(primary, dict):
        out.append((primary, str(primary.get("generator") or "")))
    extra = composite if composite is not None else _read(COMPOSITE)
    if isinstance(extra, dict) and extra is not primary:
        out.append((extra, str(extra.get("generator") or "composite")))
    return out


def _rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("results") or data.get("outputs") or []
    return [row for row in rows if isinstance(row, dict)]


def _bucket() -> Dict[str, Any]:
    return {"scores": [], "passed": 0}


def _summarise(bucket: Dict[str, Any]) -> Dict[str, Any]:
    scores = bucket["scores"]
    return {"mean": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "scored": len(scores),
            "passed": int(bucket["passed"])}


def build(*, summary: Optional[Dict[str, Any]] = None,
          composite: Optional[Dict[str, Any]] = None,
          briefs: Any = None) -> Dict[str, Any]:
    """Aggregate passes into a published generated mean plus replay context.

    `summary` is the replay pass (`state/seller/last_run.json`) unless injected. The
    composite proof is read alongside it. Each row is classified by `population_of`, and
    only `generated` rows feed `services[*].mean`. `services[*].replay` carries the other
    population so the record shows both.
    """
    sources = _sources(summary, composite)
    if not sources:
        return {"services": {}, "reason": "no seller-tester pass on disk", "at": _now()}
    mapping = brief_services(briefs)
    buckets: Dict[str, Dict[str, Dict[str, Any]]] = {}
    generated_at = ""
    for data, generator in sources:
        generated_at = generated_at or str(data.get("generated_at") or "")
        for row in _rows(data):
            service = mapping.get(str(row.get("brief_id") or ""), "design-studio")
            try:
                value = float(row.get("score"))
            except (TypeError, ValueError):
                continue
            population = population_of(row, generator)
            bucket = buckets.setdefault(
                service, {name: _bucket() for name in POPULATIONS})[population]
            bucket["scores"].append(value)
            if row.get("passed"):
                bucket["passed"] += 1

    services: Dict[str, Dict[str, Any]] = {}
    for service, split in buckets.items():
        made = _summarise(split["generated"])
        replay = _summarise(split["replay"])
        row: Dict[str, Any] = {
            "mean": made["mean"], "scored": made["scored"], "passed": made["passed"],
            "at": generated_at or _now(),
            "population": "generated",
            "replay": replay,
        }
        if not made["scored"]:
            row["reason"] = (
                f"no generated or composite output; {replay['scored']} replayed "
                "artefact(s) are context only and are not the pipeline's output")
        services[service] = row

    made_total = sum(row["scored"] for row in services.values())
    made_passed = sum(row["passed"] for row in services.values())
    replay_total = sum(row["replay"]["scored"] for row in services.values())
    replay_passed = sum(row["replay"]["passed"] for row in services.values())
    made_scores = [value for name, split in buckets.items()
                   for value in split["generated"]["scores"]]
    replay_scores = [value for name, split in buckets.items()
                     for value in split["replay"]["scores"]]
    return {
        "services": services,
        "at": _now(),
        "pass": {
            "population": "generated",
            "scored": made_total,
            "passed": made_passed,
            "mean_score": round(sum(made_scores) / len(made_scores), 1) if made_scores else 0.0,
            "replay": {
                "scored": replay_total,
                "passed": replay_passed,
                "mean_score": (round(sum(replay_scores) / len(replay_scores), 1)
                               if replay_scores else 0.0),
            },
        },
        "ceiling": ceiling(briefs=briefs, generated_scored=made_total),
    }


def ceiling(*, briefs: Any = None, generated_scored: int = 0) -> Dict[str, Any]:
    """How much of the catalogue can be judged at all, and the ceiling that implies.

    A reference brief can only be produced honestly when its reference is on disk. An
    uploaded reference with no local copy cannot be cut out, and a prompt-only brief has
    no product to verify. Counting those as passes would invent evidence, so the ceiling
    is stated instead of assumed.
    """
    from seller_tester.reference_check import normalise_reference_path  # noqa: PLC0415

    rows = _brief_rows(briefs)
    resolvable: List[str] = []
    prompt_only = 0
    unresolved: Dict[str, int] = {}
    for brief in rows:
        mode = str(brief.get("source_mode") or "unclassified")
        if mode == "prompt_only":
            prompt_only += 1
            continue
        reference = brief.get("reference") or {}
        path = reference.get("path")
        resolved = None
        if isinstance(path, str) and path.strip():
            resolved, _reason = normalise_reference_path(path)
        if resolved is not None:
            resolvable.append(str(brief.get("id")))
        else:
            unresolved[mode] = unresolved.get(mode, 0) + 1
    total = len(rows)
    coverage = round(100.0 * len(resolvable) / total, 1) if total else 0.0
    return {
        "briefs": total,
        "reference_resolvable": len(resolvable),
        "resolvable_brief_ids": resolvable,
        "prompt_only": prompt_only,
        "unresolved_reference": sum(unresolved.values()),
        "unresolved_by_mode": unresolved,
        "generated_scored": int(generated_scored),
        "coverage_of_catalog_pct": coverage,
        "ceiling_generated_mean_if_all_scoreable_pass": 100.0,
        "catalog_mean_if_every_scoreable_brief_passes": coverage,
        "note": (
            "the published mean is over generated/composite outputs. Only "
            f"{len(resolvable)} of {total} briefs have a reference on disk that can be "
            "cut out and verified; the other "
            f"{total - len(resolvable)} cannot be produced honestly here ("
            f"{prompt_only} prompt-only, {sum(unresolved.values())} with no local "
            "reference copy). Counting those as zero would be a pipeline verdict on "
            "evidence that does not exist; counting them as passes would be invention."),
    }


def write(*, out: Optional[Path] = None) -> Dict[str, Any]:
    payload = build()
    target = Path(out or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(target), **payload}


def score_for(service_id: str, *, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The seller dimension for one service: the generated mean, or a named zero.

    A service with fewer than MIN_SCORED generated outputs is not scored: five lucky
    pictures are not a service that ships. Replayed rows never satisfy this sample.
    """
    payload = data if data is not None else (_read(OUT) or {})
    row = (payload.get("services") or {}).get(service_id)
    if not row:
        return {"score": 0.0,
                "evidence": "no Seller-Tester output scored for this service"}
    scored = int(row.get("scored") or 0)
    if scored < MIN_SCORED:
        replay = row.get("replay") or {}
        return {"score": 0.0,
                "evidence": (
                    f"only {scored} generated/composite output(s) scored for this service"
                    + (f"; {replay.get('scored')} replayed artefact(s) are context only"
                       if replay.get("scored") else ""))}
    evidence = (f"{scored} Seller-Tester outputs (generated/composite), "
                f"mean {row.get('mean')}, {row.get('passed')} passed")
    replay = row.get("replay") or {}
    if replay.get("scored"):
        evidence += (f"; {replay.get('scored')} replayed artefact(s) excluded as context "
                     f"(mean {replay.get('mean')})")
    return {"score": float(row.get("mean") or 0.0), "evidence": evidence}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Seller-Tester output scores")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--ceiling", action="store_true",
                        help="report how many briefs can be judged, and the ceiling")
    ns = parser.parse_args(argv)
    if ns.ceiling:
        print(json.dumps(ceiling(), indent=2))
        return 0
    result = write() if ns.write else build()
    print(json.dumps(result, indent=2, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
