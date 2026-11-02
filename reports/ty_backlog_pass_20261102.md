# Backlog pass — three more DeepSeek-authored, Ty-supervised fixes (2026-11-02)

Queue frozen at three, all three committed. Six accepted repairs this session.
No model was loaded: the whole pass ran through the supervisor handoff.

---

## 1. QUEUE

| Contract | Probe at HEAD (exit) | Failure count | Scope (write) |
|---|---|---:|---|
| `ty-dpi-image-guard` v1 | `python state/probes/t1_dpi_image_guard.py` → **1** | 3 | `Northstar_backend/print_prep.py` |
| `ty-frame-fill-guard` v1 | `python state/probes/t2_frame_fill_guard.py` → **1** | 4 | `Northstar_backend/image_prep.py` |
| `ty-hero-fill-guard` v1 | `python state/probes/t3_hero_fill_guard.py` → **1** | 5 | `Northstar_backend/listing_image.py` |

Each is a real defect with an objective check: the print gate ignored the image it was
given; the two framing lanes accepted a scale that crops the product and an empty
cutout. Contracts carry objective, read/write scope, probe, commit paths, 8 steps and
one repair.

**Surplus proposal, no contract:** `cost_model.ppc_fee` / `cost_model.refund` show
genuine boundary defects (a **negative credit count returns a refund larger than the
amount paid**; NaN spend yields a fee). Fees, refunds and credit weighting are
**billing logic**, which the directive excludes. Recorded here, not queued.

---

## 2. TASK TABLE

| Task | Defect class | Self-revisions caught before submit | Probe | Commit | Trajectory |
|---|---|---|---|---|---|
| `ty-dpi-image-guard` | validator-ignores-input | defensive `image_size` unpack; guard before `face_pixels` so the positive control still passes; compare in pixels not mm | `FAIL(3)` → **PASS** | **`d5ba3ced`** | `validator-ignores-input.jsonl` |
| `ty-frame-fill-guard` | missing-input-validation | **ran the probe before submitting and caught a missing `import math`**; `isfinite` for nan/inf; half-open `(0,1]`; empty subject via `alpha_bbox` | `FAIL(4)` → **PASS** | **`9f692f21`** | `missing-input-validation.jsonl` |
| `ty-hero-fill-guard` | missing-input-validation | same guard shape as the framing lane so the two cannot drift; existing empty-subject refusal preserved; `fill=1.0` still valid | `FAIL(5)` → **PASS** | **`fa46b397`** | `missing-input-validation.jsonl` |

No repair attempt was needed (`max_repairs=1` unused on all three); no restore was
triggered; every commit contains exactly one file. Focused regressions before each
submit: 33, 21 and 34 tests respectively.

---

## 3. HANDOFF

* **One operator ferry**, batched: `state/author_handoffs/BACKLOG_HANDOFF_20261102.md`
  lists all three contracts with objective, write/read scope, probe and commit message.
* Per task: `--author-open` → author writes and self-reviews → `--author-close`
  (scope audit, probe, regression, commit). **Three open/close pairs, three commands
  each.**
* Friction: none material. The single real catch was the author's own — the missing
  `math` import surfaced when the probe was run *before* submitting, which is exactly
  what the self-review step exists for. The handoff leftovers are zero.

---

## 4. REGRESSION

```text
240 passed, 1 skipped in 11.54s
```

Twenty suites: the 15 supervisor/protocol suites plus `test_image_prep`,
`test_print_prep`, `test_prepress`, `test_creative_flow`, `test_studio_sizing`.
The skip is the pre-existing OCR-unavailable case.

---

## 5. LEARNING STORE

**6 trajectories** recorded (append-only, `state/fix_patterns/`): three from the
qualification pass, three from this pass. Next measurement is scheduled at **10**
recorded trajectories, per the directive — the negative cold-vs-informed delta from
the 6-run experiment stands and was **not** re-run.

---

## 6. STATE

* Task commits this pass: `d5ba3ced`, `9f692f21`, `fa46b397`.
* Session total: 6 accepted repairs (`883a7fed`, `9e8e2cdb`, `e1585917`,
  `d5ba3ced`, `9f692f21`, `fa46b397`) — 6 of the 8-task cap.
* No lock, no STOP, no worker, no resident model; no model was loaded during this
  pass. Operator daemon untouched (`cpu`/`q4_0`, GPU 0 MiB).
* All six probes (`t1`, `t2`, `t3`, `t5`, `t6`, `t7`) exit **0** at HEAD.

---

## 7. VERDICT

**READY**, scoped to *operator-ferried, DeepSeek-authored, Ty-supervised autonomous
repair*: six real defects fixed, every probe flipped fail→pass, every commit task-only
with supervisor scope audit, zero restores needed, zero out-of-scope changes.

Not claimed: unattended dispatch, the broader NorthstarOS product, or any learning
gain.

---

## 8. NEXT DECISION (one)

Authorise **unattended dispatch** through the paid OpenRouter API — the author lane
would call the model from the supervisor instead of relying on the operator session —
or stop here.

Not taken, and not recommended without a billing decision: per-token spend is a
standing gate.
