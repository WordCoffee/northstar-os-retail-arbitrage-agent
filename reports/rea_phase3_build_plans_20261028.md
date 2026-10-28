# REA PROGRAM — PHASE 3 BUILD PLANS
**2026-10-28 · drawn only from the 38 `BUILD CANDIDATES` rows in the six Phase 2 reports**

Rule for this phase: a candidate exists only if a measured finding in a Phase 2
report justifies it. Nothing here comes from taste. Each entry names the file, the
change, **the test that proves it**, and the rollback.

---

## 0. Wave 1 — SHIPPED in this session

### L1 — mesh warp for `warp_panel` (1.1 §3)
- **Where:** `Northstar_backend/mockup_compositor.py`
- **Change:** new `mesh_grid()` (quad → bowed node grid), `_mesh_pos_and_tangents()`,
  `_refine_to_mesh()` (Newton solve seeded by the homography inverse), and two new
  `warp_panel` parameters: `grid=None`, `mesh_iters=3`.
- **Why:** a 4-point homography leaves **5.413 px** mean reprojection error on a
  curved face; a 5×7 mesh leaves **0.676 px** (measured, `reports/rea_probe/warp_probe.json`).
- **Bug found while building it:** the warp region was the quad bbox ±6 px, so any
  bow larger than 6 px was silently cropped. The region now expands to the grid
  bounds. Without that, a forehead-bowed mesh would have shipped visibly truncated.
- **Second bug found:** the first cut of the Newton solve clamped `u,v` into the
  panel box, which turned out-of-panel pixels *valid* and painted panel colour
  outside the label. The clamp is now `[-pw, 2pw]`, so the caller's `valid` mask
  still works.
- **Tests:** `test_mockup_compositor.py::test_mesh_grid_with_no_bow_is_the_homography`,
  `::test_mesh_recovers_a_curved_face_to_sub_pixel`, `::test_bowed_mesh_actually_curves_the_edges`.
  Result: **27 passed** (`test_mockup_compositor` + `test_compositor_realism` +
  `test_pouch_label_placement`).
- **Rollback:** pass `grid=None`; behaviour is byte-identical to before.
- **Not yet wired:** `pouch_label` does not pass a grid. That is L2 — it needs a
  measured bow per plate, not a guess.

### U4 — `--ink-faint` contrast (1.6 §7)
- **Where:** `northstar-os-ui/src/styles/simple.css`
- **Change:** `#8d867a` → `#9a9386` (4.32:1 → **5.11:1** on `#1a2435`).
- **Why:** 4.32:1 fails WCAG 2.2 AA (4.5:1) for normal text.
- **Test:** contrast arithmetic is reproducible; `npm run build` 0 errors.
- **Rollback:** one-line revert.

### S2 — social canvas corrections (1.4 §2)
- **Where:** `northstar-os-ui/src/studio/engine/presets.js`, `adDoc.js`
- **Change:** `ig-post` 1080×1350 → **1440×1800**; `meta-story` 1080×1920 →
  **1440×2560**; `x-post` 1600×900 → **1200×628 (1.91:1)**; `linkedin` 627 → **628**;
  `yt-thumb` 1280×720 → **3840×2160**; `adDoc` thumbnail note updated.
- **Why:** IG/Stories/YouTube were rendering below the documented recommendation
  (platform upscales); X was on a placement ratio that is not the documented
  default for an image ad.
- **Test:** `npm run build` 0 errors (no test asserted the old literals — verified
  by grep before the change, so nothing was "fixed" by editing an assertion).
- **Rollback:** revert the four literals.
- **Side effect to watch:** four canvases are now larger; a render of each costs
  more time. Not measured in this wave.

---

## 1. Wave sequencing

| Wave | Candidates | Why this order | Gate |
|---|---|---|---|
| **1 (done)** | L1, U4, S2 | measured, additive, reversible | none |
| **2** | L2, S1, B1, A1 | L2 activates L1; S1 gives social specs provenance (the root cause); B1 makes the 268 s tail visible; A1 is pure data | none |
| **3** | L3, L4, A3, A4, S4, V1 | depends on wave 2's data/UI | none |
| **4** | U1, U2, U3, A2, V2, V3, S5 | router + UI chains; U2/U3 need new tools | none |
| **5** | B2, B3, B4, B5, B6, U5, U6, U8, V4, V5, A5, A6, S3, S6, B7, L5 | schema migration, refactor, instruments | none |
| **blocked** | V6 (music licence), any Amazon-side work | **spend** / **Amazon** | approval |

Not scheduled at all: nothing. Every row in the six reports is placed.

---

## 2. Wave 2 in detail

