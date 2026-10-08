# OpenCode Go Correction — Final Report

**Date:** 2026-10-08
**Commit:** `78c8600`
**Branch:** `feature/creative-social-local`

---

## 1. Files changed

| File | Change |
|------|--------|
| `Northstar_backend/adapters/reasoning_provider.py` | Reconfigured to the OpenCode Go contract: base URL `https://opencode.ai/zen/go/v1`, chat endpoint `…/chat/completions`, provider id `opencode-go`, bare model IDs, single credential env var `OPENCODE_GO_API_KEY`, flag `OPENCODE_GO_ENABLED`, Bearer auth, no header logging, per-model `verified_usability`, single `VERIFIED_GO_MODEL`. |
| `Northstar_backend/main.py` | `/api/v1/reasoning/models` now reports `provider`, `base_url`, `chat_endpoint`, `policy_preferred_model`, `verified_model`, `runtime_default_model`, `verified_usability`. |
| `Northstar_backend/reasoning_tasks.py` | `DEFAULT_TASK_MODEL = None` — no runtime default is assumed by tasks; provenance carries provider/verified flags. |
| `Northstar_backend/tests/test_reasoning_provider.py` | Tests for the exact Go endpoint, bare IDs, provider id, bearer header, verified-only default, unverified models staying unverified, error classification (403/402/401/404/429). |
| `Northstar_backend/tests/test_reasoning_routes.py` | Route tests for verified/default reporting. |
| `northstar-os-ui/src/components/ReasoningModelSelector.jsx` | Labelled "OpenCode Go model"; verified/unverified pills; no-Zen naming. |
| `northstar-os-ui/src/pages/internal/AutothinK.jsx` | "Hosted (OpenCode Go)"; unverified-model warning. |
| `.env.example` | Replaced the generic pay-as-you-go config block with the exact Go contract. |
| `docs/HOSTED_REASONING.md` | Full rewrite: Go contract, correction note, Step 5 routing policy, verification record. |

## 2. Exact non-secret configuration contract now used

```
Credential env var : OPENCODE_GO_API_KEY
Enable flag        : OPENCODE_GO_ENABLED   (value "1")
Base URL           : https://opencode.ai/zen/go/v1
Chat endpoint      : https://opencode.ai/zen/go/v1/chat/completions
Auth header        : Authorization: Bearer <OPENCODE_GO_API_KEY>
Provider id        : opencode-go
Model IDs          : bare ids, passed through unchanged
```

Only `OPENCODE_GO_API_KEY` is read as a credential — no other key name.
`https://opencode.ai/zen/v1/chat/completions` is **not** used by this
integration. "Zen" appears nowhere in user-facing UI status text.

## 3. Endpoint and model ID used for verification

- Endpoint: `https://opencode.ai/zen/go/v1/chat/completions`
- Model ID: `step-5-preview-free` (bare, unmodified)
- One minimal, non-destructive request: `max_tokens=8`, prompt `ping`.

## 4. Did a real model completion succeed?

**Yes.**

- HTTP **200**
- `success = True`
- Returned model id echoed exactly: `step-5-preview-free`

## 5. Redacted error category

None — the request succeeded. No provider error was returned.

## 6. Did any live runtime default change?

**No.** The verified model is `step-5-preview-free`, which is also the
temporary policy preference for non-creative internal work. No other model was
made a default:

- `deepseek-v4.1-flash` — **not** switched to; remains unverified.
- `kimi-k2.7-code` — remains escalation-only and unverified.

Because the Step 5 preference and the verified model coincide, no runtime
routing changed as a result of this correction. Had Step 5 failed verification,
no model would have been promoted.

## 7. Commands and checks run

| Check | Result |
|-------|--------|
| Secret-safe presence check (names/flag only, value withheld) | `OPENCODE_GO_API_KEY : SET` · `OPENCODE_GO_ENABLED : 1` |
| `git check-ignore .env` | `.env` → ignored (confirmed untracked) |
| `git ls-files .env` | not tracked |
| `git status --porcelain -- .env` | clean (not staged, not modified) |
| Endpoint/model constants | `base_url = https://opencode.ai/zen/go/v1`, `chat_endpoint = …/chat/completions`, `provider_id = opencode-go`, `policy model = step-5-preview-free` |
| **Live completion via corrected Go endpoint** | **HTTP 200, success, model echoed `step-5-preview-free`** |
| `npm run build` (root) | ✓ 415.16 kB |
| `npm run build` (UI) | ✓ 415.16 kB |
| `node Northstar_backend/test_ui_display.cjs` | ALL UI DISPLAY TESTS PASSED |
| `python -m unittest tests.test_reasoning_provider tests.test_reasoning_tasks tests.test_reasoning_routes test_noncreative_reads.py` | **58 tests, OK** |
| `git diff --check` on changed files | clean (exit 0) |

## 8. Secret handling confirmation

- **No secret value was printed, echoed, parsed into output, grepped, logged, or committed.**
- The one earlier accidental exposure was in a prior session's tool output; the
  key is being rotated by you separately.
- This session's presence checks reported only variable names and the flag
  value — never a key value.
- `.env` remains gitignored and untracked; nothing credential-shaped was staged.
- Authorization headers are never logged by the adapter; requests are never
  logged with payloads.

## Operational notes (unchanged behaviour)

1. The FastAPI app does not load `.env` itself — set `OPENCODE_GO_API_KEY` and
   `OPENCODE_GO_ENABLED=1` in the environment before starting the server.
2. `.env` line 98 is a raw `retailerapi.com key: <value>` entry that
   `python-dotenv` cannot parse; it is skipped non-fatally and is unrelated to
   the OpenCode Go path.
