# Chrome Connect — full service scan & blueprint

**Date:** 2026-10-23
**Scope:** read-only inspection of the live `chromeconnect` MCP server, its controller
runtime, its transport bridge, and the Python-side guard in this repo.
**Method:** source read + live `chromeconnect_status` / `chromeconnect_guardrails` /
`chromeconnect_preflight` / `chromeconnect_journal` + both offline test suites.
No browser task was run. No policy was edited. No credential, cookie or secret was read.

---

## 1. What it is

**AutothinK ChromeControl** (`chromeconnect`, server v2.0.0, MCP protocol `2024-11-05`) is
the single sanctioned browser-control layer for Northstar OS. It is not a Playwright
wrapper — it is a **controller** that sits between a language model and a browser.

Doctrine, stated in every module header and enforced in code:

> **Chrome Connect decides. Playwright executes.**

The model never receives a browser handle. There is no `navigate`, `click`, `type` or
`screenshot` tool on the MCP surface — deliberately. The model states a *task*; the
controller plans the steps, issues a governing instruction, calls Playwright itself,
reads and evaluates the live page, decides whether the task actually succeeded, and
returns structured output. Everything is journalled.

It exists because the previous arrangement exposed `@playwright/mcp` directly, which
published ~45 raw `browser_*` tools to the model. Under that arrangement the domain
allowlist, the Amazon blocklist and the risk-class gates in `policy.js` were decorative —
any model call could drive the browser around them. `tool-surface.js` now refuses to
start a run at all while such a surface is visible.

### Where it lives

| Part | Path |
|---|---|
| Controller runtime (external) | `C:\Users\T2Hol\OneDrive\Documents\Default Project` |
| MCP server entry | `scripts/chromecontrol-mcp-server.js` |
| Controller brain | `lib/chromecontrol/agent-loop.js` |
| Invocation gate | `lib/chromecontrol/gate.js` |
| Policy | `lib/chromecontrol/policy.js` + `config/chromecontrol_policy_owner.json` |
| Only Playwright-capable module | `lib/chromecontrol/pw-tool.js` |
| Transport bridge | `scripts/chromecontrol-playwright-bridge.js` |
| Persistent MCP client | `lib/chromecontrol/mcp-session.js` |
| Python-side guard (this repo) | `tools/chromeconnect_guard.py` |
| Repo registration | `opencode.json` → `mcp.chromeconnect` |

`opencode.json` in this repo points the MCP server at the external root and injects
`CHROMECONNECT_TRANSPORT_MODULE` = the approved bridge. The controller repo is on branch
`main` at `fcc0942`, with 4 uncommitted files.

---

## 2. The tool surface — 6 tools, zero browser tools

### `chromeconnect_preflight`
`{ require_isolated?: boolean }` — read-only. Reports attach mode, whether a profile is
pinned, selection source, session profile, transport module, and the full isolation report.
Returns `isolated_signed_out_satisfied`. If isolation cannot be proven it returns an
explicit instruction to stop and ask the operator. **Never assumes.**

### `chromeconnect_run`
`{ task: string, url?: string, max_steps?: 1-20 (default 4), require_isolated?: boolean }`
— runs **one** task through the controller. Returns
`{ run_id, status, steps, stop_reason, data, blockers, refusals, proposed_lessons, trace, stats, attach, journal }`.

### `chromeconnect_status`
`{}` — controller, policy, gate and guardrail status. Read-only. Never launches a browser.

### `chromeconnect_journal`
`{ n?: 1-500 (default 40), run?: string }` — reads the append-only run journal.

### `chromeconnect_lessons`
`{ action: list|propose|approve|reject|rollback|purge, ... }` — reviewable learning store.
Lessons start **PROPOSED** and are never used until an operator approves them.

### `chromeconnect_guardrails`
`{}` — reports the operator-owned policy fingerprint and whether it matches the
operator-recorded baseline.

### What is deliberately absent

`navigate` · `click` · `type` · `press` · `snapshot` · `screenshot` · `evaluate` ·
`tabs` · `upload` · `download` · `fill_form` · `console` · `dialog` · `frames`.
`toolSurface.assertNoRawBrowserSurface()` runs **first**, before profile selection,
connection or navigation, and refuses the run if the host exposes any of them.

