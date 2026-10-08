# Hosted Reasoning Integration Report

**Date:** 2026-10-08  
**Worktree:** C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent  
**Branch:** feature/creative-social-local  
**Base commit before work:** 56ed331  
**Current HEAD:** 7eaa0d5

## Objective

Add selectable cloud reasoning to Northstar's non-creative services using a
temporary, provider-neutral, manually operated hosted-reasoning integration
(OpenCode Go), while preserving the local creative pipeline and all local
non-creative models.

## Model verification

Verified against the live OpenCode model catalog before any configuration:

| Role | Exact ID | Status | Input $/1M | Output $/1M |
|------|----------|--------|------------|-------------|
| Default | `opencode-go/deepseek-v4.1-flash` | active | $0.15 | $0.60 |
| Alternative | `opencode-go/glm-5.3-flash` | active | $0.15 | $0.50 |
| Budget | `opencode-go/mimo-v2.6-flash` | active | $0.14 | $0.28 |

Endpoint: `https://opencode.ai/zen/go/v1/chat/completions`

No invented or silently substituted models.

## Implemented

### Backend

- `Northstar_backend/adapters/reasoning_provider.py` — common
  `ReasoningProvider` interface + `OpenCodeGoProvider` + `MockReasoningProvider`.
  Features: configurable endpoint/model, server-side credentials, streaming,
  timeouts, bounded concurrency + retries, usage/provenance reporting,
  structured errors, mockable transport.
- `Northstar_backend/reasoning_tasks.py` — task-specific workflows for
  listing proposals, ad-copy proposals, spreadsheet analysis, and generic
  reasoning. Includes deterministic validation and private-label / retail-arbitrage
  focused prompts.
- `Northstar_backend/main.py` — new routes:
  - `GET /api/v1/reasoning/models`
  - `POST /api/v1/reasoning/listing-proposal`
  - `POST /api/v1/reasoning/ad-copy-proposal`
  - `POST /api/v1/reasoning/spreadsheet-analysis`
  - `POST /api/v1/reasoning/run`
- `.env.example` — documented `OPENCODE_GO_*` configuration keys.

### Frontend

- `northstar-os-ui/src/components/ReasoningModelSelector.jsx` — selectable
  model UI with persisted default (`ns-reasoning-model` localStorage key).
- `northstar-os-ui/src/foundation/api.js` — reasoning API helpers.
- `northstar-os-ui/src/pages/internal/AutothinK.jsx` — added "hosted"
  provider lane alongside local/cloud.
- `northstar-os-ui/src/pages/internal/ListingForge.jsx` — added hosted
  listing-proposal panel with before/after review.
- `northstar-os-ui/src/pages/internal/AdPilot.jsx` — added hosted ad-copy
  proposal panel with unsupported-claim flagging.
- `northstar-os-ui/src/pages/internal/SpreadsheetLab.jsx` — new page for
  CSV upload/paste, hosted analysis, and deterministic export.
- `northstar-os-ui/src/App.jsx`, `src/data/nav-config.js`,
  `src/data/readiness.js` — routes and nav wiring.

### Tests

- `Northstar_backend/tests/test_reasoning_provider.py` (22 tests)
- `Northstar_backend/tests/test_reasoning_tasks.py` (10 tests)
- `Northstar_backend/tests/test_reasoning_routes.py` (6 tests)

All mocked; no live provider calls.

### Documentation

- `docs/HOSTED_REASONING.md` — configuration, credentials, provider
  constraints, cost/limit controls, live-test controls, status checklist.

## Build / test results

- Root `npm run build`: ✓ (413.48 kB index bundle)
- UI `npm run build`: ✓
- `node Northstar_backend/test_ui_display.cjs`: ALL PASSED
- Backend `tests.test_reasoning_provider + tests.test_reasoning_tasks + tests.test_reasoning_routes + test_noncreative_reads.py`: 38 tests, OK
- `git diff --check HEAD~6 HEAD`: clean

## Status

| Item | Status |
|------|--------|
| Provider-neutral adapter | Implemented |
| Verified model configurations (3) | Configured |
| Non-creative consumers integrated | Implemented |
| DeepSeek default | Configured |
| Manual proposal/review/export workflow | Implemented |
| Mocked tests | Passing (38) |
| Owner-triggered live-test controls | In UI |
| Configuration/credential instructions | Documented |
| Provider-usage constraints documented | Yes |
| Live comparison executed | **Pending owner approval + real key** |
| Owner-approved for routine use | **Pending** |

## Unresolved issues

- No `OPENCODE_GO_API_KEY` is present in this environment, so live calls are
  intentionally blocked (`OPENCODE_GO_ENABLED=0` by default).
- Live comparison across the three models requires owner approval and a real
  key before execution.
- Provider pricing/availability can change; re-verify catalog before scaling.

## Commits

- `dd5e8d9` — hosted reasoning backend adapter, tasks, routes, config, mocked tests
- `27b3e9f` — hosted reasoning UI integration
- `18ea970` — route-level integration tests
- `7eaa0d5` — configuration and constraint documentation
