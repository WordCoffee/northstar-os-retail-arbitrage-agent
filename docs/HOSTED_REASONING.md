# Hosted Reasoning (OpenCode Go)

Temporary, provider-neutral hosted-reasoning integration for private Northstar
testing. This adapter lets internal non-creative services call cloud language
models through **OpenCode Go** while preserving the local creative pipeline and
all local non-creative models.

> **Correction (2026-10-08).** An earlier revision of this integration pointed at
> `https://opencode.ai/zen/v1/chat/completions`. That is the **generic
> pay-as-you-go OpenCode route**, a different surface with different billing and
> routing. This document and the adapter now use the **OpenCode Go** contract
> only. Live probing proved the two surfaces behave differently: the generic
> route refused the free-tier models, while OpenCode Go returned a real
> completion. Never use the generic route for this integration.

## OpenCode Go contract (exact)

| Item | Value |
|------|-------|
| Credential env var | `OPENCODE_GO_API_KEY` |
| Enable flag | `OPENCODE_GO_ENABLED=1` |
| Base URL | `https://opencode.ai/zen/go/v1` |
| Chat-completions endpoint | `https://opencode.ai/zen/go/v1/chat/completions` |
| Auth header | `Authorization: Bearer <OPENCODE_GO_API_KEY>` |
| Model IDs | bare IDs, passed through exactly as selected |
| Provider id | `opencode-go` |

- Model IDs are **bare** — e.g. `step-5-preview-free`, `deepseek-v4.1-flash`,
  `kimi-k2.7-code`. No prefix is added or rewritten.
- Only `OPENCODE_GO_API_KEY` is read as a credential. No other key name is
  consulted.
- Authorization headers are never logged. Requests are never logged with
  payloads.

## Scope

- **In scope:** listing proposals, ad-copy proposals, spreadsheet analysis,
  AutothinK reasoning runs.
- **Out of scope:** image/video generation, automated marketplace publishing,
  automated advertising-platform actions, scheduled autonomous updates,
  customer-facing hosted service deployment.
- **Workflow:** supplied data / uploaded spreadsheet → hosted analysis →
  deterministic validation → before/after owner review → approved Excel/CSV
  export → manual upload by the owner.

## TEMPORARY MODEL-ROUTING POLICY — STEP 5 DEFAULT FOR NON-CREATIVE WORK

**Purpose:** temporarily use Step 5 Preview Free as the default model for all
non-creative operational work while it remains free on OpenCode Go. This is a
temporary cost-saving and orchestration policy, not a permanent architecture
decision.

**Primary rule:** use Step 5 Preview Free as the default model for all
non-creative tasks unless a task clearly belongs to a specialized model category
defined below.

**Non-creative work includes:** planning implementation steps; repo analysis and
codebase navigation; debugging application logic; writing or updating backend
code; frontend non-visual business logic; API integrations; database queries,
schema work, migrations, data cleanup; auth, sessions, roles, permissions,
billing logic; admin tools and internal dashboards; listings workflows, CMS
flows, sync jobs, cron jobs, queues, notifications; logging, telemetry,
monitoring, alerting, error triage; writing/fixing/running tests; CI/CD,
deployment scripts, environment handling, infrastructure glue; documentation,
technical specs, implementation plans, task breakdowns; cross-service
coordination and "manager" tasks across the platform.

**Step 5 should manage by default:** listings-related services; general
application services; back-office and operational workflows; integrations
between services; task decomposition and execution planning; most day-to-day
engineering work that is not image-generation creativity.

**Step 5 should NOT manage by default:** creative remodel image generation;
interior/exterior redesign rendering; creative-pipeline prompt generation where
a specialized image model is required; aesthetic design ideation; final creative
judgment on remodel outputs; any task whose main goal is generating or editing
property imagery.

**Creative-model rule:** for creative remodel, staging, landscaping, image
editing, or visual transformation tasks, use the dedicated creative/image
pipeline and its assigned visual models instead of Step 5. Step 5 may help with
surrounding logic, orchestration, validation, or implementation planning, but it
must not replace the creative rendering stack.

