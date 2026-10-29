# REA PHASE 3 — EXECUTION LOG
**2026-10-28 · scoped to the BUILD CANDIDATES tables · no Amazon · no spend · no new dependency**

Status: **ITEM 0 resolved (2048) and ITEM 1 delivered. ITEM 2 and ITEM 3
delivered. ITEM 4 and ITEM 5 not started.**

---

## ITEM 0 — MAX_EDGE_PX drift (1216 vs 2048)

### 0.1 History

| Field | Value |
|---|---|
| Commit | `16f7fa7717a3c892a303abf3adcd5edeb903614a` |
| Date | 2026-10-28 00:51:14 -0500 |
| Author | `Northstar Agent` |
| Subject | *Tys Assistant: admin automation agent (queue, lanes, checkpoints, controller handshake)* |
| `git log -S MAX_EDGE_PX` | that commit is the **only** one that touches the constant |

**Stated reason** (verbatim from the code comment it added, `studio_generation.py:474-479`):

> `1216 was the FLUX.2 Klein draft box, and it silently made the two listing`
> `deliverables impossible: an Amazon MAIN image must be at least 1600 px on the`
> `long edge (2000 recommended) and an A+ Premium banner is 1464x600. Both were`
> `rejected before the engine saw them. The ceiling is now a real setting, and`
> `the engine reports the same number it used.`

The commit message itself says nothing about the ceiling — the reason exists only
as a code comment. Same commit also replaced `def _fit_box(..., hi: int = 1216)`
with `hi: Optional[int] = None` reading `MAX_EDGE_PX`, and added an
`_exact_size_png` pass that snaps to the requested size within 16 px. **The tests
were not touched in that commit**, which is the whole drift.

### 0.2 One render at each ceiling (measured on this machine, 2026-10-28)

Same prompt, same seed 4242, tier `draft`, through the real `generate_image`
path against the local ComfyUI on :8188. Sampling every 0.5 s — these are
**sampled peaks at 0.5 s resolution, not instantaneous peaks**.

| Ceiling | Request | Output | Latency | Peak VRAM used | Peak RAM used | ComfyUI alive after |
|---|---|---|---|---|---|---|
| **1216** | 1024×1536 | **816×1216** (fitted) | **31.0 s** | 11,947 MB | 16,328 MB | yes |
| **2048** | 1024×1536 | 1024×1536 (unchanged) | 33.2 s | 11,851 MB | 16,532 MB | yes |
| **2048** | 1360×2048 | **1360×2048** (true 2048 long edge) | **39.3 s** | 12,811 MB | 16,528 MB | yes |

Reading: the jump from a 1216 long edge to a real 2048 long edge costs
**+8.3 s (+27 %)** and **+864 MB VRAM**. Both fit. RAM is saturated in every run
(16.3–16.5 GB of 16.56 GB used), so the binding constraint is unchanged and is
not the ceiling.

Full JSON: `reports/rea_probe/ceiling_1216.json`, `ceiling_2048_longedge.json`,
`ceiling_2048_request1536.json`. Probe: `tools/rea_ceiling_probe.py`.

### 0.3 The six failing tests and the assertions that depend on 1216

`Northstar_backend/test_pouch_label.py` — 6 failed, 28+ passed.

| Test | Line | Assertion |
|---|---|---|
| `test_fit_box_keeps_the_aspect_ratio[req1-expected1]` | 30 | `((896, 1344), (816, 1216))` |
| `test_fit_box_keeps_the_aspect_ratio[req2-expected2]` | 31 | `((1024, 1536), (816, 1216))` |
| `test_fit_box_keeps_the_aspect_ratio[req3-expected3]` | 32 | `((1536, 1024), (1216, 816))` |
| `test_fit_box_keeps_the_aspect_ratio[req5-expected5]` | 34 | `((2048, 2048), (1216, 1216))` |
| `test_fit_box_never_exceeds_the_engine_edge_and_stays_on_the_latent_grid` | 43 | `assert max(fw, fh) <= 1216` |
| `test_generate_image_reports_the_size_it_actually_used` | 65 | `assert (out["width"], out["height"]) == (816, 1216)` |

