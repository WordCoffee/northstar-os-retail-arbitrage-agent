# Creative Service & Packify.ai Quality Campaign

**Campaign:** `creative-service-packify-quality`
**Date:** 2026-11-02
**Author:** DeepSeek V4.1 Flash (opencode-go, operator session); local vision `qwen3.5:4b`
**Branch:** `feature/chrome-connect-3.0` — rollback tag `rollback/pre-packify-20261102-070637`
**Units:** 2 of 2 used · wall clock ≈ 1 h 30 m of the 4 h cap · 0 failed attempts

---

## VERDICT

**PARTIALLY READY — units delivered, two campaign objectives deliberately not attempted.**

| Objective | State |
|---|---|
| 1. Dieline & geometric precision | **Done.** Invariants enforced, impossible specs refused, one real pouch defect found and fixed. |
| 2. Typography & asset hierarchy | **Done at the acceptance gate.** Requested copy is now read back by OCR and checked against the brief; garbled or missing copy blocks delivery. |
| 3. Photoreal material & lighting | **Not attempted.** No ComfyUI workflow was changed. The finish is *recorded* from the render, never claimed as simulated. |
| 4. End-to-end verification gate | **Done and live.** Form, brief alignment, layout and typography block; material is recorded; a blocked run writes no folder. |

Not attempting (3) is the honest call inside a two-unit cap: driving foil/laminate/UV workflows
would need sampler, LoRA and prompt-template work that could not be verified in the time left,
and a half-tuned material preset would have degraded the renders the gate now protects.

---

## PER-UNIT BREAKDOWN

### Unit 1 — `ty-dieline-geometry` (commit `86e59278`)

**Purpose.** Stop the builders from *clamping* an impossible spec into a drawable one.

**Steps (4).** `dieline_geometry.py` (audit + refusal + artwork boxes) → replace the two label
clamps → gate `build_from_template` and `build_carton` → fix what the gate found.

**Invariants now refused**, each with a code: `bleed_missing`, `bleed_exceeds_face`,
`safe_missing`, `safe_inverted`, `safe_outside_trim`, `element_outside_bleed`, `panels_invalid`,
`panel_outside_trim`, `panels_overlap`, `tab_deeper_than_body`, `face_below_min`, `no_trim`.

**Artwork rule.** `art_boxes` returns one safe box per panel; `audit_artwork` refuses a rect
that straddles a fold or sits in the bleed. Type that crosses a fold is creased, not "flowing".

**Self-review catches (4).**
- A validator that lives beside the builder is ignored by the next builder → the gate is called
  inside `build_from_template` and `build_carton`, so every template passes through it.
- An audit that flags the five shipping templates is useless → all five (plus doypack) are
  positive controls in the tests.
- Pouch panel maps are `{name: [x,y,w,h]}` while carton panels are a width list; treating them
  alike crashed on `float('front')` → two modes, validated separately.
- The first violation the audit raised was real, not a threshold to relax → see below.

**Defect found on the audit's first run.** Doypack, 150×210 + 80 gusset: the back panel ended
**6 mm (one weld) past the trim line** — `y_back` added a third weld the sheet-height formula
never included. Before: back panel `y=319…529`, trim bottom `523`. After: `313…523`.

**Sample evidence.**

```
doypack audit  before: ['safe_outside_trim', 'panel_outside_trim']
doypack audit  after : ok
refusals       : safe 12mm on a 20x20mm label -> safe_inverted (422 at /print/dielines)
                 bleed 0 -> bleed_missing | 8x8mm face -> face_below_min
                 negative panel -> panels_invalid | flap 55mm on 40mm body -> tab_deeper_than_body
artwork        : panel 1 accepts an inset rect; a rect spanning panels 1-2 -> artwork_outside_safe
```

### Unit 2 — `ty-quality-gate` (commit `d746667b`)

**Purpose.** Delivery required only that the *container shape* matched. A brief asking for label
copy could ship a blank pouch and still be "accepted".

**Steps (5).** `quality_gate.py` → replace the form-only hand-off with a five-axis score →
fix the two transport defects the live run exposed → add requested-copy coverage → surface the
score in the Design Studio panel.

**Axes.**

| Axis | Blocking | How it is decided |
|---|---|---|
| `form` | yes | vision: observed container vs requested |
| `design_alignment` | yes | vision: is this the product the brief described |
| `layout` | yes | vision: balanced, not cut off or crowded |
| `typography` | yes | **OCR first** (is there text; is it the requested copy), then vision (legible) |
| `material` | **no** | recorded only — a finish cannot be proven from a PNG |

