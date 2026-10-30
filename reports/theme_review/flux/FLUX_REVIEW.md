# Ten interface designs — FLUX 3 comps

**Generated:** 2026-10-30 · **Model:** `flux-3-image-klein` (local, nvfp4) through `tools/flux3_gateway.py`
**Size:** 1216×688 · **Steps:** 26 · **Fixed seeds** (reproducible) · **~28 s per frame**, 4 min 40 s total
**Folder:** `reports/theme_review/flux/`

Open `UI_SHEET.png` for all ten together, or the numbered PNGs full size.

---

## What these are

Design comps: pictures of a proposed interface, produced by the local FLUX 3
checkpoint. They are **not** screenshots of the running app and not a template
with the colours swapped — each is a different layout archetype, information
hierarchy and interstellar motif.

| # | File | Archetype | Layout idea | Motif |
|---|---|---|---|---|
| 1 | `01-command-deck.png` | Command Deck | Icon rail · six service tabs · hero viewport · telemetry column | Lensed hole, gold disc, straight out of the film |
| 2 | `02-split-cockpit.png` | Split Cockpit | Conversation list · chat · inspector, under a wide hero band | Face-on grand-design spiral in teal |
| 3 | `03-bento-services.png` | Bento Services | Twelve rounded service tiles, varied sizes | Edge-on galaxy glowing across the lower third |
| 4 | `04-terminal-observatory.png` | Terminal Observatory | Monospace log stream, hairline charts, no chrome | One small photon ring, upper right |
| 5 | `05-full-bleed-cinema.png` | Full Bleed Cinema | No panels. Serif headline, single input bar | Poster-scale hole, vast negative space |
| 6 | `06-orbital-map.png` | Orbital Map | Radial diagram, eight service nodes on concentric orbits | Small dark sphere with a glowing accretion ring |
| 7 | `07-chat-first.png` | Chat First | One conversation column, large composer, history rail | Magenta/indigo nebula bleeding in from the right |
| 8 | `08-editorial-atlas.png` | Editorial Atlas | Magazine grid, serif headline, framed plate, gold rule | Portrait spiral galaxy |
| 9 | `09-mission-board.png` | Mission Board | Kanban, five columns, filter chips | Rust nebula with a small hole low right |
| 10 | `10-glass-layers.png` | Glass Layers | Three overlapping frosted panels at offsets | Galaxies blurred through the glass, magenta bokeh |

---

## Reading the set honestly

**What reads well.** These are usable direction, not just mood: 1, 3, 4, 6 and 9
have believable information density and could be built. 5 and 8 show how far the
product can go toward editorial before it stops looking like software. 6 (radial)
and 10 (layered glass) are the two that no ordinary dashboard does.

**What is not real.** The small type is model-generated pseudo-language. In 5, 7,
8 and 9 the headlines are invented words. Nothing here is copy, a label set, or a
component spec — it is a picture to choose a direction from. Whatever wins gets
built properly in React, with real text and real states.

**Reproduce or extend.** Every prompt, seed and timing is in
`reports/theme_review/flux/manifest.json`. `python tools/flux3_ui_variants.py --only <id> --force`
re-renders one; `--force` redoes all ten.

**Machine state after this run.** The MoE coding worker (llama-server, 15.4 GB
VRAM) was suspended through `tys_ops.graphics.suspend_competing_engines()` so
FLUX 3 could take the card — that is the documented path, not a kill.
ComfyUI is still up on 127.0.0.1:8188 with `--cache-none`, holding ~284 MiB
idle. Stop it when you are done rendering.