Passing cases that do **not** depend on the ceiling: `req0` (832×1216),
`req4` (1024×1024), and `test_fit_box_preserves_ratio_within_one_step`.

**Nothing edited.** The constant, the tests and the assertions are exactly as
found. Awaiting your decision.

### 0.4 Decision — 2048 (2026-10-28)

The operator chose **2048**. The six stale 1216 assertions were rewritten to the
measured values, not to make a red test green: 2048 is the value the engine
already used, and the measurements above show both ceilings fit on this box. The
production constant did not change (`studio_generation.py` already defaulted to
2048); only the tests and the record did.

- `test_pouch_label.py`: six expectations now 2048, plus a ceiling regression
  test that reads `sg.MAX_EDGE_PX` rather than hardcoding a number.
- `reports/rea_baseline_20261028.json`: `render_fit_box.status = "resolved"`,
  with the decision and evidence.
- Result: **23 passed** in `test_pouch_label.py` + `test_pouch_label_placement.py`.

---

## ITEM 1 — L1 + L2 acceptance (delivered)

### 1.1 What L2 changed

| File | Change |
|---|---|
| `Northstar_backend/mockup_compositor.py` | `mesh_grid` accepts `bow_x=(left, right)` as well as a scalar. A real pouch is asymmetric; one number for both sides was the difference between 0.24 px and 1.9 px residual. |
| `Northstar_backend/pouch_label.py` | Sub-pixel row edges from the blurred mask's 0.5 level set; RANSAC quadratic per side; sine-fit bow from each side's own chord; `geom_residual_px` measured mesh-vs-edge; `compose()` refuses above **1.5 px**; `mesh=False` keeps the homography path available for comparison. |
| `Northstar_backend/test_pouch_label_geometry.py` | 5 tests: known bow recovered, straight plate stays straight, mesh moves the mid-edge by >16 levels, refusal guard, per-side `mesh_grid`. |

### 1.2 Measured acceptance — Mogra reference plate

Plate: `Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png`
(blank Mogra pouch on marble; the labelled `52afb729…` is the same scene after
composition and is not a valid base).

| Metric | Value | Acceptance |
|---|---|---|
| Geometric residual (mesh vs measured edge) | **0.238 px** (left 0.292, right 0.193) | < 0.5 px **PASS** |
| Fit residual (quadratic vs inlier edge) | left 0.241, right 0.199 | reported |
| Measured bow | left −6.122 px, right −1.197 px | recorded |
| Mesh | 5 × 9, per-side bow | **PASS** |
| Mesh vs homography at mid-edge | > 16 intensity levels, > 200 pixels on the side bands | **PASS** |

Evidence: `reports/rea_probe/item1_mogra_composed.png` and
`reports/rea_probe/item1_acceptance.json`.

### 1.3 OCR, prepress, readiness

| Check | Result |
|---|---|
| OCR (`rapidocr`) | **ok** — 5 boxes: `MOGRAORGAVCS`, `Healthy&organic`, `ORGANICLION'S MANE`, `MUSHROOM POWDER`, `6 oz (170 g)`. The first is the logo read literally, not a fabricated match. |
| `verify_asset_text` | `text_present` |
| Prepress (`RSWOP.icm`) | **printable** — max TAC **254.9 %** (limit 300), 0 px over limit; out-of-gamut 2.0 %, max dE76 21.85, mean 4.74 |
| Readiness (`assess_package`) | **retail_ready**, 0 blockers, 0 warnings |

### 1.4 Regression harness

`tools/rea_regress.py` is unchanged in behaviour and now has a documented entry
point: `tools/verify-rea.ps1` (`-Full`, `-WithBuild`). A quick run with the
focused tests is **PASS**; the baseline file now records the resolved ceiling and
the measured OCR/prepress/readiness rows instead of `not_run`.

---

## ITEM 2 — S1/S2 social spec provenance + X ratio

**What changed** (`northstar-os-ui/src/studio/engine/presets.js`, `adDoc.js`)

