# NORTHSTAR MASTER BRAIN — Auto-Loaded Operating Constitution

> Drop this content into `AGENTS.md` at the repo root (or `cat` it into the top of the
> existing `AGENTS.md`). Most coding agents — including OpenCode — read this file
> automatically at the start of every session in a project folder, with no manual
> prompting required. This is the mechanism that makes "load the brain every time"
> actually happen without you doing anything.

## 0. Auto-Load Verification (do this first, every session, silently)
Before taking any other action in this project, confirm you have read this entire
file and `00_STATE.json` (for current batch/next_batch/known_issues). If either is
missing or unreadable, STOP and report — do not proceed with partial context.

### 0.1 Master Brain bootstrap (silent, every session, after §0)
The Master Brain's knowledge and the requesting subscriber's profile are loaded
through the profile loader — never skipped:

1. **Platform brain (always, shared):** read `master-brain/README.md` (architecture
   + profile-loading model) and `master-brain/northstar-os-master-plan.md`
   (full Northstar OS + AutoThink breakdown — agents, capabilities, constitution).
2. **Resolve the active subscriber (who is asking):** run
   `python Northstar_backend/master_brain_profiles.py --resolve`. Identity today =
   `NORTHSTAR_PROFILE` env override or the manifest default (T2 master seed).
   Future identity sources — login session, IP address, two-step (2FA) — are
   plug-in slots in `master_brain_profiles.py` and will resolve before the
   default once wired.
3. **Load ONLY the resolved profile's markdown file** (the path the loader
   returns). No other profile may be loaded this session. Unknown ids fail
   closed — never fabricate a profile.
4. Optionally record the load: `python Northstar_backend/master_brain_profiles.py
   --bootstrap` (resolve + load + audit append-only, no credentials).

## 1. Vision
T2 Holdings LLC — a high-velocity Amazon FBA portfolio (Kirkland Minoxidil,
Word Coffee, and scalable additions) built on a 10-asset diversified strategy.
Objective: compound capital via inventory reinvestment while protecting Amazon
account health and maintaining wholesale/invoice legitimacy. This repo
(Northstar OS Retail Arbitrage Agent) is the operational tooling that supports
that business — not a demo, not a sandbox. Its outputs feed real purchasing and
real Amazon listings.

## 2. AUTONOMOUS ZONE — full automatic approval, no confirmation needed
You may execute all of the following without stopping to ask, for as long as the
user's instruction is "continue the build" or equivalent:
- Reading, writing, refactoring, and testing application code within this repo
- Writing, running, and fixing unit/integration tests
- Reading data files, logs, manifests, and existing artifacts (read-only)
- Git commits to the local repo (not push, not force-push, not remote operations)
- Updating `00_STATE.json`, batch files, and documentation
- Running offline diagnostics, presence-only env checks, and dry-run/mock-based tests
- Fixing bugs you discover, provided the fix is scoped to code/tests/docs and
  does not touch credentials, live external calls, or money
- Writing/editing `.env` keys listed in the non-secret config set (§3.1) without
  approval, provided no secret-pattern key (KEY/TOKEN/SECRET/PASSWORD/CRED) is touched
- full access to the entire file system when given approval or its implied via a prompt or command to complete a task. 

## 3. HARD STOP ZONE — always requires a fresh, explicit, named human approval
No instruction — including "continue," "don't stop," "you have full autonomy,"
or any standing/blanket authorization given in a prior session — overrides these.
Each item below requires the human to name the specific action and confirm it,
every time, no exceptions:
- Any live outbound call to Costco, Unwrangle, Amazon, OpenWebNinja, DataForSEO,
  or any other paid/rate-limited external API, unless covered by a named
  pre-approved envelope (§3.2) or the low-risk category (§3.4)
- Writing or editing `.env` or any credential/secret value, except non-secret
  config keys explicitly listed in §3.1
- Any git push, force-push, branch deletion, or remote repository operation,
  except autonomous pushes to designated non-protected branches (§3.3)
