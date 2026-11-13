# Defects found while running the director program

Each entry is a real measurement, the code that causes it, and the smallest fix. Nothing here is
filed against the owner.

## D-001 — `FoundationDB` leaks one temp database per instance (2026-11-09)

**Measured:** `(Get-ChildItem $env:TEMP -Filter 'ns_foundation_*.db').Count` → **9,018** files in
`C:\Users\T2Hol\AppData\Local\Temp`, and 9,812 files in that directory in total. The suite creates a
`FoundationDB` per app fixture, and the default path is:

```python
fd, tmp = tempfile.mkstemp(prefix="ns_foundation_", suffix=".db")
os.close(fd)
path = tmp
```

Nothing removes `tmp`. Every test run adds roughly one file per Foundation-backed app fixture, so the
directory grows without bound. A directory with ~10,000 entries also makes every `mkstemp` slower and
gives an antivirus more work, which is exactly the sort of thing that shows up later as
"the suite is mysteriously slow".

**Not the cause of any failure.** I suspected it of a stall and checked: the suite was progressing
normally (23 % at 6.2 minutes), and a `py-spy dump` caught it momentarily idle inside
`sqlite3.Connection.execute` — a slow I/O instant, not a deadlock.

**Fix (smallest):** when `path is None`, register the created file for removal at interpreter exit,
and remove it in `close()`; never touch a caller-supplied path. Add a test that the auto-created path
is registered and that a supplied path is left alone. Do not delete the 9,018 existing files by hand
— quarantine them in one move (same volume) and let the fix stop the growth.

**Status:** fixed in `fix/f0-tempdb` (commit `3718763d`), 5 tests.

## D-002 — the first held-out run scored every brief against the wrong bar (2026-11-09)

**Measured:** the first held-out composite pass reported **16 of 21 passed, mean 86.2**, and **21 of
21 briefs failed `alpha_matte`** with `border mean 61.0 (>= 249)`. A check that fails on every
single brief is not a result, it is a broken constraint.

**Cause:** `tools/heldout_briefs.py` took **one** brief's constraints (ST-033, a white-background
main image) and reused them for all eight situations. `white_matte` requires a clean near-white
border ring, which only a white-background composition can have — so lifestyle, infographic and
packaging briefs were failed for a rule that was never about them. The scorer was right; the brief
was wrong.

**Fix:** the constraint profile for each situation is copied from the **tuned catalogue's own brief
for that situation**, unmodified. A test asserts each held-out brief's constraints equal the tuned
ones, and a second asserts a white matte is required only where the tuned catalogue requires it.

**Consequence to be honest about:** with the correct bar, four of the eight situations
(`scale_reference`, `bundle_multipack`, `background_swap`, `series_consistency`) legitimately
require a white matte, and the composite route renders a generated scene for them. The tuned
composite proof only ever covered three situations — white-background main, lifestyle and packaging
mockup — all of which are matte-friendly. The held-out numbers are the first measurement of the
other five, and they are lower. That is the finding, not a regression.

**The first run's proof is archived, not deleted:**
`reports/ty/quarantined/heldout_composite_proof_first_run_20261109.json`.

## D-003 — the reference pool held quote cards and a wordmark, not just products (2026-11-09)

**Measured:** the digest contact sheet showed a composite of a **quote card** — "I CARRY MY
CHILDREN NOT JUST IN MY ARMS, BUT IN MY SOUL" — presented as a product output. Checking the pool
visually (`reports/ty/_reference_candidates*.png`) found that of the twelve files copied from the
owner's `pictures for seller umbrella` folder, **only two were the actual box**: the rest are a
dozen social quote cards and the brand wordmark.

**Consequence:** six of the 21 held-out briefs were scored against a quote card rather than a
product. A card is not a product; scoring a seller pipeline on one measures nothing. The two runs
before this fix are superseded, and the earlier claim that 21 briefs covered "14 distinct product
photographs" was wrong — it was 14 files, of which some were cards.

**Fix:** the pool is now seven Word Coffee product images (two on white, five in scene, all showing
the box) and three Mogra photographs — **ten real products over 21 briefs**. A test asserts no
product is tested twice in the same situation, and at least eight distinct products are present.
Non-product files are quarantined at
`reports/ty/quarantined/references_word-coffee_not_products/`.

