"""GitHub deep-scan sweep for the Packify-quality workflow deep dive.

Enumerates candidate repos across every tooling category that could move
Northstar OS generation toward Packify.ai-grade output: ComfyUI workflows and
custom nodes (text rendering, control, edit/inpaint, upscale, relight),
product-photography pipelines, mockup compositors, dieline/label tooling,
design editors, matting/vectorize/post tools, LoRA training, 3D packaging.

Unauthenticated GitHub Search API: 10 req/min -> sleeps between calls.
Each returned repo is a metadata-verified source row in SOURCES_GITHUB.csv.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

QUERIES = [
    # --- ComfyUI ecosystem / generation quality ---
    "comfyui product photography", "comfyui product shot", "comfyui mockup",
    "comfyui packaging", "comfyui label", "comfyui text rendering",
    "comfyui typography", "comfyui flux", "comfyui controlnet", "comfyui ipadapter",
    "comfyui inpaint", "comfyui image edit", "comfyui upscale", "comfyui relight",
    "comfyui iclight", "comfyui background remove", "comfyui ecommerce",
    "comfyui workflow collection", "comfyui nodes", "comfyui api",
    # --- product photography / virtual shots ---
    "product photography ai", "virtual product photography", "product scene generation",
    "ecommerce image generation", "product photo composite", "amazon product image",
    "listing image generation", "packshot", "product render ai",
    # --- mockups / compositing ---
    "mockup generator", "product mockup", "mockup automation", "smart object mockup",
    "psd mockup automation", "pouch mockup", "box mockup", "bag mockup",
    "mockup api", "dynamic mockups", "mockup template", "photoshop automation mockup",
    # --- dielines / packaging print ---
    "dieline", "dieline generator", "packaging design tool", "packaging generator",
    "label generator", "label design", "print ready export", "prepress",
    "cmyk conversion", "packaging template", "fefco", "box generator",
    # --- matting / vectorize / post ---
    "background removal", "rembg", "birefnet", "rmbg", "image matting",
    "vectorize image", "vtracer", "potrace", "svg trace",
    # --- edit / fill / generation models ---
    "flux fill", "flux lora", "lora training flux", "ai toolkit flux",
    "inpainting model", "image editing diffusion", "text editing image",
    "typography generation", "text in image generation", "anytext",
    # --- design editors / generative design apps ---
    "design editor canvas", "fabric.js editor", "konva editor", "design tool ai",
    "generative design app", "canva alternative", "figma alternative",
    "canvas editor open source", "3d product configurator", "three.js product viewer",
    # --- 3d packaging / renders ---
    "3d packaging", "blender product render", "blenderproc", "product configurator",
    # --- upscale / restore ---
    "super resolution", "realesrgan", "supir", "stable diffusion upscale",
]

API = "https://api.github.com/search/repositories"
HEADERS = {"Accept": "application/vnd.github+json",
           "User-Agent": "northstar-deep-scan"}


def search(q: str, page: int = 1) -> dict:
    url = API + "?" + urllib.parse.urlencode({
        "q": q, "per_page": 100, "page": page, "sort": "stars", "order": "desc"})
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    seen: dict = {}
    qstats = []
    for i, q in enumerate(QUERIES):
        got, err = 0, None
        for attempt in (1, 2):
            try:
                data = search(q)
                for item in data.get("items", []):
                    full = item.get("full_name")
                    if full and full not in seen:
                        seen[full] = {
                            "full_name": full,
                            "url": item.get("html_url"),
                            "stars": item.get("stargazers_count"),
                            "description": (item.get("description") or "")[:200],
                            "language": item.get("language"),
                            "pushed_at": item.get("pushed_at"),
                            "topics": ",".join(item.get("topics") or [])[:200],
                            "query": q,
                        }
                        got += 1
                err = None
                break
            except Exception as exc:  # noqa: BLE001
                err = str(exc)[:120]
                time.sleep(20)
        qstats.append({"query": q, "new": got, "error": err})
        print(f"[{i+1}/{len(QUERIES)}] {q!r}: +{got} (total {len(seen)})", flush=True)
        time.sleep(6.5)  # unauthenticated search rate limit: 10/min

    rows = sorted(seen.values(), key=lambda r: -(r.get("stars") or 0))
    with (OUT_DIR / "SOURCES_GITHUB.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["full_name", "url", "stars", "description",
                                          "language", "pushed_at", "topics", "query"])
        w.writeheader()
        w.writerows(rows)
    (OUT_DIR / "sweep_summary.json").write_text(json.dumps({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "queries": len(QUERIES),
        "unique_repos": len(rows),
        "by_stars": {"1k+": sum(1 for r in rows if (r.get("stars") or 0) >= 1000),
                     "100+": sum(1 for r in rows if (r.get("stars") or 0) >= 100)},
        "errors": [s for s in qstats if s["error"]],
    }, indent=2), encoding="utf-8")
    print(f"DONE: {len(rows)} unique repos -> SOURCES_GITHUB.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
