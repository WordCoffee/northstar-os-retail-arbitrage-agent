"""Wave 2 of the secondary discovery pass: new queries, new evidence directory.

Wave 1 (commit bf648649) indexed 10,061 targets across GitHub, Hugging Face,
arXiv, the Google AI forum and YouTube. This wave deliberately asks different
questions — layout/Donut/Depth/SAM, tool-protocol implementations, virtual try-on,
ad creative, conversion/listing research — and writes to its own evidence
directory so wave 1 stays reproducible.

    python tools/expansion_scan_wave2.py --platform all

Same guards: 60/50/50 budget, resumable, no Amazon request, no spend, STOP.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import expansion_scan as es  # noqa: E402

es.RUN = ROOT / "state" / "evidence" / "expansion_wave2_20261104"

es.HF_QUERIES = {
    "models": [
        "layoutlm", "donut document", "table transformer", "depth anything",
        "segment anything 2", "trellis 3d", "hunyuan3d", "instantmesh",
        "virtual try-on", "image matting", "ad banner", "ctr prediction",
        "copywriting", "review summarization", "product catalog",
        "nutrition facts", "packaging", "style transfer", "visual search",
        "image retrieval",
    ],
    "datasets": [
        "amazon reviews", "advertising creative", "short video", "shelf images",
        "nutrition facts",
    ],
    "spaces": [
        "layout parser", "3d reconstruction", "relighting", "product photo",
        "virtual try-on",
    ],
}

es.ARXIV_QUERIES = [
    "layoutlm", "donut document understanding", "table transformer",
    "depth anything", "segment anything", "gaussian splatting",
    "3d asset generation", "virtual try-on", "ad banner",
    "copywriting", "conversion rate", "a/b testing creative",
    "social commerce", "short video advertising", "influencer marketing",
    "packaging sustainability", "nutrition label", "product catalog",
    "visual search", "image retrieval", "multimodal recommendation",
    "brand safety", "ad targeting", "creative ranking", "marketing analytics",
]

es.GFORUM_QUERIES = [
    "gemma 3", "litert", "ai edge", "vertex ai", "function calling",
    "json schema", "embeddings", "rag", "vision", "ocr",
]

es.YOUTUBE_CHANNELS = [
    "OpenAI", "Anthropic", "MistralAI", "MetaAI", "NVIDIA", "Adobe",
    "Canva", "GoogleAds", "MetaBusiness", "TikTokAds", "YouTubeAds",
    "GoogleAI",
]

es.GITHUB_QUERIES = [
    {"q": "tool calling in:name,description", "focus": "tys", "stars": 50, "pages": 5},
    {"q": "function calling in:name,description", "focus": "tys", "stars": 100, "pages": 5},
    {"q": "json schema in:name,description", "focus": "tys", "stars": 50, "pages": 5},
    {"q": "knowledge graph in:name,description", "focus": "brain", "stars": 200, "pages": 5},
    {"q": "vector database in:name,description", "focus": "brain", "stars": 200, "pages": 5},
    {"q": "document understanding in:name,description", "focus": "brain", "stars": 100, "pages": 5},
    {"q": "layout analysis in:name,description", "focus": "brain", "stars": 50, "pages": 5},
    {"q": "virtual try-on in:name,description", "focus": "creative", "stars": 50, "pages": 5},
    {"q": "ad creative in:name,description", "focus": "creative", "stars": 20, "pages": 5},
    {"q": "conversion rate in:name,description", "focus": "creative", "stars": 50, "pages": 5},
    {"q": "short video in:name,description", "focus": "creative", "stars": 50, "pages": 5},
    {"q": "amazon listing in:name,description", "focus": "creative", "stars": 20, "pages": 5},
]

PLATFORMS = {"hf": es.scan_hf, "arxiv": es.scan_arxiv, "gforum": es.scan_gforum,
             "youtube": es.scan_youtube, "github": es.scan_github}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", choices=["all", *PLATFORMS], default="all")
    args = ap.parse_args(argv)
    results = {}
    selected = PLATFORMS if args.platform == "all" else {args.platform: PLATFORMS[args.platform]}
    for name, fn in selected.items():
        print(f"== wave2 {name} ==", flush=True)
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001
            results[name] = {"platform": name, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[{name}] failed: {exc}", flush=True)
    totals = {"wave": 2, "platforms": results}
    totals["rows"] = sum(int((r or {}).get("rows") or 0) for r in results.values())
    totals["unique"] = sum(int((r or {}).get("unique") or 0) for r in results.values())
    es._save(es.RUN / "summary.json", totals)
    print(totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
