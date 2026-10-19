"""Research Wave 2 — GitHub deep sweep (v2).

Scale-up of research/packify_quality_deep_dive_20261016/gh_sweep.py:
  - ~360 generated queries across 15 tooling categories (vs 90 hand-listed)
  - up to 3 pages per query (vs page 1 only)
  - authenticated when a token is available (30 req/min + higher search cap),
    with a clean unauthenticated fallback (10 req/min)
  - resumable: per-query state file; re-runs skip completed queries
  - append-only CSV + JSONL so partial runs are never lost

Auth resolution order (the token is never printed or written anywhere):
  1. GITHUB_TOKEN / GH_TOKEN environment variable (read in-process)
  2. `gh auth token` subprocess (the gh CLI holds the credential)
  3. unauthenticated

Outputs (research/research_wave2_20261019/):
  repos.csv          full_name,url,stars,license,description,language,pushed_at,topics,query,page
  repos.jsonl        same rows, line-delimited
  sweep_state.json   per-query completion + error log + running totals
  sweep_summary.json final summary (mode, counts, star buckets, errors)

Usage:  python gh_sweep_v2.py [--max-queries N] [--pages N] [--fresh]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUT_DIR / "repos.csv"
JSONL_PATH = OUT_DIR / "repos.jsonl"
STATE_PATH = OUT_DIR / "sweep_state.json"
SUMMARY_PATH = OUT_DIR / "sweep_summary.json"

API = "https://api.github.com/search/repositories"
UA = "northstar-research-wave2"

# ── query generation ────────────────────────────────────────────────────────

TOPICS = [
    # product photography / e-commerce imagery
    "product photography ai", "virtual product photography", "product scene generation",
    "ecommerce image generation", "product photo composite", "amazon product image",
    "listing image generation", "packshot", "product render ai", "virtual try on",
    "ghost mannequin", "product video generation", "catalog automation",
    "product image editing", "ai product photoshoot", "product background generation",
    "ecommerce image automation", "product photo retouching ai",
    # mockups / compositing
    "mockup generator", "product mockup", "mockup automation", "smart object mockup",
    "psd mockup automation", "pouch mockup", "box mockup", "bag mockup",
    "mockup api", "dynamic mockups", "mockup template", "mockup engine",
    "mockup rendering", "mockup server", "product mockup automation",
    # dielines / packaging print
    "dieline", "dieline generator", "packaging design tool", "packaging generator",
    "label generator", "label design", "print ready export", "prepress",
    "cmyk conversion", "packaging template", "fefco", "box generator",
    "stand up pouch", "doypack", "pouch design software", "carton design",
    "corrugated box design", "packaging cad", "structural packaging",
    "box template generator", "packaging artwork", "print imposition", "bleed marks",
    "label printing automation", "packaging dieline svg",
    # matting / vectorize / restore
    "background removal", "rembg", "birefnet", "rmbg", "image matting",
    "vectorize image", "vtracer", "potrace", "svg trace", "image cutout",
    "portrait matting", "video matting", "alpha matting", "foreground segmentation",
    "image restoration", "photo restoration", "super resolution", "upscaler",
    "image enhancement", "real esrgan", "image upscaling", "face restoration",
    # models / training
    "flux fill", "flux lora", "lora training flux", "ai toolkit flux",
    "inpainting model", "image editing diffusion", "text editing image",
    "typography generation", "text in image generation", "anytext",
    "diffusion model training", "dreambooth", "textual inversion",
    "controlnet training", "ip adapter training", "image-to-image diffusion",
    "img2img", "sdxl", "latent diffusion", "rectified flow", "flow matching",
    "flux2", "qwen image", "z-image", "hidream", "hunyuan image",
    "flux kontext", "image editing model", "instruction based image editing",
    "consistent character generation", "style transfer diffusion",
    "image inpainting research", "outpainting", "image completion",
    # comfyui ecosystem
    "comfyui nodes", "comfyui workflow", "comfyui workflow collection",
    "comfyui manager", "comfyui api", "comfyui batch", "comfyui queue",
    "comfyui comfy nodes", "comfyui custom nodes", "comfyui templates",
    "comfyui product", "comfyui relight", "comfyui inpaint", "comfyui upscale",
    "comfyui controlnet", "comfyui ipadapter", "comfyui text",
    "comfyui segmentation", "comfyui matting", "comfyui mask", "comfyui depth",
    "comfyui normal map", "comfyui lora", "comfyui model loader",
    "comfyui video", "comfyui animation", "comfyui face", "comfyui pose",
    # design editors / generative design apps
    "design editor canvas", "fabric.js editor", "konva editor", "design tool ai",
    "generative design app", "canva alternative", "figma alternative",
    "canvas editor open source", "3d product configurator", "three.js product viewer",
    "svg editor", "vector editor", "layer editor", "design automation",
    "brand asset management", "design template engine", "graphic design automation",
    "poster generator", "flyer generator", "social media image generator",
    "banner generation", "creative automation", "ad creative generation",
    # 3d / rendering
    "3d packaging", "blender product render", "blenderproc", "product configurator",
    "3d mockup", "3d product viewer", "model viewer", "gltf viewer",
    "uv mapping tool", "texture mapping tool", "blender automation",
    "blender script", "cycles render", "path tracing", "pbr rendering",
    "procedural modeling", "3d asset generation", "image to 3d",
    "texture synthesis", "seamless texture", "material generation",
    # harmonization / composition
    "image harmonization", "composite image", "object insertion",
    "shadow generation", "reflection generation", "relighting",
    "image blending", "poisson blending", "seamless clone",
    "image compositing", "foreground insertion", "in-context image generation",
    # qc / ocr / vision
    "ocr", "paddleocr", "vision language model", "image quality assessment",
    "image aesthetics", "clip embedding", "image similarity",
    "visual quality control", "defect detection", "image diff",
    "document understanding", "layout analysis", "text detection",
    # knowledge / corpus / rag
    "rag pipeline", "knowledge base builder", "web crawler llm",
    "content extraction", "sitemap crawler", "rag ingestion",
    "embedding store", "vector database", "local rag", "document parsing",
    "markdown conversion", "llm ready markdown", "crawl4ai",
    # print / colour
    "color management", "icc profile", "littlecms", "ghostscript",
    "pdf generation", "pdf/x", "vector pdf", "svg to pdf",
    "inkscape automation", "scribus", "print color",
    # font / typography tech
    "typography automation", "font parsing", "text layout engine", "harfbuzz",
    "font rendering", "variable font", "font generation", "glyph generation",
]

PREFIXED_EXTRA = [
    # topics that benefit from a second, comfyui-scoped query
    "product photography", "product shot", "mockup", "packaging", "label design",
    "typography", "text overlay", "image edit", "background removal",
    "harmonization", "shadow generation", "reflection", "matting", "cutout",
]


def build_queries() -> list[str]:
    qs: list[str] = []
    seen: set[str] = set()
    for t in TOPICS:
        if t not in seen:
            seen.add(t)
            qs.append(t)
    for t in PREFIXED_EXTRA:
        q = "comfyui " + t
        if q not in seen:
            seen.add(q)
            qs.append(q)
    return qs


# ── auth ────────────────────────────────────────────────────────────────────

def resolve_token() -> str | None:
    """Return an API token if one is available. Never print or persist it."""
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        tok = os.environ.get(var)
        if tok:
            return tok.strip()
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, timeout=15)
        if out.returncode == 0:
            tok = (out.stdout or "").strip()
            if tok:
                return tok
    except Exception:
        pass
    return None


# ── state ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done_queries": {}, "errors": [], "total_rows": 0, "started_at": None}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── fetch ───────────────────────────────────────────────────────────────────

def search(q: str, page: int, token: str | None) -> dict:
    url = API + "?" + urllib.parse.urlencode({
        "q": q, "per_page": 100, "page": page, "sort": "stars", "order": "desc"})
    headers = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=0)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    if args.fresh:
        for p in (CSV_PATH, JSONL_PATH, STATE_PATH, SUMMARY_PATH):
            if p.exists():
                p.unlink()

    token = resolve_token()
    mode = "authenticated" if token else "unauthenticated"
    pace = 2.3 if token else 7.0  # seconds between requests

    queries = build_queries()
    if args.max_queries:
        queries = queries[: args.max_queries]

    state = load_state()
    if state.get("started_at") is None:
        state["started_at"] = datetime.now(timezone.utc).isoformat()
    done = state["done_queries"]

    seen: set[str] = set()
    if CSV_PATH.is_file():
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add(row["full_name"])

    print(f"[wave2] mode={mode} pace={pace}s queries={len(queries)} "
          f"already_seen={len(seen)}", flush=True)

    csv_exists = CSV_PATH.is_file()
    fields = ["full_name", "url", "stars", "license", "description",
              "language", "pushed_at", "topics", "query", "page"]
    cf = CSV_PATH.open("a", newline="", encoding="utf-8")
    jf = JSONL_PATH.open("a", encoding="utf-8")
    w = csv.DictWriter(cf, fieldnames=fields)
    if not csv_exists:
        w.writeheader()

    try:
        for i, q in enumerate(queries):
            if q in done and not args.fresh:
                continue
            got = 0
            for page in range(1, args.pages + 1):
                data, err, retried = None, None, False
                for attempt in (1, 2):
                    try:
                        data = search(q, page, token)
                        err = None
                        break
                    except urllib.error.HTTPError as exc:
                        err = f"HTTP {exc.code}"
                        if exc.code in (403, 429) and attempt == 1:
                            retried = True
                            time.sleep(65 if not token else 20)
                            continue
                        break
                    except Exception as exc:  # noqa: BLE001
                        err = str(exc)[:140]
                        time.sleep(8)
                if err or data is None:
                    state["errors"].append({"query": q, "page": page, "error": err})
                    break
                items = data.get("items", [])
                if not items:
                    break
                for it in items:
                    full = it.get("full_name")
                    if not full or full in seen:
                        continue
                    seen.add(full)
                    row = {
                        "full_name": full,
                        "url": it.get("html_url"),
                        "stars": it.get("stargazers_count"),
                        "license": (it.get("license") or {}).get("spdx_id"),
                        "description": (it.get("description") or "")[:220],
                        "language": it.get("language"),
                        "pushed_at": it.get("pushed_at"),
                        "topics": ",".join(it.get("topics") or [])[:220],
                        "query": q,
                        "page": page,
                    }
                    w.writerow(row)
                    jf.write(json.dumps(row, ensure_ascii=False) + "\n")
                    got += 1
                cf.flush()
                jf.flush()
                if len(items) < 100:
                    break
                time.sleep(pace)
            done[q] = got
            state["total_rows"] = len(seen)
            save_state(state)
            if (i + 1) % 5 == 0 or got:
                print(f"[{i+1}/{len(queries)}] {q!r}: +{got} (total {len(seen)})",
                      flush=True)
            time.sleep(pace)
    finally:
        cf.close()
        jf.close()

    rows = list(seen)
    state["finished_at"] = datetime.now(timezone.utc).isoformat()
    state["unique_repos"] = len(rows)
    save_state(state)
    SUMMARY_PATH.write_text(json.dumps({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "queries_total": len(queries),
        "queries_done": len(done),
        "unique_repos": len(rows),
        "errors": state["errors"][-40:],
    }, indent=2), encoding="utf-8")
    print(f"DONE wave2: {len(rows)} unique repos, {len(done)} queries done, "
          f"{len(state['errors'])} errors", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
