"""Re-render one input mode's held-out briefs, seed-pinned to the previous proof.

Why this exists: on 2026-11-11 `generators.flat()` was corrected (it returned `mode != "uniform"`,
so a white-matte brief was handed the generated scene instead of a flat canvas). That is a
*generation* change, not a scoring change, so the artefacts produced before it are stale: six
prompt-only briefs scored exactly 90.0 because they failed `alpha_matte` on the scene's edge grain.

A before/after comparison is only honest if the picture changed for the stated reason. Every render
seed is therefore read back out of the previous proof and reused, so the single variable between the
two runs is the branch that was fixed. If a seed is missing the brief is rendered with a random one
and the row says so.

    python tools/rerender_prompt_only.py --dry-run
    python tools/rerender_prompt_only.py --mode prompt_only \
        --out-dir renders/heldout_prompt_only5 \
        --summary-out state/seller/heldout_prompt_only_proof5.json

The lane discipline is the repo's: one fresh ComfyUI instance per render, stopped after (folded fix
3 of the 2026-11-08 order), the GPU lock taken by `render_scene`, RAM floor enforced there too.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from seller_tester.briefs import load_catalog  # noqa: E402
from seller_tester.generators import CompositeGenerator  # noqa: E402
from seller_tester.harness import run_pass  # noqa: E402

DEFAULT_PREVIOUS = ROOT / "state" / "seller" / "heldout_prompt_only_proof4.json"
DEFAULT_CATALOG = ROOT / "ty" / "seller_briefs_heldout_modes.json"


def seeds_from(proof: Path) -> Dict[str, Dict[str, Any]]:
    """Per-brief render seed and the model/steps/size it was rendered with."""
    out: Dict[str, Dict[str, Any]] = {}
    if not proof.is_file():
        return out
    payload = json.loads(proof.read_text(encoding="utf-8"))
    for row in payload.get("results") or []:
        scene = ((row.get("generation") or {}).get("scene") or {})
        if scene.get("seed") is None:
            continue
        out[str(row.get("brief_id"))] = {
            "seed": int(scene["seed"]),
            "model": scene.get("model"),
            "steps": scene.get("steps"),
            "width": scene.get("width"),
            "height": scene.get("height"),
        }
    return out


class SeedPinnedComposite(CompositeGenerator):
    """A composite generator that pins each brief to a previously recorded render seed."""

    def __init__(self, *, seeds: Dict[str, Dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.seeds = seeds
        self.pinned: Dict[str, bool] = {}

    def generate(self, brief: Dict[str, Any]) -> Path:
        row = self.seeds.get(str(brief.get("id"))) or {}
        seed = row.get("seed")
        if seed is not None and hasattr(self.renderer, "seed"):
            self.renderer.seed = int(seed)
            self.pinned[str(brief.get("id"))] = True
        else:
            self.renderer.seed = None
            self.pinned[str(brief.get("id"))] = False
        return super().generate(brief)


def _briefs_for(catalog: Dict[str, Any], mode: str) -> List[Dict[str, Any]]:
    return [b for b in (catalog.get("briefs") or [])
            if str(b.get("source_mode") or "") == mode]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Re-render one held-out input mode")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--previous", default=str(DEFAULT_PREVIOUS),
                        help="proof whose render seeds are reused")
    parser.add_argument("--mode", default="prompt_only")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--out-dir", default=str(ROOT / "renders" / "heldout_prompt_only5"))
    parser.add_argument("--summary-out",
                        default=str(ROOT / "state" / "seller" / "heldout_prompt_only_proof5.json"))
    parser.add_argument("--gaps", default=str(ROOT / "state" / "seller"
                                              / "heldout_prompt_only_gaps5.json"))
    parser.add_argument("--scene-size", type=int, default=768)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--model", default="sdxl", choices=["sdxl", "flux3"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    catalog = load_catalog(Path(args.catalog))
    briefs = _briefs_for(catalog, args.mode)[: args.limit]
    seeds = seeds_from(Path(args.previous))

    plan = []
    for brief in briefs:
        row = seeds.get(str(brief["id"])) or {}
        plan.append({"brief": brief["id"], "situation": brief.get("situation"),
                     "seed": row.get("seed"), "pinned": row.get("seed") is not None})
    if args.dry_run:
        pinned = sum(1 for row in plan if row["pinned"])
        print(json.dumps({"mode": args.mode, "briefs": len(plan), "seed_pinned": pinned,
                          "plan": plan}, indent=2))
        return 0

    from seller_tester.scene_render import ComfySceneRenderer, lane_ready

    ok, detail = lane_ready()
    if not ok:
        print(f"refused: {detail}", file=sys.stderr)
        return 2

    renderer = ComfySceneRenderer(width=args.scene_size, height=args.scene_size,
                                  steps=args.steps, model=args.model)
    generator = SeedPinnedComposite(seeds=seeds, renderer=renderer, out_dir=args.out_dir,
                                    repo_root=ROOT, layout="deterministic")

    summary = run_pass(generator=generator, briefs={"briefs": briefs}, limit=len(briefs),
                       mode=args.mode, judge=None,
                       gaps_path=Path(args.gaps), mirror_path=None,
                       escalation_path=None)
    summary["rerender"] = {
        "mode": args.mode,
        "previous_proof": str(Path(args.previous)),
        "seeds_reused": sum(1 for v in generator.pinned.values() if v),
        "seeds_random": sum(1 for v in generator.pinned.values() if not v),
        "scene_size": args.scene_size,
        "steps": args.steps,
        "model": args.model,
        "why": ("the render seeds come from the previous proof, so the picture changes only "
                "because the pipeline changed. The first run of this tool isolated the flat() "
                "branch and moved one brief (PO-005, 70.0 -> 90.0). The six rows that then sat "
                "at exactly 90.0 were not the branch: their border failed on a contact shadow "
                "clipped by the frame edge (bottom band luminance 243.5, std 7.19). "
                "place_product now reserves the shadow inside the frame margin."),
    }
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for row in summary["results"]:
        print(json.dumps({
            "brief": row.get("brief_id"), "route": row.get("route"),
            "score": row.get("score"), "passed": row.get("passed"),
            "artefact": row.get("artefact_path"),
            "seed": (((row.get("generation") or {}).get("scene") or {}).get("seed")),
            "failed": row.get("failed_checks") or [],
        }, ensure_ascii=False))
    print(f"summary: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
