# AUTOTHINK_AUDIT — deep audit of NorthstarOS AutothinK

**Audit date:** 2026-10-08 · **Baseline:** `2482048`

### Scope discovery first (per audit brief §7)
AutothinK's documented scope was established **before** assessment, from three sources rather than assumed:
- `master-brain/northstar-os-master-plan.md` (platform brain: services + AutothinK)
- `docs/northstar-phase1/18-autothink-spec.md` (Phase-1 spec)
- `docs/HOSTED_REASONING.md` + `adapters/reasoning_provider.py` (the hosted non-creative reasoning policy)
- Implementation: `autothink/` (backend, orchestration, memory, tests, ui) and `Northstar_backend/{main.py,reasoning_tasks.py,model_router.py}` and `northstar-os-ui/src/pages/internal/AutothinK.jsx`.

AutothinK is therefore **not** assumed to be a generic AI-agent checklist. It is scoped as: a **research-run workspace** with three execution lanes (local Ollama, cloud OpenRouter, hosted OpenCode Go), deterministic task routing, a persisted local session history, and structured proposal workflows shared with ListingForge / AdPilot / Spreadsheet Lab.

---

## 1. What actually exists

| Component | Path | Status |
|---|---|---|
| SPA room | `northstar-os-ui/src/pages/internal/AutothinK.jsx` (263 lines) | IMPLEMENTED (Engine status / Session history / Composer / Output tabs) |
| Standalone UI | `autothink/ui/index.html` + `test_ui_autothink.cjs` | IMPLEMENTED, served at `/autothink` via StaticFiles (`main.py:155-157`) |
| API (proxied to the standalone server) | `main.py:1035-1063` → `/api/autothink/{models,run,history}` | IMPLEMENTED but **unauthenticated** |
| FastAPI server | `autothink/backend/server.py` (179 lines) | IMPLEMENTED |
| LLM adapter | `autothink/backend/llm_adapter.py` (298 lines) | IMPLEMENTED; local + cloud lanes |
| Hosted adapter | `Northstar_backend/adapters/reasoning_provider.py` (889 lines) | IMPLEMENTED, **excellent fail-closed design** |
| Task workflows | `Northstar_backend/reasoning_tasks.py` (441 lines) | IMPLEMENTED (listing / ad-copy / spreadsheet / generic) with deterministic post-validation |
| Task router | `autothink/orchestration/router.py` (105 lines) | IMPLEMENTED, deterministic, reuses `master_brain_gateway.classify_task` |
| Model router | `Northstar_backend/model_router.py` | IMPLEMENTED (tier → model + credit weight, consent prompts) |
| Session store | `autothink/memory/session_store.py` (56 lines) | IMPLEMENTED, single JSON file, 50-entry cap |
| Tests | `autothink/tests/{test_llm_adapter,test_router,test_server}.py` (25 tests) | **25 passed, 0 failed** |
| UI harness | `autothink/ui/test_ui_autothink.cjs` | present; not in the audited Node run set |
| Route-level integration tests | `Northstar_backend/tests/test_reasoning_routes.py` | 5 pass / **2 fail** (env pollution, not product logic) |

---

## 2. Capability-by-capability trace: input → orchestration → permissions → data/tools → result → persistence → status

| Capability | Traced path | Verdict |
|---|---|---|
| **User input** | Composer textarea + provider select + tier/model select (`AutothinK.jsx:162-190`) | VERIFIED |
| **Orchestration** | `route_task(query)` → `master_brain_gateway.classify_task` → plan templates (`orchestration/router.py:68-77`) | VERIFIED (deterministic, zero network) |
| **Permissions** | **NONE** on `/api/autothink/*` | **BROKEN — P0-04** |
| **Data / tools** | `build_context()` returns `data_sources` (`server.py:47-56, 107`) — **the bundle is never passed to the adapter** | **NOT IMPLEMENTED** |
| **Result** | `adapter.generate(query, provider, model)` → content/reason/tokens | VERIFIED |
| **Persistence** | `store.add(...)` → `autothink/memory/session-history.json`; `audit(...)` → `autothink/audit/autothink-runs.jsonl` (append-only) | VERIFIED |
| **User-visible status** | Engine-status pills, history table, per-run ok/failed pill | VERIFIED |

---

## 3. Lane-by-lane verification

