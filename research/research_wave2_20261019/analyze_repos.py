"""Analyse the Research Wave 2 GitHub sweep: categories, standouts, licences.

Reads repos.csv and prints a compact, copy-ready summary. No network.

Usage: python analyze_repos.py [--top 12]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent

#: Query -> the capability bucket it informs.
BUCKETS = {
    "generation": ["comfyui flux", "flux2", "qwen image", "z-image", "hidream",
                   "hunyuan image", "text to image", "rectified flow", "flow matching",
                   "latent diffusion", "sdxl", "img2img"],
    "editing": ["flux kontext", "image editing model", "inpainting model",
                "instruction based image editing", "image-to-image diffusion",
                "outpainting", "image completion", "flux fill", "comfyui image edit"],
    "typography": ["typography generation", "text in image generation", "anytext",
                   "text rendering", "glyph generation", "font generation",
                   "typography automation", "text layout engine", "harfbuzz",
                   "font rendering", "variable font", "font parsing",
                   "comfyui typography", "comfyui text", "comfyui text overlay"],
    "packaging": ["dieline", "dieline generator", "packaging design tool",
                  "packaging generator", "packaging template", "stand up pouch",
                  "doypack", "carton design", "corrugated box design", "packaging cad",
                  "structural packaging", "box template generator", "packaging artwork",
                  "3d packaging", "comfyui packaging", "label generator", "label design"],
    "print_prepress": ["prepress", "cmyk conversion", "print ready export",
                       "print imposition", "bleed marks", "print color",
                       "color management", "icc profile", "littlecms", "ghostscript",
                       "pdf generation", "pdf/x", "vector pdf", "svg to pdf",
                       "scribus", "inkscape automation"],
    "mockups": ["mockup generator", "product mockup", "mockup automation",
                "smart object mockup", "pouch mockup", "box mockup", "bag mockup",
                "mockup api", "dynamic mockups", "mockup template", "mockup engine",
                "mockup rendering", "mockup server", "product mockup automation",
                "comfyui mockup"],
    "product_photo": ["product photography ai", "virtual product photography",
                      "product scene generation", "ecommerce image generation",
                      "product photo composite", "amazon product image",
                      "listing image generation", "packshot", "product render ai",
                      "catalog automation", "product image editing",
                      "ai product photoshoot", "comfyui product photography",
                      "comfyui product shot", "ai product photography workflow"],
    "matting": ["background removal", "rembg", "birefnet", "rmbg", "image matting",
                "image cutout", "portrait matting", "video matting", "alpha matting",
                "foreground segmentation", "comfyui matting",
                "comfyui background removal", "comfyui cutout"],
    "composition": ["image harmonization", "composite image", "object insertion",
                    "shadow generation", "reflection generation", "relighting",
                    "image blending", "poisson blending", "seamless clone",
                    "image compositing", "foreground insertion",
                    "in-context image generation", "comfyui reflection"],
    "upscale_restore": ["super resolution", "upscaler", "image upscaling",
                        "image restoration", "photo restoration", "image enhancement",
                        "real esrgan", "face restoration", "comfyui upscale"],
    "3d": ["3d mockup", "3d product viewer", "3d product configurator", "model viewer",
           "gltf viewer", "uv mapping tool", "texture mapping tool", "blender automation",
           "blender script", "cycles render", "path tracing", "pbr rendering",
           "procedural modeling", "3d asset generation", "image to 3d",
           "blender product render", "blenderproc", "three.js product viewer",
           "product configurator"],
    "design_editor": ["design editor canvas", "fabric.js editor", "konva editor",
                      "design tool ai", "generative design app", "canva alternative",
                      "figma alternative", "canvas editor open source", "svg editor",
                      "vector editor", "layer editor", "design automation",
                      "design template engine", "graphic design automation",
                      "brand asset management"],
    "qc_vision": ["ocr", "paddleocr", "vision language model", "image quality assessment",
                  "image aesthetics", "clip embedding", "image similarity",
                  "visual quality control", "defect detection", "image diff",
                  "document understanding", "layout analysis", "text detection"],
    "corpus_rag": ["rag pipeline", "knowledge base builder", "web crawler llm",
                   "content extraction", "sitemap crawler", "rag ingestion",
                   "embedding store", "vector database", "local rag",
                   "document parsing", "markdown conversion", "llm ready markdown",
                   "crawl4ai"],
    "training": ["lora training flux", "ai toolkit flux", "lora flux", "dreambooth",
                 "textual inversion", "controlnet training", "ip adapter training",
                 "diffusion model training"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    rows = []
    with (HERE / "repos.csv").open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                row["stars"] = int(row.get("stars") or 0)
            except ValueError:
                row["stars"] = 0
            rows.append(row)

    by_query: dict[str, list] = defaultdict(list)
    for r in rows:
        by_query[r["query"]].append(r)

    print(f"TOTAL REPOS: {len(rows)}")
    lic = Counter((r.get("license") or "none").strip() or "none" for r in rows)
    print("TOP LICENCES:", json.dumps(lic.most_common(10)))
    stars = [r["stars"] for r in rows]
    print(f"stars: max={max(stars)} >=1k={sum(1 for s in stars if s >= 1000)} "
          f">=100={sum(1 for s in stars if s >= 100)}")
    langs = Counter(r.get("language") or "?" for r in rows)
    print("TOP LANGUAGES:", json.dumps(langs.most_common(8)))
    pushes = Counter((r.get("pushed_at") or "")[:4] for r in rows)
    print("ACTIVITY BY YEAR:", json.dumps(pushes.most_common(6)))

    print("\nBUCKETS (unique repos, deduped across the bucket's queries):")
    for bucket, queries in BUCKETS.items():
        uniq = {}
        for q in queries:
            for r in by_query.get(q, []):
                uniq[r["full_name"]] = r
        if not uniq:
            continue
        top = sorted(uniq.values(), key=lambda r: -r["stars"])[:4]
        names = ", ".join(f"{t['full_name']}({t['stars']})" for t in top)
        print(f"  {bucket:15s} n={len(uniq):5d}   top: {names}")

    print(f"\nTOP {args.top} OVERALL:")
    for r in sorted(rows, key=lambda r: -r["stars"])[: args.top]:
        desc = (r.get("description") or "")[:80]
        print(f"  {r['stars']:>7}  {r['full_name']:<52} {desc}")

    # things that look directly useful and permissively licensed
    permissive = ("MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC",
                  "MPL-2.0", "0BSD", "Unlicense", "CC0-1.0")
    interesting = [r for r in rows
                   if (r.get("license") or "") in permissive and r["stars"] >= 300]
    print(f"\nPERMISSIVE (>=300 stars): {len(interesting)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
