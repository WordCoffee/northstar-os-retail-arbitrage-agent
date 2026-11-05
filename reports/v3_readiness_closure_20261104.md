# V3 readiness — closure of the 2026-11-04 action items

**Date:** 2026-11-04 · **Scope:** the four remaining items in
`reports/v3_readiness_20261104.md` §7. Nothing new was started beyond them.

---

## 1. What changed

| Item (from §7) | Result |
|---|---|
| 2. Migrate `PackifyDesign.jsx` off `services/api.js` | **done** — imports `services/signals.js`; the legacy client is no longer referenced by any v3 module |
| 2. Owner decision on `advanced_view` | **decided (already on disk) and reconciled** — catalog v5 (2026-10-30) is AutoThinK-only; the two stale test assertions now match it |
| 2. Watcher test under flake watch | **stabilised** — the two timing races were removed, not widened |
| 3. Chrome parity harness | **built and passing** — six points verified, `reports/chrome_parity_20261104.{md,json}` |
| 4. 15 s Wan master through the guardrail | **shipped** — 15.000 s, 1080×1920, 30 fps, 450 frames, OCR-clean; `reports/v3_master_video_20261104.json` |

## 2. PackifyDesign migration (V3.3)

`northstar-os-ui/src/pages/internal/PackifyDesign.jsx`

* `import { api } from '../../services/api.js'` → `import { signals } from '../../services/signals.js'`
* `api.autothinkRun(...)` → `signals.autothinkRun(...)` (same POST `/api/autothink/run`, same
  error contract: an `Error` carrying `{status, code}`).

This was the last v3 module importing the deprecated client. `test_frontend_gate
::test_v3_shell_invariants` scans `pages/internal`, `pages/customer`, `pages/admin`,
`pages/public`, `foundation` and `components` for the string `services/api`; it now finds
nothing.

**Evidence:** `test_frontend_gate.py` **25 passed**; `npm run build` **0 errors**
(1,063.65 kB main chunk, built in 1.77 s).

## 3. Advanced view + test fixes (V3.4)

### 3.1 The entitlement question was already answered

The report recorded `advanced_view` as an open product decision. It was not: the owner's
Phase II reconciliation on **2026-10-30** set it — `shared/subscription-plans.json`
**catalog_version 5** carries a dated revision note and `mover.ui_gates = []`, with
`advanced_view` on `autothink` only. The two failing tests still asserted the v4 array
(`mover` → `["advanced_view"]`), so the *tests* were stale, not the product.

Reconciled in `test_shell_modes.py`:

* `test_ui_gates_are_advanced_view_on_top_tiers_only` now asserts `mover == []`,
  `autothink == ["advanced_view"]`, and that the gate lives on **exactly one** tier
  (a future silent widening fails the test);
* `test_user_ui_gates_read_plan` asserts the same through `auth.user_ui_gates()`.

The module docstring was corrected in the same change so the prose no longer describes v4.

### 3.2 Watcher tests

Two genuine races, both self-inflicted by the tests:

1. `test_watcher_stops_after_bounded_consecutive_failures` polled `state()` against a 5 s
   wall-clock deadline. Under a loaded full-suite run the worker thread had simply not been
   scheduled twice yet, so the deadline expired first. It now **joins the worker thread**
   (bounded at 15 s so a hung loop still fails) and asserts the exact attempt count — a real
   retry-budget regression still fails, a slow box no longer does.
2. `test_watcher_start_is_idempotent_and_stop_is_clean` called `stop()` immediately after
   `start()`. If the stop flag was set before the loop body first ran, `samples` stayed 0 and
   `assert samples >= 1` failed. It now waits on a `threading.Event` that the fake sample
   sets — it tests the property, not the scheduler.

**Evidence:** `test_shell_modes.py` + `test_local_screen.py` → **82 passed**.

## 4. Chrome parity harness (V3.1 precondition)

`tools/chrome_parity_harness.py` measures the six properties that a replacement would have
to reproduce, against the controller that is actually running:

```
1. Host policy + hardcoded Amazon blocklist, evaluated first: VERIFIED
2. Profile 6 lease (exact directory); every other profile refused: VERIFIED
3. Credentials / CAPTCHA / login are stops, never automated: VERIFIED
4. Policy re-checked against the current URL after every action: VERIFIED
5. Audit journal records decisions, tool calls and results: VERIFIED
6. Browser-brain benchmark runs and measures: VERIFIED
OVERALL: PASS   (6 verified, 0 failed, 0 not_verified)
```

The harness is fail-closed: every point is `verified | failed | not_verified`, a missing
input is `not_verified` (never a pass), and `pass` requires all six. It runs read-only
against the controller (node probes + a throwaway journal directory) and refuses to measure
a different deployment than the one requested. Detail and the controller's own stale-suite
drift: `reports/chrome_parity_20261104.md`.

