# Blueprint v2 — what changed and what was built

**Date:** 2026-10-23 · **Plan:** `docs/BLUEPRINT_V2.md` (supersedes §12 + adds §11A/11B/11C)

---

## Plan changes applied

| Change | Where | State |
|---|---|---|
| **§11A Cloud readiness** — model gateway, usage ledger, price table, margin rule, caps, retries/fallback, idempotency, tenant isolation, acceptance criteria | `docs/BLUEPRINT_V2.md` | **added** |
| **§11B Bojo scope** — broad seller assistant, Autothink handoff with a brief, two routing tests | `docs/BLUEPRINT_V2.md` | **added** |
| **§11B Celestial theme** — layered background spec, palette, motion, acceptance | `docs/BLUEPRINT_V2.md` + `briefs/theme.md` | **added** — theme still **unmet**, gated on brief approval |
| **§11C Vision fidelity** — brief before building, reference board, Chrome Connect desktop+mobile screenshots, PASS/FAIL per check, no silent substitutions | `docs/BLUEPRINT_V2.md` + 3 briefs | **added** |
| **Phase 1B** inserted before agent builds | §12 table | **started** |
| **Phase 6** gains the Bojo/Autothink boundary | §12 table | **done** |
| **Phase 7** becomes cloud cutover rehearsal + hardening | §12 table | pending |
| **Definition of done** now requires the gateway check, cloud readiness test, per-call cost/margin, and match to approved briefs | §15 | **updated** |
| No-egress test **replaced** by `test_gateway.py` | `Northstar_backend/` | **done** (old file removed) |

## Built in Phase 1B (this pass)

### Model gateway — `Northstar_backend/gateway/`

| File | What it does |
|---|---|
| `roles.py` | role → provider chain from `shared/model-roles.json`; env override per role or global; unknown role refused |
| `adapters.py` | `local_ollama`, `comfyui`, `local_voice`, `stub_cloud` — one interface, no branching in the gateway |
| `ledger.py` | price table, margin rule, charge, per-user daily/monthly caps, monthly report, JSONL rows |
| `service.py` | retries with backoff, **fallback down the chain**, idempotency (a retry never double-charges), the single entry point |

Config files: `shared/model-roles.json`, `shared/provider-prices.json`, `shared/margin-rules.json`.

### Acceptance evidence (§11A.5)

| Criterion | Result |
|---|---|
| Every role swaps to `stub_cloud` by config only | **PASS** — `NORTHSTAR_FORCE_PROVIDER`, all 6 roles |
| All agent tests pass unchanged under the swap | **PASS** — 8 specialists produce identical output; ledger stays empty, proving no agent calls a provider directly |
| Ledger records correct cost **and** charge | **PASS** — recomputed from the price table and margin rule, asserted to 1e-9 |
| Forced provider failure → fallback, no user-visible error | **PASS** — `stub_cloud` fails, `local_voice` answers, caller sees success |
| Every-provider-fails path | **PASS** — honest `all_providers_failed`, `user_visible: true` |
| No call bypasses the gateway | **PASS** — only `adapters.py` may import a network client; URL allowlist enforced |

### Bojo / Autothink boundary (§11B.1)

`specialists/router.scope()` classifies deterministically and produces a **handoff brief** for
Autothink (request in the operator's words, why, acceptance criteria).

| Suite task | Expected | Result |
|---|---|---|
| `BOJO-UTIL` — "make me a quick tip calculator" | Bojo builds it | **PASS** |
| `BOJO-CODE` — "refactor the listings service to async and add unit tests" | Autothink handoff + brief | **PASS** |

### Package Designer — lesson L4/L5 closed

The gussets now carry the **side panel** (brand, subtitle, claims, cert marks, net weight), and the
guard `MIN_LEGIBLE_GUSSET_PX = 220` means a strip too narrow for legible copy falls back to shaded
field instead of slicing words.

Artifact: `reports/northstar_acceptance_20261023/screenshots/build-mogra-side-panels.png`

Lessons store now holds 6 entries (L1–L6), 5 APPLIED, 1 PROPOSED (drop the side keyline so the wrap
reads continuous).

## Numbers

| Check | Result |
|---|---|
| `pytest` (13 modules incl. gateway, scope, lessons) | **172 passed**, exit 0 |
| Acceptance suite | **150/150**, **24/24 tasks**, 0 not built |
| Controller | 1 commit (`475e09a`, packify policy) |

## Not done, and why

1. **Celestial theme — not built.** §11C requires brief approval *before* building, and
   `briefs/theme.md` has not been approved. It is the largest unmet item and it is first in the queue.
2. **Simple Mode brief** (`briefs/simple_mode.md`) — same gate; S1–S7 need desktop+mobile screenshots.
3. **Package Designer brief** — P1–P7 partly evidenced (P1, P2, P3, P5, P6, P7) but **P4** (back panel
   barcode zone) needs a fresh screenshot for sign-off.
4. **Cloud cutover rehearsal** (Phase 7) — the gateway can swap to `stub_cloud`, but no real cloud
   adapter exists yet; that needs provider choice and keys.
5. **Tenant isolation** is designed in the ledger (user/tenant on every row) but the *data* isolation
   of reports/brand kit/assets is unchanged this pass.

## Next

Approve `briefs/theme.md` (or amend it), then I build the layered background against T1–T6 and return
desktop + mobile screenshots with a PASS/FAIL per check and a contrast number. That is the only thing
standing between the current build and the definition of done for §11B.
