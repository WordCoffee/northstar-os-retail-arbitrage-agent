"""Rank the scanned Hugging Face inventory for our 5-10 second clip pipeline.

Reads reports/video_scan/huggingface.jsonl (no network) and writes a markdown
ranking to reports/video_scan/analysis.md. Ranking is by adoption signals only
(downloads, likes, recency); capability claims are NOT made here — those are
verified by running a model, never by reading its filename.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "reports" / "video_scan" / "huggingface.jsonl"
OUT = ROOT / "reports" / "video_scan" / "analysis.md"

GEN_TAGS = {"text-to-video", "image-to-video", "video-to-video"}
GEN_WORDS = (
    "t2v", "i2v", "v2v", "text2video", "img2video", "image2video",
    "wan2", "wan-2", "wan2.1", "wan2.2", "hunyuanvideo", "cogvideo",
    "ltx-video", "ltxvideo", "mochi", "open-sora", "opensora", "animatediff",
    "stable-video-diffusion", "stable_video_diffusion", "svd", "framepack",
    "vace", "skyreels", "allegro", "seedance", "hailuo", "minimax",
)
# Things that mention video but do not generate clips.
NOISE = (
    "videomae", "video-classification", "video_classification", "videoclip",
    "clip-vit", "siglip", "whisper", "wav2vec", "videollama", "video-llava",
    "qwen2-vl", "llava", "internvideo", "videomamba", "x-clip", "clip_",
    "video-retrieval", "video-caption", "video_class", "videogpt",
)
AUX_WORDS = ("vae", "interpolat", "rife", "upscal", "super-resolution",
             "super_resolution", "tokenizer", "text-encoder", "text_encoder",
             "caption", "lora", "controlnet", "ip-adapter", "ipadapter")


def load() -> list[dict]:
    rows: list[dict] = []
    with SCAN.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def kind(row: dict) -> str:
    rid = str(row.get("id") or "").lower()
    tag = str(row.get("pipeline_tag") or "").lower()
    tags = " ".join(str(t) for t in (row.get("tags") or [])).lower()
    blob = f"{rid} {tags}"
    if any(n in blob for n in NOISE):
        return "noise"
    if any(a in rid for a in ("lora", "controlnet", "ip-adapter", "ipadapter")):
        return "adapter"
    if any(a in rid for a in ("vae", "interpolat", "rife", "upscal", "super-resolution",
                              "tokenizer", "text_encoder", "text-encoder")):
        return "aux"
    if tag in GEN_TAGS or any(w in blob for w in GEN_WORDS):
        return "generation"
    if "caption" in rid or "describe" in rid:
        return "understanding"
    return "other"


def fmt(row: dict) -> str:
    rid = row.get("id")
    dl = row.get("downloads") or 0
    likes = row.get("likes") or 0
    tag = row.get("pipeline_tag") or "-"
    lic = row.get("license") or "-"
    mod = str(row.get("last_modified") or "")[:10]
    return f"| `{rid}` | {dl:,} | {likes:,} | {tag} | {lic} | {mod} |"


def top(rows: list[dict], n: int = 25, *, pred=None) -> list[dict]:
    sel = [r for r in rows if (pred is None or pred(r))]
    return sorted(sel, key=lambda r: (r.get("downloads") or 0, r.get("likes") or 0),
                  reverse=True)[:n]


def main() -> int:
    rows = load()
    kinds = Counter(kind(r) for r in rows)
    tags = Counter(str(r.get("pipeline_tag") or "none") for r in rows)
    lines = [
        "# Video-ecosystem scan — ranking",
        "",
        f"Inventory: **{len(rows):,} Hugging Face models** "
        "(GitHub rows are in `github.jsonl`; the unauthenticated search budget "
        "blocked a full repo sweep).",
        "",
        "## Composition",
        "",
        "| class | count |",
        "|---|---|",
    ]
    for k, v in kinds.most_common():
        lines.append(f"| {k} | {v:,} |")
    lines += ["", "| pipeline_tag | count |", "|---|---|"]
    for k, v in tags.most_common(12):
        lines.append(f"| `{k}` | {v:,} |")

    gen = [r for r in rows if kind(r) == "generation"]
    lines += ["", f"## Generation models ({len(gen):,}) — top by downloads", "",
              "| model | downloads | likes | tag | licence | updated |",
              "|---|---|---|---|---|---|"]
    lines += [fmt(r) for r in top(gen, 30)]

    i2v = [r for r in gen if "image-to-video" == str(r.get("pipeline_tag") or "")
           or "i2v" in str(r.get("id") or "").lower()]
    lines += ["", "### Image-to-video (animate our product stills)", "",
              "| model | downloads | likes | tag | licence | updated |",
              "|---|---|---|---|---|---|"]
    lines += [fmt(r) for r in top(i2v, 25)]

    small = [r for r in gen if re.search(
        r"(2b|1\.3b|0\.9b|tiny|small|lite|distill|gguf|fp8|int4|q4|q8)",
        str(r.get("id") or "").lower())]
    lines += ["", "### Small / quantised / distilled (16 GB candidates)", "",
              "| model | downloads | likes | tag | licence | updated |",
              "|---|---|---|---|---|---|"]
    lines += [fmt(r) for r in top(small, 25)]

    aux = [r for r in rows if kind(r) == "aux"]
    lines += ["", f"## Support models ({len(aux):,}) — top by downloads", "",
              "| model | downloads | likes | tag | licence | updated |",
              "|---|---|---|---|---|---|"]
    lines += [fmt(r) for r in top(aux, 20)]

    adapters = [r for r in rows if kind(r) == "adapter"]
    lines += ["", f"## Adapters / LoRAs ({len(adapters):,}) — top by downloads", "",
              "| model | downloads | likes | tag | licence | updated |",
              "|---|---|---|---|---|---|"]
    lines += [fmt(r) for r in top(adapters, 20)]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