**Typography rules, all tested.** Text-free brief with lettering → `typography_unwanted_text`;
text brief with none → `typography_missing`; unreadable → `typography_illegible`; under half the
requested copy → `typography_text_mismatch` (missing terms named); OCR unavailable on a text
brief → `typography_unverified` (fails closed). Coverage is recorded, never guessed.

**Self-review catches (5).** "Some text" ≠ "the requested text" → coverage added; material must
not block because it cannot be verified; an unreachable lane must fail closed or every outage is
a green run; a text-free brief must not block on missing OCR (the suppression lane is the
control there, and the axis records `verified: false`); the empty vision reply was a payload
shape problem, not a model-quality problem.

**Two live defects found while proving it.**
1. `OLLAMA_HOST` is the *server-side* bare `host:port` — here `0.0.0.0:11434` — so every
   `urlopen` raised `unknown url type: 0.0.0.0` while the server was listening. Fixed in
   `local_vision.normalise_host`, including `0.0.0.0 → 127.0.0.1` for clients (6 tests).
2. Without `think: false` the model spent the budget reasoning and returned an empty reply
   (measured: 34.6 s, 0 characters). Payload fixed; documented in the code.

**Live proof.**

| Case | Result |
|---|---|
| text-free brief | **3/3 pass**, typography `n/a`, OCR `rapidocr` confirms no lettering, vision 20.5 s |
| `LION MANE` label brief | **4/4 pass**, OCR read `LION MANE` and `6 oz`, legibility from vision |
| 4-pt pangram brief | **4/4 pass**, OCR read `THE QUICK BROWN FOX` / `JUMPS OVER THE LAZY DOG` / `0123456789` |
| same `LION MANE` brief, later run | **3/4 BLOCKED** — `typography_illegible`, "Body text is garbled/placeholder text; only 'LION MANE' is clear." No folder written (5 → 5) |

That last row is the whole point of the unit: the same brief renders well sometimes and badly
sometimes, and delivery now follows the render, not the request.

**Sample manifest output** (`state/deliverables/821a2623-…/manifest.json`, 16 keys):

```json
{
  "run_id": "821a2623-3b1a-43e8-bc87-00614e63213b",
  "created_at": "2026-11-02T07:16:22",
  "adherence": {"ok": true, "requested": "pouch", "observed": "pouch",
                "model": "qwen3.5:4b", "score": "3/3", "failed_axes": [], "reasons": []},
  "quality": {
    "axes": {
      "form": {"status": "pass", "observed": "pouch"},
      "design_alignment": {"status": "pass",
                           "detail": "Clean studio shot of an empty pouch with no branding."},
      "layout": {"status": "pass", "detail": "Centered composition with ample white space."},
      "typography": {"status": "not_applicable", "reason": "no_text_requested",
                     "verified": true, "engine": "rapidocr",
                     "detail": "OCR confirms no lettering", "vision_text_visible": false},
      "material": {"status": "recorded", "finish": "kraft",
                   "detail": "Brown kraft paper texture visible.",
                   "detail_note": "descriptive only; finish is not verifiable from a PNG"}
    },
    "verdict": {"ok": true, "passed": ["form", "design_alignment", "layout"],
                "failed": [], "not_applicable": ["typography"], "score": "3/3", "reasons": []},
    "model": "qwen3.5:4b", "available": true, "seconds": 20.5,
    "ocr": {"engine": "rapidocr", "status": "ok", "contains_text": false, "boxes": 0}
  },
  "dieline": {"built": false, "reason": "mockup render; no print dieline was generated"},
  "color_profile": {"working": "RGB", "target": "CMYK", "converted": false},
  "files": ["adherence.json", "brief.txt", "citations.json", "final.png", "manifest.json"],
  "image_size": [1024, 1024], "bytes": 1220364
}
```

`dieline.built: false` is deliberate. The run carries no dimensions, so a "dieline spec" here
would be invented. The field states the fact instead of faking a spec.

**Commits.** `86e59278` (geometry), `d746667b` (quality gate), report commit (evidence,
trajectories, UI score line).

---

## REGRESSION SUITE

**Full backend suite** (`python -m pytest -q` from `Northstar_backend`, 635.18 s):

```
30 failed, 5689 passed, 117 skipped, 2 xfailed, 88 subtests passed
```