- Added `SOCIAL_SOURCES` (7 source records) + `socialConfidenceOf()`, mirroring
  `SPEC_SOURCES` in `specRegistry.js`: `id`, `label`, `url`, `pulled`,
  `confidence`, `limits`, `note`.
- Every social canvas now carries `source: '<id>'`.
- New canvases for the placements that had none: `pin-video` (1000×1500),
  `pin-idea` (1080×1920 + documented safe zone), `x-carousel` (800×800),
  `x-vertical` (1080×1920), `yt-shorts-thumb` (1080×1920).
- X default canvas stays **1200×628 (1.91:1)** — fixed in wave 1, now sourced.
- `adDoc.js` thumbnail note matches the sourced size.

**Before / after**

| Metric | Before | After | Verdict |
|---|---|---|---|
| `social_canvases_without_source` | **8** | **0** | ok |
| `social_canvases_missing` | **7** | **0** | ok |
| `npm run build` | 0 errors | 0 errors (1.35 s) | ok |

**Sources cited, all pulled 2026-10-28** (confidence VERIFIED unless noted):
Meta ads guide (Instagram Feed), Meta ads guide (Instagram Stories), Pinterest
ad spec guide, TikTok auction in-feed ads, X creative specs, YouTube custom
thumbnails.
**LinkedIn** is `confidence: 'REPORTED'` with `url: null` and a note that the
official page 404'd at two known URLs — its values come from two independent
third-party spec documents that agree. That is marked, not hidden.

**Correction made while doing this:** the Phase 2 report said "7 entries
reviewed" while its own table listed 8. The count is corrected to 8 in
`reports/social_media_asset_specs_20261028.md` and in the baseline, with the
correction noted in place.

**UNVERIFIED:** TikTok numeric safe-zone values (published only as .zip
packages); YouTube Shorts thumbnail mobile byte cap (not stated on the page).

**Commit:** `489f2309` · **Tests:** `npm run build` 0 errors; harness PASS.

---

## ITEM 3 — B1, explaining the p95 / max tail

Instrument: `tools/rea_latency_attribution.py` →
`reports/rea_probe/latency_attribution.json`. Source: `lane_telemetry`, 52 rows.

### 3.1 The tail is not one thing

| Bucket | n | Median tool calls | ok rate |
|---|---|---|---|
| ≤ 40 s (one render) | 30 | 0.2 | 0.57 |
| 40–90 s | 9 | 1.22 | 0.78 |
| 90–300 s | 10 | 1.5 | 1.00 |
| 300–900 s | 2 | 0.5 | 1.00 |
| **> 900 s** | **1** | **0.0** | 1.00 |

### 3.2 What can be attributed, with the rows as evidence

**(a) The 2,039.7 s maximum is a zero-tool text turn — not a render.**
Row `id=38`, `2026-10-28T03:59:15Z`, `latency=2039.7 s`, **`tool_calls=0`**,
`ok=1`, inside an hour whose median was **8.21 s** (n=3). No render was involved,
so the GPU queue, ComfyUI and VRAM eviction are **not** its cause. It is an
isolated stalled turn.

**(b) The p95 of 268 s comes from one degraded hour, not a broad tail.**
Hour `2026-10-28T06`: **n=8, median 173.2 s, 6 of 8 over 90 s, max 374.6 s**.
Compare `2026-10-27T06`: **n=7, median 2.07 s, max 5.01 s** — same hour of day,
two orders of magnitude apart. A randomly slow system does not produce that;
a degraded window does.

**(c) Single-tool turns cost ~95 s more than the render they contain.**
Turns with exactly one tool call: **n=13, median 135.3 s**. A render measured
end-to-end today is **31.0 s** (1216 long edge) to **39.3 s** (2048 long edge).
The gap is model work plus brain reload around the render — *consistent with*
`unload_brain()` evicting the text model before every render, but this table
cannot prove that.

### 3.3 What cannot be attributed, and what would settle it