---

## 3. How a run actually works — the call chain

```
chromeconnect_run(task, url, max_steps, require_isolated)
  │
  ├─ 1. toolSurface.assertNoRawBrowserSurface()      fail-closed, nothing touched yet
  ├─ 2. getTransport()                                bridge module must load
  ├─ 3. resolve effective profile                     config pin → else session pick → else picker
  ├─ 4. bindProfile(dir) + session pin                no profile ⇒ no guess, no fallback
  ├─ 5. plan.buildPlan(task, url)                     deterministic; parses an explicit STEPS: block
  │
  └─ agentLoop.run(task, { transport, planner, evaluator, success, ... })
       │
       ├─ journal: run_started
       └─ for each step (≤ max_steps):
            ├─ planner(ctx)                            → { action, args, goal } or { done }
            │    └─ done ⇒ success predicate must pass, else status = FAILED
            │
            ├─ [public discovery] assessRenderedState(lastPage) before navigate
            │    └─ authenticated indicator ⇒ BLOCKED, no interaction
            │
            ├─ gate.issueInstruction({ caller: 'chromecontrol/agent-loop' })
            │    └─ caller must be exactly that string, else GateRefusal
            │
            ├─ journal: decision (phase = decide)
            │
            ├─ pwTool[action](...)                     ── the ONLY path to Playwright
            │    ├─ gate.requireInstruction(action)        no instruction ⇒ GateRefusal
            │    ├─ policy.classifyAction(action)          prohibited ⇒ PolicyRefusal
            │    ├─ policy.evaluateUrl(url)                Amazon first, then allowlist
            │    ├─ policy.evaluateActionForHost(action)   Alibaba/per-host grants
            │    ├─ assertMode()                           headed + readOnly asserted
            │    ├─ assertNamedProfile() / assertIsolatedProfile()
            │    ├─ throttle (default 400 ms between calls)
            │    ├─ journal: tool_call
            │    ├─ transport(name, args)  ──────────────┐
            │    └─ journal: tool_result                 │
            │                                            ▼
            │                              PersistentMcpSession (one child per profile)
            │                                            │
            │                              @playwright/mcp --extension --profile-dir-name X
            │                                            │
            │                              Playwright MCP Bridge extension → Chrome
            │
            ├─ pw.readLivePage()                       still inside the same instruction
            ├─ gate.clearInstruction(id)
            │
            ├─ page.status !== 'READ' ⇒ FAILED (page_unreadable) — never goal-met
            ├─ detectBlocker(title + text) ⇒ BLOCKED (captcha / login_wall /
            │     rate_limited / consent_wall / access_denied) — never solved, never retried
            ├─ evaluator(ctx)                          → { met, reason, data }
            ├─ journal: decision (phase = evaluate)
            └─ verdict.met ⇒ COMPLETE
       │
       └─ journal: run_finished + attach stats + journal file name
```

Statuses: `COMPLETE` · `FAILED` · `BLOCKED` · `REFUSED` · `ERROR` · `INCOMPLETE`.

**Success is not "the plan ended."** `done` alone yields `FAILED` with
`success_unmet:no_success_predicate`. A read-only plan passes only when the last page was
actually `READ`. A typing plan passes only when the typed text is found in the rendered
transcript DOM (`typed_text_verified_in_transcript`). This guard was added because runs
previously reported COMPLETE after a single navigate.

---

## 4. The tools it uses, and exactly how

### 4.1 Playwright MCP — the only browser tool

The bridge never imports Playwright. It speaks MCP over stdio to
`@playwright/mcp`, attached by **extension** to the owner's already-running Chrome
profile. It resolves tool names dynamically from the server's advertised tool list:

| Controller action | Playwright MCP tool | Notes |
|---|---|---|
| `navigate` | `browser_navigate` | falls back to `browser_tabs {action:'new'}` if the bound handle is dead |
| `click` | `browser_click` | sends `target` (unique CSS selector), not the old `{element, ref}` payload |
| `type` | `browser_type` | selector + literal text; refuses credential-shaped selectors before this point |
| `press_key` | `browser_press_key` | e.g. `Enter` |
| `snapshot` | `browser_snapshot` | judged as `page_snapshot`, deliberately **not** `read_page` |
| `screenshot` | `browser_screenshot` | `fullPage` by default, optional filename |
| `console` | `browser_console_messages` | read-only evidence |
| `readLivePage` / `extract` / `diagnose` | `browser_evaluate` | runs a **controller-owned** script only |
| `close` | `browser_close` | |

Two fixed scripts are injected by the controller: `READ_PAGE_FN` (returns
`{url, title, text, links}`) and `DIAGNOSE_CANVAS_FN` (canvas/WebGL state).
**The model never supplies page JavaScript.**

### 4.2 Persistent MCP session (`mcp-session.js`)

One long-lived, initialized MCP child **per Chrome profile**, reused by every action.
This replaced a per-operation spawn that raced the extension's single relay socket and
produced the "3 calls fine, then everything times out" pattern.

- States: `IDLE → CONNECTING → CONNECTED → RECONNECTING → CONNECTED` (or `DISCONNECTED` / `FAILED`).
- Recovery is bounded: one `tools/call` timeout stops the action; **exactly one** reconnect
  (terminate → await exit → respawn → initialize → one harmless page read); the action
  resumes only if that read succeeds. One recovery per run, then `FAILED`. No loops.
- **Profile lock:** `mcp_profile_<key>.lock` in the temp dir. A second session on the same
  profile is refused with `PROFILE_LOCKED`.
- Timeout 240 s.

### 4.3 Dead-page and error-text guards

A dead handle comes back as tool *content* (`### Error … Target page, context or browser
has been closed`), not as a JSON-RPC rejection, so `try/catch` never sees it. Detection
therefore lives in the one call path every action shares. A closed page is rebuilt once;
any other tool error fails fast with the real cause. `readLivePage` also refuses to treat
`### Error…` text as page data — that class of bug had produced COMPLETE runs against
error strings and `about:blank`.

### 4.4 Self-staleness kill

The bridge and MCP server `stat` their own mtimes every 15 s and `exit(0)` if either
changed, so the host respawns current code. A parent-PID watchdog in the MCP server does
the same if OpenCode dies — a surviving server would otherwise keep the old policy in
memory (this happened twice).

### 4.5 Profile selection and picker

- Never creates a user-data directory. Never launches Chrome. Never falls back.
- Effective profile = explicit `config/chromecontrol.json` pin, else the **this-session**
  picker choice in `session-profile.js` (`%TEMP%/chromeconnect-session/profile.json`, 12 h
  TTL), else the native "Who's using Chrome?" picker is surfaced and the run waits.
- Picker detection uses only window title, window class and PID (`picker-window.js`).
  It never reads tabs, content, cookies, history or credentials. Ambiguity fails closed.
- Switching profile invalidates the previous profile and its page handles.

### 4.6 Orchestrator (owner-facing flow)

`orchestrator.js` drives the 15-step flow: healthy connection check → picker → owner picks
→ window detection → extension connect → verify profile → open target → check auth →
resume checkpoint, or pause for manual sign-in. States: `idle`, `launching_profile_picker`,
`awaiting_picker_visibility_confirmation`, `awaiting_profile_selection`,
`profile_window_detected`, `awaiting_extension_connection`, `verifying_profile`,
`profile_verified`, `navigating_to_target`, `checking_site_authentication`,
`awaiting_manual_signin`, `resuming_workflow`, `connected`, `disconnected`, `failed`.

Resume phrases are exact, case-insensitive: `Profile selected.` / `Picker visible.` /
`Hey, it signed in.` / `Browser recovered.` Credit approval must match
`Approve <provider> <action> for <count> candidate(s).` and cannot be granted by a
sign-in phrase.

### 4.7 Python guard (this repo)

`tools/chromeconnect_guard.py` is the Python half of the same rule:

1. A `sys.meta_path` finder refuses `playwright`, `playwright.async_api`,
   `playwright.sync_api`, `playwright._impl` unless a controller instruction is active.