**Default routing policy:**

1. If the task is non-creative, operational, analytical, architectural,
   backend, integration, testing, or management-related, route to Step 5 first.
2. If the task is primarily visual, aesthetic, or image-generation-related, do
   not route to Step 5 as the main worker.
3. If a task begins as non-creative but requires specialized visual generation,
   let Step 5 coordinate the handoff rather than performing the visual work.

**Escalation policy:**

- If Step 5 loops, stalls, loses context, or produces weak code quality,
  escalate to **Kimi K2.7 Code** (explicit, never automatic).
- Lightweight, repetitive, cheap-to-run engineering work may intentionally use
  **DeepSeek V4.1 Flash** as a lower-cost fallback.
- Step 5 is the temporary default, not mandatory in every case.

**Execution standards:** do not claim completion without verification; read
relevant files before editing; make the smallest correct change set; preserve
existing architecture unless a change is explicitly required; run available
tests, linting, and type checks; report exact files changed, exact commands
run, exact outcomes; if uncertain, stop and state the uncertainty rather than
inventing a result.

**Northstar-specific priority:** Step 5 is the default manager for all
non-creative platform work — listings, service coordination, backend
workflows, agent logic, business rules, dashboard/admin work, and operational
debugging.

**Temporary policy note:** this routing policy is temporary and remains in
effect only while Step 5 Preview Free is available and performing well enough
to justify default use.

**Removal condition:** once Step 5 Preview Free is no longer free — or if its
quality becomes unreliable — revert default non-creative routing back to the
prior preferred model (`deepseek-v4.1-flash`).

**Hard guardrail:** under no circumstances should this policy be interpreted to
mean Step 5 becomes the default creative remodel renderer. Creative
property-image generation must remain on the specialized visual pipeline.

## Model catalog

| Role | Bare ID | Input $/1M | Output $/1M | Verified through Go |
|------|---------|------------|-------------|---------------------|
| Preferred (non-creative) | `step-5-preview-free` | Free | Free | **Yes — HTTP 200, 2026-10-08** |
| Standard | `deepseek-v4.1-flash` | $0.30 | $1.20 | No (not yet independently probed) |
| Alternative | `glm-5.3-flash` | $0.15 | $0.50 | No |
| Budget | `mimo-v2.6-flash-free` | Free | Free | No |
| Escalation | `kimi-k2.7-code` | $0.95 | $4.00 | No |

Only `step-5-preview-free` has a proven real completion through the corrected
Go endpoint. Every other model is reported unverified, and no unverified model
is ever a runtime default or an automatic fallback.

## Availability guardrail (hardened)

The adapter enforces fail-closed model selection:

- `VERIFIED_GO_MODEL` holds the single model with a proven real Go completion;
  it is also `RUNTIME_DEFAULT_MODEL` when the provider is armed.
- `verified_usability` is per-model, so the UI can never imply an unverified
  default.
- `resolve_model(requested)` behaves as:
  - **Nothing requested** → the verified model; if none is verified it raises
    `NoVerifiedModelError`.
  - **Explicit id not in the Go catalog** → `ValueError`.
  - **Explicit id in the catalog but not verified** → `ModelNotUsableError`
    (a `ValueError` subclass). **No silent substitution of another model.**
- `complete()` / `complete_stream()` convert those conditions into a structured
    `ProviderResponse` with `status=BLOCKED` and a clear message, instead of
  guessing a model.
- `DEFAULT_TASK_MODEL` is `None` in `reasoning_tasks.py` — no task assumes a
  runtime default.

### Intended roles

| Bare ID | Intended role | Rule |
|---------|---------------|------|
| `step-5-preview-free` | `default` | Non-creative hosted reasoning only. Verified. |
| `deepseek-v4.1-flash` | `fallback` | Fallback **only after** its own successful verification. |
| `kimi-k2.7-code` | `escalation` | Escalation **only after** its own successful verification; explicit, never automatic. |
| `glm-5.3-flash` | `experimental` | Not verified. |
| `mimo-v2.6-flash-free` | `experimental` | Not verified. |