The 34-minute stall's **root cause cannot be named from `lane_telemetry`**: the
table records only total latency, tool count and ok, so a cold model load, a
starved request, a hung stream and a lock wait are indistinguishable.

Missing instrumentation (all four are what B1 should add, later):
1. per-stage timestamps on a turn — queued / model loaded / tool started / tool finished;
2. an explicit "waited on render lock" marker;
3. Ollama `/api/ps` state at turn start (brain resident or evicted?);
4. ComfyUI queue depth at turn start.

**B1 verdict: PASS** under its own rule — the *shape* is attributed with row-level
evidence (zero-tool stall, one degraded hour, ~95 s of per-render overhead), and
the remainder is declared unattributed with the exact instrumentation that is
missing. **No fix shipped under B1**, as instructed.

**Commit:** `489f2309` (probe) · **Tests:** probe runs offline, no code path changed.

---

## ALSO DELIVERED — regression harness

`tools/rea_regress.py` — reruns the baseline instruments and exits non-zero if any
metric regresses **or is lost**.

```
python tools/rea_regress.py              # all probes
python tools/rea_regress.py --quick      # skip warp + video probes
python tools/rea_regress.py --with-tests --with-build
```

Gating metrics (direction + tolerance are in the file): warp homography/mesh error,
edge bleed, OCR floor, SQLite errors at 5 s, lane p95, label intent ratio,
`--ink-faint` contrast, social provenance coverage, missing canvases, video
duration.

Current run: **PASS**, all metrics at or better than baseline.

## State file

`00_STATE.json` merge was attempted again this session and **refused by
permission** ("Permission denied: edit"). The block remains parked, updated in
`reports/rea_program_state_pending_00_STATE.json`. Say the word and it can be
merged by a process that has write access, or with the permission lifted.

---

## What remains

| Item | State |
|---|---|
| ITEM 1 (L1 + L2 acceptance: synthetic **and** Mogra plate, OCR, prepress, readiness) | **DONE** — 0.238 px residual, mesh 5×9, OCR 5 boxes, prepress printable, readiness retail_ready |
| ITEM 4 (U1 auto-chain, U4 re-measure) | not started |
| ITEM 5 (V1 video assemble) | not started |
| A1–A6 | held, as instructed; to be labelled UNVERIFIED in the plan |
| Everything else | second pass |

**Ceiling decision:** **2048** (recorded 2026-10-28). The six stale assertions
were rewritten to the measured values; no production constant changed.

---

# POST-DECISION WORK (2026-10-29)

## ITEM 1 - independent re-verification

`tools/rea_verify_item1.py` recomputes the acceptance from the plate and the
artefact instead of trusting `item1_acceptance.json`.

| Check | Claimed | Actual | Verdict |
|---|---|---|---|
| geometric residual | 0.238 px | **0.238 px** | ok |
| mesh present | yes | yes | ok |
| artefact exists | yes | yes | ok |
| OCR status / boxes | ok / 5 | **ok / 5** | ok |
| OCR words (exact except spacing) | 5 boxes | identical | ok |
| prepress gamut status | ok | **ok** | ok |
| out-of-gamut share | 2.0 % | **2.0 %** | ok |
| max TAC | 254.9 % | **254.9 %** (limit 300) | ok |

**PASS: item 1 reproduces.** Text read back: MOGRAORGAVCS, Healthy&organic,
ORGANICLION'S MANE, MUSHROOM POWDER, 6 oz (170 g) - compared with whitespace
squashed because RapidOCR drops spaces inside a box (recorded finding).

**Commit:** 38d89be4 (verifier). No test changed.

## ITEM 4 - U1 auto-chain + U4 re-measure

**U1 changed** (`Northstar_backend/chat_router.py`):
- `label_brief(text)` detects label/pouch/bag/dieline intent.
- `explicit_label_title(text, options)` returns a name ONLY when the turn states
  it (an explicit product_name/title option, or a double-quoted phrase). An
  apostrophe is not a quote, so "Lion's Mane" is never mis-read.
- After a successful `generate_image` in a label turn it calls `apply_label` with
  the render's own `plate_asset_id` + `title`, emits the same tool-start /
  tool-end / asset frames a model call would, and registers the artefact.