2. Exclusive, pid-tracked lock on CDP port 9222 (`.chromeconnect/cdp_9222.lock`); a second
   holder is refused.
3. `cc_call(task, ...)` shells out to `scripts/chromecontrol-agent.js run --json
   --require-isolated` and returns structured output. **No flag or env escape hatch.**

---

## 5. Policy model

### 5.1 Domain policy

Evaluated on **every** action, using the **current** page URL, so a redirect cannot smuggle
an action onto a refused host.

1. **Amazon blocklist first, unconditionally.** 26 hosts (`amazon.*`, `sellercentral.*`,
   `amazonpay`, `amzn.to`, …) plus a regex catch on any `*.amazon.*`. Hardcoded in
   `policy.js` — deliberately **not** operator-editable.
2. Operator allowlist (11 hosts): `sellersprite.com`, `sas.selleramp.com`, `selleramp.com`,
   `costco.com`, `costcobusinessdelivery.com`, `oracle.com`, `account.squarespace.com`,
   `login.squarespace.com`, `dash.cloudflare.com`, `127.0.0.1`, `localhost`.
3. Approved suppliers: `primenationaldistribution.com`.
4. Alibaba: `alibaba.com` only — read-only, 4 actions.
5. Test fixtures: additive-only `allowHosts`, checked *after* Amazon. Cannot widen anything.

Exact-or-subdomain matching only. No substring matching.

### 5.2 Alibaba restricted profile

Permitted: `navigate_allowed_host`, `read_page`, `screenshot`, `extract`.
Everything else denied by default, with named denial classes (sign-in, credential entry,
captcha workaround, supplier chat, RFQ, follow/save, sample request, cart/checkout, form
submission, upload/download, account change, payment).

### 5.3 Action risk classes

| Class | Behaviour |
|---|---|
| `read_only` | permitted |
| `provider_credit_consuming` | requires exact provider-credit approval |
| `external_state_change` | gated; never runs without an explicit gate |
| `prohibited` | refused before Playwright is reached |

23 prohibited actions: credentials, enter_credentials, password_manager, login_submit,
mfa, submit_mfa, captcha, solve_captcha, account_recovery, cookie_extraction,
session_extraction, purchase, add_to_cart, checkout, create_listing, send_message, upload,
account_settings, billing_settings, subscription_change, accept_agreement,
amazon_direct_access, navigate_amazon.

### 5.4 Per-host grants + 24 h authorizations

`account.squarespace.com`, `login.squarespace.com`, `dash.cloudflare.com` carry
`allow: [form_submission]` and `deny: [sign_in, credential_entry, payment_action]`.

A grant is **inert** unless a live, unexpired, host- and action-matching record exists in
`config/chromecontrol_operator_authorizations.json` (operator-written, gitignored, TTL
hard-capped at 24 h). `sign_in`, `credential_entry` and `payment_action` are in no shipped
grant's allow list.

### 5.5 Guardrail fingerprint

`policy.fingerprint()` = SHA-256 over the sorted guardrail tables. Compared against
`baseline_fingerprint` in the owner config. Any edit that does not recompute and record the
baseline is detected. `lessons.propose()` re-checks it on **every** write and refuses if the
tables drifted.

**Live:** `intact: true`, fingerprint `5ae23cde016a53b29e4f6c9b59da06bf8249fcb72b142dd559386b412a570f37`,
baseline identical, owner config loaded from disk.

---

## 6. Isolation model — "prove it or stop"

`profile-isolation.js` is built so it cannot lie:

- `isolated` is never stored, defaulted or cached. It is recomputed from `checks` on every
  call and is true only when **every** check passed **and** every check was available.
- Absence of evidence is never evidence of absence. A locked store is `UNAVAILABLE`, not
  "clean".
- Signed-out is not isolation.
- Profile directory and display name compare with `===`. No fuzzy, prefix or closest match.
- `no_profile_fallback` is itself a required check.
- Corroboration (`last_used`, activation freshness, single instance) never satisfies a check.

**10 checks — 7 REQUIRED, 3 SUPPORTING_ONLY:**

