"""OCR benchmark: which engine reads our packaging best?

The reference check decides fidelity by printed text, so the OCR engine is a model choice like
any other and gets measured the same way: a fixed eval set, a stated metric, a leaderboard and a
licence per candidate. Nothing here is installed at run time and nothing leaves the machine.

Eval set: the three real Mogra Organics assets in `renders/references/mogra/`, whose printed
text is recorded in their manifest, plus a synthetic text card with known strings. Scoring is
token recall with the same fuzzy matcher the reference check uses — an engine is not "better"
because it returns more boxes.

    python tools/ocr_bench.py --run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "renders" / "references" / "mogra"
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
                    "note": "same engine, frames upscaled 2x before recognition"},
    "easyocr": {"engine": "easyocr", "licence": "Apache-2.0",
                "source": "https://github.com/JaidedAI/EasyOCR", "device": "torch"},
}

TEXT_CARD = "MOGRA ORGANICS ORGANIC LION'S MANE MUSHROOM POWDER 6 oz (170 g)"


def _text_card() -> Any:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 300), "#f7f4ec")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("segoeui.ttf", 46)
    except OSError:
        font = ImageFont.load_default()
    for index, line in enumerate(("MOGRA ORGANICS", "ORGANIC LION'S MANE",
                                  "MUSHROOM POWDER  6 oz (170 g)")):
        draw.text((40, 40 + index * 80), line, fill="#1b2a22", font=font)
    return image


def eval_set() -> List[Dict[str, Any]]:
    """Frames with the text they are known to carry."""
    manifest = REFS / "manifest.json"
    rows: List[Dict[str, Any]] = []
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for asset in data.get("assets") or []:
            path = REFS / asset["file"]
            if path.exists():
                rows.append({"id": asset["file"], "path": str(path),
                             "expected": " ".join(asset.get("printed") or [])})
    card = ROOT / "state" / "ocr" / "text_card.png"
    card.parent.mkdir(parents=True, exist_ok=True)
    _text_card().save(card)
    rows.append({"id": "text_card.png", "path": str(card), "expected": TEXT_CARD})
    return rows


def _rapidocr(image_path: str, scale: int = 1) -> str:
    import numpy as np
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
        if scale > 1:
            image = image.resize((image.width * scale, image.height * scale))
        array = np.asarray(image)
    result, _ = RapidOCR()(np.ascontiguousarray(array[:, :, ::-1]))
    return " ".join(str(row[1]) for row in (result or []))


def _easyocr(image_path: str) -> str:
    import easyocr

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
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
        mean_recall = round(sum(row["recall"] for row in rows) / max(1, len(rows)), 3)
        results[name] = {"status": "measured", "mean_recall": mean_recall,
                         "frames": len(rows), "seconds": total_seconds,
                         "per_frame": rows, **CANDIDATES[name]}

    measured = {name: row for name, row in results.items() if row.get("status") == "measured"}
    winner = max(measured.items(), key=lambda item: item[1]["mean_recall"],
                 default=("", {}))
    previous = "rapidocr"
    best = winner[0]
    margin = round(winner[1].get("mean_recall", 0.0)
                   - measured.get(previous, {}).get("mean_recall", 0.0), 3)
    payload = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eval_set": [frame["id"] for frame in frames],
        "metric": "mean token recall of the printed text (fuzzy, the same matcher the "
                  "reference check uses)",
        "candidates": results,
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
        "eval": "mogra_text",
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
                      "mean_recall": {name: row.get("mean_recall")
                                      for name, row in payload["candidates"].items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