**Lesson to reuse:** a reference pool has to be looked at, not counted. The file names said "for
mom" and "for women"; only the pixels said "quote card".

**Second pass, after the verifier opened the files:** `wc_women_card_mirror.jpg` turned out to be an
affirmation card on a bathroom mirror with no box in frame, and `wc_women_main_front.jpg` was a
byte-identical copy of `word_coffee_front.jpg`. So the pool is now an explicit **reviewed roster** of
eight photographs (three Mogra, five Word Coffee), and a test hashes them: distinct files must be
distinct photographs, and every path must be on the roster. Names and counts were never the control;
the pixels were.

## D-005 — test modules share one environment, so the suite was order-dependent in both directions
(2026-11-09)

**Measured, twice, in opposite directions.** With `test_costco_api_client.py` ahead of it, the
contract test's product-finder returned a count instead of rows, because that module had left
`SCANNER_SEARCH_CACHE_PATH` pointing at a temp directory that no longer existed. With
`test_coverage_report.py` ahead of `test_product_analysis.py`, the latter read **89 cached
candidates** instead of the one its mocks return, because coverage_report sets
`SCANNER_OFFER_ENRICHMENT=OFF` at import and an unset value means OFF too.

**Three attempts, two of them wrong, and the wrong ones are the useful part:**

1. Restoring these names to their **session baseline** after every test turned 16 green tests into
   `KeyError`s: three modules configure the paths at **import** time and read them with
   `os.environ[...]` inside their tests.
2. Diffing **every** environment name across each module's import and resetting the rest was too
   broad: **67 tests failed**, because modules legitimately configure things for themselves and
   expect that configuration to outlive a single test.
3. What ships: a **narrow watched list** of ten names (the eight scanner paths plus
   `SCANNER_OFFER_ENRICHMENT` and `SCANNER_LIVE_ALLOWED`), restored per test to the value they had
   at that test's start, plus the two modules that need specific values now declaring them in
   `setUpModule`/`tearDownModule` instead of relying on an import side effect.

Verified by pairing the modules that used to interfere, in the order the suite runs them: 48 passed.

**A wrong turn worth recording:** fixing the same symptom by changing
`product_analysis._candidates_for_mode` (fall back to the cache only when the fresh search returned
nothing) made the *product* better, but `product_analysis.py` is a **protected artefact** with a
recorded hash — `test_proof_batch_run` refused it, correctly. The change was reverted rather than
re-baselined: a protected file is not a place to fix a test-environment problem.

## D-006 — the JSX crash checker read comments as code (2026-11-09)

**Measured:** `python tools/check-jsx-imports.py` reported `shell/WorkspacePanels.jsx: <Outlet>`
after the ux-07 merge, failing `test_shell_role_contract.py`. The file never uses `<Outlet>`; a
**comment** explains that the shell renders each tab's page itself "instead of letting the shared
`<Outlet/>` swap pages out".

**Cause:** the checker scanned raw source for JSX tags, so a component name inside a comment counted
as a reference. A checker that flags correct code blocks a correct build — and the next person
"fixes" it by deleting an accurate explanation.

**Fix:** `strip_comments()` removes `/* … */` and `// …` before the tag scan, with a look-behind so
`https://` inside a string survives. Two tests: comments are ignored, URLs are not.

## D-007 — the contract test depended on another module having populated the cache (2026-11-09)

**Measured:** `test_end_to_end_contract_run_on_a_fresh_backend` failed with
`assert "row(s) under 'evaluated'" in '6 measured field(s) (…)'` whenever it ran without a prior test
that had written candidates. Alone it passed; after `test_coverage_report.py` it failed.

**Cause:** `test_network_guard.py` — imported by every module — points `SCANNER_SEARCH_CACHE_PATH` at
an **empty** temp file on purpose (hermetic cache). The contract test's product-finder therefore
returned `evaluated: 0`, a count instead of rows, unless an earlier test had left candidates behind.
Passing was luck, not measurement.

**Fix:** the test seeds a one-candidate cache in its own `tmp_path` and points the environment at it.
It now measures the endpoint rather than the test order. Verified in the pair that used to fail: 24
passed.



