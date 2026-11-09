"""Source-next-to-output sheet for the deterministic layout bench.

Each row is one brief: the seller's reference on the left, what the pipeline produced on the right,
with the brief, the situation and the measured score between them. The point of the sheet is that a
reviewer can see whether the page furniture landed where the brief asked and whether the artwork is
still the seller's — without opening a JSON file.

    python tools/layout_demo_sheet.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "layout_demo_proof.json"
BRIEFS = ROOT / "ty" / "seller_briefs_layout_demo.json"
OUT = ROOT / "reports" / "ty" / "layout_demo_source_next_to_output.png"


def _rows() -> List[Dict[str, Any]]:
    proof = json.loads(PROOF.read_text(encoding="utf-8")) if PROOF.exists() else {}
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"] if BRIEFS.exists() else []
    by_id = {brief["id"]: brief for brief in briefs}
    rows: List[Dict[str, Any]] = []
    for result in proof.get("results") or []:
        brief = by_id.get(str(result.get("brief_id"))) or {}
        source = ((brief.get("reference") or {}).get("path") or "")
        output = str(result.get("artefact_path") or "")
        rows.append({
            "brief_id": result.get("brief_id"),
            "situation": brief.get("situation") or result.get("situation"),
            "score": result.get("score"),
            "passed": result.get("passed"),
            "failed": result.get("failed_checks") or [],
            "source": source,
            "output": output,
            "source_ok": bool(source) and (ROOT / source).is_file(),
            "output_ok": bool(output) and (ROOT / output).is_file(),
            "layout": (result.get("layout") or {}).get("kind"),
        })
    return rows


def sheet(target: Optional[Path] = None, *, tile: int = 520) -> Optional[Path]:
    from PIL import Image, ImageDraw, ImageFont

    rows = [row for row in _rows() if row["source_ok"] and row["output_ok"]]
    if not rows:
        return None
    try:
        font = ImageFont.truetype("segoeui.ttf", 18)
        small = ImageFont.truetype("segoeui.ttf", 15)
    except OSError:  # pragma: no cover - a machine without the font still gets a sheet
        font = ImageFont.load_default()
        small = font
    header = 34
    canvas = Image.new("RGB", (tile * 2 + 24, (tile + header + 26) * len(rows)), "#f6f3ec")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), "source (the upload)", fill="#1b2a22", font=font)
    draw.text((tile + 20, 6), "output (deterministic layout)", fill="#1b2a22", font=font)
    for index, row in enumerate(rows):
        top = header + index * (tile + header + 26)
        for column, path in enumerate((row["source"], row["output"])):
            with Image.open(ROOT / path) as image:
                thumb = image.convert("RGB")
                thumb.thumbnail((tile - 10, tile - 10))
            canvas.paste(thumb, (8 + column * (tile + 12), top + 4))
        caption = (f"{row['brief_id']}  {row['situation']}  "
                   f"score {row['score']}  {'pass' if row['passed'] else 'fail'}")
        if row["failed"]:
            caption += "  failed: " + ", ".join(row["failed"])
        draw.text((8, top + tile - 4), caption, fill="#1b2a22", font=small)
    destination = Path(target or OUT)
    canvas.save(destination)
    return destination


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Layout demo sheet")
    parser.add_argument("--out", type=Path, default=None)
    ns = parser.parse_args(argv)
    path = sheet(ns.out)
    print(json.dumps({"sheet": str(path) if path else None,
                      "rows": len(_rows()),
                      "pairs": sum(1 for r in _rows() if r["source_ok"] and r["output_ok"])},
                     indent=2))
    return 0 if path else 1


if __name__ == "__main__":
    raise SystemExit(main())