| Check | Class |
|---|---|
| `local_state_readable` | REQUIRED |
| `selected_directory_exact` | REQUIRED |
| `display_name_exact` | REQUIRED |
| `chrome_signed_out` | REQUIRED |
| `no_sensitive_session_cookies` | REQUIRED (gated behind `CHROMECONNECT_COOKIE_METADATA_AUTHORIZED=1`) |
| `transport_profile_binding` | REQUIRED |
| `no_profile_fallback` | REQUIRED |
| `browser_process_identity` | SUPPORTING_ONLY |
| `extension_relay_present` | SUPPORTING_ONLY |
| `extension_attachment_profile` | SUPPORTING_ONLY |

Cookie-store metadata (host_key + name only, values never read) is **off by default** —
"names only" was previously assumed sufficient permission and is not.

**Live verdict:** `isolated: false`, `signed_out: false`.
- `chrome_signed_out` **FAILED** — profile 6 "Work" has Chrome identity `northstarosllc@gmail.com`.
- `no_sensitive_session_cookies` **UNAVAILABLE** — `cookie_metadata_inspection_not_authorized`.
- Everything else passes, including `transport_profile_binding` (MCP child pid 24920 alive,
  `--extension --profile-dir-name Profile 6`, extension answered, session `CONNECTED`).
- `isolated_signed_out_satisfied: false` → `chromeconnect_run({require_isolated:true})`
  would refuse. `chromeconnect_preflight` correctly instructs: stop and ask the operator.

---

## 7. Journal — the evidence trail

`journal.js` writes one append-only JSONL file per run to `data/agent-journal/`
(249 files on disk). Record types:

`run_started` · `decision` (phase `plan` | `decide` | `act` | `evaluate`) · `tool_call` ·
`tool_result` · `refusal` · `note` · `run_finished`, plus `rendered_state_audit`,
`public_discovery_url`, `isolated_profile_verified`, `named_profile_confirmed`,
`lesson_proposed`, `operator_authorized_lesson`.

Every record carries `seq`, `ts`, `run_id`, instruction id, URL, action, risk class,
outcome, reason and duration. Secrets are redacted **on write**: exact key names
(`password`, `token`, `cookie`, `api_key`, `cvv`, `mfa_code`, …) and value patterns
(Bearer, AKIA, JWT). The journal is plain text so any lesson drawn from it is reviewable
in a diff.

---

## 8. Lessons — PROPOSED only

`propose → PROPOSED` (never used) · `approve → APPROVED` · `reject → REJECTED` ·
`rollback → PROPOSED` with a reason · `purge → deleted`.

Lessons are **data, never code**. Nothing can write a `.js` file, edit `policy.js` or touch
an allowlist. Enforced in `propose()`:

- Allowed fields only: `site`, `kind` (`hint|selector|note`), `text`, `selector`, `url`,
  `reason`, `run_id`, `step_note`.
- Domain-shaped fields (`domain`, `host`, `origin`, `allowlist`, …) are refused outright.
- A `site` must already exist in `policy.js` — a lesson may never introduce a new host.
- ~22 forbidden phrases screen free text: "add to the allowlist", "bypass", "disable the
  gate", "solve captcha", "log in automatically", any URL, any bare domain, any supplier
  marketplace name.
- A guardrail-touching lesson is refused **unless** the operator supplied
  `operator_authorized:true` **and** a live `authorization_ref` matching task/host — and
  even then it stays PROPOSED until an operator approves it.
- Every write re-checks the guardrail fingerprint.

7 lessons on disk.

---

## 9. Blueprint — layers