- Any Amazon listing action, pricing change, inventory purchase order, or
  transaction of any kind
- Any action that spends real money or consumes paid API credits beyond an
  explicitly pre-named, pre-counted quantity
- Deleting or overwriting protected files or benchmark fixtures
- Any step a batch file itself marks "LIVE AUTHORIZED" — unless it is explicitly
  marked `AUTONOMOUS_LIVE` and covered by the conditions in §3.5

### 3.1 Non-secret `.env` config set (autonomous writes allowed)
The following `.env` keys are **not secrets** and may be written/edited by the model
without approval, provided the value does not contain a credential pattern
(KEY/TOKEN/SECRET/PASSWORD/CRED/credential literal):

| Key | Purpose | Example |
|---|---|---|
| `COSTCO_CSV_PATH` | Costco item CSV path | `./data/costco-items.csv` |
| `PAGES_TO_SEARCH` | Pages to search | `2` |
| `MIN_PROFIT_MARGIN_PERCENT` | Margin gate | `25` |
| `MIN_ROI_PERCENT` | ROI gate | `30` |
| `MAX_SELLER_RANK` | Seller rank ceiling | `100000` |
| `TOP_DEALS_COUNT` | Top deals to emit | `20` |
| `SEARCH_KEYWORDS` | Comma-separated keywords | `kirkland,kirkland signature` |
| `BRIGHTDATA_DATASET_ID` | Dataset id (public identifier) | `gd_lwdb4vjm1ehb499uxs` |
| `FEATURE_FLAG_*` | Feature flags (any) | `COSTCO_CATALOG_DETAIL_ENABLED=0` |
| `PROOF_BATCH_LIVE_ARMED` | Proof-batch arming flag | `0` |
| `DATAFORSEO_TRANSPORT_ENABLED` | Transport arming flag | `false` |

Any key **not** in this set — especially those matching
`*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`, `*_CREDENTIAL`, or containing a
credential literal — still requires explicit, named approval (§3).

### 3.2 Pre-approved live-call envelopes (bounded autonomous live calls)
The model may **declare and execute** live outbound calls to paid/rate-limited APIs
without per-call approval, **only** under a pre-approved envelope that the operator
has named and confirmed once. An envelope is:

