# Autonomous creative campaign — simple mode, first unit (2026-11-02)

DeepSeek built the simple-mode creative path end to end and fixed the defect that made
it useless: **the text-suppression phrase was choosing the subject.** Evidence below is
from the live backend, not a fixture.

---

## 1. AUDIT — creative stack, as measured

| Piece | Class | Evidence |
|---|---|---|
| Chat surface (simple mode) | **VERIFIED** | `northstar-os-ui/src/chat/ChatSurface.jsx`; `/ui/` serves; asset list API 200 |
| Design Studio generate API | **VERIFIED** | `POST /api/design-studio/generate` 200, asset in 26 s |
| ComfyUI / FLUX bridge | **VERIFIED** | `127.0.0.1:8188` reachable, `flux3-image-klein-nvfp4` loaded |
| Media engine gate | **DEFECT → FIXED** | live server reported `armed:false` because it was a bare `uvicorn` (launcher env lost); restart through `launch_alpha.ps1` → `armed:true` |
| Text-suppression phrase | **DEFECT → FIXED** | below |
| Deliverable fetch | **VERIFIED** | `/api/design-studio/assets/{id}/file` → 1.2–1.7 MB PNG, 1024×1024 |
| Mockup/label step | **NOT RUN** | needs the operator's plate + logo; separate unit |
| A+ module render | **VERIFIED (earlier)** | `reports/aplus_render_20261031.md` |
| Theme polish | **NOT STARTED** | gated behind journey stability |

Journey rate: **1 of 1** end-to-end completes (health → armed → generate → fetch).

---

## 2. THE UNIT — `ty-suppression-subject`

**Defect.** Every text-safe render appends `SUPPRESSION_PHRASE` to the brief. It read:

```text
Blank unprinted matte packaging surface shown as pure material, finish and
botanical illustration only: no lettering, no words, ...
```

Two positive scene instructions — "blank … packaging surface" and "botanical
illustration only" — so the brief was overridden:

| Render | Output |
|---|---|
| brief: a 6 oz pouch of lion's mane powder, **before** | botanical herbarium plate |
| after removing only "botanical illustration only" | blank framed grey panel |
| after removing the whole scene clause (**fix**) | kraft packaging photographed on white |

**Fix.** The phrase is now purely prohibitive:

```text
no lettering, no words, no typography, no logo, no barcode, no QR code,
no captions, no watermark of any kind
```

**Probe** `state/probes/t10_suppression_phrase.py` (fails at HEAD): no subject named,
every clause is a prohibition, phrase appended verbatim, the brief's subject survives,
and an explicit typographic demand is still suppressed. **Commit `6f069143fe01`.**

**Still open (named, not hidden):** the render returned a **carton**, not a stand-up
pouch — subject class is right, product form is not. That is prompt-adherence at the
draft tier, a separate unit.

---

## 3. FAILED PATH — the unattended lane hung twice

`scripts/go_author.py` (the Go CLI lane) hung for 25–30 minutes on the two large-file
contracts (`text_fidelity.py` 24 KB, `mockup_compositor.py` 22 KB), leaving the task in
`authoring` with no edit and no commit. The supervisor restored cleanly both times; the
harness now has a per-turn timeout (returncode 124) and a 600 s task deadline.

Consequence: **this unit shipped through the supervised handoff** (operator ferry), not
unattended. The unattended lane remains proven only for the small-file task
`ty-quad-area-guard`.

**A second, more serious finding from the same window:** the restore path used to
delete any file created during the handoff, including another process's report. That
is fixed — `restore_baseline(paths=…)` now honours an explicit path list, and an
out-of-scope file is reported (`out_of_scope_left`) and **left untouched**. Test
updated accordingly. One unrelated improvement report (`reports/improvement/cycles/
20261102-010002-3e6ad4.md`) was deleted by the old behaviour before the fix.

---

## 4. SPEND

| Item | Cost |
|---|---|
| Go interface probe (9,663 in / 8 out) | $0.001456 |
| Go edit-shape probe (estimate) | $0.002000 |
| Two hung unattended turns (estimate, no usage returned) | $0.002200 |
| **Window position now** | **5h $0.0057 / $7.20 · week / month accordingly** |

Zero spend on the creative renders: local ComfyUI on the operator's GPU.

---

## 5. DECISIONS (autonomous)

1. Diagnosed the journey as **disarmed engine**, not a UI bug — the live server was a
   bare uvicorn without the launcher env. Evidence: `armed:false`, `gate:false`.
2. Restarted through `launch_alpha.ps1 -NoTunnel -NoAutothink -NoComfy` (documented
   rule; no public endpoint, no spend).
3. Rejected the "text-safe" phrase as *guidance* and treated it as a defect: it was
   choosing the subject.
4. Fixed the phrase to **pure prohibitions**, and extended the probe to enforce that
   ("every clause starts with `no `") so the class of bug cannot return silently.
5. Fixed the restore path before using the lane further, after it deleted a concurrent
   file — safety before throughput.
6. Shipped this unit via the **supervised handoff** because the unattended lane hung
   twice on large prompts; did not retry a third time.

---

## 6. LEARNING

* Trajectories: **7** (threshold for the cold-vs-informed re-measurement is 10 — not
  reached; the negative delta stands).
* Lessons for `state/lessons/`: "suppression must be negative-only"; "creative code
  changes need a launcher restart — the server serves the imported module"; "large
  prompts hang the CLI lane".

---

## 7. REGRESSION

```text
python -m pytest Northstar_backend/test_text_fidelity.py -q
1 failed, 19 passed   (the failure is the PRE-EXISTING auth-ordering test)
python -m pytest test_go_author.py test_author_lane.py -q
19 passed
```

---

## 8. STATE

* HEAD after this report: `6f069143fe01` + docs.
* Backend restarted via the launcher and **armed**; seller-facing services untouched.
* No lock, no STOP, no worker, no resident model.
* `state/evidence/simple_mode_journey.json` records the latest journey stages.

---

## 9. VERDICT

**ADVANCING** — the simple-mode journey now completes end to end on the live backend,
and the defect that made every text-safe render a botanical plate is fixed with a probe
that fails at HEAD before the fix.

Not **STABLE**: the product-form adherence (carton vs pouch) is open, the mockup step is
unrun, and the UI journey has only been verified through the API plus the static build —
no browser pass.

---

## 10. NEXT DECISION (one)

Authorise the **subject-adherence unit** (make the draft tier honour the requested
product form, with a render-level check) — or move to the mockup/label step first.