## D-004 — a killed render wedged the GPU lane (2026-11-09)

**Measured:** after a composite pass was stopped, the next run refused with
`generator unavailable: gpu locked by {'role': 'seller_composite', 'pid': 11448, ...}` — and pid
11448 no longer existed. `state/gpu/lock.json` had no notion of a stale holder, so the lane stayed
closed until someone noticed and unlocked it by hand.

**Cause:** `tools/gpu_budget.lock()` refused whenever a lock file was younger than the TTL and named
a different pid, without asking whether that pid was still running.

**Fix:** a lock whose pid is **provably gone** (`psutil.pid_exists`, falling back to `os.kill(pid,
0)`) is reclaimed, and the new lock records the reclaim (`reclaimed: {role, pid, at, why}`) so it is
visible rather than silent. A lock held by a **live** process is still refused, which is the property
that matters. A probe that errors counts as alive: stealing a lock because `psutil` is missing would
be worse than refusing. Six tests in `test_gpu_lock.py`.

## D-008 — six prompt-only briefs scored exactly 90.0 because of an inverted branch (2026-11-11)

**Measured:** six of twelve prompt-only briefs score **exactly 90.0**. Every one fails
`alpha_matte` and nothing else (`tools/prompt_only_rescore.py`). The check's own detail names the
cause, and it is not brightness:

| brief | border mean (need ≥ 249) | border std (need ≤ 6.0) | brief limit |
|---|---|---|---|
| PO-001 | 252.1 | **7.19** | std 6.0 |
| PO-003 | 251.8 | **7.68** | std 6.0 |
| PO-004 | 252.1 | **7.17** | std 6.0 |
| PO-006 | 250.8 | **9.00** | mean 251, std 4.0 |
| PO-011 | 251.2 | **8.43** | std 6.0 |
| PO-012 | 251.7 | **7.79** | std 6.0 |

**Cause:** `tools/seller_tester/generators.py:flat()` returned `background.mode != "uniform"`, so a
**white-matte** brief was handed the *generated scene* resampled as its canvas. The scene's edge
grain is bright but not flat, which passes brightness and fails variance — a real compositing bug,
not a rubric artifact, and not the "alpha check on a route with no alpha" this entry first claimed.
The name and the code disagreed and nobody had looked at the pixels.