- Bounded: once per turn, never after an explicit `apply_label`, never when the
  turn supplies no name. Missing name emits one `notice` (`label_needs_title`);
  nothing is invented.

**Tests** (`test_label_autochain.py`, 5) + 46 passed across test_turn_contract /
test_chat_router_intent / test_chat_tools / test_label_autochain.

| Metric | Before | After | Note |
|---|---|---|---|
| label turn reaches the print pass (deterministic harness) | 1 call (render only) | **2 calls** (render + print) | the capability change |
| corpus `apply_label` / label turns | 0.143 | **0.409** | **from real usage, not this patch** - historical rows cannot change. Not evidence for U1. |

**U4 re-measured:** `--ink-faint` on `#1a2435` **4.32 -> 5.11** (AA needs 4.5), ok.

**Commit:** 38d89be4.

## ITEM 5 - V1 video assembly service

`Northstar_backend/studio_video_assemble.py`:
`assemble(images, captions=..., narration=..., out_path=..., seconds_per_shot=...,
size=..., fps=...)` - the exact FFmpeg chain from 1.3 section 5 as a callable
service: per-shot zoompan, concat, PIL caption overlays with enable windows,
Piper narration, loudnorm + apad, and an ffprobe read-back. CLI included.

Produced clip `reports/rea_probe/video/assembled_v1.mp4` (via the CLI):

    video: h264 1080x1920 30/1
    audio: aac 96000 Hz
    duration: 8.000000 s
    size: 1,639,562 bytes

Tests (`test_video_assemble.py`, 3): real assembly with two captions (360x640,
h264, ~2.4 s), refusal on a missing source, probe accuracy. 1.15 s. Skipped when
ffmpeg is absent.

| Metric | Before | After | Verdict |
|---|---|---|---|
| `video_clip_seconds` (reference artefact) | 12.0 | 12.0 | ok |
| assembly available as a service | no | **yes** | capability added |

**UNVERIFIED:** the Wan B-roll lane was not re-measured; this service assembles
stills, it does not generate footage.

## Harness after all of the above

    python tools/rea_regress.py
    label_warp_homography_mean_px      5.413 -> 5.413   ok
    label_warp_mesh_5x7_mean_px        0.676 -> 0.676   ok
    label_edge_bleed_lum              57.013 -> 57.013  ok
    ocr_legibility_floor_px               10 -> 10      ok
    sqlite_errors_at_5s                    0 -> 0       ok
    lane_create_p95_s                268.020 -> 268.020 ok
    label_intent_tool_ratio            0.143 -> 0.409   ok
    ink_faint_contrast                 4.320 -> 5.110   ok
    social_canvases_without_source         8 -> 0       ok
    social_canvases_missing                7 -> 0       ok
    video_clip_seconds                12.000 -> 12.000  ok
    PASS: every measured metric is at or better than baseline.

## Still open

- A1-A6 remain held; each arc must be labelled UNVERIFIED when unblocked.
- L2-L5, S3-S6, B2-B7, U2/U3/U5-U8, V2-V6: second pass.
- 00_STATE.json merge still refused by permission; block parked in
  reports/rea_program_state_pending_00_STATE.json.

---

# WAVE 2 (2026-10-29) - L3/L4, B3/B4/B5

## L3 - feather derived from the measured residual

**Changed** (`mockup_compositor.py`, `pouch_label.py`): `feather_sigma(residual_px,
lo=1.0, hi=12.0, per_px=2.5)` maps the measured edge residual to an edge ramp;
`warp_panel(edge_feather=...)` applies it as an **inward** ramp from the panel
border. `compose()` passes `feather_sigma(geom_residual_px)` on every call.

Why inward: the halo probe measured that outward paint is the entire bleed
(1 px overshoot = 57.013 lum = 28.5 % of panel contrast; feathering alone = 0.000).
An inward ramp cannot paint outside the true edge, so it softens the print without
manufacturing the artefact the constant was hiding.