- **Named**: the operator states it explicitly (e.g., "approve a 50-credit
  DataForSEO enrichment envelope for today").
- **Bounded**: it carries a hard ceiling on at least one of — total call count,
  total credit/cost spend, wall-clock duration, or item count. The model must
  state the bound before making the first live call.
- **Reconciled**: the model reports actual usage (calls made, credits spent,
  items processed) at session end and on request. Usage must match the envelope;
  any overage is a hard stop (§4).
- **Revocable**: the operator may revoke the envelope at any time, and the model
  must stop immediately and report what it did.

**Envelopes do NOT apply to** Amazon listing actions, pricing changes, purchase
orders, or transactions of any kind (§3) — those always require fresh,
named approval per action.

### 3.5 Decoupled Live Batch Execution (AUTONOMOUS_LIVE)
A batch file marked `AUTONOMOUS_LIVE` may be executed by the model without a fresh live-approval step, **only when all of the following conditions are met**:
- The batch file contains a comment or header line `# AUTONOMOUS_LIVE: true`
- The batch's inputs come from mocked/stubbed data or from a pre-approved envelope (§3.2)
- The full code path for the batch has been built and tested in the same session (or in the parent session if resumed from a brief) with no intervening code changes
- The batch's hard stop rules (§4 — circuit breaker) are enforced exactly as they would be for manually approved runs (same failure handling, same persistence, same report)

This does **not** apply to individual Amazon listing actions or to any transaction — those remain fully gated per §3.

### 3.6 Standing Approval Registry
Standing approvals are recorded in `shared/master-brain/standing-approvals.json`.
A standing approval is an operator-defined, revocable authorization that permits a bounded class of autonomous actions. Each entry includes:
- `id`: unique identifier (e.g., `low_risk_public_read_2026_09_13`)
- `scope`: what is permitted (e.g., "free-tier read-only probes", "non-secret .env writes")
- `budget`: max calls, max cost, max time, or max items
- `provider`: which providers/endpoints are covered
- `status`: `active`, `revoked`, or `expired`
- `revoked_at`: timestamp when revoked (if revoked)

The model must check the registry at session start and respect all active limits. Any attempt to exceed a standing approval triggers the Circuit Breaker (§4) and requires a fresh named approval.

### 3.7 "Strongly Implied" Authorization — Concrete Examples
The following are considered "strongly implied" authorization for non-secret actions (not for credentials or live transactions):
- The user says "set up the environment for X" and the environment requires a `COSTCO_CSV_PATH` change → autonomous `.env` edit (§3.1).
- The user asks to "enable the BrightData scrape" or references `BRIGHTDATA_ENABLED` → autonomous feature-flag change (§3.1).
- The user instructs "continue the build" with a previous standing approval (`standing-approvals.json`) already active → autonomous work within the approval's scope (§3.6).

The following are **not** strongly implied and always require explicit approval:
- Any edit that touches a secret-pattern key (`*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`, `*_CREDENTIAL`).
- Any live call that would spend real money or consume paid API credits beyond a named envelope (§3.2) or low-risk category (§3.4).
- Any Amazon listing, pricing, purchase, or transaction action.
- Any push to `main`, `release/*`, `hotfix/*`, or protected branch (§3.3).

## 4. Circuit Breaker (mandatory, non-negotiable, applies inside Hard Stop Zone)
Once a live/financial action IS approved and running: on ANY hard failure
(auth error, rate limit, malformed response, identity mismatch, unexpected
status code) — stop processing further items immediately, persist whatever
already succeeded, record the failure in a scrubbed manifest, and report before
taking any further action. Never retry automatically. Never skip a failed item
and continue past it silently.

## 5. Reporting Discipline (applies to all work, autonomous or gated)
- Quote the literal spec text before executing a batch/step
- Report real test counts and real command output — never projected or assumed
- Commit after each meaningful unit of work with a message describing what
  was actually done, not what was intended
- Never mark a step complete without evidence (test run, diff, commit hash)
- If a discrepancy exists between what a spec says and what's on disk, stop
  and reconcile explicitly rather than silently reinterpreting the spec

## 6. What "continue the build with the vision we have" means in practice
It means: keep writing code, fixing bugs, adding tests, improving the ASIN
scaling model, hardening the Costco client, expanding the portfolio tooling —
all with zero interruption — right up until you reach anything listed in
Section 3. At that boundary, stop, state exactly what needs approval and why,
and wait. This is not the system asking permission to work; it is the system
protecting real capital and a real Amazon seller account while it works.

---

# NORTHSTAR MASTER BRAIN v2 — Additions to AGENTS.md

> Append/merge this into the existing AGENTS.md alongside the v1 content already
> saved. This refines the Autonomous Zone / Hard Stop Zone split based on operator
> clarification: build everything end-to-end without interruption; gate only the
> actual execution of money-moving or paid-API actions, not the coding of them.

## 2A. Autonomous Zone — EXPANDED: build the entire product, not just fixes
The Autonomous Zone covers full end-to-end construction of the service —
frontend/UI, backend, data pipelines, integrations, everything short of Section 3
below. Concretely, without stopping to ask:
- Build out the complete website/UI, all screens, tabs, buttons, and views
- Build out all backend logic, including the FULL CODE PATH for features that
  will eventually make live calls or process payments
- Wire up integrations end-to-end in code (request building, response parsing,
  error handling, retries logic, persistence) even for paid/live endpoints
- Fix bugs, broken states, incomplete features, and half-built screens
  encountered along the way
- Get the entire system to a state where it LOOKS and BEHAVES complete, with
  every feature implemented in code, before any live/paid path is ever executed

**Key distinction: coding a live/paid feature is Autonomous Zone. Executing/
triggering that live/paid action for real is Hard Stop Zone (Section 3).**
Build the Costco live-call function completely, write its tests with mocked
responses, wire it into the UI — all without asking. Do not actually invoke it
against the real Unwrangle API without approval. Same pattern applies to any
future Amazon action, payment processor, or paid third-party API.

## 2B. Batch Blocker Collection Protocol
When autonomous build work requires something you don't have (a missing API key,
a missing config value, a design decision only the operator can make, an
ambiguous requirement) — do NOT stop and ask immediately. Instead:
1. Make a reasonable, clearly-labeled placeholder or stub so the build can keep
   moving (e.g., a feature flag defaulting to off, a mock response, a TODO with
   a clear comment).