### 3.1 Local lane (Ollama) — **VERIFIED WORKING**
Probe (`evidence/autothink-local-probe.txt`):
```
local_available: True
installed models: ['qwen3:4b', 'northstar-qwen3:rev1', 'qwen3:14b', 'qwen2.5vl:7b']
ok: True | model: northstar-qwen3:rev1 | content: READY | elapsed_ms: 14238.0
```
- Real completion from the pinned default model (`DEFAULT_LOCAL_MODEL = "northstar-qwen3:rev1"`, `llm_adapter.py:26`), streamed with `num_predict=8192`, `num_ctx=32768`.
- Free, private, zero credential. This is genuinely the "first-class citizen" the docstring claims.

### 3.2 Hosted lane (OpenCode Go) — **BROKEN (P0-02)**
- Backend design is the strongest part of the whole system: `resolve_model()` fails closed on unknown (`ValueError`), on unverified (`ModelNotUsableError`), and on no-verified-model (`NoVerifiedModelError`); **nothing is auto-substituted**. `models_status()` exposes provider/base/endpoint/configured/enabled/verified/intended-role. Creative separation is enforced (`allowed_for_creative: False`, `HOSTED_REASONING_IS_CREATIVE_RENDERER = False`).
- **But the UI cannot reach it.** `foundation/api.js:175-179` calls `/api/v1/foundation/reasoning/*`; those routes do not exist. Live-proven:
  ```
  GET /api/v1/foundation/reasoning/models -> 404
  GET /api/v1/reasoning/models           -> 200
  ```
- Consequence: `AutothinK.jsx` `form.provider === 'hosted'` → `providerOk = hostedArmed` (from a null catalog) → `canRun` is false, and any attempt yields a settled error. The model selector shows "No models" everywhere in the suite.
- **Second defect:** root `.env` has `OPENCODE_GO_ENABLED=1` and a key, but `main.py` never loads root `.env`, so the running API reports `configured:false / enabled:false / armed:false` while the operator's file says armed. Probed directly: loading the file yields `armed: true, runtime_default_model: step-5-preview-free`.
- **Live hosted call: NOT TESTED.** No live OpenCode Go completion was performed by this audit. The repo's own records claim a verified HTTP 200 for `step-5-preview-free` (`reasoning_provider.py:104-106, 252-257`) — that is **REPORTED, not independently re-verified here**.

### 3.3 Cloud lane (OpenRouter) — **GATED BY DESIGN**
- `CLOUD_MODEL_LIVE` is absent from both `.env` files → `cloud_live_armed()` is false → the path returns a `[CLOUD FALLBACK]` with `reason: not_approved`. Correct per the §3 rule.
- **Gap:** the armed path has **no cost cap and no `max_price`** (`llm_adapter.py:245`: `"provider": {"sort":"price","allow_fallbacks": True}` with a comment "no hard max_price ceiling yet"). An armed cloud call is unbounded spend with no ledger write.

---

## 4. Capability checklist against the audit brief §7

| Capability | Status | Evidence |
|---|---|---|
| Conversation and task interfaces | IMPLEMENTED | Composer + history + output tabs |
| Service/workspace context | NOT IMPLEMENTED | no org/session/room context reaches `build_context` |
| Retrieval and grounding | **NOT IMPLEMENTED** | `server.py` calls `build_context(...)` at `:107` and never uses the result; `build_system_prompt_with_context` has **0 references** in `server.py` |
| Reasoning / task orchestration | IMPLEMENTED | deterministic router + plan templates |
| Tool selection and execution | NOT IMPLEMENTED | no tool registry; "plan" steps are display strings only |
| Structured outputs & downstream compatibility | IMPLEMENTED for the 3 hosted task workflows | `reasoning_tasks.py` `_safe_json_parse` + deterministic validation |
| Task history, saved results, continuation | PARTIAL | history persists; **no continuation** — each run is independent |
| Long-running task state / queues / workers | NOT IMPLEMENTED for AutothinK | generic `jobs-durable` exists and is real, but no AutothinK job type is registered |
| Cancellation / retry / timeout / recovery | NOT IMPLEMENTED in the product path | blocking POST; timeouts only (local 600 s, hosted 120 s); no cancel |
| Approval checkpoints for consequential actions | NOT APPLICABLE for reasoning — **but no approval gate exists for paid cloud runs either** |
| Model configuration & routing | IMPLEMENTED (hosted) / PARTIAL (local, cloud) | `model_router.resolve(provider, tier, model)` + `consent_prompt(prev_tier, tier)` |
| Usage / cost accounting & caps | MISSING | `/api/autothink/run` writes no usage event, no credit debit, no cap |
| Memory scope, retention, workspace isolation | MISSING | single global JSON file; no org key; capped at 50 entries with silent overwrite of the tail |
| Citations, evidence links, data freshness | MISSING | no citations emitted; the UI *claims* "every output cites its source" (`AutothinK.jsx:207`) |
| User-facing explanations & limitations | STRONG | honest fallback markers, provider-not-ready reasons, "unverified model" warnings (`:191-195`), presence-only engine status |