| Metric | Before | After |
|---|---|---|
| feather source | constant (26.0 in `erase_rect`, none on the panel edge) | **derived**: `residual * 2.5`, clamped 1.0-12.0 px |
| Mogra plate (residual 0.238 px) | no edge ramp | **1.0 px** ramp (clean fit needs none) |
| bleed outside the true edge (1 px overshoot, probe) | 57.013 lum | 57.013 lum (unchanged: geometry, not feather) |
| dark-fringe regression guard | none | new test asserts no pixel between background and panel is darker than background |

**Commit:** `9fe0b04c` - **Tests:** `test_plate_geometry.py::test_feather_follows_the_residual_and_clamps`,
`::test_edge_feather_softens_the_edge_without_a_grey_fringe`; 34 passed across
plate-geometry + compositor + placement + realism.
**UNVERIFIED:** the ramp on a *new* operator plate through the chat tool (only
`compose()` was exercised directly).

## L4 - per-plate fit cache

**Changed** (`pouch_label.py`): `plate_key()` (sha256 of the plate bytes),
`load_plate_geometry()`, `save_plate_geometry()`, and `compose(reuse_geometry=True)`.
A fit is stored only when it passes the existing residual guard, and only keyed to
that exact plate, so a new render can never inherit an old fit.

| Metric | Before | After |
|---|---|---|
| `measure_face` calls for two composes of the same plate | 2 | **1** |
| Mogra plate, second compose | re-measured | `geometry_reused: true`, identical quad, same feather |
| a different plate | n/a | cache MISS (content hash differs) |
| a bad fit (residual > 1.5 px) | n/a | **not cached** |

**Commit:** `9fe0b04c` - **Tests:** 4 in `test_plate_geometry.py` (round trip, bad
fit refused, cross-plate isolation, reuse, `reuse_geometry=False`).
**UNVERIFIED:** cache growth/eviction over many plates (no size cap yet - it is a
small JSON of quads, but it is unbounded by design for now).

## B3 - the RAM-heavy lanes refuse an engine started without --cache-none

**Changed** (`studio_generation.py`, `scripts/launch_alpha.ps1`,
`tools/start_comfyui.ps1`): both launchers write
`Northstar_backend/data/comfyui_launch.json` with `cache_none: true`;
`comfyui_cache_none()` returns True/False/None; `require_cache_none(lane)` raises
`comfyui_cache_none_required` **only** when the marker positively says false.
`generate_edit` and `generate_video` call it; `generate_image` does not (it is the
lane that fits).

| Metric | Before | After |
|---|---|---|
| edit/video on an engine started without the flag | runs, then dies at ~20 GB RAM with no traceback | **refuses with the reason and the fix** |
| engine started by a launcher | no record | **marker written**, with argv and timestamp |
| marker absent | indistinguishable from "flag missing" | **None = unknown**, never blocks |

**Commit:** `8d571d9d` + `f07428f6` - **Tests:** 3 in `test_generation_guards.py`
(true allows / false refuses / absent-and-broken is unknown, plus the two lanes
actually call the guard). Both launchers parse clean under the PowerShell parser.
**UNVERIFIED:** a real edit render against a live engine (no GPU job was fired);
the marker is only as good as the launcher - a hand-started `python main.py` still
produces "unknown", by design.

## B4 - the turn says why chat will be slow after a render

**Changed** (`studio_generation.py`, `chat_router.py`): `unload_brain()` records
the model ids it evicted and when; `generate_image()` returns `brain_evicted`;
the turn emits `notice {code: brain_evicted_for_render}` naming them.

| Metric | Before | After |
|---|---|---|
| evictions recorded | none | **ids + UTC timestamp** |
| operator-visible cause for the post-render stall | none | one notice naming the models |
| notice when nothing was resident | n/a | **not emitted** (no false alarm) |

**Commit:** `8d571d9d` - **Tests:** 2 in `test_generation_guards.py` (records the
evicted ids; records nothing when nothing was resident).
**UNVERIFIED:** not observed on a live turn (needs a resident model plus a render).

## B5 - the render lock's wait is a number now

