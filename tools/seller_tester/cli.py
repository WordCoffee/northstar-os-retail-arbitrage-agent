"""Seller-Tester CLI.

    python -m tools.seller_tester catalog
    python -m tools.seller_tester run --limit 30 [--judge] [--summary-out PATH]
    python -m tools.seller_tester escalate --brief ST-001 --steps 5

`run` uses the stored generator by default (offline replay). `--comfy` probes
the local ComfyUI adapter instead and refuses cleanly when it is not reachable.
`--judge` opts into the local vision model; without it, scoring is pure code.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .briefs import (
    DEFAULT_CATALOG_PATH,
    SITUATIONS,
    SOURCE_MODES,
    load_catalog,
    mode_counts,
    validate_catalog,
)
from .escalate import escalate
from .generators import (CompositeGenerator, ComfyGenerator, GeneratorUnavailable,
                         StoredGenerator)
from .harness import run_pass
from .judge import local_judge

DEFAULT_SUMMARY_PATH = Path(__file__).resolve().parents[2] / "state" / "seller" / "last_run.json"
DEFAULT_COMPOSITE_CATALOG = Path(__file__).resolve().parent / "mogra_briefs.json"


def _cmd_catalog(args: argparse.Namespace) -> int:
    payload = load_catalog(args.catalog)
    errors = validate_catalog(payload)
    briefs = payload.get("briefs", [])
    print(json.dumps({
        "path": str(args.catalog or DEFAULT_CATALOG_PATH),
        "briefs": len(briefs),
        "source_modes": mode_counts(payload),
        "situations": sorted({b.get("situation") for b in briefs}),
        "categories": sorted({b.get("category") for b in briefs}),
        "tiers": sorted({b.get("difficulty") for b in briefs}),
        "errors": errors,
        "valid": not errors,
    }, indent=2))
    return 0 if not errors else 1


def _cmd_run(args: argparse.Namespace) -> int:
    payload = load_catalog(args.catalog)
    errors = validate_catalog(payload)
    if errors:
        print("catalog invalid:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    if args.comfy:
        generator = ComfyGenerator()
        ok, detail = generator.available()
        if not ok:
            print(f"refused: {detail}", file=sys.stderr)
            return 2
    else:
        generator = StoredGenerator()
    judge = local_judge if args.judge else None
    summary = run_pass(generator=generator, briefs=payload.get("briefs", []),
                       limit=args.limit, mode=args.mode, judge=judge)
    out = Path(args.summary_out) if args.summary_out else DEFAULT_SUMMARY_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    head = {k: summary[k] for k in (
        "generated_at", "generator", "judge_enabled", "mode_filter", "selected",
        "scored", "not_scored", "passed", "failed", "pass_rate", "mean_score",
        "gaps_filed", "gaps_in_file", "gaps_path", "mirror_path")}
    head["escalations"] = len(summary["escalations"])
    head["catalog_by_mode"] = summary["catalog_by_mode"]
    head["by_mode"] = {
        name: {"scored": row["scored"], "passed": row["passed"],
               "mean_score": row["mean_score"]}
        for name, row in summary["by_mode"].items()
    }
    print(json.dumps(head, indent=2))
    print(f"summary: {out}")
    return 0


def _cmd_escalate(args: argparse.Namespace) -> int:
    payload = load_catalog(args.catalog)
    briefs = payload.get("briefs", [])
    brief = next((row for row in briefs if row.get("id") == args.brief), None)
    if brief is None:
        print(f"no brief {args.brief!r}", file=sys.stderr)
        return 1
    catalog = payload.get("briefs", [])
    used = {row.get("category") for row in briefs}
    for step in range(max(1, args.steps)):
        mode = brief.get("source_mode")
        outcome = escalate(brief, catalog, used_categories=used,
                           source_mode=mode if mode in SOURCE_MODES else None)
        print(f"{step + 1}. {outcome['action']}: {outcome['detail']} "
              f"(id={outcome['brief'].get('id')}, tier={outcome['brief'].get('difficulty')}, "
              f"mode={outcome['brief'].get('source_mode')})")
        brief = outcome["brief"]
        used.add(str(brief.get("category")))
    return 0


def _cmd_composite(args: argparse.Namespace) -> int:
    """The composite path end to end: real cutout, generated scene, measured verdict."""
    catalog_path = Path(args.catalog or DEFAULT_COMPOSITE_CATALOG)
    payload = load_catalog(catalog_path)
    errors = validate_catalog(payload, require_coverage=False)
    if errors:
        print("catalog invalid:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    from .scene_render import ComfySceneRenderer, lane_ready

    if args.renderer == "comfy":
        ok, detail = lane_ready()
        if not ok:
            print(f"refused: {detail}", file=sys.stderr)
            return 2
        renderer = ComfySceneRenderer(width=args.scene_size, height=args.scene_size,
                                      steps=args.steps, model=args.model)
    else:
        from .scene_render import renderer_from_name

        renderer = renderer_from_name("synthetic")
    generator = CompositeGenerator(renderer=renderer, method=args.method,
                                   out_dir=args.out_dir, repo_root=Path(args.root),
                                   layout=getattr(args, "layout", "deterministic"))
    summary = run_pass(generator=generator, briefs=payload.get("briefs", []),
                       limit=args.limit, judge=None,
                       gaps_path=Path(args.gaps) if args.gaps else None,
                       mirror_path=Path(args.gaps) if args.gaps else None,
                       escalation_path=None)

    from .reference_check import cosine, embed

    for row in summary["results"]:
        check = row.get("reference_check") or {}
        text = check.get("text") or {}
        similarity = None
        if text.get("produced_text") and text.get("reference_text"):
            similarity = cosine(embed(text["produced_text"]),
                                embed(text["reference_text"]))
        row["text_embedding_similarity"] = (
            None if similarity is None else round(float(similarity), 4))
    out = Path(args.summary_out) if args.summary_out else DEFAULT_SUMMARY_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in summary["results"]:
        check = row.get("reference_check") or {}
        print(json.dumps({
            "brief": row.get("brief_id"), "route": row.get("route"),
            "fidelity": row.get("fidelity"), "passed": row.get("passed"),
            "cannot_verify": row.get("cannot_verify"),
            "score": row.get("score"), "artefact": row.get("artefact_path"),
            "decided_by": check.get("decided_by"),
            "recall": (check.get("text") or {}).get("recall"),
            "matched": (check.get("text") or {}).get("matched"),
            "embedding": (check.get("meaning") or {}).get("similarity"),
            "text_embedding_similarity": row.get("text_embedding_similarity"),
            "colour_gate": (check.get("diagnostic") or {}).get("colour_gate"),
            "scene_source": ((row.get("generation") or {}).get("scene") or {}).get("source"),
            "failure": (check.get("detail") if not check.get("ok") else None),
            "cannot_verify_reason": row.get("cannot_verify_reason"),
        }, ensure_ascii=False))
    print(f"summary: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.seller_tester",
                                     description="Seller-Tester harness (D9)")
    parser.add_argument("--catalog", default=None, help=f"catalog path (default {DEFAULT_CATALOG_PATH})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog", help="validate the brief catalog")

    run = sub.add_parser("run", help="run one pass with the stored generator")
    run.add_argument("--limit", type=int, default=20)
    run.add_argument("--mode", default=None, choices=list(SOURCE_MODES),
                     help="restrict the pass to one input mode (default: all three)")
    run.add_argument("--judge", action="store_true",
                     help="enable the LOCAL vision judge (off by default)")
    run.add_argument("--comfy", action="store_true",
                     help="use the local ComfyUI adapter instead of stored replay")
    run.add_argument("--summary-out", default=None)

    esc = sub.add_parser("escalate", help="show the escalation ladder for one brief")
    esc.add_argument("--brief", required=True)
    esc.add_argument("--steps", type=int, default=5)

    comp = sub.add_parser(
        "composite",
        help="run the composite path: real cutout, generated scene, measured check")
    comp.add_argument("--catalog", default=None,
                      help=f"default {DEFAULT_COMPOSITE_CATALOG}")
    comp.add_argument("--limit", type=int, default=3)
    comp.add_argument("--renderer", default="comfy", choices=["comfy", "synthetic"],
                      help="comfy starts its own lane; synthetic is the offline fallback")
    comp.add_argument("--method", default="birefnet",
                      help="cutout method (birefnet, grabcut, background_distance, otsu_lab)")
    comp.add_argument("--layout", default="deterministic", choices=["deterministic", "scene"],
                      help=("deterministic lays out infographics and packaging panels with "
                            "measured geometry; scene leaves those two situations to the model"))
    comp.add_argument("--scene-size", type=int, default=768,
                      help="scene render size in px (768 is what renders under the shared VRAM)")
    comp.add_argument("--steps", type=int, default=20)
    comp.add_argument("--model", default="sdxl", choices=["sdxl", "flux3"],
                      help="scene model: sdxl (classic checkpoint) or flux3")
    comp.add_argument("--out-dir", default=None)
    comp.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    comp.add_argument("--summary-out", default=str(
        Path(__file__).resolve().parents[2] / "state" / "seller" / "composite_proof.json"))
    comp.add_argument("--gaps", default=str(
        Path(__file__).resolve().parents[2] / "state" / "seller" / "composite_gaps.json"),
        help="gap file for this run (kept out of the shared ty/seller_gaps.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            return _cmd_catalog(args)
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "composite":
            return _cmd_composite(args)
        return _cmd_escalate(args)
    except GeneratorUnavailable as exc:
        print(f"generator unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
