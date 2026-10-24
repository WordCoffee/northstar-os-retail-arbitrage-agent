# Blueprint build — phase report

**Date:** 2026-10-23 · **Repo:** `feature/v4.1-mesh` @ `10a1062c` (uncommitted work preserved)
**Blueprint:** Northstar OS Agent and Creative Build Blueprint (§12 phases)

---

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 — Audit (read-only) | **DONE** | `docs/audit.md` — real inventory + the three code-level causes of both reported failures |
| 1 — Study (Tier A + B) | **NOT DONE** — no repo cloned, no product observed | `specs/*.md` mark every competitor claim **UNVERIFIED**; `provenance.csv` carries explicit `NOT ADOPTED / NOT REVIEWED` rows |
| 2 — Test harness + baseline | **DONE** | `tests/agents/tasks.json` (22 tasks), `tests/agents/run_suite.py`, `test_no_egress.py` |
| 3 — Package Designer | **DONE + ACCEPTED** | real Mogra brief → front + back + side + sheet + dieline SVG/PDF + mockup |
| 4 — Listing Optimizer + PPC | **DONE + ACCEPTED** | 5/5 and 4/4 suite tasks at full marks |
| 5 — Image/A+, Social, Video, Content | **SPEC ONLY** | `agents/<name>/` folders exist; suite reports them `not_built`, never as passes |
| 6 — Router + model selection | **ROUTER DONE**, model comparison **NOT RUN** | router wired into every turn; no candidate model benchmark was performed |
| 7 — Hardening | **PARTIAL** | no-egress gate done; GPU queue, observability, cost tracking, rollback not built |

---

## What was built

### Specialist layer — `Northstar_backend/specialists/`

| File | What it does |
|---|---|
| `registry.py` | the roster: 8 agents, each with required/optional inputs, outputs, validators, routing keywords |
| `router.py` | deterministic classifier + required-input gate; strips quoted spans and negated clauses |
| `package_designer.py` | inputs → gaps → three panels → dieline → mockup → validation |
| `panels.py` | front/back/side renderers, panel sheet, `validate_panels()` |
| `listing_optimizer.py` | 100-point rubric, keyword coverage, rewrite, 250-byte backend builder, change log |
| `ppc_agent.py` | report validation, harvest/negatives, change-row validation against the source |

### Chat wiring

Three new tools — `build_package`, `optimize_listing`, `ppc_plan` — plus the router line injected
into every turn:

```
[router] package_designer — ask for: dims, company, address, country_of_origin
```

Only injected when the router is confident; a greeting or a question is left alone.

### Deliverables per §13

```
docs/audit.md              docs/decisions.md          provenance.csv
specs/package_designer.md  specs/listing_optimizer.md specs/ppc_agent.md
agents/<8 folders>/        prompt.md inputs.json tools.json schema.json README.md
tests/agents/tasks.json    tests/agents/run_suite.py
```

---

## Test evidence

| Command | Result | Exit |
|---|---|---|
| `python tests/agents/run_suite.py` | **114/114 deterministic (100 %)** — 18 of 22 tasks runnable, 4 correctly `not_built` | 0 |
| `pytest test_specialists.py` | 20 passed | 0 |
| `pytest test_no_egress.py` | 3 passed | 0 |
| `pytest test_specialists test_no_egress test_chat_tools test_shell_modes test_pouch_label test_creative_execute_artifact test_voice_speak` | **106 passed** | 0 |

Suite by group: package 36/36 · listing 32/32 · ppc 18/18 · routing 28/28 · creative 0 runnable.

Bugs the suite caught and that are now fixed:

1. **Apostrophe ate the brief.** `Lion's Mane` was parsed as a quoted span, deleting the weight and
   dimensions from a complete request. Quote handling now requires the apostrophe not to be glued
   to a word.
2. **Negation was too blunt.** "I don't need a video, just the A+ modules" dropped the clause the
   operator *did* want. Negation now blanks only the span after the negator.
3. **Flat sheet mistaken for the pouch.** `build_from_template("doypack")` returns the flat sheet
   (113 mm) at top level while the pouch is 95 mm. Both numbers are now named and tested.
4. **Vague request returned a schema rejection, not a checklist.** The tool no longer requires
   `title` at the schema layer, so the operator gets the seven real questions.
5. **Side panel collision.** The net weight overlapped the third certification mark; the icon
   column is now centred in the space left above the weight band.

---

## Real artifact (Phase 3 acceptance)

`reports/northstar_acceptance_20261023/screenshots/phase3-sheet.png`

Front: product name, subtitle, two claims, three drawn certification marks, `NET WT 6 OZ (170 g)`.
Back: ingredients, suggested use, warnings, company, address, country of origin, **reserved barcode
zone** and lot-code area. Side: brand, name, claims, marks, weight.

Validation returned honestly:

```
ready_for_print: true
warnings: ["height/width ratio 2.11 is outside the usual 1.2-1.9 stand-up-pouch band",
           "claims are rendered as supplied — screen each one for disease/treatment language"]
```

Vague request ("Create a product image for my pouch") returns **7 questions** and builds nothing.

---

## What is deliberately NOT claimed

- **No Tier A repository was cloned or adapted.** Writing a capability map for code nobody read
  would be fabrication. Every competitor claim in `specs/` is marked `UNVERIFIED`.
- **No hosted product was observed.** Nothing was extracted from Packify/Pacdora/etc.; no
  proprietary asset, template, prompt or code was copied.
- **Four creative agents are spec-only.** The suite reports them `not_built` rather than counting
  them as green.
- **No manager-model comparison** (blueprint §9/Phase 6) was run. The router is deterministic, so
  routing quality does not depend on the model — but "is the 27B good enough as a manager" remains
  unanswered.
- **No bulk-file writer.** The PPC agent returns validated change rows and a change log, not an
  upload-ready `.xlsx`.

---

## Next increments, in order

1. **Phase 1 properly** — clone the Tier A repos, read them, produce real capability maps, and
   replace the UNVERIFIED rows with cited evidence.
2. **Phase 5** — image/A+, social, video, content agents, one at a time, each with its acceptance
   task in `tasks.json`.
3. **Phase 6** — run the suite on the current model and on gpt-oss-20B / Gemma 4 26B-A4B, record
   latency and cost, choose on score.
4. **PPC bulk writer** — validated against a current Amazon bulk template.
5. **Phase 7** — GPU queue with priority, run observability, cost tracking, per-agent READMEs
   (folders exist; content is generated from the registry).
