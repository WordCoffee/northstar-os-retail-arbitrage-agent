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
#: The pass that renders through the app's own `product_picture.build` (D-011).
PRODUCT = ROOT / "state" / "seller" / "product_proof.json"
PRODUCT_JUDGED = ROOT / "state" / "seller" / "product_proof_judged.json"
#: The app-path pass over the full seller catalog (`ty/seller_briefs.json`).
PRODUCT_CATALOG = ROOT / "state" / "seller" / "product_catalog.json"
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


def _sources(summary: Any = None, composite: Any = None,
             product: Any = None) -> List[Tuple[Dict[str, Any], str]]:
    """The passes to aggregate: an injected summary, or the passes on disk.

    The **app-path pass wins** when it exists: it is the only one whose pictures
    came out of `product_picture.build`. The harness composite pass is then left
    out entirely, because two generated means over the same briefs are not two
    populations — they are two pipelines, and blending them hides which one a
    seller would receive. Without an app pass the old behaviour stands: the replay
    summary plus the composite proof.
    """
    app_pass = product if isinstance(product, dict) and product.get("results") else None
    if app_pass is None and product is None and summary is None:
        app_pass = _app_pass()
    if app_pass is not None:
        out: List[Tuple[Dict[str, Any], str]] = [
            (app_pass, str(app_pass.get("generator") or "product_pipeline"))]
        replay_rows = summary if isinstance(summary, dict) else _read(SUMMARY)
        if isinstance(replay_rows, dict) and replay_rows is not app_pass:
            out.append((replay_rows, str(replay_rows.get("generator") or "")))
        return out
    if summary is not None:
        out = [(summary, str(summary.get("generator") or ""))] if isinstance(summary, dict) else []
        if isinstance(composite, dict):
            out.append((composite, str(composite.get("generator") or "composite")))
        return out
    out = []
    primary = composite if isinstance(composite, dict) else _read(COMPOSITE)
    if isinstance(primary, dict):
        out.append((primary, str(primary.get("generator") or "")))
    replay = _read(SUMMARY)
    if isinstance(replay, dict) and replay is not primary:
        out.append((replay, str(replay.get("generator") or "")))
    return out


def _app_pass() -> Optional[Dict[str, Any]]:
    """Every app-path pass on disk, merged by brief: the seller sample is all of it.

    The judged held-out pass wins for a brief it covers (it is the stricter one),
    then the mechanical held-out pass, then the catalog pass. A brief appears once.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    sources: List[str] = []
    judged = False
    plates: set = set()
    at = ""
    for path in (PRODUCT_JUDGED, PRODUCT, PRODUCT_CATALOG):
        data = _read(path)
        if not isinstance(data, dict) or not data.get("results"):
            continue
        sources.append(path.name)
        judged = judged or bool(data.get("judge_enabled"))
        if data.get("plate_source"):
            plates.add(str(data["plate_source"]))
        at = at or str(data.get("generated_at") or "")
        for row in data["results"]:
            brief_id = str(row.get("brief_id") or "")
            if brief_id and brief_id not in merged:
                merged[brief_id] = row
    if not merged:
        return None
    return {
        "generator": "product_pipeline",
        "pipeline": "app",
        "generated_at": at,
        "judge_enabled": judged,
        "plate_source": "+".join(sorted(plates)) or None,
        "sources": sources,
        "results": list(merged.values()),
    }


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
          briefs: Any = None,
          product: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aggregate passes into a published generated mean plus replay context.

    `product` is the app-path pass (`python -m tools.seller_tester product`); when it
    exists it is the published population. `summary` is the replay pass, kept as
    context. `composite` is the old harness pipeline and is used only when there is
    no app-path pass at all.
    """
    sources = _sources(summary, composite, product)
    if not sources:
        return {"services": {}, "reason": "no seller-tester pass on disk", "at": _now()}
    mapping = brief_services(briefs)
    buckets: Dict[str, Dict[str, Dict[str, Any]]] = {}
    generated_at = ""
    made_at = ""
    for data, generator in sources:
        generated_at = generated_at or str(data.get("generated_at") or "")
        for row in _rows(data):
            service = mapping.get(str(row.get("brief_id") or ""), "design-studio")
            try:
                value = float(row.get("score"))
            except (TypeError, ValueError):
                continue
            population = population_of(row, generator)
            if population == "generated":
                # The published mean's timestamp is the pass that produced the pictures,
                # not the replay pass that happens to be read first.
                made_at = made_at or str(data.get("generated_at") or "")
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
            "at": made_at or generated_at or _now(),
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
        "pipeline": _pipeline_block(product, injected=summary is not None),
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


def _pipeline_block(product: Optional[Dict[str, Any]] = None, *,
                    injected: bool = False) -> Dict[str, Any]:
    """Which pipeline the published mean describes, stated instead of assumed."""
    if product is not None:
        app_pass = product if product.get("results") else None
    elif injected:
        app_pass = None
    else:
        app_pass = _app_pass()
    if app_pass:
        return {
            "rendered_by": ("tools/seller_tester ProductPipelineGenerator -> "
                            "product_picture.build"),
            "product_renders_with": ("Northstar_backend/product_picture.py::build "
                                     "(brand_art + mockup_compositor + "
                                     "mockup_quality.assert_legible)"),
            "same_pipeline": True,
            "plate_source": app_pass.get("plate_source"),
            "judged": bool(app_pass.get("judge_enabled")),
            "at": app_pass.get("generated_at"),
            "why_it_matters": (
                "sel-06 (2026-11-11): the pass renders through the same "
                "product_picture.build the API calls, so the number describes the "
                "product. The plate is named above: when it is 'drawn' the picture's "
                "photograph is a stand-in and only the artwork, warp and gate are real."),
        }
    return {
        "rendered_by": "tools/seller_tester (CompositeGenerator: product_composite.place_product "
                       "+ label_warp)",
        "product_renders_with": "Northstar_backend/product_picture.py::build "
                                "(brand_art + mockup_compositor)",
        "same_pipeline": False,
        "why_it_matters": (
            "No app-path pass is on disk. These scores measure the harness pipeline, not "
            "the one the app sells; run `python -m tools.seller_tester product` first."),
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
