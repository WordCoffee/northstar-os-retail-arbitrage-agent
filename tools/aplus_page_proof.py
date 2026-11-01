"""Live proof: render a full A+ page from an existing finished mockup.

Run from the repo root:  python tools/aplus_page_proof.py
Writes real, upload-sized assets under renders/aplus_live_<date>/ and prints the
measured QA for each module. No provider call, no spend, no browser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import aplus_render as ar  # noqa: E402

PLATE = ROOT / "renders" / "mogra-forest-dusk-mockup-complete.png"
OUT = ROOT / "renders" / "aplus_live_20261031"

BRAND = {"field": "#F4F0E6", "ink": "#1E3A2F", "accent": "#A8894F"}

COPY = {
    "headline": "Lion's Mane, Grown Slow",
    "sub": "Organic mushroom powder, 6 oz (170 g)",
    "kicker": "Mogra Organics",
}

MODULES = [
    {"kind": "header", "copy": COPY},
    {"kind": "three_tiles",
     "copy": {"tiles": ["Whole fruiting body", "Cold-milled, never heated",
                        "Third-party tested"]}},
    {"kind": "banner", "copy": {"headline": "One ingredient. Nothing else.",
                                "sub": "No fillers, no carriers, no sweeteners",
                                "kicker": "The label, read closely"}},
    {"kind": "four_tiles",
     "copy": {"tiles": ["Vegan", "6 oz", "Resealable", "Batch dated"]}},
    {"kind": "comparison", "copy": {
        "headline": "Compare the range",
        "columns": ["Lion's Mane", "Shiitake"],
        "rows": [{"label": "Organic", "values": ["yes", "yes"]},
                 {"label": "Fruiting body only", "values": ["yes", "no"]},
                 {"label": "Net weight", "values": ["6 oz", "4 oz"]}]}},
    {"kind": "logo", "copy": {"brand": "Mogra Organics"}},
]


def main() -> int:
    if not PLATE.is_file():
        print(f"plate not found: {PLATE}")
        return 2
    page = ar.render_page(MODULES, brand=BRAND, image=PLATE, tiles=[PLATE], out_dir=OUT)
    print(json.dumps({"ok": page["ok"], "problems": page["problems"][:8],
                      "bytes_total": page["bytes_total"],
                      "preview": page["preview"]}, indent=2))
    for m in page["modules"]:
        print(f'{m["index"]:02d} {m["kind"]:<14} {m["size"]} {m["bytes"]:>8} B  '
              f'copy={m["copy_mode"]:<6} contrast={m["qa"]["min_contrast"]} '
              f'warnings={m["qa"]["warnings"]}')
    return 0 if page["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
