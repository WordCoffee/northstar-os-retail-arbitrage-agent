"""Extract repository references from Marco Kaz shorts transcripts.

Input:  shorts_meta.tsv (id, title, description) + subs/<id>.en.vtt
Output: repos_found.jsonl  (one row per video that mentions a repo/URL)
        mentions.csv       (flat: video id, title, kind, value)

No network. Pure text extraction, so every claim is traceable to a caption line.

Usage: python extract_repos.py [--grep "github|repo"]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
SUBS = HERE / "subs"

TIMING = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
TAGS = re.compile(r"<[^>]+>")
URL = re.compile(r"https?://[^\s<>\"']+")
GH = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
#: "it's called X", "the repo is X", "search X on github"
CALLED = re.compile(
    r"(?:called|named|search (?:for )?|repo(?:sitory)? is|project is)\s+"
    r"([A-Za-z0-9][A-Za-z0-9 ._+-]{1,40})",
    re.IGNORECASE,
)
KEYWORDS = ("github", "repo", "open source", "open-source", "star")


def clean_vtt(path: Path) -> str:
    """Auto-captions roll: consecutive lines repeat. Keep first occurrence of a run."""
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("WEBVTT") or TIMING.match(line) or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        line = TAGS.sub("", line).strip()
        if not line:
            continue
        if out and (line == out[-1] or line in out[-1] or out[-1] in line):
            # rolling caption overlap: keep the longer of the two
            if len(line) > len(out[-1]):
                out[-1] = line
            continue
        out.append(line)
    return " ".join(out)


def load_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    meta = HERE / "shorts_meta.tsv"
    if not meta.exists():
        return titles
    for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip():
            titles[parts[0].strip()] = parts[1].strip()
    return titles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep", default="", help="only show rows whose transcript matches this regex")
    args = ap.parse_args()
    only = re.compile(args.grep, re.IGNORECASE) if args.grep else None

    titles = load_titles()
    rows: list[dict] = []
    flat: list[dict] = []

    for vtt in sorted(SUBS.glob("*.en.vtt")):
        vid = vtt.name.split(".")[0]
        text = clean_vtt(vtt)
        if not text:
            continue
        title = titles.get(vid, "")
        if only and not only.search(text + " " + title):
            continue

        urls = sorted({u.rstrip(".,);]") for u in URL.findall(text)})
        gh = sorted({f"{m[0]}/{m[1]}" for m in GH.findall(text)})
        called = []
        for m in CALLED.finditer(text):
            cand = m.group(1).strip(" .,")
            # drop sentence tails: keep at most 4 words, must look like a name
            words = cand.split()
            cand = " ".join(words[:4])
            if len(cand) >= 3:
                called.append(cand)

        hits = [s for s in re.split(r"(?<=[.!?])\s+", text) if any(k in s.lower() for k in KEYWORDS)]

        row = {
            "id": vid,
            "title": title,
            "urls": urls,
            "github": gh,
            "called": called[:12],
            "repo_lines": hits[:8],
            "chars": len(text),
        }
        rows.append(row)
        for kind, values in (("url", urls), ("github", gh), ("called", called[:12])):
            for v in values:
                flat.append({"id": vid, "title": title, "kind": kind, "value": v})

    (HERE / "repos_found.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    with (HERE / "mentions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "title", "kind", "value"])
        w.writeheader()
        w.writerows(flat)

    with_url = sum(1 for r in rows if r["github"])
    print(f"videos parsed: {len(rows)}  with github url: {with_url}  mentions: {len(flat)}")
    for r in rows:
        if r["github"]:
            print(f"  {r['id']}  {r['title'][:58]:58}  {', '.join(r['github'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
