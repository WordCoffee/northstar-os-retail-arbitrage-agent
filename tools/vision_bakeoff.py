"""Ty's Vision model bake-off — 20 golden cases, three local models.

The question is narrow: can a local Ollama vision model return a correct,
parseable yes/no verdict on our own product assets? Accuracy counts a parse
failure as wrong; a model only clears Stage 2 at **18/20** with a full JSON
parse rate.

    python tools/vision_bakeoff.py --build-manifest
    python tools/vision_bakeoff.py --models moondream:latest,llava:7b,qwen2.5vl:7b

One model is loaded at a time; `ollama stop` runs after each model so the box
does not carry two 5-7 GB models. No cloud call, no paid endpoint.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "vision_bakeoff_20261104"
IMAGES = RUN / "images"
MANIFEST = RUN / "manifest.json"
OLLAMA = "http://127.0.0.1:11434/api/chat"
MAX_EDGE = 640
NUM_CTX = 2048

PROMPT = (
    "You are a strict visual verifier for an e-commerce product asset. "
    "Look only at the image. Decide whether this statement is true:\n"
    "{constraint}\n"
    "Judge what is visible, not what was intended. If it is not clearly true, "
    "answer false. Reply with exactly one JSON object and no other text: "
    '{{"pass": true|false, "reasons": ["..."], "confidence": 0.0-1.0}}'
)

CASES: List[Dict[str, Any]] = [
    {"image": "renders/mogra_lions_mane/reference_pp/product_front.png",
     "constraint": "a stand-up pouch is the main subject", "expected": True,
     "category": "pouch"},
    {"image": "renders/mogra_lions_mane/reference_pp/product_front.png",
     "constraint": "the brand wordmark MOGRA is visible", "expected": True,
     "category": "wordmark"},
    {"image": "renders/mogra_lions_mane/reference_pp/product_front.png",
     "constraint": "the net weight 6 oz is visible", "expected": True,
     "category": "net_weight"},
    {"image": "renders/mogra_lions_mane/reference_pair/product_back.png",
     "constraint": "a nutrition facts table is present", "expected": True,
     "category": "nutrition"},
    {"image": "renders/mogra_lions_mane/reference_pair/product_back.png",
     "constraint": "a barcode is visible", "expected": True,
     "category": "barcode"},
    {"image": "renders/mogra_lions_mane/reference_check/reference_1536_seed777.png",
     "constraint": "a stand-up pouch is visible", "expected": True,
     "category": "pouch"},
    {"image": "Northstar_backend/data/studio_generated/tiktok_e445423614.png",
     "constraint": "the image canvas is taller than it is wide", "expected": True,
     "category": "layout"},
    {"image": "Northstar_backend/data/studio_generated/tiktok_e445423614.png",
     "constraint": "large on-screen text is present", "expected": True,
     "category": "layout"},
    {"image": "Northstar_backend/data/studio_generated/white-bg_67b967d23c.png",
     "constraint": "the background is pure white", "expected": True,
     "category": "background"},
    {"image": "Northstar_backend/data/studio_generated/white-bg_67b967d23c.png",
     "constraint": "the image is square", "expected": True,
     "category": "layout"},
    {"image": "renders/mogra_lions_mane/mogra_lions_mane_front_label.png",
     "constraint": "the image is flat artwork rather than a photograph of a pouch",
     "expected": True, "category": "artwork"},
    {"image": "renders/mogra_lions_mane/mogra_lions_mane_front_label.png",
     "constraint": "a stand-up pouch is visible", "expected": False,
     "category": "pouch"},
    {"image": "renders/mogra_lions_mane/mogra_lions_mane_back_label.png",
     "constraint": "a nutrition facts table is present", "expected": True,
     "category": "nutrition"},
    {"image": "renders/mogra_lions_mane/mogra_lions_mane_back_label.png",
     "constraint": "a photograph of a pouch is visible", "expected": False,
     "category": "pouch"},
    {"image": "state/evidence/vision_bakeoff_20261104/images/blurred_front.png",
     "constraint": "the label text is readable", "expected": False,
     "category": "blur"},
    {"image": "state/evidence/vision_bakeoff_20261104/images/blank.png",
     "constraint": "a product pouch is visible", "expected": False,
     "category": "blank"},
    {"image": "state/evidence/vision_bakeoff_20261104/images/cropped_front.png",
     "constraint": "the entire pouch is visible", "expected": False,
     "category": "crop"},
    {"image": "renders/mogra_lions_mane/reference_pp/product_front.png",
     "constraint": "a large rectangular printed area is visible on the package",
     "expected": True, "category": "label"},
    {"image": "renders/mogra_lions_mane/reference_pair/product_back.png",
     "constraint": "the brand wordmark MOGRA is visible", "expected": True,
     "category": "wordmark"},
    {"image": "renders/mogra_lions_mane/reference_check/reference_1536_seed777.png",
     "constraint": "a human hand is holding the pouch", "expected": False,
     "category": "human"},
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prepare(image_path: Path, out_path: Path) -> None:
    from PIL import Image, ImageFilter

    source = Image.open(image_path).convert("RGB")
    if out_path.name == "blank.png":
        Image.new("RGB", (1024, 1024), (200, 200, 200)).save(out_path)
        return
    if out_path.name == "blurred_front.png":
        source.filter(ImageFilter.GaussianBlur(20)).save(out_path)
        return
    if out_path.name == "cropped_front.png":
        width, height = source.size
        source.crop((0, 0, width, int(height * 0.35))).save(out_path)
        return
    source.save(out_path)


def build_manifest() -> Dict[str, Any]:
    IMAGES.mkdir(parents=True, exist_ok=True)
    for name in ("blurred_front.png", "blank.png", "cropped_front.png"):
        _prepare(ROOT / "renders/mogra_lions_mane/reference_pp/product_front.png",
                 IMAGES / name)
    rows = []
    for index, case in enumerate(CASES, 1):
        path = ROOT / case["image"]
        if not path.is_file():
            raise SystemExit(f"case {index}: missing image {case['image']}")
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
        rows.append({"id": f"v{index:02d}", **case, "width": width,
                     "height": height, "exists": True})
    manifest = {"created_at": _now(), "max_edge": MAX_EDGE,
                "num_ctx": NUM_CTX, "cases": rows}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _encode(path: Path) -> bytes:
    from io import BytesIO

    from PIL import Image

    with Image.open(path) as image:
        img = image.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()


def _parse(raw: str) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text else text
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or "pass" not in payload:
        return None
    reasons = payload.get("reasons")
    if isinstance(reasons, str):
        reasons = [reasons]
    return {"pass": bool(payload.get("pass")),
            "reasons": [str(r)[:200] for r in (reasons or [])][:5],
            "confidence": payload.get("confidence")}


def _ask(model: str, image_bytes: bytes, constraint: str,
         *, use_format: bool = True, timeout: float = 240.0) -> Tuple[str, str]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(constraint=constraint),
                      "images": [base64.b64encode(image_bytes).decode("ascii")]}],
        "stream": False,
        "keep_alive": "2m",
        "options": {"temperature": 0.0, "num_ctx": NUM_CTX},
    }
    if use_format:
        payload["format"] = "json"
    req = urllib.request.Request(
        OLLAMA, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str((data.get("message") or {}).get("content") or ""), (
        "json" if use_format else "prompt")


def _stop(model: str) -> None:
    try:
        subprocess.run(["ollama", "stop", model], capture_output=True, timeout=30)
    except Exception:
        pass


def run_model(model: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    started = time.time()
    for case in cases:
        image = ROOT / case["image"]
        began = time.time()
        error = ""
        raw = ""
        mode = "json"
        try:
            raw, mode = _ask(model, _encode(image), case["constraint"])
        except urllib.error.HTTPError as exc:
            if mode == "json":
                try:
                    raw, mode = _ask(model, _encode(image), case["constraint"],
                                     use_format=False)
                except Exception as retry_exc:  # noqa: BLE001
                    error = f"HTTP {exc.code}; retry {type(retry_exc).__name__}: {retry_exc}"
            else:
                error = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        verdict = _parse(raw)
        correct = bool(verdict is not None and verdict["pass"] == case["expected"])
        rows.append({
            "id": case["id"], "image": case["image"],
            "constraint": case["constraint"], "expected": case["expected"],
            "category": case["category"], "parsed": verdict is not None,
            "pass": None if verdict is None else verdict["pass"],
            "correct": correct, "format": mode, "error": error,
            "seconds": round(time.time() - began, 1),
            "raw": raw[:400],
        })
        print(f"[{model}] {case['id']} {'OK' if correct else 'MISS'} "
              f"{case['category']} ({round(time.time() - began, 1)}s)", flush=True)
    _stop(model)
    correct = sum(1 for row in rows if row["correct"])
    parsed = sum(1 for row in rows if row["parsed"])
    return {"model": model, "cases": len(rows), "correct": correct,
            "accuracy": round(correct / max(1, len(rows)), 3),
            "json_parse_rate": round(parsed / max(1, len(rows)), 3),
            "mean_seconds": round(sum(r["seconds"] for r in rows) / max(1, len(rows)), 1),
            "seconds": round(time.time() - started, 1),
            "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="moondream:latest,llava:7b,qwen2.5vl:7b")
    ap.add_argument("--build-manifest", action="store_true")
    ap.add_argument("--out", default="reports/vision_bakeoff_results.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    if args.build_manifest or not MANIFEST.is_file():
        manifest = build_manifest()
        print(f"manifest: {len(manifest['cases'])} cases -> {MANIFEST}")
        if args.build_manifest:
            return 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"][: args.limit or None]
    results = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"== {model} ==", flush=True)
        results.append(run_model(model, cases))
    winner = max(results, key=lambda r: (r["accuracy"], r["json_parse_rate"],
                                         -r["mean_seconds"])) if results else None
    threshold = 18 / 20
    enough_cases = len(cases) >= 20
    report = {
        "generated_at": _now(),
        "threshold": {"correct": 18, "cases": 20, "accuracy": round(threshold, 3)},
        "cases_run": len(cases),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "models": results,
        "winner": winner["model"] if winner else None,
        "winner_accuracy": winner["accuracy"] if winner else None,
        "threshold_met": bool(enough_cases and winner
                              and winner["accuracy"] >= threshold
                              and winner["json_parse_rate"] == 1.0),
        "stage2_unblocked": bool(enough_cases and winner
                                 and winner["accuracy"] >= threshold
                                 and winner["json_parse_rate"] == 1.0),
        "notes": [
            "A parse failure counts as wrong; a model cannot clear the gate on guesses.",
            "One model is loaded at a time; ollama stop runs after each model.",
            f"Images are downscaled to {MAX_EDGE}px and num_ctx={NUM_CTX}.",
        ],
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"winner": report["winner"],
                      "accuracy": report["winner_accuracy"],
                      "threshold_met": report["threshold_met"],
                      "report": str(out)}, indent=2))
    return 0 if report["threshold_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
