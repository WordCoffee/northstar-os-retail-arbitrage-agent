"""Proof run for the folding-carton form (sel-06b).

Renders the Word Coffee gift box through the **app's own** path —
`product_picture.build` -> `brand_art` panels -> face measurement -> warp ->
OCR gate — and, optionally, asks the local vision model to judge the result.

The plate is the one thing this tool fakes: the FLUX 3 lane is unarmed on this
box (`studio_generation.engine_status()['armed']` is False), so a drawn,
chromatically distinct carton stands in for the photograph. Everything after the
plate is the shipped code, and the report says exactly that.

Usage:
    python tools/box_form_proof.py                    # render + report
    python tools/box_form_proof.py --judge            # also ask gemma3:4b
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "Northstar_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import brand_art as ba          # noqa: E402
import product_picture as pp    # noqa: E402


def synth_plate() -> Image.Image:
    """A drawn stand-in for the FLUX plate: a slim pale-pink carton on a sweep."""
    img = Image.new("RGB", (1024, 1536), (232, 230, 226))
    d = ImageDraw.Draw(img)
    box = (330, 300, 700, 1240)
    d.polygon([(box[0], box[1]), (box[2], box[1]),
               (box[2] + 10, box[3]), (box[0] - 10, box[3])],
              fill=(240, 196, 202))
    d.rectangle([box[0], box[1], box[2], box[1] + 18], fill=(228, 182, 190))
    return img


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generator(plate: Image.Image):
    payload = _png(plate)

    def inner(brief, *, width, height, tier, seed):
        return {"bytes": payload, "seed": seed, "model": "synthetic-plate",
                "width": plate.width, "height": plate.height,
                "used_brief": brief, "contains_text": False}
    return inner


RUBRIC = {
    "constraint": (
        "A product photograph of a slim pale-pink and cream gift box printed with "
        "the words WORD COFFEE, the words For Mom in large lilac script, and the "
        "line Empowering Moms, One Message at a Time, with a readable net weight."),
}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "renders" / "heldout_box_form"))
    ap.add_argument("--report", default=str(REPO / "reports" / "ty" / "sel06b_proof.json"))
    ap.add_argument("--judge", action="store_true", help="ask the local vision model")
    args = ap.parse_args(argv)

    out = Path(args.out)
    design = ba.design_for("word-coffee")
    panel_dir = out / "panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    for face, fn in (("front", ba.front_panel), ("back", ba.back_panel)):
        fn(design).save(panel_dir / f"panel_{face}.png")

    result = pp.build(design, out_dir=str(out / "picture"), out_root=str(out),
                      faces=("front", "back"), generator=generator(synth_plate()))

    report = {
        "job": "sel-06b-second-brand",
        "design": ba.manifest(design),
        "plate": {"source": "synthetic (FLUX 3 lane unarmed: MEDIA_GEN_LIVE is not 1)",
                  "file": str(out / "panels" / "plate.png")},
        "build_ok": result["ok"],
        "form": result["product"]["form"],
        "faces": [{
            "face": r.get("face"),
            "stage": r.get("stage"),
            "gate_ok": r.get("gate_ok"),
            "reason": r.get("reason"),
            "brief": r.get("brief"),
            "quad": r.get("quad"),
            "words": (r.get("legibility") or {}).get("words"),
            "file": r.get("file"),
            "bytes": r.get("bytes"),
        } for r in result["faces"]],
    }
    synth_plate().save(out / "panels" / "plate.png")

    if args.judge:
        sys.path.insert(0, str(REPO))
        from tools.seller_tester.judge import local_judge

        report["judge"] = {}
        for face in ("front", "back"):
            path = out / "picture" / f"product_{face}.png"
            if not path.is_file():
                report["judge"][face] = {"available": False, "reason": "no artefact"}
                continue
            report["judge"][face] = local_judge(path.read_bytes(), RUBRIC)
        for face in ("front", "back"):
            report["judge"][f"panel_{face}"] = local_judge(
                (panel_dir / f"panel_{face}.png").read_bytes(), RUBRIC)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": report["build_ok"],
        "form": report["form"],
        "faces": [{"face": f["face"], "gate": f["gate_ok"], "reason": f["reason"],
                   "file": f["file"]} for f in report["faces"]],
        "judge": {k: {"pass": v.get("pass"), "score": v.get("score"),
                      "model": v.get("model")} for k, v in (report.get("judge") or {}).items()},
        "report": str(report_path),
    }, indent=2))
    return 0 if report["build_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
