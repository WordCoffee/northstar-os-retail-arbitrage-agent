"""Research Wave 2 — Hugging Face sweep (models + datasets + spaces).

Enumerates HF assets relevant to the creative pipeline: generation/editing
models, matting, harmonization, shadow, depth, 3D, OCR, typography, packaging.
Free public API; no auth required. Resumable, append-only.

Outputs (research/research_wave2_20261019/):
  hf_models.csv / hf_models.jsonl
  hf_datasets.csv
  hf_spaces.csv
  hf_sweep_summary.json

Usage: python hf_sweep_v2.py [--limit 100] [--fresh]
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
UA = "northstar-research-wave2"
API = "https://huggingface.co/api"

MODEL_SEARCHES = [
    # generation / editing
    "flux", "flux.2", "flux2 klein", "qwen-image", "qwen image edit",
    "z-image", "hidream", "hunyuan image", "stable diffusion xl", "sdxl",
    "text to image", "image editing", "image-to-image", "inpainting",
    "outpainting", "kontext", "controlnet", "ip-adapter", "ipadapter",
    "lora flux", "lora sdxl", "dreambooth", "textual inversion",
    # product / commerce
    "product photography", "product shot", "packshot", "ecommerce",
    "virtual try on", "ghost mannequin", "mockup", "packaging", "label",
    # compositing realism
    "image harmonization", "shadow generation", "reflection generation",
    "relighting", "image blending", "seamless clone", "object placement",
    "image composition", "in context lora", "omnigen",
    # matting / segmentation
    "background removal", "matting", "birefnet", "rmbg", "isnet", "u2net",
    "segmentation", "sam2", "sam3", "grounding dino", "transparent object",
    # restore / upscale
    "super resolution", "upscaler", "restoration", "real-esrgan", "seedvr",
    "codeformer", "gfpgan",
    # depth / normals
    "depth estimation", "depth anything", "normal estimation", "stable normal",
    # 3d / texture
    "image to 3d", "trellis", "hunyuan3d", "triposr", "texture generation",
    "pbr", "material estimation",
    # typography / text rendering
    "text rendering", "typography", "glyph", "font generation", "anytext",
    "textdiffuser", "ocr-free text",
    # ocr / vlm / qc
    "ocr", "paddleocr", "vision language model", "qwen vl", "image quality",
    "aesthetic", "clip", "siglip",
    # video
    "wan video", "ltx video", "text to video", "image to video", "frame interpolation",
]

PIPELINE_FILTERS = [
    "text-to-image", "image-to-image", "image-to-video", "text-to-video",
    "image-segmentation", "depth-estimation", "image-classification",
    "object-detection", "zero-shot-image-classification", "image-feature-extraction",
    "mask-generation", "video-classification",
]


def get_json(url: str, tries: int = 3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except Exception as exc:  # noqa: BLE001
            if attempt == tries - 1:
                return {"__error__": str(exc)[:160]}
            time.sleep(3 + attempt * 4)
    return {"__error__": "unreachable"}


def sweep(kind: str, searches: list[str], limit: int) -> dict:
    csv_path = OUT / f"hf_{kind}.csv"
    jsonl_path = OUT / f"hf_{kind}.jsonl"
    seen: set[str] = set()
    if csv_path.is_file():
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add(row["id"])

    fields = ["id", "kind", "downloads", "likes", "pipeline_tag", "license",
              "last_modified", "tags", "query"]
    csv_exists = csv_path.is_file()
    stats = {"queries": 0, "new": 0, "errors": []}
    with csv_path.open("a", newline="", encoding="utf-8") as cf, \
            jsonl_path.open("a", encoding="utf-8") as jf:
        w = csv.DictWriter(cf, fieldnames=fields)
        if not csv_exists:
            w.writeheader()
        for q in searches:
            url = f"{API}/{kind}?" + urllib.parse.urlencode({
                "search": q, "limit": limit, "sort": "downloads", "direction": -1,
                "full": "false"})
            data = get_json(url)
            stats["queries"] += 1
            if isinstance(data, dict) and "__error__" in data:
                stats["errors"].append({"query": q, "error": data["__error__"]})
                time.sleep(1.0)
                continue
            for it in data:
                mid = it.get("id") or it.get("modelId")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                tags = [t for t in (it.get("tags") or [])]
                lic = next((t.split(":", 1)[1] for t in tags
                            if t.startswith("license:")), "")
                row = {
                    "id": mid, "kind": kind,
                    "downloads": it.get("downloads"),
                    "likes": it.get("likes"),
                    "pipeline_tag": it.get("pipeline_tag") or "",
                    "license": lic,
                    "last_modified": (it.get("lastModified") or "")[:19],
                    "tags": ",".join(tags[:24]),
                    "query": q,
                }
                w.writerow(row)
                jf.write(json.dumps(row, ensure_ascii=False) + "\n")
                stats["new"] += 1
            cf.flush()
            jf.flush()
            print(f"[hf:{kind}] {q!r}: total {len(seen)}", flush=True)
            time.sleep(0.7)
    stats["total"] = len(seen)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    if args.fresh:
        for p in OUT.glob("hf_*"):
            p.unlink()

    summary = {"ran_at": datetime.now(timezone.utc).isoformat()}
    summary["models"] = sweep("models", MODEL_SEARCHES, args.limit)
    # pipeline-tag filtered passes (search can't filter, so use ?filter=)
    tag_rows = 0
    tag_errors = []
    csv_path = OUT / "hf_models_by_tag.csv"
    fields = ["id", "kind", "downloads", "likes", "pipeline_tag", "license",
              "last_modified", "tags", "query"]
    seen_tag: set[str] = set()
    if csv_path.is_file():
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen_tag.add(row["id"])
    csv_exists = csv_path.is_file()
    with csv_path.open("a", newline="", encoding="utf-8") as cf:
        w = csv.DictWriter(cf, fieldnames=fields)
        if not csv_exists:
            w.writeheader()
        for tag in PIPELINE_FILTERS:
            url = f"{API}/models?" + urllib.parse.urlencode({
                "filter": tag, "limit": 100, "sort": "downloads",
                "direction": -1})
            data = get_json(url)
            if isinstance(data, dict) and "__error__" in data:
                tag_errors.append({"tag": tag, "error": data["__error__"]})
                continue
            for it in data:
                mid = it.get("id")
                if not mid or mid in seen_tag:
                    continue
                seen_tag.add(mid)
                tags = it.get("tags") or []
                lic = next((t.split(":", 1)[1] for t in tags
                            if t.startswith("license:")), "")
                w.writerow({
                    "id": mid, "kind": "models", "downloads": it.get("downloads"),
                    "likes": it.get("likes"), "pipeline_tag": it.get("pipeline_tag") or "",
                    "license": lic, "last_modified": (it.get("lastModified") or "")[:19],
                    "tags": ",".join(tags[:24]), "query": f"filter:{tag}"})
                tag_rows += 1
            cf.flush()
            print(f"[hf:models-by-tag] {tag}: total {len(seen_tag)}", flush=True)
            time.sleep(0.7)
    summary["models_by_tag"] = {"total": len(seen_tag), "new": tag_rows,
                                "errors": tag_errors}

    summary["datasets"] = sweep("datasets", MODEL_SEARCHES, 50)
    summary["spaces"] = sweep("spaces", MODEL_SEARCHES[:40], 50)

    (OUT / "hf_sweep_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print("DONE hf sweep", json.dumps({
        "models": summary["models"]["total"],
        "models_by_tag": summary["models_by_tag"]["total"],
        "datasets": summary["datasets"]["total"],
        "spaces": summary["spaces"]["total"],
    }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
