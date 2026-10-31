#!/usr/bin/env python3
"""Live four-format FLUX run with measured surfaces.

For each format (pouch, box, bottle, tube) this script:
  1. renders a real blank plate on the local FLUX 3 gateway (ComfyUI :8188),
  2. gates it for burned-in text,
  3. MEASURES the printable surface from the plate (surface_measure),
  4. composites the deterministic label onto that measured quad,
  5. cuts out, builds the white hero, scores it, and writes the flow report.

It never falls back to a nominal quad: a plate whose surface cannot be measured
is blocked and reported. Renders are sequential and a hard render failure stops
the run (circuit breaker, no retry).

Usage:
    python tools/run_flow_formats.py                 # live, all four
    python tools/run_flow_formats.py --formats box tube
    python tools/run_flow_formats.py --dry-run       # synthetic plates, no GPU
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

os.environ.setdefault("MEDIA_GEN_LIVE", "1")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import creative_flow  # noqa: E402
import pouch_label  # noqa: E402
import surface_measure  # noqa: E402

FORMATS = ("pouch", "box", "bottle", "tube")
SEEDS = {"pouch": 4242, "box": 4243, "bottle": 4244, "tube": 4245}
COPY = {"title": "LION'S MANE", "subtitle": "Organic Mushroom Powder",
        "weight": "6 oz (170 g)",
        "bullets": ["Fruiting body only", "Third-party tested", "60 servings"]}
DIMS = {
    "pouch": {"width": 100.0, "height": 200.0},
    "box": {"width": 80.0, "depth": 40.0, "height": 180.0},
    "bottle": {"diameter": 60.0, "height": 200.0, "label_height": 80.0,
               "label_top_offset": 30.0},
    "tube": {"diameter": 40.0, "height": 160.0},
}
PROMPTS = {
    "pouch": ("A pristine blank unprinted kraft stand-up pouch, plain uniform matte "
              "kraft stock, standing upright, no label, no printing, no text, no logo, "
              "no graphics, soft diffused studio lighting, seamless neutral light-grey "
              "background, photorealistic product shot"),
    "box": ("A pristine blank unprinted kraft folding carton box, straight tuck box, "
            "standing upright, plain uniform matte kraft board, no label, no printing, "
            "no text, no logo, no graphics, soft diffused studio lighting, seamless "
            "neutral light-grey background, photorealistic product shot"),
    "bottle": ("A pristine blank unprinted matte amber glass supplement bottle with a "
               "plain white cap, standing upright, no label, no printing, no text, no "
               "logo, no graphics, soft diffused studio lighting, seamless neutral "
               "light-grey background, photorealistic product shot"),
    "tube": ("A pristine blank unprinted matte kraft cosmetic tube with a flat crimped "
             "top, standing upright, no label, no printing, no text, no logo, no "
             "graphics, soft diffused studio lighting, seamless neutral light-grey "
             "background, photorealistic product shot"),
}


def _png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _synthetic(kind: str, w: int = 768, h: int = 960) -> bytes:
    """A deterministic stand-in plate for --dry-run (never used live)."""
    bg, body, side = (208, 208, 208), (176, 146, 116), (140, 116, 92)
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    sx, sy = w / 512.0, h / 640.0
    def P(x, y):
        return (x * sx, y * sy)
    if kind == "pouch":
        d.polygon([P(120, 60), P(300, 60), P(310, 460), P(110, 460)], fill=body)
    elif kind == "box":
        d.rectangle([P(120, 120), P(320, 520)], fill=body)
        d.polygon([P(320, 140), P(430, 190), P(430, 500), P(320, 520)], fill=side)
    elif kind == "bottle":
        d.rectangle([P(230, 80), P(282, 140)], fill=body)
        d.polygon([P(230, 140), P(200, 190), P(200, 540), P(312, 540),
                   P(312, 190), P(282, 140)], fill=body)
    elif kind == "tube":
        d.rectangle([P(210, 70), P(302, 90)], fill=body)
        d.polygon([P(220, 90), P(292, 90), P(300, 520), P(212, 520)], fill=body)
        d.rectangle([P(210, 520), P(302, 540)], fill=body)
    return _png(img)


def _paint_metrics(plate_png: bytes, labelled_png: bytes, quad) -> Dict[str, Any]:
    """How much of the composite changed inside vs outside the measured quad."""
    a = np.asarray(Image.open(BytesIO(plate_png)).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(BytesIO(labelled_png)).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return {"error": f"size mismatch {a.shape} vs {b.shape}"}
    diff = np.abs(a - b).max(axis=2) > 12
    mask = Image.new("L", (b.shape[1], b.shape[0]), 0)
    ImageDraw.Draw(mask).polygon([(float(x), float(y)) for x, y in quad], fill=255)
    inside = np.asarray(mask) > 127
    changed = int(diff.sum())
    inside_px = int((diff & inside).sum())
    outside_px = int((diff & ~inside).sum())
    return {"changed_px": changed, "inside_quad_px": inside_px,
            "outside_quad_px": outside_px,
            "inside_share": round(inside_px / changed, 4) if changed else None}


def _ocr(png: bytes) -> Dict[str, Any]:
    try:
        import text_fidelity
        return text_fidelity.verify_asset_text(
            png, brief=f"{COPY['title']} {COPY['subtitle']}", text_safe=True)
    except Exception as exc:  # noqa: BLE001 - OCR is evidence, not a gate here
        return {"verdict": "unavailable", "error": str(exc)[:200]}


def _summary(state: Dict[str, Any]) -> Dict[str, Any]:
    steps = state.get("steps", {}) or {}
    keep = {}
    for name in ("bind", "snapshot", "plate", "gate", "compose", "hero",
                 "aplus", "evaluate", "memory"):
        step = steps.get(name)
        if not isinstance(step, dict):
            keep[name] = step
            continue
        if name == "compose":
            keep[name] = {k: step.get(k) for k in
                          ("status", "residual_px", "bytes", "error")}
            keep[name]["surface"] = step.get("surface")
        elif name == "bind":
            keep[name] = {"geometry": step.get("geometry"),
                          "tier": step.get("tier"), "margin": step.get("margin")}
        elif name == "plate":
            keep[name] = {k: step.get(k) for k in
                          ("bytes", "allowed", "guard", "vram_ratio", "temp_c")}
        elif name == "evaluate":
            keep[name] = {k: step.get(k) for k in
                          ("score", "grade", "defects", "legibility", "fill",
                           "contrast", "balance", "background")}
        else:
            keep[name] = step
    return {"status": state.get("status"), "blocked": state.get("blocked"),
            "steps": keep}


def run_format(kind: str, out_root: Path, *, dry_run: bool, width: int,
               height: int) -> Dict[str, Any]:
    import studio_generation as sg

    out_dir = out_root / kind
    prompt = PROMPTS[kind]
    job = creative_flow.CreativeJob(
        job_id=f"formats-{kind}",
        product={"id": f"lions-mane-6oz-{kind}", "target_price": 34.0,
                 "unit_cost": 11.5,
                 "brand": {"colors": ["#1d4a1d"], "fonts": {"heading": "Playfair Display"}}},
        pricing={"target_price": 34.0, "unit_cost": 11.5},
        keywords=["lion's mane powder", "fruiting body mushroom"],
        copy=COPY, geometry=kind, geometry_dims=DIMS[kind],
        out_dir=str(out_dir),
    )
    seed = SEEDS[kind]
    if dry_run:
        render = lambda p, w, h: _synthetic(kind, width, height)
        cutout = lambda b: b
    else:
        render = lambda p, w, h: sg.generate_image(
            p, width, height, tier="draft", seed=seed)["bytes"]
        cutout = lambda b: sg.generate_cutout(b)["bytes"]
    flow = creative_flow.CreativeFlow(
        job, root=ROOT,
        render=render,
        cutout=cutout,
        compose=lambda path, **kw: pouch_label.compose(path, **kw),
        prompt_author=lambda _brief: prompt,
        # The live run must never revert the code under test or the operator's
        # pre-existing edits. The flow still records a snapshot; rollback stays
        # available to the production path.
        auto_revert=False,
    )
    started = time.time()
    error = None
    try:
        state = flow.run()
    except Exception as exc:  # noqa: BLE001 - a hard render failure stops the run
        state = flow.state.to_dict()
        state["status"] = "failed"
        error = f"{type(exc).__name__}: {exc}"[:400]
    elapsed = round(time.time() - started, 1)

    plate_path = out_dir / "01_plate.png"
    labelled_path = out_dir / "02_labelled.png"
    hero_path = out_dir / "03_hero.png"
    record: Dict[str, Any] = {
        "kind": kind, "seed": seed, "prompt": prompt, "duration_s": elapsed,
        "error": error, "summary": _summary(state),
        "artefacts": {
            "plate": str(plate_path) if plate_path.exists() else None,
            "labelled": str(labelled_path) if labelled_path.exists() else None,
            "hero": str(hero_path) if hero_path.exists() else None,
            "report": (state.get("steps", {}).get("report") or {}).get("path"),
        },
    }
    compose = (state.get("steps", {}) or {}).get("compose") or {}
    surface = compose.get("surface") or {}
    if plate_path.exists() and labelled_path.exists() and surface.get("quad"):
        record["paint"] = _paint_metrics(plate_path.read_bytes(),
                                         labelled_path.read_bytes(),
                                         surface["quad"])
    if labelled_path.exists():
        record["ocr"] = _ocr(labelled_path.read_bytes())
    return record


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--formats", nargs="+", default=list(FORMATS), choices=FORMATS)
    ap.add_argument("--dry-run", action="store_true",
                    help="use synthetic plates; no render, no GPU")
    ap.add_argument("--size", type=int, nargs=2, default=[1024, 1024],
                    metavar=("W", "H"))
    ap.add_argument("--out", default="", help="output directory")
    args = ap.parse_args(argv)

    stamp = time.strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(args.out) if args.out else ROOT / "exports" / f"flow_formats_{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": bool(args.dry_run), "formats": {}, "status": "unknown",
    }
    if not args.dry_run:
        import studio_generation as sg
        report["engine"] = sg.engine_status()
        if not sg.media_live_armed():
            report["status"] = "disarmed"
            print(json.dumps(report, indent=2)[:2000])
            return 2

    failed = []
    for kind in args.formats:
        print(f"[formats] {kind} ...", flush=True)
        try:
            rec = run_format(kind, out_root, dry_run=bool(args.dry_run),
                             width=int(args.size[0]), height=int(args.size[1]))
        except Exception as exc:  # noqa: BLE001 - circuit breaker, no retry
            rec = {"kind": kind, "error": f"{type(exc).__name__}: {exc}"[:400],
                   "summary": {"status": "failed"}}
        report["formats"][kind] = rec
        status = (rec.get("summary") or {}).get("status")
        print(f"[formats] {kind}: {status} ({rec.get('duration_s')}s) "
              f"error={rec.get('error')}", flush=True)
        if status not in ("ok",):
            failed.append(kind)
            if rec.get("error"):
                break  # hard failure: stop the sequence, never auto-retry
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    report["status"] = "ok" if not failed else ("partial" if len(failed) < len(args.formats)
                                                else "failed")
    (out_root / "run_report.json").write_text(json.dumps(report, indent=2),
                                              encoding="utf-8")
    print(json.dumps({"status": report["status"], "out": str(out_root),
                      "formats": {k: (v.get("summary") or {}).get("status")
                                  for k, v in report["formats"].items()}},
                     indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
