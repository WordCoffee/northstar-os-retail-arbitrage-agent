# Northstar OS — V3 Master Plan (engineering reconciliation)

**Owner plan accepted as the V3 direction.** This document is the engineering reconciliation: what
V2 actually delivered, what the V3 pivots require, and the gates that must be met before a module is
called customer-ready. It supersedes no safety rule; where the owner plan and the standing capsule
disagree, the disagreement is named and the safe path is stated.

---

## 1. V2 closure — what is true on disk

| Owner claim | Reality | Evidence |
|---|---|---|
| Tys Assistant Vision established | **Not present.** No vision module existed; `agent_kernel/vision_verify.py` is the first implementation. The local `qwen2.5vl:7b` runner returns degenerate text/no parseable JSON on real product images, so Stage 2 is **blocked**, not passed. | `reports/v3_graduation_memory_20261104.json` |
| Architecture stabilized, fragmented toolsets reduced | Partly. One kernel, one loop, one image gate, one memory API. Chrome Connect, the kernel and the studio still have separate tool surfaces by design. | `AGENTS.md`, `Northstar_backend/agent_kernel/` |
| Chrome Connect to be retired | **Not executed.** Chrome Connect is still the browser controller and the policy/lease/Amazon enforcement point. | `lib/chromecontrol/`, `config/chromecontrol*.json` |
| Wan 2.2 standard | **True.** `shorts.py` + `video_formats.py` use Wan 2.2; A14B Q4 experts are on disk. | `Northstar_backend/shorts.py`, `video_formats.py` |
| Product-grade packaging | **True for the reference lane.** Reference-conditioned FLUX 3 + vector panel; front and back passed the OCR gate. Remaining: DRAFT nutrition/UPC data. | `renders/mogra_lions_mane/reference_pair/` |

**V2 verdict:** agentic foundation and packaging are real; "Tys Vision" is a V3 deliverable, not a
V2 achievement; Chrome Connect was not retired.

## 2. Deprecations and pivots

### 2.1 Chrome Connect → Ty's Assistant Vision (V3.1)

Accepted as the **target architecture**, not as a switch that can be flipped today. Removing the
controller before its replacement enforces the same rules would bypass the standing browser gates.
The migration is gated on parity:

1. host policy + hardcoded Amazon blocklist evaluated first;
2. Profile 6 lease and profile-identity refusal;
3. stop on credential entry, CAPTCHA, login, purchase/checkout, external state change;
4. per-action URL re-check after redirects;
5. audit journal + lessons store;
6. a measured browser-task benchmark showing equal or better completion.

Until all six pass, Chrome Connect stays the controller and the vision layer is an **observer**
(screenshot + DOM summary + verification), not a second driver.

### 2.2 Video standardisation — Wan 2.2

Wan 2.2 is the only video engine. The human-feature guardrail is now implemented:

* `video_guard.check_prompt` detects faces/hands/bodies/people;
* `/api/design-studio/shorts` and `/generate` (kind=video) return **422 `human_features_warning`**
  with the owner's text before any GPU work;
* `human_features_ack: true` is the only override;
* product-only prompts pass untouched.

### 2.3 Stabilisation rubric

`tools/v3_graduation.py` implements the three stages, fail-closed:

| Stage | Gate | Current status |
|---|---|---|
| 1 | AST symbol audit (no duplicate top-level symbols, no TODO/TBD/FIXME/XXX) + 100% passing test command | Implemented; memory module passes |
| 2 | Ty's Vision verdict on a screenshot against a design constraint | **Blocked**: the local vision model is not reliable; gate fails closed |
| 3 | End-to-end benchmark command exit 0 | Implemented (wired to the chosen benchmark) |

A report is written per run (`reports/v3_graduation_<module>_<ts>.json`); no stage may be skipped.

## 3. V3 roadmap and acceptance

| Version | Focus | Deliverables | Acceptance |
|---|---|---|---|
| **V3.1** | Ty's Assistant Vision | Vision model bake-off (moondream2 / llava / qwen2.5vl) on 20 reference images; `vision_verify` reliability; DOM+screenshot observation inside the controller; Chrome parity checklist | ≥18/20 correct verdicts, 0 policy bypasses, browser benchmark ≥ current |
| **V3.2** | Wan 2.2 video | Guardrail (done), Wan A14B chained shots, SeedVR2 upscale, captions/audio; 15 s and 30 s product masters | ffprobe contract, OCR captions, −16 LUFS, human guardrail 100% interception |
| **V3.3** | Packaging | Reference front/back pair, vector typography, per-face refs, print dieline, real nutrition/UPC | `product_front/back` pass identity+legibility; 300 DPI; no placeholder data |
| **V3.4** | Stabilisation & onboarding | Full-suite green, graduation reports for every customer module, first-run flow, support docs | Stage 1 100%, Stage 2 pass for every shipped asset, Stage 3 E2E pass |

## 4. Hard-freeze rules (effective now)

1. **No new feature lane** until Stage 1 is 100% on the full backend suite; existing failures are
   fixed or explicitly quarantined with a written reason.
2. Every change ships with a graduation report; a red stage blocks the merge.
3. No module is "customer-ready" on unit tests alone; Stage 2 and Stage 3 are mandatory.
4. Chrome Connect is not deleted, disabled or bypassed during the V3.1 migration.
5. Amazon remains behind the standing gate; no A+ or ad-spec claim is verified without the owner's
   document.

## 5. Immediate blockers

| Blocker | Impact | Next action |
|---|---|---|
| Local vision model returns degenerate output (`qwen2.5vl:7b`) | Stage 2 cannot pass; "Tys Vision" not credible | Model bake-off on 20 fixed images; pick the smallest model that scores ≥90% and fits 16 GB |
| Full-suite pass rate below 100% | Hard-freeze rule 1 blocks new lanes | Fix or quarantine the failures listed in `reports/v3_readiness_20261104.md` |
| Chrome parity not proven | V3.1 migration cannot remove the controller | Build the parity harness; run the browser benchmark |
| DRAFT nutrition/UPC | V3.3 print readiness | Owner supplies final values; replace the DRAFT watermark |

## 6. Decisions

1. Accept the V3 direction; **do not** retire Chrome Connect until the six-point parity gate passes.
2. Treat "Tys Vision" as V3.1 work, not a V2 achievement; the verifier is scaffolded and fails closed.
3. Keep the Wan 2.2 + human guardrail; the override is explicit and logged.
4. Adopt the three-stage graduation rubric as a merge gate, with the report as evidence.
5. Hard freeze: no new feature lanes while Stage 1 is red.
