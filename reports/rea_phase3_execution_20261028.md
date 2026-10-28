# REA PHASE 3 — EXECUTION LOG
**2026-10-28 · scoped to the BUILD CANDIDATES tables · no Amazon · no spend · no new dependency**

Status: **ITEM 0 measured and stopped for your decision. ITEM 2 and ITEM 3
delivered. ITEM 1, 4, 5 not started** (they wait on the ceiling decision).

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
| ITEM 1 (L1 + L2 acceptance: synthetic **and** Mogra plate, OCR, prepress, readiness) | **blocked on the ceiling decision** |
| ITEM 4 (U1 auto-chain, U4 re-measure) | not started |
| ITEM 5 (V1 video assemble) | not started |
| A1–A6 | held, as instructed; to be labelled UNVERIFIED in the plan |
| Everything else | second pass |

**Decision needed:** is the engine's real long-edge ceiling **1216** or **2048**?
If 2048, the six assertions are stale and should be rewritten to the measured
values above — with your explicit approval, not mine.
