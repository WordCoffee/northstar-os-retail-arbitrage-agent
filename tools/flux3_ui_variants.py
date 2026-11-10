"""Generate ten DIFFERENT Northstar OS interface designs with FLUX 3.

These are design comps: pictures of a UI, produced by the local FLUX 3 Image
Klein checkpoint through tools/flux3_gateway.py. Nothing here is a screenshot of
the running app and nothing here is a template with the colours changed — each
entry is a different layout archetype, a different information hierarchy and a
different interstellar motif.

    python tools/flux3_ui_variants.py                 # all ten
    python tools/flux3_ui_variants.py --only orbital-map
    python tools/flux3_ui_variants.py --force         # re-render everything

Requires ComfyUI on 127.0.0.1:8188 (tools/start_comfyui.ps1 --cache-none).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "reports" / "theme_review" / "flux"

# 1216x688 is 16:9-ish and a multiple of 16 on both axes (latent constraint).
W, H = 1216, 688
STEPS = 26

NEGATIVE = (
    "photograph of a laptop, phone mockup, monitor bezel, hands, desk, "
    "perspective tilt, isometric device, watermark, signature, blurry, "
    "low contrast, muddy, cluttered, comic book, cartoon, text gibberish"
)

DESIGN_SYSTEM = (
    "Professional desktop application user interface design, full-bleed screenshot, "
    "flat orthographic front view, no device frame, high-end product design, "
    "precise alignment, realistic UI chrome, vector-crisp panels, legible small labels"
)

VARIANTS = [
    {
        "id": "command-deck",
        "name": "Command Deck",
        "prompt": (
            f"{DESIGN_SYSTEM}. A dense mission-control dashboard: slim icon rail on the far left, "
            "a row of six service tabs across the top (Auto, Create, Grow, Research, Operate, "
            "Infrastructure), and a wide central viewport framing a photorealistic lensed black "
            "hole with a brilliant gold accretion disc arcing over its shadow. Right column of "
            "stacked telemetry cards with tiny sparklines and thin rules. Deep obsidian background, "
            "warm gold accent, hairline borders, restrained type. Cinematic, serious, expensive."
        ),
    },
    {
        "id": "split-cockpit",
        "name": "Split Cockpit",
        "prompt": (
            f"{DESIGN_SYSTEM}. Three-column layout: left conversation list, centre chat column, "
            "right inspector panel with sliders and toggles. Above the columns a wide hero band "
            "showing a spiral galaxy seen face-on, cool teal and ice blue, dust lanes dark against "
            "luminous arms. Frosted glass panels floating over deep space, soft inner glows, "
            "generous white space, thin cyan accent lines, modern sans-serif. Calm and precise."
        ),
    },
    {
        "id": "bento-services",
        "name": "Bento Services",
        "prompt": (
            f"{DESIGN_SYSTEM}. A bento grid of twelve rounded cards of different sizes on a near-black "
            "canvas, each card a service tile with a small icon, a number and a one-line status. "
            "Behind the grid, a vast starfield with a distant edge-on galaxy glowing amber across the "
            "lower third. Cards are dark smoked glass with 1px light borders and subtle warm rim "
            "light. Rounded 20px corners, tight typographic scale. Clean, contemporary, SaaS."
        ),
    },
    {
        "id": "terminal-observatory",
        "name": "Terminal Observatory",
        "prompt": (
            f"{DESIGN_SYSTEM}. Minimal console aesthetic: monospaced type, a thin single-column log "
            "stream down the left two thirds, and a narrow right gutter of plain numeric readouts. "
            "Almost no chrome, no rounded corners. A restrained starfield with one small bright "
            "photon ring in the upper right corner, pale blue-white on true black. Charts rendered "
            "as thin single-pixel lines. Quiet, technical, instrument-like, no decoration."
        ),
    },
    {
        "id": "full-bleed-cinema",
        "name": "Full Bleed Cinema",
        "prompt": (
            f"{DESIGN_SYSTEM}. No panels at all: an immersive full-screen black hole, enormous, "
            "centred and slightly low, with a razor-thin accretion disc and a hot white photon ring. "
            "A single elegant serif headline sits high in the frame with two short lines beneath it, "
            "and one slim translucent input bar floats at the bottom centre. Tiny monochrome status "
            "text in the corners. Poster composition, vast negative space, dramatic, editorial."
        ),
    },
    {
        "id": "orbital-map",
        "name": "Orbital Map",
        "prompt": (
            f"{DESIGN_SYSTEM}. Radial interface: a large circular orbital diagram at centre with "
            "concentric rings, and eight service nodes placed around the rings connected by thin "
            "curved lines. The orbit centre is a small dark sphere with a glowing accretion ring. "
            "Left edge has a compact vertical label column; bottom edge a horizontal timeline. "
            "Deep indigo palette with violet and pearl highlights, delicate geometry, scientific "
            "instrument feel, generous darkness."
        ),
    },
    {
        "id": "chat-first",
        "name": "Chat First",
        "prompt": (
            f"{DESIGN_SYSTEM}. A chat-first assistant interface: one tall centred conversation column "
            "with soft rounded message bubbles, a large multi-line composer pinned at the bottom with "
            "an attach icon and a send button, and a narrow left history rail. The background is a "
            "deep space field with a soft nebula bloom in magenta and indigo bleeding in from the "
            "right edge. Bubbles are dark glass with faint borders, the composer glows softly. "
            "Friendly, modern, spacious."
        ),
    },
    {
        "id": "editorial-atlas",
        "name": "Editorial Atlas",
        "prompt": (
            f"{DESIGN_SYSTEM}. Magazine-style layout on a warm near-black background: a very large "
            "elegant serif headline on the left half, a narrow column of body text beneath it, and a "
            "tall portrait image of a spiral galaxy on the right half with a thin gold rule framing "
            "it. A horizontal index bar of numbered sections runs across the top. Print-inspired "
            "typography, wide margins, generous leading, muted cream text, one gold accent. Cultured, "
            "expensive, calm."
        ),
    },
    {
        "id": "mission-board",
        "name": "Mission Board",
        "prompt": (
            f"{DESIGN_SYSTEM}. Kanban board across the whole frame: five columns of task cards with "
            "priority dots and small avatars, a top bar with search and filter chips, and a narrow "
            "left navigation rail with icons. Behind everything, a dark nebula field in burnt orange "
            "and rust with a small black hole silhouette low and to the right. Cards are charcoal "
            "with thin warm borders and 8px corners. Dense, operational, confident."
        ),
    },
    {
        "id": "glass-layers",
        "name": "Glass Layers",
        "prompt": (
            f"{DESIGN_SYSTEM}. Layered frosted-glass composition: three large translucent panels "
            "overlapping at slight offsets, each with a blurred luminous galaxy visible through it, "
            "creating depth. Top panel holds a compact toolbar, middle panel a wide content area, "
            "bottom panel a media strip of thumbnails. Magenta, lavender and pale cyan light bleeds "
            "through the glass with strong bokeh and refraction. Very soft edges, high blur, 28px "
            "radii, futuristic and elegant."
        ),
    },
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--steps", type=int, default=STEPS)
    args = ap.parse_args()

    import flux3_gateway as gw

    ready = gw.health()
    if ready.get("status") != "ok":
        print(json.dumps({"status": "blocked", "detail": ready}, indent=2))
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    wanted = [v for v in VARIANTS if not args.only or v["id"] == args.only]
    if not wanted:
        raise SystemExit(f"no variant matches {args.only!r}")

    for i, v in enumerate(VARIANTS):
        if v not in wanted:
            continue
        target = OUT / f"{i + 1:02d}-{v['id']}.png"
        if target.exists() and not args.force:
            print(f"skip {target.name} (exists)")
            continue
        seed = 20261030 + i
        started = time.time()
        print(f"[{i + 1}/{len(VARIANTS)}] {v['id']} seed={seed}", flush=True)
        try:
            result = gw.generate(
                v["prompt"], width=W, height=H, steps=args.steps,
                seed=seed, negative=NEGATIVE,
            )
        except Exception as exc:  # noqa: BLE001 - report, never fake a success
            print(f"  FAILED: {exc}")
            manifest[v["id"]] = {"status": "failed", "error": str(exc)}
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            return 1
        shutil.copyfile(result["path"], target)
        manifest[v["id"]] = {
            "status": "ok",
            "name": v["name"],
            "file": str(target.relative_to(ROOT)),
            "seed": result["seed"],
            "size": f"{result['width']}x{result['height']}",
            "steps": result["steps"],
            "seconds": round(time.time() - started, 1),
            "prompt": v["prompt"],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"  ok {target.name} in {manifest[v['id']]['seconds']}s", flush=True)

    done = len([m for m in manifest.values() if m.get("status") == "ok"])
    print(json.dumps({"rendered": done, "of": len(VARIANTS), "dir": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