**Changed** (`studio_generation.py`, `ops_status.py`): `acquire()` times every
attempt; `render_lock_stats()` exposes `attempts`, `timeouts`, `total_wait_s`,
`last_wait_s`, `max_wait_s`; `ops_status.render_lock_status()` publishes it.

| Metric | Before | After |
|---|---|---|
| concurrent render wait | invisible | **measured** (attempts / last / max / total) |
| lock timeouts | indistinguishable from slow renders | **counted** |
| status surface | none | `ops_status.render_lock_status()` |

**Commit:** `8d571d9d`. **Tests:** `test_render_lock_counts_attempts_and_waits`
(real second lock, real 0.4 s timeout, asserts the wait is recorded).
**UNVERIFIED:** the counters are process-local and reset on restart; they are a
live signal, not history.

## Harness after wave 2

    python tools/rea_regress.py --quick
    PASS: every measured metric is at or better than baseline.

Full run (with probes) was green immediately before this wave; no metric in the
baseline measures feather radius or cache hits yet, so those two rows above are
new evidence rather than regression gates. Adding them to `rea_regress.py` is the
next small step.

---

# WAVE 3 (2026-10-29) - U3, S4

## U3 - logo placement (the gap with no tool at all)

Baseline: 5 of 60 surveyed turns asked for the logo and **no tool served them**.

**Built** (`logo_placement.py` + `place_logo` in `chat_tools.py`, in the Creative
Studio scope and the model schema set):

- `place(plate_png, logo_png, anchor=…, scale=…, opacity=…, margin=…, blend=…)`
  trims the logo's empty margins, scales it to a fraction of the short edge,
  alpha-composites it (or multiplies, for print-like seating), and returns the
  bytes plus the placement and its evidence.
- `anchor="auto"` measures a 3x3 grid of local gradient magnitude and picks the
  **calmest perimeter cell** — never the dead centre, and it reports all nine
  scores so the choice can be argued with.
- The result reports **ink/backdrop contrast**; below 1.5:1 the tool says so in
  the summary instead of shipping a mark that disappears.

| Metric | Before | After |
|---|---|---|
| turns with a logo ask that reach a tool | **0** (no such tool) | 1 tool, in the Creative Studio scope |
| placement basis | n/a | measured flatness (9 scores reported) or the operator's anchor |
| low-contrast mark | n/a | flagged in the summary, never silent |
| end-to-end through the tool (files -> asset record -> bytes on disk) | n/a | **6 checks pass**, incl. a real registration |

**Commit:** `9c02ca8b` - **Tests:** 12 (6 module, 6 tool incl. end-to-end).
**UNVERIFIED:** the `auto` anchor's aesthetic quality on real product shots (it is
a flatness measure, not a taste judgement); no live chat turn exercised it yet.

## S4 - local pre-upload validator

