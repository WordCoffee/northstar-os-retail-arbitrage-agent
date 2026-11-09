"""OCR benchmark: which engine reads our packaging best?

The reference check decides fidelity by printed text, so the OCR engine is a model choice like
any other and gets measured the same way: a fixed eval set, a stated metric, a leaderboard and a
licence per candidate. Nothing here is installed at run time and nothing leaves the machine.

Eval set (rebuilt 2026-11-08): **hard crops of the three real Mogra Organics references**, not
whole frames. The earlier set was three full frames plus a synthetic card and rapidocr scored
1.000 on it, so it could not separate engines at all. These crops are the label regions a seller
actually cares about — brand lockup, product name, weight panel — cut from the real uploads at
their native size (16-42 px cap height), saved as JPEG q72 so real compression is in the
picture, and carrying real pouch curvature. Ground truth per crop is the text that crop is
known to contain, taken from the frame and the manifest; it is written into the leaderboard.

Scoring is token recall with the same fuzzy matcher the reference check uses — an engine is not
"better" because it returns more boxes.

    python tools/ocr_bench.py --run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "renders" / "references" / "mogra"
CROPS = ROOT / "state" / "ocr" / "crops"
OUT = ROOT / "ty" / "ocr_leaderboard.json"
ROLES = ROOT / "ty" / "model_roles.json"

sys.path.insert(0, str(ROOT / "tools"))
from seller_tester.reference_check import text_match  # noqa: E402

#: Licence for each candidate, recorded here because the benchmark is where the choice is made.
CANDIDATES: Dict[str, Dict[str, Any]] = {
    "rapidocr": {"engine": "rapidocr_onnxruntime", "licence": "Apache-2.0",
                 "source": "https://github.com/RapidAI/RapidOCR", "device": "cpu/onnx"},
    "rapidocr-2x": {"engine": "rapidocr_onnxruntime", "licence": "Apache-2.0",
                    "source": "https://github.com/RapidAI/RapidOCR", "device": "cpu/onnx",
                    "note": "same engine, crops upscaled 2x before recognition"},
    "easyocr": {"engine": "easyocr", "licence": "Apache-2.0",
                "source": "https://github.com/JaidedAI/EasyOCR", "device": "torch"},
}

#: The eval set. `box` is [left, top, right, bottom] in the source frame's pixels.
#: `expected` is only the text that crop is known to contain — a crop is not credited for
#: text that sits outside it, and the fuzzy matcher drops very short runs and bare numbers.
CROPS_SPEC: List[Dict[str, Any]] = [
    {"id": "main_brand_left", "file": "mogra_pair_main.png",
     "box": [415, 825, 645, 922], "text_px": 23,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup + subtitle on the green pouch, small caps"},
    {"id": "main_brand_right", "file": "mogra_pair_main.png",
     "box": [1340, 845, 1585, 942], "text_px": 24,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup + subtitle on the black pouch"},
    {"id": "main_name_left", "file": "mogra_pair_main.png",
     "box": [200, 1068, 880, 1132], "text_px": 43,
     "expected": "ORGANIC LION'S MANE",
     "note": "display serif over dark green, real curvature"},
    {"id": "main_name_right", "file": "mogra_pair_main.png",
     "box": [1120, 1088, 1818, 1156], "text_px": 48,
     "expected": "ORGANIC SHIITAKE",
     "note": "display serif over near-black"},
    {"id": "main_panel_left", "file": "mogra_pair_main.png",
     "box": [205, 1128, 790, 1500], "text_px": 28,
     "expected": "MUSHROOM POWDER 6 oz (170 g)",
     "note": "sub-name + weight panel, low contrast on dark green"},
    {"id": "main_panel_right", "file": "mogra_pair_main.png",
     "box": [1215, 1148, 1730, 1500], "text_px": 31,
     "expected": "MUSHROOM POWDER 8 oz (227 g)",
     "note": "sub-name + weight panel on near-black"},
    {"id": "life_brand_left", "file": "mogra_pair_lifestyle.png",
     "box": [265, 610, 412, 662], "text_px": 17,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup at 17 px in a scene, blurred background"},
    {"id": "life_brand_right", "file": "mogra_pair_lifestyle.png",
     "box": [805, 618, 960, 674], "text_px": 22,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup at 22 px on the black pouch"},
    {"id": "life_name_left", "file": "mogra_pair_lifestyle.png",
     "box": [140, 730, 548, 785], "text_px": 31,
     "expected": "ORGANIC LION'S MANE",
     "note": "display serif in the greenhouse scene"},
    {"id": "life_name_right", "file": "mogra_pair_lifestyle.png",
     "box": [676, 741, 1096, 799], "text_px": 34,
     "expected": "ORGANIC SHIITAKE",
     "note": "display serif in the greenhouse scene"},
    {"id": "life_panel_left", "file": "mogra_pair_lifestyle.png",
     "box": [190, 762, 495, 996], "text_px": 24,
     "expected": "MUSHROOM POWDER 6 oz (170 g)",
     "note": "sub-name + weight, shallow depth of field"},
    {"id": "life_panel_right", "file": "mogra_pair_lifestyle.png",
     "box": [730, 775, 1050, 1000], "text_px": 23,
     "expected": "MUSHROOM POWDER 8 oz (227 g)",
     "note": "sub-name + weight on the black pouch"},
    {"id": "forest_brand_left", "file": "mogra_forest_dusk.png",
     "box": [185, 278, 532, 362], "text_px": 32,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup at dusk, warm low light"},
    {"id": "forest_brand_right", "file": "mogra_forest_dusk.png",
     "box": [680, 278, 1035, 357], "text_px": 35,
     "expected": "EST 2023 MOGRA ORGANICS Healthy & Organic",
     "note": "brand lockup at dusk, warm low light"},
    {"id": "forest_name_left", "file": "mogra_forest_dusk.png",
     "box": [168, 350, 548, 414], "text_px": 36,
     "expected": "ORGANIC LION'S MANE",
     "note": "display serif, warm low light, mild blur"},
    {"id": "forest_panel_right", "file": "mogra_forest_dusk.png",
     "box": [720, 372, 1000, 715], "text_px": 23,
     "expected": "MUSHROOM POWDER 8 oz (227 g)",
     "note": "sub-name + weight, lowest-contrast case in the set"},
]

#: JPEG quality for the crops: real marketplace images are compressed, so the eval set is.
CROP_JPEG_QUALITY = 72

_RAPID: Dict[str, Any] = {}
_EASY: Dict[str, Any] = {}


def build_crops(folder: Path = CROPS) -> List[Dict[str, Any]]:
    """Cut the crops from the real references and return the eval rows."""
    from PIL import Image

    folder.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for spec in CROPS_SPEC:
        source = REFS / spec["file"]
        if not source.is_file():
            rows.append({"id": spec["id"], "path": None, "expected": spec["expected"],
                         "source": spec["file"], "box": list(spec["box"]),
                         "missing": True})
            continue
        target = folder / f"{spec['id']}.jpg"
        with Image.open(source) as opened:
            image = opened.convert("RGB").crop(tuple(int(v) for v in spec["box"]))
            image.save(target, format="JPEG", quality=CROP_JPEG_QUALITY)
        rows.append({"id": spec["id"], "path": str(target),
                     "expected": spec["expected"], "source": spec["file"],
                     "box": list(spec["box"]), "text_px": spec.get("text_px"),
                     "note": spec.get("note"), "width": image.width,
                     "height": image.height})
    return rows


def eval_set() -> List[Dict[str, Any]]:
    """The hard-crop frames with the text each one is known to carry."""
    return [row for row in build_crops() if row.get("path")]


def _rapidocr(image_path: str, scale: int = 1) -> str:
    import numpy as np
    from PIL import Image

    engine = _RAPID.get("engine")
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR

        engine = _RAPID["engine"] = RapidOCR()
    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
        if scale > 1:
            image = image.resize((image.width * scale, image.height * scale),
                                 Image.LANCZOS)
        array = np.asarray(image)
    result, _ = engine(np.ascontiguousarray(array[:, :, ::-1]))
    return " ".join(str(row[1]) for row in (result or []))


def _easyocr(image_path: str) -> str:
    reader = _EASY.get("reader")
    if reader is None:
        import easyocr

        reader = _EASY["reader"] = easyocr.Reader(["en"], gpu=False, verbose=False)
    lines = reader.readtext(image_path, detail=0)
    return " ".join(str(line) for line in lines)


RUNNERS: Dict[str, Callable[[str], str]] = {
    "rapidocr": lambda path: _rapidocr(path, 1),
    "rapidocr-2x": lambda path: _rapidocr(path, 2),
    "easyocr": _easyocr,
}


def benchmark(candidates: Optional[List[str]] = None) -> Dict[str, Any]:
    frames = eval_set()
    results: Dict[str, Any] = {}
    for name in candidates or list(CANDIDATES):
        runner = RUNNERS.get(name)
        if runner is None:
            results[name] = {"status": "missing", "reason": "no runner"}
            continue
        started = time.time()
        rows: List[Dict[str, Any]] = []
        try:
            for frame in frames:
                begin = time.time()
                try:
                    text = runner(frame["path"])
                    error = ""
                except Exception as exc:  # noqa: BLE001 - an engine failure is a datum
                    text, error = "", f"{type(exc).__name__}: {exc}"
                verdict = text_match(text, frame["expected"])
                rows.append({"id": frame["id"], "seconds": round(time.time() - begin, 2),
                             "recall": verdict.get("recall", 0.0),
                             "matched": verdict.get("matched", []),
                             "missing": verdict.get("missing", []),
                             "error": error, "text": text[:400]})
        except Exception as exc:  # noqa: BLE001
            results[name] = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
            continue
        total_seconds = round(time.time() - started, 2)
        hard = [row for row in rows if row["recall"] < 1.0]
        mean_recall = round(sum(row["recall"] for row in rows) / max(1, len(rows)), 3)
        results[name] = {"status": "measured", "mean_recall": mean_recall,
                         "frames": len(rows), "seconds": total_seconds,
                         "crops_read_exactly": len(rows) - len(hard),
                         "hard_crops": [row["id"] for row in hard],
                         "per_frame": rows, **CANDIDATES[name]}

    measured = {name: row for name, row in results.items() if row.get("status") == "measured"}
    winner = max(measured.items(), key=lambda item: (item[1]["mean_recall"],
                                                     -item[1]["seconds"]),
                 default=("", {}))
    previous = "rapidocr"
    best = winner[0]
    margin = round(winner[1].get("mean_recall", 0.0)
                   - measured.get(previous, {}).get("mean_recall", 0.0), 3)
    per_crop = {}
    for frame in frames:
        per_crop[frame["id"]] = {
            name: next((row["recall"] for row in (payload.get("per_frame") or [])
                        if row["id"] == frame["id"]), None)
            for name, payload in measured.items()}
    leaderboard = sorted(
        ({"engine": name, "mean_recall": payload.get("mean_recall"),
          "crops_read_exactly": payload.get("crops_read_exactly"),
          "seconds": payload.get("seconds"), "licence": payload.get("licence"),
          "hard_crops": payload.get("hard_crops")}
         for name, payload in measured.items()),
        key=lambda row: (-(row["mean_recall"] or 0.0), row["seconds"] or 0.0))
    payload = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eval_set": frames,
        "crop_count": len(frames),
        "crop_source": "renders/references/mogra/*.png (real uploads), cropped and saved "
                       f"as JPEG q{CROP_JPEG_QUALITY}",
        "metric": "mean token recall of the crop's known printed text (fuzzy, the same "
                  "matcher the reference check uses)",
        "candidates": results,
        "leaderboard": leaderboard,
        "per_crop": per_crop,
        "winner": best,
        "incumbent": previous,
        "margin_over_incumbent": margin,
        "decision": ("keep rapidocr" if best == previous or margin < 0.05
                     else f"replace rapidocr with {best} (+{margin})"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def register_role(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add the OCR result to the model leaderboard under an `ocr` role."""
    try:
        data = json.loads(ROLES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "reason": "model_roles.json unreadable"}
    roles = data.setdefault("roles", {})
    roles["ocr"] = {
        "label": "OCR (printed text on packaging)",
        "eval": "mogra_crops",
        "incumbent": payload.get("incumbent"),
        "candidates": [name for name in payload.get("candidates", {})],
        "measured": {name: {"mean_recall": row.get("mean_recall"),
                            "licence": row.get("licence")}
                     for name, row in (payload.get("candidates") or {}).items()
                     if row.get("status") == "measured"},
        "decision": payload.get("decision"),
        "source": "ty/ocr_leaderboard.json",
    }
    ROLES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "role": "ocr"}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OCR benchmark")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--candidates", default="")
    ns = parser.parse_args(argv)
    names = [name.strip() for name in ns.candidates.split(",") if name.strip()]
    payload = benchmark(names or None)
    register_role(payload)
    print(json.dumps({"winner": payload["winner"],
                      "decision": payload["decision"],
                      "crops": payload["crop_count"],
                      "leaderboard": payload["leaderboard"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
