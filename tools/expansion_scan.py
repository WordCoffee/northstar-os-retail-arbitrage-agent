"""Secondary discovery across six platforms, bounded by the campaign quota.

Platforms and request budgets (the owner's "60/50/50" plus supplemental):

    github   60 search requests  (12 extraction-focused queries x 5 pages)
    huggingface 50 API requests  (30 model + 12 dataset + 8 space searches)
    arxiv    50 API queries      (50 results each, recent first)
    gforum   15 search requests  (Google AI Developers Forum, Discourse JSON)
    youtube  16 channels + RSS    (public feed, no scraping of watch pages)

Every platform writes JSONL + a summary and is resumable per query. No auth, no
Amazon request, no paid endpoint. Run:

    python tools/expansion_scan.py --platform all
    python tools/expansion_scan.py --platform hf
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "expansion_20261104"
UA = "northstar-expansion/1.0"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

HF_QUERIES = {
    "models": [
        "document ocr", "dieline", "packaging design", "product photography",
        "relighting", "multi-view 3d", "image to 3d", "depth estimation",
        "image segmentation", "inpainting", "text-to-image", "embeddings",
        "reranker", "speech recognition", "text to speech",
        "small language model", "function calling", "structured output",
        "ecommerce", "ad creative", "flux", "qwen image edit", "grounding dino",
        "table structure", "nutrition label", "label detection",
        "background removal", "image matting", "super resolution", "video generation",
    ],
    "datasets": [
        "product images", "ecommerce", "packaging", "document layout", "ocr",
        "advertising", "short video", "product catalog", "reviews", "marketing",
        "nutrition label", "shelf",
    ],
    "spaces": [
        "comfyui", "flux", "image editing", "3d reconstruction", "ocr",
        "relighting", "product photo", "background removal",
    ],
}

ARXIV_QUERIES = [
    "packaging dieline", "die-cut packaging", "label OCR", "document layout analysis",
    "product photography relighting", "image-based relighting",
    "multi-view stereo product", "single image to 3D", "diffusion product image",
    "e-commerce conversion", "advertising creative effectiveness",
    "click-through rate prediction", "A+ content", "listing optimization",
    "short-form video engagement", "marketing copy generation",
    "constrained decoding", "grammar-constrained generation", "agent memory",
    "knowledge graph memory", "retrieval augmented generation e-commerce",
    "synthetic product images", "background replacement",
    "table structure recognition", "nutrition label OCR",
    "product image generation", "visual merchandising", "consumer attention advertising",
    "packaging design automation", "brand compliance imaging",
    "document understanding transformer", "key information extraction receipts",
    "3D asset generation e-commerce", "virtual try-on product",
    "pricing promotion e-commerce", "recommendation explanation e-commerce",
    "conversational commerce", "review summarization e-commerce",
    "ad creative generation", "marketing mix modeling",
    "social media image engagement", "video ad retention",
    "prompt optimization multimodal", "small language model tool use",
    "function calling evaluation", "structured output generation",
    "retrieval reranking", "embedding compression", "vector search",
    "product taxonomy classification",
]

GFORUM_QUERIES = [
    "gemma", "function calling", "structured output", "embeddings", "litert",
    "mediapipe", "gemini api", "json schema", "tool use", "quantization",
    "fine-tuning", "grounding", "vision", "ocr", "ai edge",
]

YOUTUBE_CHANNELS = [
    "GoogleDeepMind", "GoogleAI", "HuggingFace", "StabilityAI",
    "BlackForestLabs", "ComfyUI", "aiDotEngineer", "mreflow", "WesRoth",
    "TheAIGRID", "Shopify", "HubSpotMarketing", "NeilPatel", "JonLoomer",
    "ThinkwithGoogle", "a16z",
]

GITHUB_QUERIES = [
    # niche extraction targets
    {"q": "topic:packaging", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:dieline", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:relighting", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:3d-generation", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:product-photography", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:image-editing", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:document-layout-analysis", "focus": "brain", "stars": 0, "pages": 3},
    {"q": "topic:table-recognition", "focus": "brain", "stars": 0, "pages": 3},
    {"q": "topic:agent-memory", "focus": "brain", "stars": 0, "pages": 3},
    {"q": "topic:ocr", "focus": "brain", "stars": 0, "pages": 3},
    {"q": "topic:constrained-decoding", "focus": "tys", "stars": 0, "pages": 3},
    {"q": "topic:advertising", "focus": "creative", "stars": 0, "pages": 3},
    # broader pools where the niche queries are thin
    {"q": "topic:image-generation", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:3d-reconstruction", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:document-ai", "focus": "brain", "stars": 0, "pages": 3},
    {"q": "topic:computer-vision", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:generative-ai", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:ecommerce", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:marketing", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:product-design", "focus": "creative", "stars": 0, "pages": 3},
    # supplemental within the 60-request GitHub budget (10 requests)
    {"q": "topic:local-llm", "focus": "bojo", "stars": 0, "pages": 3},
    {"q": "topic:retail", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:design-tools", "focus": "creative", "stars": 0, "pages": 3},
    {"q": "topic:3d-modeling", "focus": "creative", "stars": 0, "pages": 1},
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get(url: str, *, headers: Optional[Dict[str, str]] = None,
         timeout: int = 40, retries: int = 2) -> bytes:
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={**{"User-Agent": UA}, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except Exception:  # noqa: BLE001 - retry transient, then surface
            if attempt == retries:
                raise
            time.sleep(3)
    raise RuntimeError("unreachable")


def _append(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _done(path: Path) -> set:
    return set(_json(path, {"done": []}).get("done") or [])


def _mark(path: Path, key: str) -> None:
    data = _json(path, {"done": []})
    done = set(data.get("done") or [])
    done.add(key)
    _save(path, {"done": sorted(done), "updated_at": _now()})


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------

def scan_hf(limit: int = 50) -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / "hf.jsonl"
    done_path = RUN / "hf_done.json"
    done = _done(done_path)
    requests = added = 0
    plan = []
    for kind, queries in HF_QUERIES.items():
        for query in queries:
            plan.append((kind, query))
    for kind, query in plan:
        key = f"{kind}|{query}"
        if key in done or requests >= limit:
            continue
        params = urllib.parse.urlencode({
            "search": query, "limit": 100, "sort": "downloads",
            "direction": -1, "full": "false",
        })
        try:
            payload = json.loads(_get(f"https://huggingface.co/api/{kind}?{params}"))
        except Exception as exc:  # noqa: BLE001
            print(f"[hf] {kind} {query!r} failed: {exc}", flush=True)
            continue
        requests += 1
        for item in payload if isinstance(payload, list) else []:
            row = {
                "platform": "huggingface", "kind": kind, "id": item.get("id") or item.get("modelId"),
                "author": item.get("author"), "downloads": item.get("downloads"),
                "likes": item.get("likes"), "pipeline_tag": item.get("pipeline_tag"),
                "library": item.get("library_name"), "tags": item.get("tags") or [],
                "sha": item.get("sha"), "last_modified": item.get("lastModified"),
                "created_at": item.get("createdAt"), "gated": item.get("gated"),
                "query": query, "scanned_at": _now(),
            }
            lic = next((t.split(":", 1)[1] for t in row["tags"]
                        if isinstance(t, str) and t.startswith("license:")), "")
            row["licence"] = lic
            _append(out, row)
            added += 1
        _mark(done_path, key)
        print(f"[hf] {kind} {query!r}: {len(payload) if isinstance(payload, list) else 0} items", flush=True)
        time.sleep(0.4)
    summary = {"platform": "huggingface", "requests": requests, "rows": added,
               "queries": len(plan), "unique": _count_unique(out, "id"),
               "finished_at": _now()}
    _save(RUN / "hf_summary.json", summary)
    return summary


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

ATOM = "{http://www.w3.org/2005/Atom}"


def scan_arxiv(limit: int = 50) -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / "arxiv.jsonl"
    done_path = RUN / "arxiv_done.json"
    done = _done(done_path)
    requests = added = 0
    for query in ARXIV_QUERIES:
        if query in done or requests >= limit:
            continue
        q = urllib.parse.quote(f'all:"{query}"')
        url = (f"http://export.arxiv.org/api/query?search_query={q}"
               f"&start=0&max_results=50&sortBy=submittedDate&sortOrder=descending")
        try:
            root = ET.fromstring(_get(url, timeout=60))
        except Exception as exc:  # noqa: BLE001
            print(f"[arxiv] {query!r} failed: {exc}", flush=True)
            continue
        requests += 1
        for entry in root.findall(f"{ATOM}entry"):
            ident = (entry.findtext(f"{ATOM}id") or "").strip()
            row = {
                "platform": "arxiv", "id": ident.rsplit("/", 1)[-1],
                "title": " ".join((entry.findtext(f"{ATOM}title") or "").split()),
                "summary": " ".join((entry.findtext(f"{ATOM}summary") or "").split())[:1200],
                "published": entry.findtext(f"{ATOM}published"),
                "updated": entry.findtext(f"{ATOM}updated"),
                "authors": [a.findtext(f"{ATOM}name") for a in entry.findall(f"{ATOM}author")][:8],
                "categories": [c.get("term") for c in entry.findall(f"{ATOM}category")][:6],
                "url": ident, "query": query, "scanned_at": _now(),
            }
            _append(out, row)
            added += 1
        _mark(done_path, query)
        print(f"[arxiv] {query!r}: {len(root.findall(f'{ATOM}entry'))} papers", flush=True)
        time.sleep(3.1)  # arXiv API policy
    summary = {"platform": "arxiv", "requests": requests, "rows": added,
               "queries": len(ARXIV_QUERIES), "unique": _count_unique(out, "id"),
               "finished_at": _now()}
    _save(RUN / "arxiv_summary.json", summary)
    return summary


# ---------------------------------------------------------------------------
# Google AI Developers Forum (Discourse)
# ---------------------------------------------------------------------------

def scan_gforum(limit: int = 15) -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / "gforum.jsonl"
    done_path = RUN / "gforum_done.json"
    done = _done(done_path)
    requests = added = 0
    for query in GFORUM_QUERIES:
        if query in done or requests >= limit:
            continue
        url = "https://discuss.ai.google.dev/search.json?" + urllib.parse.urlencode({"q": query})
        try:
            payload = json.loads(_get(url))
        except Exception as exc:  # noqa: BLE001
            print(f"[gforum] {query!r} failed: {exc}", flush=True)
            continue
        requests += 1
        topics = {t.get("id"): t for t in payload.get("topics") or []}
        for post in payload.get("posts") or []:
            topic = topics.get(post.get("topic_id"), {})
            row = {
                "platform": "gforum", "query": query,
                "topic_id": post.get("topic_id"), "post_id": post.get("id"),
                "title": topic.get("title") or post.get("topic_title"),
                "slug": topic.get("slug"), "created_at": post.get("created_at"),
                "username": post.get("username"),
                "blurb": (post.get("blurb") or "")[:500],
                "url": (f"https://discuss.ai.google.dev/t/{topic.get('slug')}/{post.get('topic_id')}"
                        if topic.get("slug") else None),
                "scanned_at": _now(),
            }
            _append(out, row)
            added += 1
        _mark(done_path, query)
        print(f"[gforum] {query!r}: {len(payload.get('posts') or [])} posts", flush=True)
        time.sleep(1.0)
    summary = {"platform": "gforum", "requests": requests, "rows": added,
               "queries": len(GFORUM_QUERIES), "unique": _count_unique(out, "post_id"),
               "finished_at": _now()}
    _save(RUN / "gforum_summary.json", summary)
    return summary


# ---------------------------------------------------------------------------
# YouTube (public channel RSS)
# ---------------------------------------------------------------------------

def _channel_id(handle: str) -> Optional[str]:
    try:
        html = _get(f"https://www.youtube.com/@{handle}?hl=en",
                    headers={"User-Agent": BROWSER_UA,
                             "Accept-Language": "en-US,en;q=0.9"}, timeout=30).decode(
                                 "utf-8", "replace")
    except Exception:
        return None
    match = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', html)
    return match.group(1) if match else None


def scan_youtube(limit: int = 16) -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / "youtube.jsonl"
    done_path = RUN / "youtube_done.json"
    cache_path = RUN / "youtube_channels.json"
    cache = _json(cache_path, {})
    done = _done(done_path)
    channels = added = 0
    for handle in YOUTUBE_CHANNELS[:limit]:
        if handle in done:
            continue
        channel = cache.get(handle) or _channel_id(handle)
        if not channel:
            print(f"[youtube] @{handle}: channel id not found", flush=True)
            continue
        cache[handle] = channel
        _save(cache_path, cache)
        try:
            xml = _get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}")
            root = ET.fromstring(xml)
        except Exception as exc:  # noqa: BLE001
            print(f"[youtube] @{handle} RSS failed: {exc}", flush=True)
            continue
        ns = {"a": "http://www.w3.org/2005/Atom",
              "yt": "http://www.youtube.com/xml/schemas/2015"}
        for entry in root.findall("a:entry", ns):
            row = {
                "platform": "youtube", "channel_handle": handle,
                "channel_id": channel,
                "video_id": entry.findtext("yt:videoId", namespaces=ns),
                "title": entry.findtext("a:title", namespaces=ns),
                "published": entry.findtext("a:published", namespaces=ns),
                "updated": entry.findtext("a:updated", namespaces=ns),
                "url": entry.findtext("a:link", namespaces=ns) or None,
                "scanned_at": _now(),
            }
            for link in entry.findall("a:link", ns):
                if link.get("rel") == "alternate":
                    row["url"] = link.get("href")
            _append(out, row)
            added += 1
        _mark(done_path, handle)
        channels += 1
        print(f"[youtube] @{handle}: {len(root.findall('a:entry', ns))} videos", flush=True)
        time.sleep(0.8)
    summary = {"platform": "youtube", "channels": channels, "rows": added,
               "channels_total": len(YOUTUBE_CHANNELS),
               "unique": _count_unique(out, "video_id"), "finished_at": _now()}
    _save(RUN / "youtube_summary.json", summary)
    return summary


# ---------------------------------------------------------------------------
# GitHub (extraction-focused, reuses the scan client)
# ---------------------------------------------------------------------------

def scan_github(limit: int = 60) -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "tools"))
    import github_scan as gs  # noqa: WPS433

    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / "github.jsonl"
    done_path = RUN / "github_done.json"
    done = _done(done_path)
    requests = added = 0
    for query in GITHUB_QUERIES:
        key = query["q"]
        if key in done or requests >= limit:
            continue
        for page in range(1, int(query.get("pages") or 5) + 1):
            params = urllib.parse.urlencode({
                "q": f"{query['q']} stars:>={query['stars']} archived:false fork:false",
                "sort": "stars", "order": "desc", "per_page": 100, "page": page})
            try:
                payload = gs._request(f"https://api.github.com/search/repositories?{params}")
            except Exception as exc:  # noqa: BLE001
                print(f"[github] {key!r} page {page} failed: {exc}", flush=True)
                break
            requests += 1
            items = payload.get("items") or []
            for repo in items:
                if repo.get("archived") or repo.get("fork"):
                    continue
                row = gs._row(repo, {"q": query["q"], "focus": query["focus"]})
                row["platform"] = "github"
                row["extraction_focus"] = query["focus"]
                _append(out, row)
                added += 1
            print(f"[github] {key!r} p{page}: {len(items)}", flush=True)
            if len(items) < 100 or requests >= limit:
                break
            time.sleep(6.2)
        _mark(done_path, key)
        time.sleep(6.2)
    summary = {"platform": "github", "requests": requests, "rows": added,
               "queries": len(GITHUB_QUERIES),
               "unique": _count_unique(out, "full_name"), "finished_at": _now()}
    _save(RUN / "github_summary.json", summary)
    return summary


def _count_unique(path: Path, key: str) -> int:
    if not path.is_file():
        return 0
    seen = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get(key):
                seen.add(str(row[key]))
    return len(seen)


PLATFORMS = {"hf": scan_hf, "arxiv": scan_arxiv, "gforum": scan_gforum,
             "youtube": scan_youtube, "github": scan_github}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", choices=["all", *PLATFORMS], default="all")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    results = {}
    selected = PLATFORMS if args.platform == "all" else {args.platform: PLATFORMS[args.platform]}
    for name, fn in selected.items():
        print(f"== {name} ==", flush=True)
        try:
            results[name] = fn(args.limit) if args.limit else fn()
        except Exception as exc:  # noqa: BLE001 - one platform is not the pass
            results[name] = {"platform": name, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[{name}] failed: {exc}", flush=True)
    totals = {"platforms": results, "generated_at": _now()}
    totals["rows"] = sum(int((r or {}).get("rows") or 0) for r in results.values())
    totals["unique"] = sum(int((r or {}).get("unique") or 0) for r in results.values())
    _save(RUN / "summary.json", totals)
    print(json.dumps(totals, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