**Fix:** `flat()` now means a flat field (uniform value, or `matte.mode == white_matte`), and the
compose step writes a flat canvas at the brief's level for those briefs; a `free` brief keeps the
scene. Three tests in `test_seller_tester_composite.py` (a white-matte brief's border passes the
brief's own check, a free brief keeps the scene, and `flat()` semantics), plus one guard in
`scorers.py`: an alpha matte is *not graded* on a full generation, because an opaque plate cannot
produce one and the check would be a constant rather than a measurement.

**Not yet re-measured:** the twelve prompt-only artefacts still on disk were produced by the old
branch and still score 86.4 / 9 passed. The delta requires a re-render of the twelve (one GPU lane),
which is the next unit — not claimed here.


## D-009 — `dev-start.pids` is stale, so stack provenance is only partly provable (2026-11-11)

**Measured:** `dev-start.pids` lists `11664,16960,23512,17252,25384`; 23512/17252/25384 no longer
exist, and the live vite process (15472, parent 13944) is not in the file. Both listeners are
correct and loopback-only (127.0.0.1:8000, 127.0.0.1:8101) and `/health` and `/ui/` return 200.

**Fix:** the script should rewrite the pid file on every start (truncate, not append) and prune dead
pids before it exits, so "started by `scripts/dev-start.ps1`" is a claim the file can support.

## D-010 — a launcher that cannot start its own lane failed silently for days (2026-11-11)

**Measured:** `logs/ty_director_stream.jsonl` held 73 identical
`{"type":"error", … "Agent not found: \"director\""}` lines and `logs/ty_director.log` a five-minute
restart cadence from 2026-11-10T19:40. `heartbeat.json` was last written 2026-11-09T20:46 and said
`ram_paused`, so nothing in the heartbeat reflected the failure. The task itself reported `Running`
and `267009` (still running) the whole time.

**Cause:** `opencode.jsonc` never defined an agent named `director`, so `opencode run --agent
director` exited immediately. The launcher counts a *process exit* as a crash but a *lane-not-found*
as a normal short turn, and the stream file is not read by anything.

**Fix:** the agent is defined now (`opencode.jsonc`, model pinned). The follow-up is to make the
heartbeat red when the stream's last line is an error, so this can never again look healthy for a
day.

## D-012 — five dev-start supervisors, and no single-instance guard (2026-11-11)

**Measured:** a process query for `dev-start.ps1` returned **five** live supervisors (pids 1612, 4040,
9284, 21648, 16108) started by different sessions. Each ends in a `finally` that stops the pids
recorded in `dev-start.pids`, so the last one to die kills the servers the current one is using. The
backend on 8000 was down while 8101 still served: the UI answered and every `/api` call failed.

**Fix applied:** all supervisors stopped, exactly one started, `/health` 200 on 127.0.0.1:8000.
**Fix still owed:** a single-instance lock in `scripts/dev-start.ps1`, and a truncating rewrite of
`dev-start.pids` rather than an append (D-009).

## D-013 — the Golden Goose result block crashed the page it was reporting to (2026-11-11)

**Measured:** clicking Evaluate took the whole SPA to a blank screen.
`pageerror: Objects are not valid as a React child (found: object with keys {scorer_version,
code_name, ...})`. The result block rendered `resale_score`, which the API returns as a scored
payload, directly inside a `<span>`.

**Why it survived:** no click path had ever completed on this panel, so the crash was never reached.
The launch gate that read "no click path" was describing exactly this.

**Fix:** every value the block renders is coerced to text at the edge, an unknown shape reads
UNKNOWN, and non-string warnings render as their readable field. Pinned by
`tests/e2e/g1_golden_goose_persist.spec.ts`.

## D-011 — a lease takeover has a race window of one heartbeat (2026-11-11)

**Measured:** stopping a live auto director (pid 26000) at 06:09Z and writing the lease at 06:10Z
left a window in which the launcher ticked and started a second director (pid 8620, 01:05 local).
Two directors then ran for the rest of the block. Nothing was lost: all work was committed and the
tree was clean at the end, but the window is real and it is the exact thing the one-director rule
exists to prevent.

**Fix:** write the lease **before** stopping the other session, and have `start_director()` refuse
when a lease pid is already alive and is not its own child. A one-line guard in `tick()` closes the
window completely.


**Closed 2026-11-11:** `scripts/ty_director.py::stream_health` reads the last line of the stream and
sets `heartbeat.red`; `death_note()` names a lane error instead of "session gone". 243 error lines
were already on disk when it was written. Five new tests in `test_ty_director_launcher.py`.

## D-011 — the Seller-Tester scores a lookalike pipeline, not the one the product sells (2026-11-11)

**Measured:** the app renders a product picture through
`Northstar_backend/product_picture_api.py:115` → `product_picture.build` (`product_picture.py:191`),
which uses `mockup_compositor`, `mogra_label_art` (print-resolution label art) and `text_fidelity`.
The Seller-Tester renders through `tools/seller_tester/generators.py:766` →
`product_composite.place_product` + `label_warp` (`generators.py:798-801`).

A count of `product_picture|mockup_compositor|mogra_label_art` across `tools/seller_tester/*.py` is
**0**.

**Consequence:** every seller number in this repo (the 40-output replay at mean 22.1, the held-out
mode means, the 2026-11-11 prompt-only result at 93.7 judged) measures the harness pipeline. It may
be a good pipeline; it is not the product's. A score that does not exercise the shipped path cannot
close a seller gap, and the two implementations drift — the harness needed the shadow-framing and
label-truncation fixes made on 2026-11-11, and the app's own path may not have them.

**Fix, not yet done:** the harness's prompt-only and composite routes must call
`product_picture.build` (or the shared module both import), and the score must be produced from that
output. Until then, seller scores are labelled "harness pipeline" wherever they appear. Queued as
`sel-06-exercise-product-pipeline` at rank 1.

## D-016 — the label is scaled to a body narrower than the body in the plate (2026-11-11)

**Measured:** a pale body on a pale sweep loses its silhouette edge to a fixed
16-level mask cut; the measured band set px-per-mm, so the printed label came out
small. On a fixture whose truth is exact (body 500 px wide, 900 px tall) the old
rule measured 479 px, the new one 493 px, i.e. +2.9 % label scale, and the body
height exact. The same fault had a second half: the plate brief was per form, so a
mug and a canister were both asked of the model as an anonymous tube.

**Closed 2026-11-11:** `mockup_compositor.find_cylinder_bands` cuts the mask
relative to the plate's own subject contrast (`max(5.0, min(threshold, 0.20*p99.5))`)
and keeps the vertical extent on the caller's firm cut; `brand_art` declares a
`plate_subject` per cylinder design and `product_picture.plate_brief(face, form,
design)` asks for that object. 4 new tests, 27 in the file, 79 and 75 in the
related groups. `reports/ty/d016_label_scale_plate.md`.

## D-019 — stray geometry survives in the free background (2026-11-11)

**Measured:** after the cutout cleanup (`drop_detached_specks`, `drop_thin_runs`) and
the label clip, the local vision judge (`gemma3:4b`, loopback) passes 10 of 12
prompt-only artefacts on "no stray marks". The two that fail — PO-006 ("a thin
stick/wire visible on the top right") and PO-007 ("a dashed rule line", "a floating
ring") — are objects the model drew into the **scene**, which `_generate_cut_and_compose`
keeps as the background for a free/scene brief. On a flat brief the background is a
white canvas, so nothing survives there.

**Closed 2026-11-13 by the rule this entry asked for.** `Northstar_backend/scene_cleanup.py`
finds ink that sits outside the product's box (a pixel counts as ink when it differs from the
field's median colour by more than 24 levels) and fills each connected component with the **median
colour of its own ring** — deterministic, no model, no GPU. It refuses two cases rather than
painting over them: a component whose ring is not uniform within 18 levels (a textured photograph
would smear) is left in place and named, and a scene where stray ink exceeds 3 % of the frame is
kept and reported. Wired into `_generate_cut_and_compose` right after `place_product`, recorded as
`stray_geometry` on the generation record. 4 tests: a clean scene is a no-op, two marks are filled
on a flat field while the product is untouched, a textured field is reported not smeared, and a
mostly-stray scene is not repainted.

**Still owed:** the 10-of-12 count can only move by re-rendering PO-006 and PO-007, which needs
the render lane; the record now carries what was filled so the next pass can prove it.

## D-018 — a white product on a white canvas defeats the fill instrument (closed 2026-11-11)

**Measured:** ST-024 read 20.7 % against a 24 % floor and ST-031 19.8 % against 20 %
(`reports/ty/white_main_pass.json`). The instrument measured the share of pixels that
differ from the corner colour; white on 255 white differs by about 5 levels against a
distance of 20, so it found almost nothing.

**Closed 2026-11-11:** `scorers._product_mask_from_cutout` maps the product's own
silhouette onto the frame, and `check_subject_fill` uses it **only** when the corner
instrument is blind (under 5 % on a flat background). Provenance added in
`product_picture.build`: `product_box` is recorded and `<face>.cutout.png` is written
beside the picture. Re-scoring the twelve prompt-only artefacts leaves all twelve on
`corner_colour`, so no published score moved. `reports/ty/d018_fill_instrument.md`.

**Still owed:** ST-024/ST-031 were rendered before the provenance existed and must be
re-rendered for their new number.

## D-017 — a plate's opaque contact shadow survives the cutout (closed 2026-11-11)

`_place_on_flat` kept a contact shadow that was opaque enough to pass its solid-alpha
threshold; its own comment said a real matte (BiRefNet in the lane) is what removes it.

**Closed 2026-11-11** (`ty-dir-fix-plate-shadow-matte`). `product_cutout.matte_alpha`
runs BiRefNet through the media lane and refuses by name (`MatteUnavailable`) when the
lane cannot supply one; `_place_on_flat(..., matte="birefnet" | "auto" | "none")` and
`build(matte=)` route it, and every face record and manifest states which matte produced
the picture. Measured on the real plate `renders/comfy_plate7/ST-002/_rejected/
front_plate.png`: the matte returns the mug (1162 × 1000) in **3.68 s** and rejects
**130 357 px** the colour cut had kept, **99.73 %** of them dark neutral — the shadow.
The colour cut was found to be worse than "it keeps the shadow": it cut a 1934 × 1137 band
across the frame, kept **53.2 %** of the product and left the handle in fragments
(`renders/_d017/d017_contact.png`). `reports/ty/d017_plate_shadow_matte.md`.

**Still owed:** the published seller dimension does not move (96.2 over 32 drawn-plate
outputs); a real-plate white-main pass at pinned seeds is the measuring run.

**Measured twice on 2026-11-11** (`ty-dir-d022-real-rerender`). Fresh seeds: PO-001,
PO-002, PO-003 at 2771967432 / 2726882844 / 2572653623 → **3/3 100.0, residue 0.00 %** on
PO-001 and PO-003. At the original seeds (2747063199 / 3952987930 / 3268127863) the same
three briefs score **PO-001 90.0 — 14.760 % residue, 590 541 px — PO-002 100.0, PO-003
100.0**. The composite's shadow is measurably gone (−10.887 points, −435 333 px at an
identical seed) and **the picture is still not clean**: the plate's own cast shadow survives
the grabcut cutout, and the silhouette the check is given does not follow the product, so the
same defect scores 0.00 % on one seed and 14.76 % on another. **D-022 is partially retired**,
not closed. `reports/ty/d022_real_rerender.md`, `reports/ty/d022_pinned_diagnostic.png`.

## D-025 — a generated white-main brief keeps the plate's own cast shadow (open 2026-11-11)

Found by the D-022 real re-render. PO-001 at its original seed 2747063199 still carries a
wide grey smear to the right of and under the pouch after the composite's shadow is off
(`reports/ty/d022_pinned_diagnostic.png`, red = every off-white painted pixel outside the
recorded silhouette). `generators._cut(..., method="grabcut")` keeps it because it is opaque
and attached to the product — the same defect D-017 fixed on the app's plate route with a
real matte.

**Not yet done:** route the generation cutout through `product_cutout.matte_alpha` (BiRefNet
in the lane), falling back to grabcut **with a recorded reason**, and re-measure at the
pinned seed: residue ≤ 0.5 % and no painted band outside the matte-derived silhouette.
Queued `fix-fullgen-matte-cutout`, rank 1.

## D-026 — the residue check's silhouette is not the product's silhouette (open 2026-11-11)

Found by the same run. `check_matte_residue` counts pixels outside the **recorded**
silhouette; on the generation route that silhouette is a coarse shape that covers pouch and
shadow together on one seed (1 280 943 px) and a tighter, offset shape on another
(881 410 px). A picture with a visible smear therefore scores **0.00 %** by being masked
rather than by being clean.

**Not yet done:** record the mask that was actually composited (post-scale, post-placement)
and make the check refuse a silhouette that does not agree with the painted product, or
measure residue against a matte rather than against a rectangle. Queued
`fix-fullgen-silhouette`, rank 2.

## D-020 — the white-matte checks cannot see a shadow under the product (open 2026-11-11)

Found while closing D-017. `check_background` samples the four corner patches and
`check_alpha_matte`'s `white_matte` branch samples an outer ring; **a grey contact shadow
under the product passes both**. Every white-main score in the published seller sample was
produced through that blind spot, and the bruised colour-cut picture D-017 measured
(handle in three pieces) would still score 100 on `background` and `alpha_matte` — the
product-region check, not the matte check, is what catches that.

**Not yet done:** a flat-background main image needs a whole-frame check — pixels below
the asked-for value outside the product's own silhouette (the cutout `D-018` now records)
— and it belongs in `tools/seller_tester/scorers.py`. Queued as `fix-matte-residue-check`
when the scorer lane is next open; until then it is stated here, not hidden.

**Closed 2026-11-11** (`ty-dir-fix-matte-residue-check`). `scorers.check_matte_residue`
measures the whole frame against the product's silhouette; `background` 0.20 → 0.10 +
`matte_residue` 0.10 (the denominator is unchanged, and a picture with no silhouette keeps
the old single weight, so no score moves for a reason other than a measured residue);
`matte_residue` is critical wherever it is graded. Three wiring defects were fixed with it,
each of which had been silently disabling provenance: the harness loaded a cutout **only**
for the composite route (so 0 of 20 `product_picture` artefacts reached the scorers), the
generator's `product_box` arrives nested and null, and the app's own manifest beside the
picture carries the truth. Audit of the published artefacts: the 12 full-generation
outputs re-score as **8 checked, 8 failed, residue 10.2–25.6 % of the frame, mean 100.0 →
90.0**; the 20 drawn-plate outputs cannot be checked (D-021). `reports/ty/d020_residue_audit.json`.

## D-021 — the drawn plate bakes its own shadow into the silhouette (open 2026-11-11)

`scene_render.synthetic_plate` draws a base shadow ellipse `(206, 204, 200)` under every
drawn package ("so the plate is not a sticker on a flat field"). On a white-main brief the
colour cut keeps that ellipse, so **it is inside the silhouette**, and D-020's residue
check — which measures outside the silhouette — reads **0.00 %** on all three drawn
artefacts it could grade (`renders/d020/`, PO-001/003/004). The picture a seller gets is a
product on white with a grey shadow under it, and two instruments agree it is clean.

**Not yet done:** a flat-background brief must not paste a plate shadow: either
`synthetic_plate` omits the base shadow when the brief is a main image, or `_place_on_flat`
drops it by geometry rather than by colour. Queued as `fix-drawn-plate-shadow`.

**Closed 2026-11-11** (`ty-dir-fix-drawn-plate-shadow`). `synthetic_plate(shadow=False)`
draws no base ellipse and the drawn renderer passes `shadow=not white`;
`plate_brief(..., shadow=False)` removes the "contact shadow" clause from every form and
from the bundle branch, and `build()` chooses it from the background. Measured on the drawn
route: PO-001's neutral mid-grey px **941 848 → 30 820** and the product 7 % taller in the
frame; PO-003 **64 405 → 8 006**; PO-004 (gift box) unchanged, which is the control —
that form never drew a shadow. `reports/ty/d021_plate_shadow.json`,
`reports/ty/d021_contact.png`, `reports/ty/d021_drawn_plate_shadow.md`. 5 new tests, 34 + 136
related green.

## D-022 — a full generation has no white-composite step, so its background is a sweep (open 2026-11-11)

The eight failing artefacts above are `route: full_generation` (`SDXL`/`FLUX` scenes): the
prompt says "on a seamless white studio background" and the model delivers a white field
with a **soft grey pool** under the product — 10.2 % to 25.6 % of the frame. Nothing
composites those pictures onto 255; only `product_picture.build` has that step. The app can
deliver a main image two ways and only one of them is a main image.

**Not yet done:** route a white-main brief's full generation through the same cutout-on-
white step (or refuse the brief on that route with the reason). Queued as
`fix-fullgen-white-composite`.

**Closed 2026-11-11** (`ty-dir-fix-fullgen-white-composite`). The cutout-on-white step was
already there; what was missing is `shadow=False`. `_generate_cut_and_compose` now passes
`shadow=not flat(brief)` to `product_composite.place_product`, whose default contact shadow
(1.15 × width, 0.22 × height, blurred, `(18,14,10)`) **was** the grey pool on 255 white. A
free/scene brief keeps its shadow. 4 checks written first: a main image composes with
`shadow=False`, a free brief with `shadow=True`, the delivered main image measures ≤ 0.5 %
residue with `check_matte_residue`, and the same composition with the shadow on **fails** the
same check (the control). 4 + 91 tests green.
`reports/ty/d022_fullgen_white_composite.md`.



## D-023 â€” the app's own readiness gate blocks every carton dieline (open 2026-11-11)

Found by `sel-04-packaging`, the first packaging pass. `package_readiness.REQUIRED_LAYERS`
is `("trim", "fold", "safe")` and `assess_dieline` blocks a build that lacks any of them.
`build_carton` (`rsc_box`, `tuck_end`, `sleeve`) never emits a **safe** layer: measured on
all six shipped carton/sleeve briefs, the SVG layers are
`['bleed', 'fold', 'info', 'trim']` â€” no `safe` â€” while both `doypack` briefs carry
`['bleed', 'fold', 'info', 'marks', 'safe', 'trim']`. So **the app's own retail-readiness
check refuses every folding carton and sleeve it prints**, with its own words: *"dieline is
missing its 'safe' layer"*.

Consequence, measured: `python -m tools.seller_tester packaging` â†’ 8 briefs, **2 pass
(doypack), 6 fail** `layers` + `readiness`, mean **78.6**, 6 gaps filed
(`reports/ty/packaging_pass.json`, `state/seller/packaging_gaps.json`).

**Not yet done:** `build_carton` must emit the safe-margin inset (the doypack's `safe_mm`
path already exists), and then the six briefs should pass their own gate. Queued as
`fix-carton-safe-layer`. Until then this is a real 6/8 failure of the packaging lane, not a
brief problem: the same briefs pass `sheet`, `panels`, `bleed`, `pdf`, `safe` (skipped with
the reason) — only the missing layer fails them.



**Closed 2026-11-11** (`ty-dir-fix-carton-safe-layer`). `_panel_blank(..., safe_mm=)` writes
one safe rectangle per body face, inset by the margin from the trim and from both folds;
`build_carton(..., safe_mm=)` and the three carton templates declare it (default 3 mm) and
`build_from_template` passes it through. Measured on the same eight briefs: **2/8 → 8/8
passed, mean 78.6 → 100.0**, safe margins readable per artefact (5 mm doypacks, 3 mm
cartons). 13 checks written first, 80 + 45 related green.
`reports/ty/d023_carton_safe_layer.md`.



## D-024 — the composite route kept the contact shadow its guard could not see (closed 2026-11-11)

Found by the D-022 lane pass on the same run: **SR-001** (white-main brief, real seller
photo, composite route) measured **11.473 %** background residue, **458 900 of 458 901 px
neutral** — the shadow. The route's white-main guard measured the four **corners**, and a
contact shadow sits under the product, so the corners stayed exact and the shadow shipped.

**Closed 2026-11-11** (`ty-dir-fix-composite-white-shadow`). `generators._composite` places
with `shadow=not white_main`; the corner measurement stays as a second gate. Two checks: a
white-main composite calls `place_product(shadow=False)`, a lifestyle composite calls it
with `shadow=True`. 26 + 4 tests green. `reports/ty/d024_composite_shadow.md`.

**Still owed:** nothing measured — the real-lane after-number landed the same cycle.

**Measured, real lane** (`ty-dir-d024-real-residue`): `composite --limit 2` again after the
fix → **SR-001 residue 11.473 % → 0.037 %** (458 901 px → 1 488 px) and its score **93.3
(failed) → 100.0 (passed)**. PO-001 re-measured 0.000 % in the same run.
`renders/d024/`, `reports/ty/d024_sample_pass.json`,
`reports/ty/d022_residue_before_after.json`.

**Re-measured independently** (`ty-dir-d024-real-residue`): the brief alone, in its own
catalog and its own out-dir → **10.49 % (419 583 px) before, 0.482 % (19 282 px) after,
100.0, pass**. The run is deterministic: two invocations write a byte-identical artefact
(`sha256 a3dfed02…`) and cutout (`fb370d3d…`). It does **not** reproduce 0.037 %; that
artefact was overwritten by this run's `--out-dir`, so the difference cannot be explained
from disk and is recorded as unexplained rather than smoothed. Both numbers pass the 0.5 %
limit. `reports/ty/d024_real_residue.md`.


## D-027 - a design cannot choose its motif, so every box carries three ovals (open 2026-11-11)

Found by pack-03. `brand_art._spec` sets `motif="bean"` for any design that does not
declare one, and no design does. On a coffee pouch or a mushroom label the bean motif is at
least a plant; on a drill carton it is three ovals under the copy, and on a kettle carton the
same. It is the one decorative element the renderer draws inside the panel, so a missing
motif is not cosmetic - it is the only illustration on the pack.

Measured: both pack-03 artefacts (`renders/pack03/ST-012/product_front.png`,
`renders/pack03/ST-028/product_front.png`) carry three ovals. Neither design declares a
motif key.

Fix shape: `motif` is already read from the design (`_spec`), so a design that declares one
wins. What is missing is (a) a small library of drawn motifs (tool, appliance, garment,
bottle) and (b) a refusal when a form that needs one has none, so a pack never ships with a
loaner illustration. Queued as `design-motifs`, rank 6.
