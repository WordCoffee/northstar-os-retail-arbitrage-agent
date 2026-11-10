"""Render every Galactic variant's scene, unobstructed, into one sheet.

The UI contact sheet shows what the operator gets with the chrome on top. This
one shows the art underneath — the same shader, the same uniforms, no panel.

Variant parameters are read from the shipped JS module via node, so this cannot
drift from what the app renders.

    C:\\Users\\T2Hol\\ComfyUI\\venv\\Scripts\\python.exe tools\\galactic_scene_sheet.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "theme_review" / "scenes"
PY = Path(r"C:\Users\T2Hol\ComfyUI\venv\Scripts\python.exe")
W, H = 800, 450
CELL_W, LABEL_H, GAP, COLS = 700, 54, 18, 2


def variants() -> list[dict]:
    js = (
        "import('./northstar-os-ui/src/shell/galacticVariants.js')"
        ".then(m => console.log(JSON.stringify(m.GALACTIC_VARIANTS)))"
    )
    res = subprocess.run(
        ["node", "--input-type=module", "-e", js],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(res.stdout)


def grade(raw):
    top = max(raw) or 1.0
    return ",".join(f"{c / top:.4f}" for c in raw)


def font(size: int, bold: bool = False):
    names = ("Inter-Bold.ttf",) if bold else ("Inter-Regular.ttf",)
    for name in names:
        for base in (ROOT / "assets" / "fonts", ROOT / "northstar-os-ui" / "src" / "assets" / "fonts"):
            p = base / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass
    return ImageFont.load_default()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    items = variants()
    cells = []

    for v in items:
        s = v["scene"]
        target = OUT / f"{v['id']}.png"
        cmd = [
            str(PY), str(ROOT / "tools" / "galactic_render.py"),
            "--width", str(W), "--height", str(H),
            "--expo", str(s["expo"]), "--temp", str(s["temp"]),
            "--incl", str(s["incl"]), "--dist", str(s["dist"]),
            "--gal", str(s["gal"]), "--grade", grade(s["tint"]),
            "--out", str(target.relative_to(ROOT)),
        ]
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout, res.stderr, file=sys.stderr)
            return 1
        img = Image.open(target).convert("RGB")
        ratio = CELL_W / img.width
        cells.append((v, img.resize((CELL_W, int(img.height * ratio)), Image.LANCZOS)))

    cell_h = cells[0][1].height + LABEL_H
    rows = (len(cells) + COLS - 1) // COLS
    sheet = Image.new(
        "RGB",
        (COLS * CELL_W + (COLS + 1) * GAP, rows * cell_h + (rows + 1) * GAP),
        (6, 8, 14),
    )
    draw = ImageDraw.Draw(sheet)
    f_name, f_note = font(19, bold=True), font(13)

    for i, (v, img) in enumerate(cells):
        col, row = i % COLS, i // COLS
        x = GAP + col * (CELL_W + GAP)
        y = GAP + row * (cell_h + GAP)
        sheet.paste(img, (x, y))
        ty = y + img.height + 6
        draw.text((x + 3, ty), f"{i + 1}. {v['name']}", font=f_name, fill=(240, 236, 228))
        s = v["scene"]
        note = f"temp {s['temp']:.2f} · expo {s['expo']:.2f} · incl {s['incl']:.1f} · dist {s['dist']:.1f} · gal {s['gal']:.1f}"
        draw.text((x + 3, ty + 24), note, font=f_note, fill=(146, 154, 170))

    out = ROOT / "reports" / "theme_review" / "SCENE_SHEET.png"
    sheet.save(out, "PNG", optimize=True)
    print(json.dumps({"out": str(out), "size": f"{sheet.width}x{sheet.height}", "count": len(cells)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