Before this campaign the same suite was `34 failed, 5639 passed`. **+50 passing, −4 failing, and
the 4 that stopped failing are the studio auth tests fixed earlier today** (`7ee328fc`,
`670792fb`, `199293d0`). **No new failures: the 30 are the same 30, by name, classified into
four root causes:**

| Root cause | Count | Where |
|---|---|---|
| `autothink/backend/server.py` imports `build_system_prompt_with_context`, absent from its `llm_adapter` | 11 | `test_autothink_routes` (8), `test_autothink_auth_boundary` (2), `test_ui_route_contract` live probe (1) |
| `agent_kernel/local_model.py:89` — `NameError: num_ctx is not defined` | 5 | `test_local_model` |
| Dev-shim tests build a Starlette `Request` without `app` → `KeyError: 'app'` | 5 | `test_session_cookie_contract::DevShimSessionTests` |
| Stale fixtures/invariants (route count 53 vs 57, HITL totals, shell-mode plan gates, two guard-prompt strings, a sample URL in `HitlQueue.jsx`) | 8 | `test_frontend_gate`, `test_autonomy_hitl_pathlike`, `test_hitl_counts`, `test_shell_modes`, `test_coding_guardrails`, `test_generation_guards`, `test_ui_route_contract` |
| Order-dependent (passes alone: 24 passed) | 1 | `test_provider_suite` |

**Touched-area suites:** 127 passed, 0 failed
(`test_quality_gate` 22 · `test_dieline_geometry` 18 · `test_deliverables` 10 ·
`test_local_vision` 20 · `test_design_studio_print` + `test_dieline_art` + `test_print_prep`
27 · `test_text_fidelity` + `test_mockup_compositor` + `test_design_studio_lanes` +
`test_generate_form` 30).

**UI:** `npm run build` → 0 errors; the bundle carries the panel and the new quality line (no
browser was run — static check only).

---

## SPEND & RESIDUE

- **Cloud / Go spend this campaign: $0.00.** No `opencode run` invocation was made; the author
  lane was this operator session. Ledger unchanged: **11 entries, $0.005656 cumulative**
  (0.08 % of the $7.20 / 5 h halt share, ≈ **$7.1943** remaining; weekly and monthly shares
  untouched).
- **Renders:** 4, all local on the operator GPU at **$0** (3 accepted, 1 blocked). One vision
  call per render at 0 cost.
- **Downloads:** none. No model pull, no package install.
- **State residue: zero.** No daemons started or left; the backend on 8000 is the operator's
  launcher (restarted for module reloads, still `armed: true`); Ollama is the process recovered
  earlier and is running. `state/deliverables/` holds 5 packages — user output, gitignored.
  Scratch files removed; rollback tag `rollback/pre-packify-20261102-070637` points at the
  pre-campaign commit.

---

## DECISIONS & ANCHORS

**Decision anchors.**

1. **Refuse, never clamp.** An impossible number is a spec error the user can fix; a clamped
   number is a production defect nobody sees. `dieline_geometry` is the one gate both builders
   and the endpoint answer to.
2. **The gate blocks on what it can prove, and records what it cannot.** Typography is decided
   by OCR presence and requested-copy coverage before the vision model opines on legibility;
   material finish is recorded because no PNG proves matte vs gloss. A "verified" claim the
   pipeline cannot support is the failure mode this campaign removed.
3. **A blocked run leaves the filesystem untouched.** Proven live: 3/4 verdict, no folder,
   render kept as an asset with the reason attached.
4. **The audit is also a detector.** Running the new invariants against the shipping templates
   was not a formality — it found a real 6 mm pouch overflow on the first pass. Validation that
   never runs on the product is decoration.

**NEXT DECISION — one operator choice.**

| Option | What it buys |
|---|---|
| **A. Material & lighting workflows** (recommended) | The one campaign objective not attempted: matte laminate, foil, UV spot, kraft and soft-touch presets in ComfyUI, each verified by a finished render and a gate run — and each declared in the manifest as *simulated*, not claimed. |
| B. Dieline spec in the manifest | Add a dimensions step (fill weight → published pouch ladder) so a delivered run can carry a real dieline spec instead of `built: false`. |
| C. Suite green | Fix the autothink import (11) and `local_model` `num_ctx` (5) to take the 30 failures to 14. |

Option A is recommended because it is the only stated campaign objective still open, and the
gate is now strict enough that a bad material preset cannot ship silently.
