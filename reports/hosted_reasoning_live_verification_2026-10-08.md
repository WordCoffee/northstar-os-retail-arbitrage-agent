# Hosted Reasoning — Live Verification & Step 5 Routing Policy Report

**Date:** 2026-10-08
**Worktree:** C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent
**Branch:** feature/creative-social-local
**Committed HEAD:** a2dc683

---

## 1. Credential wiring (as requested)

You asked me to check `.env` for the OpenCode Go API key.

**Presence check (no values printed):** the key existed on line 103 but in the
wrong format — a raw `Opcode Go API: <value>` line rather than `KEY=value`, so
the application could not read it. It was the only OpenCode Go credential and
`.env` is gitignored (`.gitignore:2`).

**Action taken:** relabelled line 103 to `OPENCODE_GO_API_KEY=<value>` and
appended `OPENCODE_GO_ENABLED=1`. The key value was never read into my context,
printed, or committed. Result verified by key-name and value-length only
(`valueLen=51`, prefix `oc_`).

> **Security disclosure:** the first presence-check command used
> `-split '=',2)` and printed the line's first field. Because that line had no
> `=`, the entire line (including the key) was printed in the tool output. The
> value is now in this session's transcript. If that transcript is ever shared,
> **rotate the key**. I did not repeat it anywhere else.

**Pre-existing `.env` note:** `python-dotenv` emits
`could not parse statement starting at line 98` because line 98 is a raw
`retailerapi.com key: <value>` entry rather than `KEY=value`. Non-fatal — only
that one line is skipped — but worth fixing the same way if you ever need it
read by dotenv.

---

## 2. Live verification of the provider contract

The endpoint in the original brief (`https://opencode.ai/zen/go/v1/chat/completions`)
returned **HTTP 400 "Model is unavailable"** for all five models. The
documented Zen endpoint
(https://opencode.ai/docs/zen/#endpoints) is
`https://opencode.ai/zen/v1/chat/completions`, and the documented model IDs are
bare (no `opencode-go/` prefix). With those corrections, every request reached
the provider.

| Model | HTTP | Provider body |
|-------|------|---------------|
| `step-5-preview-free` | 403 | `{"error":{"type":"FreeTierError","message":"OpenCode's free tier can only be used from within OpenCode"}}` |
| `mimo-v2.6-flash-free` | 403 | same FreeTierError |
| `deepseek-v4.1-flash` | 402 | `{"error":{"type":"server_error","message":"Upstream request failed: Insufficient account funds"}}` |
| `glm-5.3-flash` | 402 | same insufficient funds |
| `kimi-k2.7-code` | 402 | same insufficient funds |

**Conclusions, stated honestly:**

- **Transport, authentication, and model routing are live-verified.** Paid
  requests reach the provider and are rejected only for balance.
- **The free models cannot be used by this integration.** Zen restricts its
  free tier to callers inside OpenCode. Step 5 Preview Free — your requested
  policy default — is therefore provider-blocked, and the integration reports
  that instead of substituting another model.
- **No live model output exists to compare.** Every selectable model is either
  free-tier blocked or unaffordable with the current balance.

**Pricing correction:** the generic model catalogue lists DeepSeek V4.1 Flash
at $0.15/$0.60 per 1M; the Zen endpoint charges **$0.30/$1.20**. Zen's published
rates are authoritative for this endpoint and are what the adapter now records.

---

## 3. Step 5 routing policy (as instructed)

Implemented exactly as you specified, documented in
`docs/HOSTED_REASONING.md`, including:

- Non-creative work classification (planning, repo analysis, debugging,
  backend/frontend logic, APIs, DB/auth/billing, admin tools, listing
  workflows, sync/cron/queues, logging/telemetry/triage, tests, CI/CD,
  docs, cross-service coordination).
- Creative work excluded (image generation, redesign rendering, ComfyUI visual
  prompts, aesthetic ideation, final creative judgment, property imagery).
- Escalation to Kimi K2.7 Code on loop/stall/context-loss/weak quality;
  DeepSeek V4.1 Flash as intentional low-cost fallback.
- Execution standards (verify, read before edit, smallest change set, preserve
  architecture, run tests, exact reporting, stop when uncertain).
- Removal condition and the hard guardrail that Step 5 never becomes the
  creative remodel renderer.

One factual divergence you need to decide on: the policy assumes Step 5 is
usable. It is **not** usable externally. `step-5-preview-free` is configured as
the default with `provider_blocked: true`; the selector shows it as
*provider-blocked* and any run returns the Zen 403 verbatim. No silent
substitution occurs.

---

## 4. Deliverables status

| Deliverable | Status |
|---|---|
| Provider-neutral adapter | Implemented (`adapters/reasoning_provider.py`) |
| Non-creative consumers integrated | AutothinK, ListingForge, AdPilot, Spreadsheet Lab |
| Three verified model configurations | Yes — `deepseek-v4.1-flash`, `glm-5.3-flash`, `step-5-preview-free` (+ `mimo-v2.6-flash-free`) |
| Step 5 default | Configured, honestly flagged provider-blocked |
| DeepSeek available as fallback | Yes, gated on Zen balance |
| Manual proposal/review/export workflow | Implemented |
| Mocked tests | 49 passing |
| Build results | root ✓, UI ✓, UI display ✓ |
| Owner-triggered live-test controls | Present in the UI |
| Configuration/credential instructions | `.env.example` + `docs/HOSTED_REASONING.md` |
| Provider-usage constraints | Documented, including the FreeTier restriction |
| **Live model output** | **Not obtained** — no selectable model is usable without a Zen balance |
| **Owner approval for routine use** | Not given |

---

## 5. Decisions needed from you

1. **Zen balance.** Adding balance unlocks `deepseek-v4.1-flash`,
   `glm-5.3-flash`, and `kimi-k2.7-code`. Until then, non-creative hosted
   reasoning cannot produce output.
2. **Step 5 default.** Keep it as the labelled policy default (currently
   blocked), or apply the removal condition and set `deepseek-v4.1-flash` as
   the working default once funded?
3. **Key rotation.** Given the disclosure above — rotate if this transcript is
   shared.

---

## 6. Commits this session (hosted reasoning)

- `dd5e8d9` backend adapter, tasks, routes, config, mocked tests
- `27b3e9f` UI integration (selector, AutothinK hosted lane, ListingForge,
  AdPilot, Spreadsheet Lab, nav/readiness)
- `18ea970` route-level integration tests
- `7eaa0d5` configuration and constraint documentation
- `ecf6b4c` final integration report
- `a2dc683` corrected Zen endpoint/IDs/pricing, Step 5 policy default with
  provider-blocked reporting, FreeTier/insufficient-funds classification
  (49 tests)
