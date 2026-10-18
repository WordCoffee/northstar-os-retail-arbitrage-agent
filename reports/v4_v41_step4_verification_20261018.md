# V4.1 Step 4 — Verification & Regression Guardrails

**Date:** 2026-10-18
**Branch:** `feature/v4.1-mesh` (V3 baseline tagged `v3-final-stable` @ `5c3022f`)
**Scope:** Step 4 of the V4.1 plan — verify the drift/vector/telemetry suites, the UI
build, and the V3 shell harness; confirm zero regressions.

All local-only. Nothing pushed. No credential read, printed or committed.

---

## 1. Gate results (all green)

| Gate | Command | Result |
|---|---|---|
| Embeddings drift suite | `pytest test_corpus_drift.py` | **35 passed, 0 failed** |
| REA capture harness suite | `pytest test_operator_rea_capture.py` | **21 passed, 0 failed** |
| V3 shell/chat/seo/corpus + both V4.1 suites | `pytest` (14 files) | **243 passed, 0 failed** |
| UI production build | `npm run build` | **✓ built, 0 errors** (warnings only) |
| V3 shell contract harness | `node verify-shell-v3.cjs` | **28 passed, 0 failed** |

### UI build
`npm run build` → `✓ built in 1.88s`. Only Vite chunk-size / dynamic-vs-static import
warnings (pre-existing); **zero errors**.

### Shell harness (scenarios A–F)
`28 passed, 0 failed` — Simple-first shell, focus chips, Advanced gating,
AG-UI cards + human handover, fork/rewind, workbench + immersive plan graph.
No UI file was changed by V4.1, so this is a pure regression confirmation.

## 2. Regression honesty (full backend)

Full `Northstar_backend` suite, excluding the pre-broken `costco_non_kirkland/`
collection errors:

```
3668 passed, 11 failed, 65 skipped, 89 subtests passed
```

All 11 failures are **pre-existing and unrelated**. Nine were proven identical with
and without the V4.1 changes staged (`git stash` → same failing set); the remaining
two are UI/static-file assertions (`App.jsx` route count; frozen-file boundary) that
V4.1 does not touch. `test_ui_route_contract.py` fails only on *missing* API paths —
V4.1 only **adds** routes. The `costco_non_kirkland/` errors are a pre-existing
import break in an unrelated module (commit `a2238ec`).

## 3. Real (non-mocked) evidence carried from earlier steps

- **Embeddings lane is real.** `qwen3-embedding:0.6b` (1024-d) live via local Ollama;
  a real end-to-end run embedded 3 corpus + 3 SQP records and returned a sensible
  ranking (query *"mushroom supplement sourcing"* → *"mushroom supplement"* @ 0.082,
  then the Lion's Mane doc @ 0.206) and a measured drift of `0.2012`.
- **REA harness is honest.** With no operator policy file, every Packify target is
  `BLOCKED host_not_allowlisted` — it never assumes a host is permitted.

## 4. V4.1 status

| Step | State |
|---|---|
| 1 — branch + V3 baseline tag | ✅ `feature/v4.1-mesh`, tag `v3-final-stable` @ `5c3022f` |
| 2 — embeddings drift engine (§5.4) | ✅ committed `4d02d7d`; 35/0 + real e2e |
| 3 — operator REA capture harness (Packify) | ✅ committed `575e0c3`; 21/0; live capture gated |
| 4 — verification & guardrails | ✅ this report; 243/0, build 0 errors, harness 28/0 |

**Open operator decisions (surfaced once):**
1. Add `www.packify.ai` to the operator-owned allowlist
   (`config/chromecontrol_policy_owner.json`) to enable live Packify captures.
2. Provide an operator window with Chrome Connect live for the actual captures.

Both are operator-owned by design; no code blocker remains.
