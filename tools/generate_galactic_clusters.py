"""Generate the ten Galactic cluster backdrops through Ty's FLUX 3 graphics lane.

Run from the repository root:
    python tools/generate_galactic_clusters.py

The endpoint is local (127.0.0.1:8190). No downloads and no external calls.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
from tys_ops import graphics  # noqa: E402

OUT = ROOT / "northstar-os-ui" / "src" / "assets" / "galactic"
OUT.mkdir(parents=True, exist_ok=True)

# Ten different cosmic compositions, not ten palettes of one image. Every
# prompt bans text/logos/UI; the motion and shooting stars are added in CSS.
SCENES = [
    ("orion-nursery", 101,
     "A colossal star-forming cluster in deep space, hundreds of blue-white stars "
     "inside translucent teal and violet gas, intricate filaments and glowing dust "
     "lanes, a few faint meteors, ultra-detailed astrophotography, cinematic depth, "
     "no text, no logos, no planets, no UI"),
    ("pleiades-veil", 102,
     "The Pleiades star cluster wrapped in cold blue reflection nebulosity, seven "
     "brilliant sapphire stars with delicate diffraction spikes, silver veils of dust, "
     "scattered tiny stars, deep indigo void, crisp astrophotography, no text, no logos, "
     "no planets, no UI"),
    ("carina-cliffs", 103,
     "Towering star-forming dust cliffs in the Carina Nebula, burnt-orange and cyan "
     "ionized gas, a young embedded cluster blazing through the ridge, dark dust pillars, "
     "dramatic scale, Hubble-style astrophotography, no text, no logos, no planets, no UI"),
    ("crab-pulsar", 104,
     "The Crab Nebula supernova remnant, violet and gold filamentary gas expanding in "
     "chaotic ribbons, a tiny brilliant pulsar at the center with twin beams, cold stars, "
     "deep black space, high-detail astrophotography, no text, no logos, no UI"),
    ("andromeda-spiral", 105,
     "A vast tilted spiral galaxy like Andromeda, silver-blue star lanes, a warm golden "
     "core, dark dust rifts, a faint companion galaxy, scattered foreground stars, "
     "wide-field deep-space photography, no text, no logos, no UI"),
    ("globular-core", 106,
     "An immense globular cluster, thousands of densely packed golden and white stars "
     "concentrating into a blazing core, faint blue stragglers, black space around the "
     "edges, sharp telescope photography, no text, no logos, no planets, no UI"),
    ("magellanic-reef", 107,
     "A turquoise and rose star-forming reef in the Large Magellanic Cloud, lacy gas "
     "ridges, scattered blue supergiants, pink emission knots, dark dust channels, "
     "wide-field space telescope image, no text, no logos, no planets, no UI"),
    ("black-hole-disk", 108,
     "A supermassive black hole with a luminous orange-gold accretion disk, extreme "
     "gravitational lensing, a dark event horizon, relativistic jets, surrounded by a "
     "dense star cluster and cold blue nebula, cinematic astrophysics, no text, no logos, no UI"),
    ("meteor-rain", 109,
     "A meteor shower streaking over the dark limb of an alien planet, dozens of bright "
     "shooting stars, the Milky Way arching overhead, aurora-green atmosphere, deep "
     "indigo night, ultra-wide cinematic astrophotography, no text, no logos, no UI"),
    ("rose-galaxy", 110,
     "Two interacting galaxies twisted into a rose-shaped collision, crimson and rose "
     "gas, blue star clusters bursting along the tidal arms, luminous dust, dark cosmic "
     "background, deep-space telescope image, no text, no logos, no planets, no UI"),
]


def contact_sheet(paths):
    thumb = 420
    margin, gap, cap = 28, 16, 42
    cols = 2
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb + (cols - 1) * gap + margin * 2,
                              rows * (thumb + cap) + (rows - 1) * gap + margin * 2),
                      (5, 7, 13))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(str(ROOT / "Northstar_backend" / "assets" / "fonts" / "Inter.ttf"), 22)
    except Exception:
        font = ImageFont.load_default()
    for i, (name, path) in enumerate(paths):
        im = Image.open(path).convert("RGB")
        im.thumbnail((thumb, thumb), Image.LANCZOS)
        x = margin + (i % cols) * (thumb + gap)
        y = margin + (i // cols) * (thumb + cap + gap)
        sheet.paste(im, (x + (thumb - im.width) // 2, y))
        draw.text((x, y + thumb + 9), name, fill=(230, 226, 214), font=font)
    out = OUT.parent / "galactic_contact_sheet.png"
    sheet.save(out, format="PNG")
    print("contact", out)


def main() -> int:
    ready = graphics.status()
    if not ready.get("available"):
        print("FLUX 3 unavailable:", ready.get("detail"))
        return 2
    built = []
    for name, seed, prompt in SCENES:
        started = time.time()
        print(f"[{name}] generating ...", flush=True)
        result = graphics.generate(prompt, width=1536, height=1024, steps=16, seed=seed)
        artifact = result["artifacts"][0]
        src = Path(artifact)
        dest = OUT / f"{name}.webp"
        Image.open(src).convert("RGB").save(dest, "WEBP", quality=88, method=6)
        built.append((name, dest))
        print(f"[{name}] {dest.name} {dest.stat().st_size // 1024} KB "
              f"in {time.time() - started:.1f}s", flush=True)
    contact_sheet(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