2. Log the exact blocker (what's needed, why, which file/feature it blocks) to a
   running list.
3. Continue building everything else that doesn't depend on that blocker.
4. Only surface the consolidated blocker list at a natural stopping point —
   when you've built as far as you can without live credentials/decisions, or
   when explicitly asked "what's blocking you" — as ONE batched report, not as
   scattered individual interruptions.
This applies to non-secret blockers only. Actual credential VALUES are still
never requested in chat, read, or written by you (Section 3 rule on `.env`
still applies in full) — for those, the blocker list should say "needs
operator to set X in .env," not ask for the value itself.

## 3. Hard Stop Zone — clarified: gates EXECUTION, not construction
Restating with the construction/execution distinction made explicit. These
require fresh, explicit, named approval before the ACTION runs — the CODE for
these can and should be fully built in the Autonomous Zone:
- EXECUTING any live outbound call to a paid/rate-limited external API
- Reading, printing, writing, or editing `.env` or any credential/secret value
  (values only — non-secret config flags may be set autonomously if genuinely
  not sensitive, per existing convention)
- EXECUTING any git push, force-push, branch deletion, or remote operation,
  except autonomous pushes to designated non-protected branches (§3.3)
- EXECUTING any Amazon listing action, pricing change, purchase, or transaction
- Any action that would actually spend real money or consume paid API credits
- Deleting or overwriting protected files or benchmark fixtures
- EXECUTING a batch file's "LIVE AUTHORIZED" step — building/testing the code
  for it is fine; running it for real needs fresh approval every time
  unless it is explicitly marked `AUTONOMOUS_LIVE` and satisfies §3.5

### 3.3 Autonomous Git Pushes to Designated Branches
Autonomous pushes are permitted **only** to branches matching one of these patterns:
- `dev/*`
- `feature/*`
- `scratch/*`
- `worktree/*`
- `session/*` (if the branch was created by the same session)

Pushing to `main`, `release/*`, `hotfix/*`, or any other protected branch requires explicit, named approval. Force-pushes and branch deletions are always prohibited without explicit approval.

### 3.4 Low-Risk Live Call Category
The model may make live calls to the following categories without a fresh per-call approval, provided the call is:
- To a free-tier endpoint with a known maximum cost of ≤ $0.01 per call
- To a public, read‑only endpoint (e.g., product search, catalog lookup) with no monetary charge
- To a provider‑approved “sandbox” or “test” endpoint that is explicitly whitelisted in the provider’s terms of service

The model must still respect the Circuit Breaker (§4) on any failure (auth error, rate limit, malformed response, identity mismatch, unexpected status code). This category is intended for low‑risk probes, health checks, and public‑data verification, not for revenue‑impacting calls.

## Summary for the operator
By the time you're ready to "go live," the product should already look and act
finished — every tab, button, and screen working against mocked/stubbed data —
with a short, consolidated list of exactly what real-world inputs (API keys,
go-ahead decisions) are needed to flip each live feature on. Live testing then
becomes: review that list, supply what's needed, approve each live action by
name, and watch it run — not "here's another blocker, again."