```
┌──────────────────────────────────────────────────────────────────────┐
│ L0  HOST            OpenCode / MCP client                            │
│                     sees 6 chromeconnect_* tools. No browser tools.  │
├──────────────────────────────────────────────────────────────────────┤
│ L1  SURFACE         chromecontrol-mcp-server.js                      │
│                     stdio JSON-RPC: initialize / tools/list /        │
│                     tools/call / ping. 6 tools. Parent watchdog.     │
├──────────────────────────────────────────────────────────────────────┤
│ L2  PRE-FLIGHT      tool-surface.js   no raw browser surface         │
│                     profile-store.js  pin → session → picker         │
│                     profile-isolation.js  10 fail-closed checks      │
├──────────────────────────────────────────────────────────────────────┤
│ L3  CONTROLLER      agent-loop.js     plan → decide → act → evaluate │
│                     plan.js           STEPS: grammar + success pred.  │
│                     rendered-state.js public-discovery stop condition │
├──────────────────────────────────────────────────────────────────────┤
│ L4  GATE            gate.js           one instruction in scope        │
│                     caller must be 'chromecontrol/agent-loop'         │
│                     static audit of unwrapped Playwright use          │
├──────────────────────────────────────────────────────────────────────┤
│ L5  POLICY          policy.js         Amazon → allowlist → per-host   │
│                     authorization.js  24h operator grants             │
│                     sourcing-policy.js  public_sourcing_readonly_v1   │
│                     outreach-policy.js  alibaba_sourcing_outreach_v1  │
├──────────────────────────────────────────────────────────────────────┤
│ L6  ENFORCEMENT     pw-tool.js        the single choke point          │
│                     7 checks on EVERY call, not once per run          │
│                     throttle, journal tool_call/tool_result           │
├──────────────────────────────────────────────────────────────────────┤
│ L7  TRANSPORT       chromecontrol-playwright-bridge.js                │
│                     mcp-session.js    one persistent MCP child        │
│                     profile lock, 1 bounded reconnect, dead-page fix  │
├──────────────────────────────────────────────────────────────────────┤
│ L8  BROWSER         @playwright/mcp --extension --profile-dir-name X  │
│                     → Playwright MCP Bridge extension → Chrome        │
│                     (no CDP port required; Default never relaunched)  │
├──────────────────────────────────────────────────────────────────────┤
│ L9  EVIDENCE        journal.js        append-only JSONL, redacted     │
│                     store.js          SQLite: cc_timeline, cc_tabs,   │
│                                       cc_pause_state, cc_credit_       │
│                                       approvals, cc_model_usage       │
│                     lessons.js        PROPOSED-only learning          │
│                     notify.js         toast → MessageBox → console    │
└──────────────────────────────────────────────────────────────────────┘
```

### Parallel Python boundary (this repo)

```
tools/chromeconnect_guard.py
  ├─ meta_path finder  → refuses import playwright* without an instruction
  ├─ cdp_9222.lock     → exactly one CDP driver at a time
  └─ cc_call(task)     → node scripts/chromecontrol-agent.js run --json --require-isolated
```

### Supporting modules

| Module | Role |
|---|---|
| `connection.js` | attachment mode, CDP reachability, permitted tabs, profile enumeration |
| `profile-flow.js` | picker-first state machine; marker-tab verification |
| `profile-detect.js` | non-invasive profile detection from process/window metadata |
| `picker-window.js` | visible-window enumeration (title/class/PID only) |
| `signin.js` | deterministic sign-in detection, pause states, exact resume phrases |
| `credit.js` | exact provider-credit approval gate |
| `model-router.js` | deterministic text/vision routing + budgets ($0.02/action, $5.00/run) |
| `orchestrator.js` | the 15-step owner-facing flow |
| `store.js` | durable SQLite timeline / tabs / pause / credit / model usage |
| `notify.js` | toast → PowerShell MessageBox → console + status file |
| `tool-surface.js` | refuses runs while a raw browser surface is visible |

---

## 10. What it can do today

**Read and research**
- Navigate an allowlisted host and read the live rendered page (url, title, text, links).
- Structured extraction into a caller-supplied schema; anything the page did not return is
  `null` — never `''`, never `[]`, never a guess.
- Full-page screenshots, DOM snapshots, console messages, canvas/WebGL diagnostics.
- Multi-step tasks via an explicit `STEPS:` block: `click`, `type … | text`, `press Enter`,
  `read`, `console`, `diagnose`, `screenshot <path>`.
- Public, no-sign-in supplier discovery under `public_sourcing_readonly_v1` with a
  pre- and post-navigation authenticated-state stop condition.
- Operator-authorized Alibaba sourcing + supplier outreach under
  `alibaba_sourcing_outreach_v1` (navigate/read/screenshot/extract, plus click/type/submit
  on `alibaba.com` only; purchase/checkout/payment/cart/contract/credentials denied).

