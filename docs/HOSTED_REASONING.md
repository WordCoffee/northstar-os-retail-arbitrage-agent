# Hosted Reasoning (OpenCode Go)

Temporary, provider-neutral hosted-reasoning integration for private Northstar
testing. This adapter lets internal non-creative services call cloud language
models through OpenCode Go while preserving the local creative pipeline and all
local non-creative models.

## Scope

- **In scope:** listing proposals, ad-copy proposals, spreadsheet analysis,
  AutothinK reasoning runs.
- **Out of scope:** image/video generation, automated marketplace publishing,
  automated advertising-platform actions, scheduled autonomous updates,
  customer-facing hosted service deployment.
- **Workflow:** supplied data / uploaded spreadsheet → hosted analysis →
  deterministic validation → before/after owner review → approved Excel/CSV
  export → manual upload by the owner.

## Verified model catalog

All three selectable models were verified against the live OpenCode model
catalog before configuration. Exact endpoint IDs are used; no invented or
silently-substituted models.

| Role | ID | Input $/1M | Output $/1M | Cache read $/1M | Source |
|------|----|------------|-------------|-----------------|--------|
| Default | `opencode-go/deepseek-v4.1-flash` | $0.15 | $0.60 | $0.003 | OpenCode catalog |
| Alternative | `opencode-go/glm-5.3-flash` | $0.15 | $0.50 | $0.03 | OpenCode catalog |
| Budget | `opencode-go/mimo-v2.6-flash` | $0.14 | $0.28 | $0.0028 | OpenCode catalog |

Pricing observed: 2026-10-08. DeepSeek peak/off-peak pricing is not published
by the provider; assume the listed rates when estimating cost.

## Configuration

Copy these keys into your local `.env` (gitignored, never committed):

```bash
# Required
OPENCODE_GO_API_KEY=your_opencode_go_key_here
OPENCODE_GO_ENABLED=1

# Optional overrides
# OPENCODE_GO_ENDPOINT=https://opencode.ai/zen/go/v1/chat/completions
# OPENCODE_GO_MAX_CONCURRENCY=2
# OPENCODE_GO_TIMEOUT_SECONDS=120
# OPENCODE_GO_MAX_TOKENS=4096
# OPENCODE_GO_RETRIES=2
```

`OPENCODE_GO_ENABLED=1` is required for any live call. A key alone is not
enough — the adapter is intentionally fail-closed so paid usage is never
automatic.

## Architecture

- `Northstar_backend/adapters/reasoning_provider.py` — common
  `ReasoningProvider` interface and `OpenCodeGoProvider` implementation.
- `Northstar_backend/reasoning_tasks.py` — task-specific workflows
  (listing/ad/spreadsheet/generic) with deterministic validation.
- `Northstar_backend/main.py` — routes under `/api/v1/reasoning/*`.
- `northstar-os-ui/src/components/ReasoningModelSelector.jsx` — selectable
  model UI with persisted default.
- `northstar-os-ui/src/pages/internal/SpreadsheetLab.jsx`,
  `ListingForge.jsx`, `AdPilot.jsx`, `AutothinK.jsx` — consumer surfaces.

## Provider constraints

- OpenCode Go documentation qualifies the endpoint as typical coding-agent
  traffic. Northstar uses it for planning/reasoning tasks only (listing
  analysis, ad-copy drafting, spreadsheet classification, AutothinK research).
- The adapter uses a truthful User-Agent (`NorthstarOS/<version>
  private-testing (non-creative-reasoning)`) and a stable
  `x-opencode-session` value per conversation.
- We do not disguise listing/ad requests as coding work, spoof another client,
  or attempt to bypass provider restrictions.

## Security / privacy

- API key is server-side only; it never reaches the browser, logs, reports, or
  git.
- Only task-relevant data is sent.
- Reasoning endpoints are protected by existing foundation authentication.
- No public tunnels, firewall rules, or creative-service access are altered.

## Cost and limit controls

- Bounded concurrency via semaphore (`OPENCODE_GO_MAX_CONCURRENCY`, default 2).
- Conservative default max_tokens (4096).
- Retries are limited (`OPENCODE_GO_RETRIES`, default 2).
- No infinite retry loops; rate/usage limits return a clear user-visible error.
- No paid Zen balance fallback or another paid provider is enabled
  automatically.
- Usage and provenance are recorded (tokens, model, latency, estimated cost,
  pricing source/timestamp).

## UI model selection

The selector persists the chosen model in `localStorage`
(`ns-reasoning-model`). The default is `opencode-go/deepseek-v4.1-flash`.
Per-task override is available on each reasoning surface. The actual
provider/model used is shown on the request and the resulting proposal.

## Live-test controls

Owner-triggered comparison tests are prepared in the UI surfaces:

1. **ListingForge → Editor → Hosted listing proposal**
2. **AdPilot → Planner → Hosted ad-copy proposal**
3. **Spreadsheet Lab → Upload/paste CSV → Analyze with hosted reasoning**

These use the same sanitized inputs across the three selectable models. Score
factual correctness, schema compliance, usefulness, repetition, latency, and
token usage.

Do **not** execute live comparison requests without explicit owner approval.
The implementation is complete and mocked-tested; live validation is gated on
`OPENCODE_GO_ENABLED=1` and a real key.

## Test results

Mocked test suites:

- `Northstar_backend/tests/test_reasoning_provider.py`
- `Northstar_backend/tests/test_reasoning_tasks.py`
- `Northstar_backend/tests/test_reasoning_routes.py`

Run with:

```bash
cd Northstar_backend
python -m unittest tests.test_reasoning_provider tests.test_reasoning_tasks tests.test_reasoning_routes
```

## Status checklist

- [x] Provider-neutral adapter implemented
- [x] Three verified model configurations selectable
- [x] Non-creative consumers integrated (AutothinK, ListingForge, AdPilot, Spreadsheet Lab)
- [x] DeepSeek default
- [x] Manual proposal/review/export workflow
- [x] Mocked tests passing
- [x] Owner-triggered live-test controls in UI
- [x] Configuration and credential instructions
- [x] Accurate provider-usage constraints documented
- [ ] Live comparison executed (requires owner approval + real key)
- [ ] Owner-approved for routine use

## Unresolved issues

- Live comparison results are pending owner approval and a real
  `OPENCODE_GO_API_KEY`.
- Provider pricing and availability can change; the catalog should be
  re-verified before scaling usage.
