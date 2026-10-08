# Hosted Reasoning (OpenCode Zen)

Temporary, provider-neutral hosted-reasoning integration for private Northstar
testing. This adapter lets internal non-creative services call cloud language
models through **OpenCode Zen** while preserving the local creative pipeline and
all local non-creative models.

## Scope

- **In scope:** listing proposals, ad-copy proposals, spreadsheet analysis,
  AutothinK reasoning runs.
- **Out of scope:** image/video generation, automated marketplace publishing,
  automated advertising-platform actions, scheduled autonomous updates,
  customer-facing hosted service deployment.
- **Workflow:** supplied data / uploaded spreadsheet → hosted analysis →
  deterministic validation → before/after owner review → approved Excel/CSV
  export → manual upload by the owner.

## Verified configuration (2026-10-08)

**Documented endpoint** (https://opencode.ai/docs/zen/#endpoints):

```
https://opencode.ai/zen/v1/chat/completions
```

> The `/zen/go/v1/chat/completions` path that appeared in the original request
> is **not** the documented Zen endpoint. It returned
> `HTTP 400 Model is unavailable` for every model. The documented path above was
> verified live: auth and model routing both succeed.

**Verified models** (bare Zen IDs — no `opencode-go/` prefix):

| Role | ID | Input $/1M | Output $/1M | Cached read $/1M | Live status |
|------|----|------------|-------------|------------------|-------------|
| Policy default | `step-5-preview-free` | Free | Free | Free | **403 FreeTierError — provider-blocked** |
| Standard | `deepseek-v4.1-flash` | $0.30 | $1.20 | $0.006 | 402 Insufficient account funds |
| Alternative | `glm-5.3-flash` | $0.15 | $0.50 | $0.03 | 402 Insufficient account funds |
| Budget | `mimo-v2.6-flash-free` | Free | Free | Free | **403 FreeTierError — provider-blocked** |
| Escalation | `kimi-k2.7-code` | $0.95 | $4.00 | $0.19 | 402 Insufficient account funds |

Pricing source: OpenCode Zen docs (https://opencode.ai/docs/zen/), observed
2026-10-08. The catalogue values differ from the generic model catalogue
(DeepSeek V4.1 Flash is $0.30/$1.20 on Zen, not $0.15/$0.60); the Zen figures
above are authoritative for this endpoint.

### Live provider findings

| Model | HTTP | Body |
|-------|------|------|
| `step-5-preview-free` | 403 | `{"error":{"type":"FreeTierError","message":"OpenCode's free tier can only be used from within OpenCode"}}` |
| `mimo-v2.6-flash-free` | 403 | same FreeTierError |
| `deepseek-v4.1-flash` | 402 | `{"error":{"type":"server_error","message":"Upstream request failed: Insufficient account funds"}}` |
| `glm-5.3-flash` | 402 | same insufficient funds |
| `kimi-k2.7-code` | 402 | same insufficient funds |

Interpretation:

- The integration is **transport/auth/routing verified** — paid requests reach
  the provider and are rejected only for balance.
- **Free-tier models cannot be used by this integration at all.** Zen restricts
  its free tier to callers inside OpenCode. The Step 5 policy default is
  therefore provider-blocked and the UI says so; no substitute model is used
  silently.
- Zen publishes `mimo-v2.6-flash-free`, not a paid `mimo-v2.6-flash`.

## TEMPORARY MODEL ROUTING POLICY — STEP 5 DEFAULT FOR NON-CREATIVE WORK

**Purpose:** temporarily use Step 5 Preview Free as the default model for all
non-creative operational work while it remains free on OpenCode Zen. This is a
temporary cost-saving and orchestration policy, not a permanent architecture
decision.

**Primary rule:** use Step 5 Preview Free as the default model for all
non-creative tasks unless a task clearly belongs to a specialized model category
defined below.

**What counts as non-creative work** — planning implementation steps; repo
analysis and codebase navigation; debugging application logic; writing or
updating backend code; frontend non-visual business logic; API integrations;
database queries, schema work, migrations, data cleanup; auth, sessions, roles,
permissions, billing logic; admin tools and internal dashboards; listing
workflows, CMS flows, sync jobs, cron jobs, queues, notifications; logging,
telemetry, monitoring, alerting, error triage; writing/fixing/running tests;
CI/CD, deployment scripts, environment handling, infrastructure glue;
documentation, technical specs, implementation plans, task breakdowns;
cross-service coordination and "manager" tasks across the platform.

**What Step 5 should manage by default:** listings-related services; general
application services; back-office and operational workflows; integrations
between services; task decomposition and execution planning; most day-to-day
engineering work that is not image-generation creativity.

**What Step 5 should NOT manage by default:** creative remodel image
generation; interior/exterior redesign rendering; ComfyUI creative prompt
generation where a specialized image model is required; aesthetic design
ideation; final creative judgment on remodel outputs; any task whose main goal
is generating or editing property imagery.

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
  escalate to **Kimi K2.7 Code**.
- Lightweight, repetitive, cheap-to-run engineering work may intentionally use
  **DeepSeek V4.1 Flash** as a lower-cost fallback.
- Step 5 is the temporary default, not mandatory in every case.

**Execution standards for Step 5:** do not claim completion without
verification; read relevant files before editing; make the smallest correct
change set; preserve existing architecture unless a change is explicitly
required; run available tests, linting, and type checks; report exact files
changed, exact commands run, exact outcomes; if uncertain, stop and state the
uncertainty rather than inventing a result.

**Northstar-specific priority:** Step 5 is the default manager for all
non-creative platform work — listings, service coordination, backend
workflows, agent logic, business rules, dashboard/admin work, and operational
debugging.

**Implementation note:** because Zen free-tier models are provider-blocked for
external callers, `step-5-preview-free` is configured as the default with
`provider_blocked: true`. The selector shows it as *provider-blocked*, and any
run against it returns the Zen 403 FreeTierError verbatim. Nothing substitutes
another model automatically.

**Temporary policy note:** this routing policy is temporary and remains in
effect only while Step 5 Preview Free is available and performing well enough to
justify default use.

**Removal condition:** once Step 5 Preview Free is no longer free — or if its
quality becomes unreliable — revert default non-creative routing back to the
prior preferred model (`deepseek-v4.1-flash`).

**Hard guardrail:** under no circumstances should this policy be interpreted to
mean Step 5 becomes the default creative remodel renderer. Creative
property-image generation must remain on the specialized visual pipeline.

## Configuration

Copy these keys into your local `.env` (gitignored, never committed):

```bash
# Required
OPENCODE_GO_API_KEY=your_opencode_zen_key_here
OPENCODE_GO_ENABLED=1

# Optional overrides
# OPENCODE_API_KEY=                     # Zen-documented alias; either works
# OPENCODE_GO_ENDPOINT=https://opencode.ai/zen/v1/chat/completions
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
  Includes `_classify_provider_error` for FreeTier / insufficient-funds / auth /
  rate-limit conditions.
- `Northstar_backend/reasoning_tasks.py` — task-specific workflows
  (listing/ad/spreadsheet/generic) with deterministic validation.
- `Northstar_backend/main.py` — routes under `/api/v1/reasoning/*`.
- `northstar-os-ui/src/components/ReasoningModelSelector.jsx` — selectable
  model UI with persisted default and provider-blocked badge.
- `northstar-os-ui/src/pages/internal/SpreadsheetLab.jsx`,
  `ListingForge.jsx`, `AdPilot.jsx`, `AutothinK.jsx` — consumer surfaces.

## Provider constraints

- OpenCode documents Zen as serving "models that work well as coding agents";
  this integration uses it for Northstar's planning/reasoning tasks (listing
  analysis, ad-copy drafting, spreadsheet classification, AutothinK research).
- The adapter uses a truthful User-Agent (`NorthstarOS/<version>
  private-testing (non-creative-reasoning)`) and a stable
  `x-opencode-session` value per conversation.
- We do not disguise listing/ad requests as coding work, spoof another client,
  or attempt to bypass provider restrictions.
- **No paid Zen balance fallback and no other paid provider is enabled
  automatically.** The selected model's error is surfaced verbatim.

## Security / privacy

- API key is server-side only; it never reaches the browser, logs, reports, or
  git. The backend accepts `OPENCODE_GO_API_KEY` or `OPENCODE_API_KEY`.
- Only task-relevant data is sent.
- Reasoning endpoints are protected by existing foundation authentication.
- No public tunnels, firewall rules, or creative-service access are altered.

## Cost and limit controls

- Bounded concurrency via semaphore (`OPENCODE_GO_MAX_CONCURRENCY`, default 2).
- Conservative default max_tokens (4096).
- Retries are limited (`OPENCODE_GO_RETRIES`, default 2).
- No infinite retry loops; rate/usage limits return a clear user-visible error.
- Usage and provenance are recorded (tokens, model, latency, estimated cost,
  pricing source/timestamp).

## UI model selection

The selector persists the chosen model in `localStorage`
(`ns-reasoning-model-v2`). The configured default is `step-5-preview-free`
(policy default, currently provider-blocked). Per-task override is available on
each reasoning surface. The actual provider/model used is shown on the request
and the resulting proposal.

## Live-test controls

Owner-triggered comparison tests are available on:

1. **ListingForge → Editor → Hosted listing proposal**
2. **AdPilot → Planner → Hosted ad-copy proposal**
3. **Spreadsheet Lab → Upload/paste CSV → Analyze with hosted reasoning**

These use the same sanitized inputs across selectable models. Score factual
correctness, schema compliance, usefulness, repetition, latency, and token
usage.

Do **not** execute live comparison requests without explicit owner approval.
A full comparison is currently blocked because every selectable model either
returns FreeTierError (free models) or insufficient funds (paid models).

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
- [x] Three verified model configurations selectable (+ escalation)
- [x] Non-creative consumers integrated (AutothinK, ListingForge, AdPilot, Spreadsheet Lab)
- [x] Policy default = Step 5 Preview Free
- [x] Manual proposal/review/export workflow
- [x] Mocked tests passing
- [x] Owner-triggered live-test controls in UI
- [x] Configuration and credential instructions
- [x] Accurate provider-usage constraints documented
- [x] Live transport/auth/routing verified (402/403 observed)
- [ ] Live model output comparison — **blocked**: no usable model without Zen balance
- [ ] Owner-approved for routine use

## Unresolved issues

1. **No usable model without a Zen balance.** Every paid model returns 402
   Insufficient account funds; every free model returns 403 FreeTierError.
2. **Step 5 policy default is provider-blocked.** Either add Zen balance and
   keep DeepSeek as the working default, or drop the Step 5 default per the
   removal condition.
3. The `/zen/go/v1/chat/completions` endpoint from the original request is not
   the documented path; `/zen/v1/chat/completions` is used instead.
4. The generic model catalogue's DeepSeek pricing differs from Zen's; Zen is
   authoritative for this endpoint.

## Commits

- `dd5e8d9` — hosted reasoning backend adapter, tasks, routes, config, mocked tests
- `27b3e9f` — hosted reasoning UI integration
- `18ea970` — route-level integration tests
- `7eaa0d5` — configuration and constraint documentation