**Built** (`social_validate.py`): 13 canvases, every rule from the platform's own
page (pulled 2026-10-28). Blocks on: byte cap, format, aspect ratio outside
**1 %** (Meta's documented tolerance), minimum dimension, caption length. Warns
on: non-8-bit colour, >80 % of the byte cap. Reports `manual` for safe-area
occupancy (a flat asset cannot prove placement), and lists the rules that are
**UNVERIFIED** rather than guessing them (TikTok safe-zone pixels, Shorts mobile
byte cap, carousel card minima).

The drift guard is the point: `test_parity_with_the_ui_table` parses
`presets.js` and fails if any canvas differs from the Python table.

| Metric | Before | After |
|---|---|---|
| pre-upload validation | none | 13 canvases, sourced, with confidence labels |
| wrong-ratio asset | reaches the platform | **blocked locally** (4:5 canvas, 1:1 file) |
| UI/Python spec drift | possible, silent | **parity test** (fails on any w/h mismatch) |
| harness gate | none | `social_validator_ok` = 1 |

**Commit:** `71e16997` - **Tests:** 10, incl. the parity test.
**UNVERIFIED:** no HTTP route yet (module + CLI only); upload-time platform
rejection behaviour cannot be tested without uploading, which is out of scope.

## Backend verification (authorised this session)

Against the live backend on `127.0.0.1:8000`:

    GET /health              -> 200 {"status":"ok","service":"northstar-backend"}
    GET /api/v1/status       -> 200 contract bff/v1, mode live
    GET /api/v1/provider-suite -> 200, local lane active
    GET /api/design-studio/lanes/status -> 401 (auth required)

Authed studio routes were exercised in-process through `TestClient` with a
dependency override instead of using credentials (no credential was read).

## Harness after wave 3

    python tools/rea_regress.py --quick
    feather_policy_ok        1 -> 1   ok
    logo_tool_present        1 -> 1   ok
    social_validator_ok      1 -> 1   ok
    PASS: every measured metric is at or better than baseline.

14 gating metrics now. Wave 3 added three of them, so the guards themselves can
regress.

---

# REA-FIRST PASS - S5 (2026-10-29)

Method change per your instruction: reverse-engineer the reference before writing
code. Both sources were read before a line was written.

## What was reverse-engineered

| Source | What it contributed |
|---|---|
| Cloudinary "Image resizing and cropping" (fetched 2026-10-29) | the vocabulary and the rule: `fill` = cover (scale until the shorter side fits, crop the longer one); what survives is decided by a **gravity** point; `fit`/`pad` are the non-cropping modes; gravity is compass, auto, or explicit coordinates |
| `specRegistry.js` `SAFE_ZONES` (in-repo, 2026-10-10) | the discipline: boxes in **normalised 0..1**, BOTH documented figures kept, and the **stricter union** applied - never a single convenient number |
| `presets.js` + `social_validate.py` | the target canvases and their sourced sizes |

The transfer: SAFE_ZONES answers "where must I NOT put things". S5 needed the
inverse - "what survives every crop" - so the same stricter-union rule is applied
to the **intersection** of the crop windows instead of the union of keep-outs.

## Built

`northstar-os-ui/src/studio/engine/variants.js`:
- `cropFor(master, target, focal)` - cover scale, crop rect in px and normalised,
  `upscale` flag, gravity recorded.
- `keepInIntersection(crops)` - the shared region, with `areaPct` and `empty`.
- `buildVariantMatrix({master, targets, focal})` - the matrix plus
  `ok`/`reason`. It returns `ok:false` when the targets cannot share an anchor,
  and when no targets are selected - an outage is stated, never passed.

Wired into `outputPacks.buildSocialAssetPack`, so the downloadable pack carries
the matrix (or says UNKNOWN when the master/targets were not recorded).

## Numbers (from `tools/test_social_variants.mjs`)

Master 1440x1800 (IG portrait), targets ig-post / pin / x-post / tiktok:

| Target | Crop (normalised) | Note |
|---|---|---|
| ig-post 4:5 | full frame | no crop |
| x-post 1.91:1 | w 1.000, h **0.419** | the tightest crop |
| tiktok 9:16 | w 0.703, h 1.000 | upscales 1.07x (flagged) |
| **keep-in intersection** | **h 0.419**, area ~41.9 % | the band that survives all four |

Also asserted: gravity 0 pins left, gravity 1 pins right, upscale is disclosed,
an empty intersection is refused with a reason, and an empty target list is
refused.

| Metric | Before | After |
|---|---|---|
| one-master variant matrix | none | 4 targets, per-crop rects + keep-in box |
| contradictory anchors | would silently "work" | **refused**, reason stated |
| pack output | placements + copy only | **+ variants / keepIn** (or UNKNOWN) |
| harness | - | `social_variants_ok` = 1 (gated) |

**Commits:** `a6d1f7c9` (module + pack + test), `1dbd8e3f` (harness gate).
**Tests:** 14 node checks, `npm run build` 0 errors.
**UNVERIFIED:** the matrix is not yet used by the Social workspace UI (the pack
consumes it; the canvas does not); no real master asset was run through it - the
fixture is the IG portrait; crop *aesthetics* (where the product lands) remain an
operator judgement, not a computed one.
