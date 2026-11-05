# V3 readiness — measured baseline after the V2 close

> **Addendum 2026-11-05 — bake-off complete.** `gemma3:4b` cleared the Stage 2 gate at **18/20**
> with a **1.0 JSON parse rate**; `moondream` 13/20, `llava:7b` 12/20, `qwen2.5vl:7b` 0/20
> (degenerate output). The memory module now graduates all three stages
> (`reports/v3_graduation_memory_20261105.json`). The "blocked" findings below are the record of the
> first pass; the final result is in `reports/vision_bakeoff_results.json`.

> **Status 2026-11-04 (later the same day):** the three residual test failures listed in
> §3, the Chrome parity condition in §5 and the 15 s Wan master in §7.4 are now closed.
> Evidence: `reports/v3_readiness_closure_20261104.md`,
> `reports/chrome_parity_20261104.{md,json}`, `reports/v3_master_video_20261104.json`.
> The body below is the historical baseline as measured at the time and is not rewritten.

**Date:** 2026-11-04 · **Scope:** the V2→V3 reconciliation, the human-feature guardrail, the
three-stage graduation gate, and the first Ty's Vision implementation. No new feature lane was
started.

---

## 1. V2 closure — corrected record

| Claim | Measured reality |
|---|---|
| Tys Assistant Vision established | **Not true.** No vision module existed before this pass. `agent_kernel/vision_verify.py` now exists, but the local `qwen2.5vl:7b` runner returns degenerate text on real product images; Stage 2 is **blocked**. |
| Architecture stabilised | Partly: one kernel, one loop, one image gate, one memory API; Chrome Connect, kernel and studio remain separate by design. |
| Chrome Connect retired | **Not executed.** It is still the browser controller and the policy/lease/Amazon enforcement point. |
| Wan 2.2 standard | **True** (`shorts.py`, `video_formats.py`; A14B Q4 on disk). |
| Product-grade packaging | **True for the reference lane** (front/back passed the OCR gate); DRAFT nutrition/UPC remains. |

## 2. Implemented in this pass

### 2.1 Human-feature guardrail (V3.2)

* `Northstar_backend/video_guard.py` detects faces/hands/bodies/people in a video prompt.
* `POST /api/design-studio/shorts` and `POST /api/design-studio/generate` (kind=video) return
  **422 `human_features_warning`** with the owner's exact text before any GPU work.
* `human_features_ack: true` is the only override; product-only prompts pass.
* Tests: **6 passed** (`test_video_guard.py`).

### 2.2 Three-stage graduation gate

`tools/v3_graduation.py`: AST symbol audit + test command (Stage 1), Ty's Vision verdict on a
screenshot/constraint (Stage 2), E2E command (Stage 3). Every stage fails closed; a missing
screenshot or E2E is `not_verified` / `not_run`, never a pass. Tests: **6 passed**.

### 2.3 Ty's Vision

`agent_kernel/vision_verify.py` asks the local vision model for one JSON verdict, with an injectable
caller and a hard `available: false` on any failure. It downscales to 512px and caps `num_ctx` at
4096 to avoid the 7.4 GB / 64K default that left 0.74 GB free RAM.

**Live result:** the verifier returned `available: false` — `qwen2.5vl:7b` produced no parseable
JSON on the real `product_front.png`. A probe shows the runner also returns HTTP 500 when
`format=json` is combined with an image; text-only and 64px-image calls work. The model is not
usable for Stage 2 as installed. This is a blocker, not a pass.

## 3. Measured test baseline

Full backend suite (before the fixes in this pass):

```
13 failed, 6045 passed, 117 skipped, 2 xfailed, 89 subtests passed in 950.92s (15:50)
```

Failures and disposition:

| Failure(s) | Cause | Status |
|---|---|---|
| `test_session_cookie_contract` ×5 | `request.app` raises `KeyError` when a bare Request has no ASGI app scope | **fixed** in `auth_deps`; 5 targeted tests pass |
| `test_provider_suite` ×1 | `test_blockers` leaked `FakePS` into `sys.modules` | **fixed** with `monkeypatch.setitem`; 49 targeted tests pass |
| `test_autonomy_readiness` ×3 | fixtures wrote a new module without the new `wiring` contract | **fixed** in the fixtures; 18 pass |
| `test_frontend_gate` route count | `App.jsx` has 58 routes after the UX rebuild; test expected 53 | count updated; the test now fails later on a **real** legacy import |
| `test_frontend_gate` legacy client | `pages/internal/PackifyDesign.jsx` still imports `services/api.js` | **open** (V3.3 packaging) |
| `test_shell_modes` ×2 | `advanced_view` entitlement is `[]` for every plan; the tests expect `mover+` | **open** — owner product decision |
| `test_local_screen` watcher | timing-sensitive; passes alone and in the 80-test file rerun | flake; monitor |

**Residual known failures: 3** (one real packaging legacy import, two product-decision tests).
A full-suite rerun was not performed after the fixes; the targeted reruns above are the evidence.
Stage 1 is therefore **red** and the hard freeze applies.

## 4. Memory module graduation report

`reports/v3_graduation_memory_20261104.json`:

| Stage | Result |
|---|---|
| 1 — AST + `test_semantic_memory.py` | **passed** (13 symbols, 0 duplicates/placeholders, tests exit 0) |
| 2 — vision on `product_front.png` | **failed** — `no JSON object in the vision answer` |
| 3 — E2E (`test_tracing.py`) | **passed** |
| Overall | **failed** (Stage 2) |

That is the rubric working as intended: a module cannot graduate on tests alone.

## 5. Chrome Connect decision

The V3.1 direction is accepted, but the controller is **not** retired in this pass. Removing it
before the replacement enforces the same rules would bypass the browser gates. Migration requires
six-point parity (host policy + Amazon blocklist first, Profile 6 lease, credential/CAPTCHA/login
stops, redirect re-check, audit journal, browser benchmark). Until then the vision layer observes;
Chrome Connect enforces.

## 6. V3.x status

| Version | Status |
|---|---|
| V3.1 Vision | Scaffolded; **blocked** on a working local vision model and Chrome parity |
| V3.2 Wan 2.2 | Engine already present; **guardrail implemented and tested**; 15/30 s masters next |
| V3.3 Packaging | Reference front/back verified; open: PackifyDesign legacy client, DRAFT nutrition/UPC |
| V3.4 Stabilisation | Rubric implemented; full-suite Stage 1 red (3 known failures) |

## 7. Next actions (in order)

1. **Vision bake-off** on 20 fixed reference images (moondream2 / llava / qwen2.5vl), pick the
   smallest model with ≥18/20 correct verdicts and a measured RAM ceiling. Update `vision_verify`.
2. **Fix or quarantine the 3 residual failures**: migrate `PackifyDesign.jsx` off `services/api.js`
   (V3.3); owner decision on `advanced_view` entitlements; keep the watcher test under flake watch.
3. **Chrome parity harness** before any controller change.
4. **V3.2**: one 15 s Wan master through the guardrail, ffprobe + OCR + loudness checks.

## 8. Decisions

1. Accept V3; do not retire Chrome Connect before parity.
2. Treat Ty's Vision as unproven until the bake-off passes; Stage 2 stays fail-closed.
3. Adopt the graduation rubric as a merge gate; the memory module report is the first artifact.
4. Hard freeze remains: no new feature lane while Stage 1 is red.
5. The human-feature override is explicit, logged and off by default.