**Tests:** `Northstar_backend/test_chrome_parity_harness.py` — **31 passed**, including
tampered-evidence cases for each evaluator (Amazon not refused, wrong profile authorized,
CAPTCHA removed from the prohibited list, unredacted secret in the journal, missing bench
artifact) so a rubber-stamping harness cannot pass.

## 5. 15-second Wan master (V3.2)

Two defects had to be fixed before the lane could produce anything at all, which is the
honest reason the milestone had never been met:

| Defect | Effect | Fix |
|---|---|---|
| `NameError: uuid` in the `/shorts` **stitched** branch | the multi-clip path had never executed; every 15 s request died before the first sampler call | `import uuid` in `make_shorts` + an endpoint-level regression test (`test_the_shorts_endpoint_wires_the_stitched_branch`) |
| the negative prompt was not threaded through `generate_stitched` | each clip rendered with the module default only; Wan painted lettering onto the pouch | `negative=` parameter threaded to every clip, `shorts.master_negative()` as the single source of truth, text-suppression terms added, endpoint passes it |

### Runs (all real, all on this GPU)

| # | Prompt | Guardrail | Outcome |
|---|---|---|---|
| 1 | “…a pair of **hands** gently turns the pouch…” | 422 `human_features_warning` without ack → **allowed with `human_features_ack: true`** | 6 clips, 1,052.2 s, then the quality gate **refused**: OCR read invented text (“RDOGiT”), layout “cropped by hands”, 0/3. File deleted. |
| 2 | clean prompt, mushroom/plinth brief | passes cleanly, no override | 931.8 s, layout **pass**, typography **pass** (OCR: no lettering — the new negative worked), design_alignment **fail** (`brief_mismatch` against a blank pouch). File deleted. |
| 3 | “a plain stand-up pouch, front panel facing the camera, neutral studio background, soft studio light, matte kraft finish, slow steady camera orbit” | passes cleanly | **PASS**, 200 OK |

Run 1 is the override-path evidence: the guardrail refused before any GPU work, then an
explicit acknowledgement let the render proceed — and the resulting frame was exactly the
degradation the owner's warning describes. That is the guardrail being right, not a bug.
Runs 2–3 are the shipping path the guardrail itself recommends: product-only.

### Shipped master (run 3)

```
file      Northstar_backend/data/studio_generated/short_stitched_148acb2e38.mp4
duration  15.000 s        canvas 1080 × 1920 (9:16)      fps 30
frames    450             codec  h264 / yuv420p          bytes 8,307,840
audio     none (silent clip — reported, not invented)
OCR       contains_text false, 0 boxes  (rapidocr)
plan      shorts · 6 clips × 77 frames · max 81 frames/clip · compliance verified (2026-11-03)
quality   layout pass · typography not_applicable (OCR confirms no lettering) · design_alignment pass
```

A frame was read back and looks like what the brief says: a plain kraft stand-up pouch,
centred, no lettering.

**Not claimed:** loudness is `no audio stream`, so there is no EBU R128 measurement to
report — the master is silent by construction. The label lane composites real text later;
this master is the clean plate that lane consumes.

## 6. Test baseline

| Suite | Result |
|---|---|
| `test_frontend_gate.py` | 25 passed |
| `test_shell_modes.py` + `test_local_screen.py` | 82 passed |
| `test_shorts_stitch.py` + `test_video_guard.py` + `test_video_formats.py` | 20 passed |
| `test_chrome_parity_harness.py` | 31 passed |
| `npm run build` | 0 errors |
| full `Northstar_backend` suite | **6095 passed, 117 skipped, 2 xfailed, 89 subtests, 0 failed** in 885.20 s (`reports/v3_full_suite_20261104.txt`) |

The baseline this closes out was `13 failed, 6045 passed, 117 skipped, 2 xfailed, 89
subtests in 950.92 s`. Zero failures, 50 more tests (the new harness/endpoint/negative
coverage), and a shorter run.

## 7. Decisions recorded

1. `advanced_view` stays AutoThinK-only (v5 catalog). The tests were reconciled to the
   decision; the decision was not moved to fit the tests.
2. Chrome Connect is still the controller. A passing parity report removes an objection; it
   does not create a replacement. Retirement still needs a replacement that passes this
   harness.
3. The human-feature override stays explicit, logged and off by default. Live evidence now
   exists for both positions (refusal and override), plus the measured cost of overriding.
4. The video lane suppresses invented lettering by default (`shorts.TEXT_SUPPRESSION`); a
   video render never composes text.
