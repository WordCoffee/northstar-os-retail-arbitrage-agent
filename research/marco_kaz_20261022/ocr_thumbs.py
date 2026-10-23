"""OCR Marco Kaz short thumbnails and pull GitHub repo references out of them.

Thumbnails carry the repo URL as on-screen text; captions do not. RapidOCR runs
fully offline (onnxruntime), so nothing leaves the machine.

Outputs (next to this file):
  thumbs_ocr.csv   id, text           -- every OCR line, joined
  thumbs_gh.csv    id, raw, owner, repo, confident

Usage: python ocr_thumbs.py [--limit N] [--show ID]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
THUMBS = HERE / "thumbs"

#: tolerant of OCR punctuation/spacing: "github com /owner/repo", "github.com/0wner/repo"
GH = re.compile(
    r"github\s*[.,:;]?\s*com\s*[/\\|]\s*([A-Za-z0-9_.\-]{2,40})\s*[/\\|]\s*([A-Za-z0-9_.\-]{2,60})",
    re.IGNORECASE,
)
#: fallback: a bare "owner/repo" token sitting near the word github
BARE = re.compile(r"(?<![\w/])([A-Za-z0-9][\w.\-]{1,38})/([A-Za-z0-9][\w.\-]{1,50})(?![\w/])")


def clean(repo: str) -> str:
    return repo.rstrip(".,;:)]}'\"|").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--show", default="")
    args = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR  # imported late: slow model load

    engine = RapidOCR()
    images = sorted(THUMBS.glob("*.jpg"))
    if args.limit:
        images = images[: args.limit]

    rows: list[dict] = []
    hits: list[dict] = []

    for i, img in enumerate(images, 1):
        vid = img.stem
        try:
            result, _ = engine(str(img))
        except Exception as exc:  # noqa: BLE001 - one bad image must not stop the sweep
            rows.append({"id": vid, "text": f"__OCR_ERROR__ {exc}"})
            continue
        text = " | ".join(line[1] for line in (result or []))
        rows.append({"id": vid, "text": text})

        found = []
        for m in GH.finditer(text):
            found.append(("url", m.group(0), clean(m.group(1)), clean(m.group(2))))
        if not found and "github" in text.lower():
            for m in BARE.finditer(text):
                if m.group(1).lower() not in {"github", "http", "https", "www"}:
                    found.append(("bare", m.group(0), m.group(1), clean(m.group(2))))
        for kind, raw, owner, repo in found:
            hits.append({"id": vid, "raw": raw, "owner": owner, "repo": repo,
                         "confident": "yes" if kind == "url" else "check"})

        if args.show and vid == args.show:
            print(f"== {vid}\n{text}\n")
        if i % 25 == 0:
            print(f"  ... {i}/{len(images)}", flush=True)

    with (HERE / "thumbs_ocr.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "text"])
        w.writeheader()
        w.writerows(rows)
    with (HERE / "thumbs_gh.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "raw", "owner", "repo", "confident"])
        w.writeheader()
        w.writerows(hits)

    uniq = sorted({f"{h['owner']}/{h['repo']}" for h in hits})
    print(f"images: {len(rows)}  hits: {len(hits)}  unique repos: {len(uniq)}")
    for r in uniq:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