**Operate**
- Profile picker flow, extension attach, profile verification, tab registry that never
  closes human-owned tabs, sign-in pause/resume, provider-credit gate, model budgets,
  bounded recovery ladder, durable checkpoints, popup notifications.
- Prove or refuse isolation, prove or refuse guardrail integrity, replay the journal,
  curate lessons.

## 11. What it will never do

- Enter credentials, OTP, MFA or card data (credential-shaped selectors refused in code).
- Solve, click through or retry past a CAPTCHA.
- Submit a login form, recover an account, extract cookies or sessions.
- Navigate to Amazon or any Amazon-related host.
- Purchase, add to cart, check out, create a listing, send a message, upload a file,
  change account/billing settings, change a subscription, or accept an agreement.
- Submit a form on a per-host grant host without a live ≤24 h operator authorization.
- Fall back to a different profile, a fresh profile, or a temporary browser.
- Be driven by the model directly. There is no handle to hold.

---

## 12. Verified state and test evidence

**Live, this session**

| Signal | Value |
|---|---|
| `controller` | `chromeconnect (agent-loop)` |
| `model_owns_browser` | `false` |
| `guardrails.intact` | `true` |
| fingerprint vs baseline | identical (`5ae23cde…570f37`) |
| `owner_config_loaded` | `true` |
| `transport_configured` | `true` |
| `attach_mode` | `extension` |
| pinned profile | `Profile 6` / `Work` (`selection_source: config_pin`) |
| MCP child | pid 24920, alive, `--extension --profile-dir-name Profile 6`, `CONNECTED` |
| `isolated_signed_out_satisfied` | **`false`** |
| blocking checks | `chrome_signed_out` FAILED, `no_sensitive_session_cookies` UNAVAILABLE |
| journal files | 249 |
| lessons | 7 |
| repo | `main` @ `fcc0942`, 4 uncommitted files |

**Offline suites**

| Suite | Result |
|---|---|
| `node test/chromecontrol-tests.js` | **72 passed, 0 failed** |
| `node test/run-tests.js` | **21 passed, 0 failed** |

The `run-tests.js` exit code 1 is PowerShell surfacing an expected watchdog `stderr` line
("CDP unreachable and browser auto-recovery not possible/disabled") — the assertion itself
passes.

---

## 13. Honest gaps and caveats

1. **Isolation is currently unproven.** The pinned profile is signed into a Google account
   and cookie metadata inspection is not authorized. Any task passed with
   `require_isolated: true` will refuse — by design. Clear it by pinning a genuinely
   signed-out profile, or authorize cookie metadata inspection for the check only.
2. **`tool-surface.json` is self-asserted.** `tool-surface.js` cannot introspect the host
   catalog, so "guard passed" means "the declaration says clean", not "the catalog was
   probed". The declaration is also **project-scoped** — a session opened in another
   directory without `tools: { "browser": false }` recompiles the 45-tool group while this
   file still says `false`. That is a real residual bypass window, documented in the file.
3. **The MCP planner is deterministic, not an LLM.** `plan.js` parses a `STEPS:` block and
   never invents an action. The architectural claim "the controller decides" is true, but
   in the MCP path the "decision" is a bounded, explicit plan — not model reasoning about
   the page. Richer plans must be stated by the caller.
4. **`gate_in_loop: false` in status output** is expected while idle: no instruction is in
   scope. It flips true only during an action.
5. **`README.md` in the controller repo is stale.** It still documents the retired raw
   Playwright MCP path and `npm run mcp:start` / `control:start`, which now refuse and exit
   78. The authoritative docs are `docs/autothink-chromecontrol.md` and
   `docs/browser-control-architecture.md`.
6. **Two policy profiles coexist.** The commerce policy (`policy.js`) and the sourcing
   profile (`public_sourcing_readonly_v1`) are deliberately separate; the sourcing profile
   cannot widen commerce, Amazon, Alibaba, credit or risk-class gates. Confusing which one
   is active is the most likely operator error — `chromeconnect_status` reports
   `policy_profile` and `policy_mode` for this reason.
