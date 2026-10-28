# REA PROGRAM — PHASE 2 COMPLETE
**2026-10-28 · six research deliverables + baseline · no Amazon contact · no spend**

---

## What was delivered

| Plan | Deliverable | The one number that matters |
|---|---|---|
| 1.1 Label compositing | `reports/packaging_workflow_analysis_20261028.md` | 4-point homography = **5.41 px** mean error; 5×7 mesh = **0.68 px** |
| 1.2 A+ content | `reports/a_content_layout_patterns_20261028.md` | **0** arcs existed; 5 specified from seller-taught workflows |
| 1.3 Video ads | `reports/video_ad_structures_20261028.md` | a real **12.0 s / 1080×1920** narrated, captioned clip built by FFmpeg alone |
| 1.4 Social specs | `reports/social_media_asset_specs_20261028.md` | 7 entries reviewed: **1** exact, **1** off-recommendation, **7** canvases missing |
| 1.5 Bojo infra | `reports/bojo_infrastructure_plan_20261028.md` | p50 **35 s**, p95 **268 s**, max **2,040 s**; SQLite contention **refuted** |
| 1.6 SMUI | `reports/smui_wireframes_and_flow_20261028.md` | label intent **21 turns → 3 tool calls** (0.14) |
| Baseline | `reports/rea_baseline_20261028.json` | every Phase 5 comparison row, measured or explicitly `not_run` |

Probes (all reproducible, all offline):
`tools/rea_warp_probe.py`, `tools/rea_video_probe.py`, `tools/rea_smui_intents.py`,
`tools/rea_bojo_probe.py` → outputs in `reports/rea_probe/`.

---

## The five findings worth arguing about

1. **The halo was never the feather's fault.** Swept independently: feathering
   alone produces **0.000** bleed outside the true edge; a **1 px** quad
   overshoot produces **57 lum** of bleed (28 % of panel contrast), 3 px produces
   **190** (95 %). Feathering only *smears* an error the geometry created. Any
   plan that tunes the feather radius is solving the wrong variable.

2. **A mesh is worth 8× and costs nothing.** 5.413 → 0.676 px mean for a 5×7
   quad mesh through `cv2.remap` (OpenCV already installed, Apache-2.0). Blender
   was not needed and is not recommended.

3. **Social specs have no provenance while Amazon specs do.** `presets.js`
   carries every social canvas as `{id,label,w,h}` — no source, no date, no
   confidence — in the same repo where `specRegistry.js` dates and rates every
   Amazon spec. X's default canvas is also the wrong ratio (16:9 instead of
   1.91:1).

4. **Everything in a short-form ad except the footage is deterministic.**
   Shots, Ken-Burns, captions, narration, loudness, vertical framing all
   assembled locally with 0 spend. The generative part is one shot source with a
   832×480 ceiling — which is why it cannot be the hero shot.

5. **The substrate is slow and opaque, not contended.** Four concurrent SQLite
   writers lose **zero** rows at the configured 5 s timeout. The measured problem
   is a p95 of 268 s against a 35 s median. Adding Redis or RabbitMQ would solve
   the failure that measurement says we do not have.

---

## Found while measuring (not part of any plan)

`test_pouch_label.py` fails **6 tests** that assert `_fit_box` clamps to 1216,
while `studio_generation.py:478` now defaults `MAX_EDGE_PX` to **2048**. The
module is clean in git, so this is drift, not a local edit. It is recorded, not
patched: **the decision needed is which value is the engine's real ceiling**, and
editing the assertions first would hide that question. Everything else ran green:
`npm run build` 0 errors; the focused pytest subset 28 passed.

---

## What was deliberately not done

- **No Amazon contact.** The A+ plan's Amazon crawl stayed blocked; the research
  used seller YouTube tutorials, seller-forum guidance and design literature
  instead, and lists Amazon-only gaps as gaps.
- **No spend, no trials, no new dependency.**
- **No 20–30-ad timing corpus** (ad libraries are JS-gated; timing a video means
  playing it). The instrument to do it exists and is named in the report.
- **No render fired at the live GPU lane** while the operator's stack was
  serving; peak RAM/VRAM is a snapshot, not a peak, and says so.
- **No provider rate-limit matrix** — vendor docs were not fetched; recorded as
  debt with the method to close it.

## Next step

Phase 3 = build plans drawn **only** from the `BUILD CANDIDATES` tables in the six
reports (38 candidate rows total: L1–L5, A1–A6, V1–V6, S1–S6, B1–B7, U1–U8).
Each row already carries its evidence section, effort, risk and gate, so a build
plan can be rejected on evidence rather than on taste.

Nothing has been built. Awaiting `approve phase 3` — or name the candidate ids to
build first (my order: **L1 → S1/S2 → B1 → U1 → U4 → V1**).