Every model carries `allowed_for_creative: false`, and the API exposes
`hosted_reasoning_is_creative_renderer: false`.

**Live probe of the fail-closed behaviour (2026-10-08, no secrets printed):**
each model was submitted individually and only `step-5-preview-free` returned
`success=True`; every other model returned `status=blocked` with a
"not verified usable" message. With no model requested, the request resolved to
`step-5-preview-free`.

**Live verification performed (2026-10-08):** one minimal, non-destructive
completion request — model `step-5-preview-free`, `max_tokens=8`, prompt
`ping` — against
`https://opencode.ai/zen/go/v1/chat/completions`.
Result: **HTTP 200, success, model id echoed unchanged.** No provider error.

The earlier `403` free-tier refusal was observed only on the generic
pay-as-you-go route, not on Go.

## Configuration

Copy these keys into your local `.env` (gitignored, never committed):

```bash
# Required
OPENCODE_GO_API_KEY=your_opencode_go_key_here
OPENCODE_GO_ENABLED=1

# Optional overrides
# OPENCODE_GO_ENDPOINT=https://opencode.ai/zen/go/v1/chat/completions
# OPENCODE_GO_MODEL=step-5-preview-free
# OPENCODE_GO_MAX_CONCURRENCY=2
# OPENCODE_GO_TIMEOUT_SECONDS=120
# OPENCODE_GO_MAX_TOKENS=4096
# OPENCODE_GO_RETRIES=2
```

`OPENCODE_GO_ENABLED=1` is required for any live call. A key alone is not
enough — the adapter is intentionally fail-closed so paid usage is never
automatic.

> **Operational note:** the FastAPI app does not itself load `.env`. Set the
> variables in the shell/environment (or via the compose `env_file`) before
> starting the server. This is the pre-existing behaviour and is unchanged here.

## Architecture

- `Northstar_backend/adapters/reasoning_provider.py` — common
  `ReasoningProvider` interface and `OpenCodeGoProvider` implementation.
  Includes `_classify_provider_error` for free-tier / insufficient-balance /
  auth / not-found / rate-limit conditions.
- `Northstar_backend/reasoning_tasks.py` — task-specific workflows
  (listing/ad/spreadsheet/generic) with deterministic validation.
- `Northstar_backend/main.py` — routes under `/api/v1/reasoning/*`.
- `northstar-os-ui/src/components/ReasoningModelSelector.jsx` — selectable
  model UI with persisted default and verified/unverified badge.
- `northstar-os-ui/src/pages/internal/SpreadsheetLab.jsx`,
  `ListingForge.jsx`, `AdPilot.jsx`, `AutothinK.jsx` — consumer surfaces.

## Provider constraints

- OpenCode documents Go/Zen as serving "models that work well as coding
  agents"; this integration uses it for Northstar's planning/reasoning tasks
  (listing analysis, ad-copy drafting, spreadsheet classification, AutothinK
  research).
- The adapter uses a truthful User-Agent (`NorthstarOS/<version>
  private-testing (non-creative-reasoning)`) and a stable
  `x-opencode-session` value per conversation.
- We do not disguise listing/ad requests as coding work, spoof another client,
  or attempt to bypass provider restrictions. If a provider restriction is
  returned, it is reported verbatim and nothing is substituted.
- **No paid balance fallback and no other paid provider is enabled
  automatically.**

## Security / privacy

- API key is server-side only; it never reaches the browser, logs, reports, or
  git. Only `OPENCODE_GO_API_KEY` is read as a credential.
- Only task-relevant data is sent.
- Reasoning endpoints are protected by existing foundation authentication.
- No public tunnels, firewall rules, or creative-service access are altered.
- Presence checks report only that a variable is set — never its value.

## Cost and limit controls

