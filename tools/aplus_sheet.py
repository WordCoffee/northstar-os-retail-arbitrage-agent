"""Six A+ pages, source next to output, for the digest.

An A+ page is the unit a seller reviews: the module stack as it will appear on the product page. The
sheet pairs each page with the seller's own reference image, because the only question that matters
is "is this the right product, laid out well" — and that needs both halves.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "aplus_proof.json"
CATALOG = ROOT / "ty" / "seller_briefs.json"
OUT = ROOT / "reports" / "ty" / "aplus_source_next_to_output.png"


def rows() -> List[dict]:
    proof = json.loads(PROOF.read_text(encoding="utf-8")) if PROOF.exists() else {}
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {}
    by_id = {brief.get("id"): brief for brief in catalog.get("aplus_briefs") or []}
    out = []
    # The proof stores `briefs`, each with `page_path` and its own reference_path; the first version
    # read `results` and produced an empty sheet without saying why.
    for row in proof.get("briefs") or []:
        brief = by_id.get(row.get("brief_id")) or {}
        source = str(row.get("reference_path") or
                     ((brief.get("reference") or {}).get("path")) or "")
        page = str(row.get("page_path") or "")
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        out.append({"brief": row.get("brief_id"),
                    "content_type": row.get("content_type"),
                    "brand": brief.get("product_line") or "mogra",
                    "score": row.get("score"),
                    "modules": f"{row.get('module_pass_count')}/{row.get('module_count_total')}",
                    "passed": row.get("passed"),
                    "source": str(source_path), "page": page,
                    "ok": source_path.is_file() and bool(page) and (ROOT / page).is_file()})
    return [row for row in out if row["ok"]]


def sheet(target: Optional[Path] = None, *, limit: int = 6, tile: int = 520) -> Optional[Path]:
    from PIL import Image, ImageDraw, ImageFont

    picked, seen = [], set()
    for row in rows():
        if row["brand"] in seen and len(picked) < limit:
            continue
        picked.append(row)
        seen.add(row["brand"])
        if len(picked) >= limit:
            break
    for row in rows():
        if len(picked) >= limit:
            break
        if row not in picked:
            picked.append(row)
    if not picked:
        return None
    try:
        font = ImageFont.truetype("segoeui.ttf", 17)
        small = ImageFont.truetype("segoeui.ttf", 14)
    except OSError:
        font = small = ImageFont.load_default()
    header = 32
    canvas = Image.new("RGB", (tile * 2 + 24, (tile + header + 24) * len(picked)), "#f6f3ec")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), "source (the upload)", fill="#1b2a22", font=font)
    draw.text((tile + 20, 6), "A+ page (deterministic modules)", fill="#1b2a22", font=font)
    for index, row in enumerate(picked):
        top = header + index * (tile + header + 24)
        for column, path in enumerate((row["source"], row["page"])):
            with Image.open(ROOT / path) as image:
                thumb = image.convert("RGB")
                thumb.thumbnail((tile - 10, tile - 10))
            canvas.paste(thumb, (8 + column * (tile + 12), top + 4))
        caption = (f"{row['brief']}  {row['content_type']}  {row['brand']}  "
                   f"score {row['score']}  modules {row['modules']}")
        draw.text((8, top + tile - 6), caption, fill="#1b2a22", font=small)
    destination = Path(target or OUT)
    canvas.save(destination)
    return destination


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A+ source-next-to-output sheet")
    parser.add_argument("--out", type=Path, default=None)
    ns = parser.parse_args(argv)
    path = sheet(ns.out)
    print(json.dumps({"sheet": str(path) if path else None,
                      "pairs": len(rows())}, indent=2))
    return 0 if path else 1


if __name__ == "__main__":
    raise SystemExit(main())