---

## 5. Failure and abuse cases (tested / reasoned)

| Case | Observed behaviour | Verdict |
|---|---|---|
| Missing credentials / unavailable model | Cloud: `not_approved`. Hosted: `not configured` / `not armed` / `ModelNotUsableError` — all typed, no substitution | PASS |
| Local engine down | `[LOCAL FALLBACK] Ollama is unavailable (…)` + `reason`; UI shows "local not reachable" | PASS |
| Invalid or ambiguous input | `query` min_length=1 / max_length=4000, provider pattern `^(local\|cloud)$`, tier pattern `^(T1..V3)$`; empty → 422 | PASS |
| Malformed model output | `_safe_json_parse` returns None → `ok:false, error:"Model did not return valid JSON."` + warning | PASS |
| Partial tool failure | no tools exist → N/A; partial streaming handled in `complete_stream` | N/A |
| Repeated execution / duplicate effects | **no idempotency key** on `/api/autothink/run` → duplicate runs are possible; the UI disables the button while submitting | **GAP** |
| Stale or contradictory evidence | no evidence layer at all → nothing to contradict; the risk is **unsupported confidence**, not contradiction | GAP |
| Prompt injection in retrieved content | spreadsheet promise says "treat as untrusted data" (`reasoning_tasks.py:302`); the local lane has no such rule and no retrieval | PARTIAL |
| Unauthorized tool/action requests | **no auth at all** (P0-04) | **FAIL** |
| Cross-workspace context leakage | single global history file; any caller who can reach the API reads every past query | **FAIL** |
| Fabricated evidence / false claims of completed actions | `live_action_requested` is hardcoded `false` and `approval_status` `"not_requested"` in the run entry (`server.py:134-135`) — honest, and no action is ever claimed | PASS |
| Lost connection / app restart during a task | in-memory only; streaming loop aborts → `[LOCAL FALLBACK]`; nothing resumable | GAP |

---

## 6. AutothinK gaps (consolidated)

| ID | Gap | Severity |
|---|---|---|
| AT-01 | Hosted lane unreachable from the UI (404 route) | **P0** |
| AT-02 | `/api/autothink/*` unauthenticated; global history readable by anyone | **P0** |
| AT-03 | `OPENCODE_GO_ENABLED=1` in root `.env` but `main.py` never loads it → runtime says disarmed while config says armed | **P0** |
| AT-04 | Retrieval/grounding not wired (`build_context` unused) | P1 |
| AT-05 | No usage/credit ledger, no cost cap on any lane | P1 |
| AT-06 | No tenant/workspace scoping or retention policy for session history | P1 |
| AT-07 | No cancellation / resumable long-running state; no durable job integration | P1 |
| AT-08 | No idempotency on run | P1 |
| AT-09 | UI copy claims citations that do not exist | P1 |
| AT-10 | Local lane has no deterministic output validation (unlike the hosted task workflows) | P2 |
| AT-11 | No OpenRouter `max_price` ceiling on the armed path | P2 |
| AT-12 | Four spellings of the product name (route/page/API/legacy) | P3 |

---

## 7. Verdict

**Is AutothinK complete for its approved scope? — NO.**

For its **documented** scope (research-run workspace, local-first), AutothinK is partially delivered: the local lane genuinely works end-to-end, the routing and honest-status design are strong, and the hosted adapter's fail-closed model selection is exemplary.

But three P0 defects (unreachable hosted lane, unauthenticated API, config/runtime disagreement on arming) plus six P1 gaps (no grounding, no metering, no tenancy, no cancellation, no idempotency, overclaiming copy) mean it cannot be considered complete, and the hosted lane cannot be tested at all until AT-01 and AT-03 are resolved.

**Live-hosted validation remains BLOCKED** pending: (a) the route fix, (b) a fresh operator authorization for one bounded live call, and (c) an explicit spend cap.