- Bounded concurrency via semaphore (`OPENCODE_GO_MAX_CONCURRENCY`, default 2).
- Conservative default max_tokens (4096).
- Retries are limited (`OPENCODE_GO_RETRIES`, default 2).
- No infinite retry loops; rate/usage limits return a clear user-visible error.
- Usage and provenance are recorded (tokens, model, latency, estimated cost,
  pricing source/timestamp).

## UI model selection

The selector persists the chosen model in `localStorage`
(`ns-reasoning-model-v2`). The runtime default is the verified model. Per-task
override is available on each reasoning surface. The actual provider/model used
is shown on the request and the resulting proposal.

The models/status API returns, per model:

- `provider` (always `opencode-go`), `base_url`, `endpoint`
- `configured` (key present), `enabled` (flag set), `armed` (both)
- `verified_usability`, `intended_role`, `allowed_for_creative`
- `is_runtime_default`, `policy_preferred`, `usable`

Top-level status adds `verified_model`, `runtime_default_model`,
`verified_models`, `unverified_models`, `policy_preferred_model`,
`credential_env`, `enable_env`, `hosted_reasoning_is_creative_renderer`, and a
`note`. `runtime_default_model` is `None` when the provider is not armed, so
"configured", "verified" and "active default" stay three distinct states.

## Live-test controls

Owner-triggered comparison tests are available on:

1. **ListingForge → Editor → Hosted listing proposal**
2. **AdPilot → Planner → Hosted ad-copy proposal**
3. **Spreadsheet Lab → Upload/paste CSV → Analyze with hosted reasoning**

Do **not** execute live comparison requests without explicit owner approval.

## Test results

Mocked test suites:

- `Northstar_backend/tests/test_reasoning_provider.py`
- `Northstar_backend/tests/test_reasoning_tasks.py`
- `Northstar_backend/tests/test_reasoning_routes.py`

```bash
cd Northstar_backend
python -m unittest tests.test_reasoning_provider tests.test_reasoning_tasks tests.test_reasoning_routes
```

## Status checklist

- [x] Provider-neutral adapter implemented
- [x] OpenCode Go contract exact (base, endpoint, auth, bare IDs, provider id)
- [x] Non-creative consumers integrated (AutothinK, ListingForge, AdPilot, Spreadsheet Lab)
- [x] Manual proposal/review/export workflow
- [x] Mocked tests passing (65 tests)
- [x] Owner-triggered live-test controls in UI
- [x] Configuration and credential instructions
- [x] Accurate provider-usage constraints documented
- [x] Real OpenCode Go completion verified for `step-5-preview-free` (HTTP 200)
- [x] Fail-closed model selection (no silent fallback to an unverified model)
- [x] Status API distinguishes configured / enabled / verified / active default
- [x] Intended roles: default, fallback, escalation, experimental
- [x] Creative separation enforced (`allowed_for_creative: false` on every model)
- [ ] Owner-approved for routine use

## Unresolved issues

1. Only `step-5-preview-free` has been verified end-to-end.
   `deepseek-v4.1-flash`, `glm-5.3-flash`, `mimo-v2.6-flash-free`, and
   `kimi-k2.7-code` are catalogued but unverified — each needs its own real Go
   completion before it is treated as usable.
2. The FastAPI app does not load `.env` itself; operators must export the
   variables in the environment. Pre-existing behaviour, unchanged.
3. `.env` line 98 is a raw `retailerapi.com key: <value>` entry that
   `python-dotenv` cannot parse; it is skipped non-fatally. Worth converting to
   `KEY=value` if that credential is ever needed by the app.

## Commits (hosted reasoning)

- `dd5e8d9` backend adapter, tasks, routes, config, mocked tests
- `27b3e9f` UI integration
- `18ea970` route-level integration tests
- `7eaa0d5` configuration and constraint documentation
- `ecf6b4c` final integration report
- `a2dc683` earlier Zen-path revision (superseded)
- `191d7cd` live verification report
- see this session's final commit for the OpenCode Go correction
