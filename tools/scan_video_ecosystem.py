"""Scan GitHub + Hugging Face for open video-generation tooling.

Purpose: find what could improve our 5-10 second ad-clip pipeline on a 16 GB
laptop GPU (local) and in production (cloud). Nothing here is executed or
installed; this only inventories the ecosystem and records honest counts.

Usage:
  python tools/scan_video_ecosystem.py                # targeted pass
  python tools/scan_video_ecosystem.py --wide         # + broad paginated pass
  python tools/scan_video_ecosystem.py --skip-github  # HF only

Outputs (reports/video_scan/):
  github.jsonl       one row per repo
  huggingface.jsonl  one row per model
  meta.json          counts, queries, rate-limit state, timestamps

GitHub unauthenticated search is capped at 10 requests/minute and 60/hour, so
the scan stops cleanly at the budget and records what it could not reach
instead of pretending the list is complete. `gh auth login` raises that to
30 requests/minute and makes a 20k-repo GitHub sweep practical.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "video_scan"
OUT.mkdir(parents=True, exist_ok=True)

UA = "northstar-video-scan/1.0 (+local research)"
GITHUB_PAGES = 3          # 100 per page -> up to 300 repos per query
GITHUB_PACE_S = 6.6       # unauth search budget: 10 requests/minute
HTTP_TIMEOUT = 40

GH_QUERIES = [
    "video generation model", "text-to-video", "image-to-video", "video diffusion",
    "text to video in:name", "i2v in:name,description", "t2v in:name,description",
    "wan video", "hunyuanvideo", "cogvideox", "animatediff",
    "stable video diffusion", "ltx-video", "mochi video", "open-sora",
    "framepack", "video generation comfyui", "comfyui video nodes",
    "video interpolation rife", "video upscale model", "short video generator",
    "product video ai", "video captioning model", "ai video editor open source",
    "temporal consistency video diffusion", "camera motion video generation",
    "video generation lora", "video generation benchmark",
]

HF_QUERIES = [
    "video", "video-generation", "text-to-video", "image-to-video",
    "wan", "wan2.1", "wan2.2", "hunyuanvideo", "cogvideox", "animatediff",
    "stable-video-diffusion", "ltx-video", "mochi", "open-sora", "framepack",
    "svd", "i2v", "t2v", "vace", "skyreels", "allegro", "veo", "kling",
    "video-upscale", "rife", "film interpolation", "video caption",
]

# Breadth pass: broad terms exist only to widen recall past the 1,000-per-query
# cap. They are noisy by design; ranking happens afterwards.
HF_BROAD = ["video", "animation", "motion", "temporal", "frames", "clip",
            "video diffusion", "video vae", "camera", "depth video"]

HF_PIPELINE_TAGS = [
    "text-to-video", "image-to-video", "video-to-video",
    "video-classification", "unconditional-image-generation",
]

HF_SEARCH_LIMIT = 1000


def http_json(url: str, timeout: int = HTTP_TIMEOUT) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return json.loads(body), {k.lower(): v for k, v in resp.headers.items()}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_link(hdrs: dict) -> str | None:
    link = hdrs.get("link") or ""
    if 'rel="next"' not in link:
        return None
    try:
        return link.split("<", 1)[1].split(">", 1)[0]
    except IndexError:
        return None


def scan_github(meta: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    calls = 0
    for q in GH_QUERIES:
        for page in range(1, GITHUB_PAGES + 1):
            url = ("https://api.github.com/search/repositories"
                   f"?q={urllib.parse.quote(q)}&sort=stars&order=desc"
                   f"&per_page=100&page={page}")
            try:
                data, hdr = http_json(url)
            except urllib.error.HTTPError as exc:
                meta["github_stop"] = f"HTTP {exc.code} on '{q}' page {page}"
                print(f"  [gh] stop: {meta['github_stop']}", flush=True)
                return rows
            except Exception as exc:  # noqa: BLE001 - a scan never dies on one query
                print(f"  [gh] skip '{q}' p{page}: {exc}", flush=True)
                break
            calls += 1
            items = (data.get("items") if isinstance(data, dict) else None) or []
            for it in items:
                full = str(it.get("full_name") or "")
                if not full or full.lower() in seen:
                    continue
                seen.add(full.lower())
                rows.append({
                    "source": "github", "id": full, "url": it.get("html_url"),
                    "description": it.get("description") or "",
                    "stars": it.get("stargazers_count") or 0,
                    "forks": it.get("forks_count") or 0,
                    "language": it.get("language"),
                    "license": ((it.get("license") or {}) or {}).get("spdx_id"),
                    "topics": it.get("topics") or [],
                    "pushed_at": it.get("pushed_at"),
                    "created_at": it.get("created_at"),
                    "archived": bool(it.get("archived")), "queries": [q],
                })
            remaining = hdr.get("x-ratelimit-remaining")
            print(f"  [gh] {q!r} p{page}: {len(items)} items "
                  f"(total {len(rows)}, remaining {remaining})", flush=True)
            if not items or len(items) < 100:
                break
            if remaining is not None and int(remaining) <= 1:
                meta["github_stop"] = "hourly search budget exhausted"
                print("  [gh] hourly budget exhausted", flush=True)
                return rows
            time.sleep(GITHUB_PACE_S)
    meta["github_calls"] = calls
    return rows


def _hf_row(m: dict) -> dict:
    return {
        "source": "huggingface", "id": m.get("id") or m.get("modelId"),
        "url": "https://huggingface.co/" + str(m.get("id") or ""),
        "downloads": m.get("downloads") or 0, "likes": m.get("likes") or 0,
        "pipeline_tag": m.get("pipeline_tag"), "tags": m.get("tags") or [],
        "license": next((str(t).split(":", 1)[1] for t in (m.get("tags") or [])
                         if str(t).startswith("license:")), None),
        "created_at": m.get("createdAt"), "last_modified": m.get("lastModified"),
        "gated": m.get("gated"), "library": m.get("library_name"),
    }


def scan_hf(meta: dict, *, wide: bool, seen: set[str], existing: int) -> list[dict]:
    rows: list[dict] = []
    calls = 0
    queries = [(q, HF_SEARCH_LIMIT) for q in HF_QUERIES]
    if wide:
        # Broad terms get paginated; narrow ones almost never exceed one page.
        queries = queries + [(q, 8) for q in HF_BROAD]
    for q, pages in queries:
        url = ("https://huggingface.co/api/models"
               f"?search={urllib.parse.quote(q)}&limit={HF_SEARCH_LIMIT}"
               "&sort=downloads&direction=-1")
        for page in range(pages):
            try:
                data, hdr = http_json(url)
                calls += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  [hf] skip {q!r} p{page + 1}: {exc}", flush=True)
                break
            batch = data if isinstance(data, list) else []
            added = 0
            for m in batch:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id") or m.get("modelId")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                rows.append(_hf_row(m))
                added += 1
            print(f"  [hf] {q!r} p{page + 1}: {len(batch)} found, {added} new "
                  f"(running {existing + len(rows)})", flush=True)
            url = _next_link(hdr)
            if not url or len(batch) < HF_SEARCH_LIMIT:
                break
    for tag in HF_PIPELINE_TAGS:
        url = (f"https://huggingface.co/api/models?pipeline_tag={tag}"
               f"&limit={HF_SEARCH_LIMIT}&sort=downloads&direction=-1")
        try:
            data, _ = http_json(url)
            calls += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [hf] skip tag {tag!r}: {exc}", flush=True)
            continue
        added = 0
        for m in (data if isinstance(data, list) else []):
            if not isinstance(m, dict):
                continue
            mid = m.get("id") or m.get("modelId")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            rows.append(_hf_row(m))
            added += 1
        print(f"  [hf] pipeline_tag={tag}: {added} new "
              f"(running {existing + len(rows)})", flush=True)
        time.sleep(0.3)
    meta["hf_calls"] = calls
    return rows


def _read_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id"):
                ids.add(str(row["id"]))
    return ids


def _append(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    wide = "--wide" in argv
    skip_github = "--skip-github" in argv
    hf_path = OUT / "huggingface.jsonl"
    gh_path = OUT / "github.jsonl"
    seen_hf = _read_ids(hf_path)
    existing_hf = len(seen_hf)
    seen_gh = _read_ids(gh_path)
    existing_gh = len(seen_gh)

    meta: dict = {"started": now(), "wide": wide,
                  "github_queries": 0 if skip_github else len(GH_QUERIES),
                  "hf_queries": len(HF_QUERIES) + (len(HF_BROAD) if wide else 0)
                  + len(HF_PIPELINE_TAGS),
                  "pre_existing": {"github": existing_gh, "huggingface": existing_hf}}

    if not skip_github:
        print("GitHub scan (unauthenticated: 10/min, 60/hour)...", flush=True)
        gh = scan_github(meta)
        new_gh = [r for r in gh if str(r["id"]).lower() not in {x.lower() for x in seen_gh}]
        _append(gh_path, new_gh)
        print(f"GitHub: +{len(new_gh)} new", flush=True)

    print("Hugging Face scan...", flush=True)
    hf = scan_hf(meta, wide=wide, seen=seen_hf, existing=existing_hf)
    _append(hf_path, hf)
    print(f"Hugging Face: +{len(hf)} new", flush=True)

    meta.update({
        "finished": now(),
        "github_new": 0 if skip_github else len(new_gh),
        "hf_new": len(hf),
        "totals": {"github": existing_gh + (0 if skip_github else len(new_gh)),
                   "huggingface": existing_hf + len(hf)},
    })
    meta["totals"]["all"] = meta["totals"]["github"] + meta["totals"]["huggingface"]
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
