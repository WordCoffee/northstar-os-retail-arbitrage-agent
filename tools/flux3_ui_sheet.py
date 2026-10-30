"""Contact sheet for the ten FLUX 3 interface comps.

    python tools/flux3_ui_sheet.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "theme_review" / "flux"
CELL_W, LABEL_H, GAP, COLS = 760, 56, 18, 2

NAMES = [
    ("01-command-deck", "Command Deck", "Dense mission control: icon rail, six service tabs, hero hole, telemetry column"),
    ("02-split-cockpit", "Split Cockpit", "Three columns over a face-on spiral. Frosted glass, teal accent, inspector panel"),
    ("03-bento-services", "Bento Services", "Twelve rounded service tiles on starfield; edge-on galaxy across the lower third"),
    ("04-terminal-observatory", "Terminal Observatory", "Monospace log stream, hairline charts, one photon ring. Almost no chrome"),
    ("05-full-bleed-cinema", "Full Bleed Cinema", "No panels. Serif headline, one input bar, poster composition"),
    ("06-orbital-map", "Orbital Map", "Radial diagram, eight service nodes on concentric orbits. Indigo and pearl"),
    ("07-chat-first", "Chat First", "Single conversation column, large composer, nebula bleeding in from the right"),
    ("08-editorial-atlas", "Editorial Atlas", "Magazine layout: serif headline, narrow column, framed galaxy plate, gold rule"),
    ("09-mission-board", "Mission Board", "Kanban, five columns, rust nebula and a small hole low right. Operational"),
    ("10-glass-layers", "Glass Layers", "Three overlapping frosted panels, galaxies blurred through them. Magenta bokeh"),
]


def font(size: int, bold: bool = False):
    for name in (("Inter-Bold.ttf",) if bold else ("Inter-Regular.ttf",)):
        for base in (ROOT / "assets" / "fonts", ROOT / "northstar-os-ui" / "src" / "assets" / "fonts"):
            p = base / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass
    return ImageFont.load_default()


def main() -> int:
    manifest_path = SRC / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    cells = []
    for stem, name, note in NAMES:
        p = SRC / f"{stem}.png"
        if not p.exists():
            continue
        img = Image.open(p).convert("RGB")
        ratio = CELL_W / img.width
        meta = manifest.get(stem.split("-", 1)[1], {})
        cells.append((img.resize((CELL_W, int(img.height * ratio)), Image.LANCZOS), name, note, meta))

    if not cells:
        raise SystemExit("no flux comps found")

    cell_h = cells[0][0].height + LABEL_H
    rows = (len(cells) + COLS - 1) // COLS
    sheet = Image.new(
        "RGB",
        (COLS * CELL_W + (COLS + 1) * GAP, rows * cell_h + (rows + 1) * GAP),
        (6, 8, 14),
    )
    draw = ImageDraw.Draw(sheet)
    f_name, f_note, f_meta = font(20, bold=True), font(13), font(12)

    for i, (img, name, note, meta) in enumerate(cells):
        col, row = i % COLS, i // COLS
        x = GAP + col * (CELL_W + GAP)
        y = GAP + row * (cell_h + GAP)
        sheet.paste(img, (x, y))
        ty = y + img.height + 7
        draw.text((x + 3, ty), f"{i + 1}. {name}", font=f_name, fill=(240, 236, 228))
        draw.text((x + 3, ty + 25), note, font=f_note, fill=(150, 158, 174))
        if meta.get("seed"):
            draw.text(
                (x + 3, ty + 40),
                f"seed {meta['seed']} · {meta.get('steps', '?')} steps · {meta.get('seconds', '?')}s",
                font=f_meta,
                fill=(104, 112, 128),
            )

    out = SRC / "UI_SHEET.png"
    sheet.save(out, "PNG", optimize=True)
    print(json.dumps({"out": str(out), "size": f"{sheet.width}x{sheet.height}", "count": len(cells)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