### L2 — sub-pixel edge fit + residual (`pouch_label`)
- **Where:** `Northstar_backend/pouch_label.py` (side fits), then the `warp_panel`
  call site.
- **Change:** fit each of the four sides with sub-pixel precision; compute the
  per-side residual in px; build `grid=mc.mesh_grid(quad, bow_x=<measured bow>)`
  from the fitted edge curvature; return `geom_residual_px` with the result.
- **Why:** 1 px of quad overshoot = **28.5 %** of the panel's contrast bleeding
  outside the true edge; 3 px = 95 %. Feathering only smears it.
- **Acceptance:** residual < 0.5 px on the two reference plates; composited output
  differs from the homography path by ≥ 1 px at mid-edge (proving the bow is real,
  not zero).
- **Test:** `test_pouch_label_placement.py` extension + a new synthetic-plate case
  reusing the probe's geometry. Refuse to compose at residual > 1.5 px.
- **Risk:** medium — this is the first change that alters a shipping composite.

### S1 — social provenance table
- **Where:** `northstar-os-ui/src/studio/engine/specRegistry.js` (new `SOCIAL_SOURCES`
  + social rows carrying `url`, `pulled`, `confidence`).
- **Why:** social entries have **no** source/date/confidence while Amazon entries do.
- **Acceptance:** every social canvas resolves to a source object; a missing source
  reports `UNSOURCED` rather than defaulting to a plausible value.
- **Test:** a JS unit check in the existing engine test path; `npm run build`.

### B1 — stage progress + stalled state
- **Where:** `design_studio_async.py` (`ds_jobs`), `lane_telemetry.py` writer.
- **Change:** write a stage timestamp per phase (`queued → preparing → rendering →
  post → done`); mark `stalled` when runtime > 2× p95 (≈ 9 min) with the stage it
  is stuck in.
- **Why:** p50 35 s vs p95 268 s vs max **2,039 s** (`lane_telemetry`, n=43).
- **Acceptance:** a deliberately slow job reports `stalled` + stage, and the UI can
  say "still rendering, 6 min" instead of spinning.
- **Test:** unit test with an injected clock; no GPU needed.

### A1 — A+ arc data
- **Where:** new `northstar-os-ui/src/studio/engine/aplusArcs.js`
- **Change:** the five arcs (A1–A5) as ordered module ids + text budgets, using only
  ids that already exist in `presets.js`.
- **Why:** **0** arcs existed; specs alone do not compose a page.
- **Test:** a validator that every arc id resolves in `ALL_FORMATS` and every budget
  is inside the module's documented character limit.

---

## 3. Wave 3–5 headlines (not built)

- **L3** derive feather σ from measured edge residual (1 h, low).
- **L4** persist the measured quad + residual per plate (2 h).
- **A3/A4** type-scale tokens (headline 3.0–4.5 %, body 1.6–2.2 %, baked-text floor
  2.5 % of module width) + a `compliance.js` lint that blocks baked text below it.
- **S4** local pre-upload validator: format, ratio ±1 %, dims, bytes, sRGB,
  safe-area occupancy, caption length.
- **V1** `studio_video_assemble.py` — the exact FFmpeg chain proven in 1.3 §5.
- **U1/U2/U3** the three intent gaps: auto-chain `apply_label`; an A+ pack tool; a
  logo placement tool (21 turns → 3 calls is the number to move).
- **B2** asset metadata columns incl. `geom_residual_px` (migration on a live DB —
  the only risky item in the set).
- **U5** split `ChatSurface` (44 `useState`) — highest risk, lowest urgency; only
  after U1–U3 prove the interaction model.
- **V6** music — **spend gate**, blocked.

---

## 4. Verification run for this session

```
pytest test_mockup_compositor.py test_compositor_realism.py test_pouch_label_placement.py
  -> 27 passed
pytest test_compositor_realism.py test_pouch_label.py test_studio_sizing.py
  -> 36 passed, 6 failed   (the 6 are the pre-existing MAX_EDGE_PX 1216/2048 drift)
npm run build
  -> 0 errors, built in 1.30 s
```

The 6 failures are **not** from this session and are not edited to pass. They are
tracked in `reports/rea_baseline_20261028.json` as `render_fit_box: partial_fail`.
The decision they need (is the engine ceiling 1216 or 2048?) belongs to whoever
owns the render lane, and it is the one thing in this program that should not be
settled by a guess.

## 5. Rollback

Wave 1 is two reversible edits and one additive code path:
`git revert` of the wave-1 commit restores the previous behaviour exactly; the
mesh path is inert unless a caller passes `grid=`.
