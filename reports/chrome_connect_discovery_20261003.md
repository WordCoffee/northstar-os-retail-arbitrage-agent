# Chrome Connect → Playwright Architecture: Findings Report

**Date:** 2026-10-03
**Workspace:** `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`
**Owner project:** `C:\Users\T2Hol\OneDrive\Documents\Default Project` ("Northstar Browser Control")
**Scope:** read-only discovery. No edits made. No Alibaba. No live web. No paid calls. No installs. No commits.
**Status:** awaiting owner approval before any edit (Phase 3).

Every claim below is labelled **VERIFIED** (read in code/config/logs during this session) or **UNKNOWN**.

---

## PHASE 1 — Where Chrome Connect lives, and what it actually is

### 1.1 Location — VERIFIED

It is **not** in this workspace. It is a separate Node project:

```
C:\Users\T2Hol\OneDrive\Documents\Default Project\
```

Read from `README.md` line 1: *"Northstar Browser Control — Persistent, recoverable, stateful browser automation for retail-arbitrage research across Costco Business Center, Amazon, SellerAmp SAS, Keepa, and Seller Central."*

The internal name used in code and logs is **AutothinK ChromeControl** (`lib/chromecontrol/index.js:3`, `lib/chromecontrol/policy.js:2`, `orchestrator.js` header comments). Both names refer to the same thing.

Corroborating references to it exist in this workspace's state log: `00_STATE.json` line 1240 describes *"ChromeConnect detected Default/T2 and the Playwright bridge responded…"* on durable run `oracle-20260930T003129Z`. So it has been live before. **VERIFIED** (in logs).

### 1.2 What it is — VERIFIED

It is **three different things layered on top of each other**, and conflating them is the whole problem:

| Layer | File | What it actually is |
|---|---|---|
| A. Brain / state machine | `lib/chromecontrol/orchestrator.js` (694 lines) + 20 sibling modules | A deterministic **connection / profile / sign-in state machine**. |
| B. CLI | `scripts/chromecontrol.js` (13,135 bytes) | Human/agent-invoked command line over layer A. |
| C. MCP launcher | `scripts/chromecontrol-mcp.js` (1,676 bytes) | A **14-line wrapper that starts `@playwright/mcp` and proxies stdio**. |

**Layer C is the one OpenCode actually loads.** Layers A and B are not in the MCP tool path at all.

Full module inventory of `lib/chromecontrol/` (VERIFIED by directory listing):

```
orchestrator.js     createOrchestrator, STATES, popup builders, phrase matchers
index.js            public facade (status, connect, capabilities, tabs, open_permitted_provider_tab,
                    recover_connection, pause, resume, + re-exported sub-modules)
policy.js           DOMAIN_ALLOWLIST, AMAZON_BLOCKLIST, action risk classes
connection.js       CDP / extension attachment state
signin.js           detectLoginState(page)
credit.js           provider credit approval gates
model-router.js     routeTask(), recordUsage(), modelBudgetPopup()
store.js            browser_state, timeline, pauses
notify.js           desktop/popup notifications
profile-store.js    reads config/chromecontrol.json -> resolveMcpArgs()
profile-flow.js     listChromeProcesses, launchProfilePicker
profile-detect.js   map a profile ref to a real Chrome user-data-dir
picker-window.js    enumerate/detect/activate visible Chrome windows
db.js (lib/)        SQLite persistence (14,067 bytes)
```

### 1.3 How it is started — VERIFIED

Two independent entry points:

```powershell
# B: brain / CLI
node scripts/chromecontrol.js status | check | connect | recover | tabs | open --service sellersprite
                                | pause | resume-signin "Hey, it signed in." | resume-browser | approve-credit
# C: MCP launcher (this is what opencode runs)
node scripts/chromecontrol-mcp.js
```

`scripts/chromecontrol-mcp.js` body, read in full:
- `:14-15` requires `../lib/spawner` and `../lib/chromecontrol/profile-store`
- `:17-18` `loadSelection()` → `resolveMcpArgs(selection)`
- `:29` writes one stderr line `[ChromeControl MCP] attach_mode=… profile=… endpoint=…`
- `:32` `spawnMcp(args, { stdio: 'inherit' })`
- `:33-34` exits when the child exits

**There is no planning code, no decision code, no evaluation code and no extraction code in that file.** It resolves an attach mode and launches Playwright. **VERIFIED.**

Live process tree confirming it is running right now (**VERIFIED**, `Win32_Process`):

```
PID 82480  node.exe  "...\Default Project\scripts\chromecontrol-mcp.js"
  └─ PID 56836  node.exe  "...\@playwright\mcp\cli.js --extension"
```

`--extension` with no `--cdp-endpoint` matches `config/chromecontrol.json`:

```json
{ "attach_mode": "extension",
  "extension_profile_dir_name": null,
  "cdp_endpoint": "http://127.0.0.1:9222" }
```

`null` profile = unpinned; the operator picks the profile in Chrome. **VERIFIED.**

### 1.4 What tools it exposes — VERIFIED

**Zero.** ChromeControl exposes **no MCP tools whatsoever**. The tools OpenCode registered from this MCP server are `@playwright/mcp`'s own tools (`browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`, …) — they are Playwright's, not ChromeConnect's.

The only callable surface of the brain is the CLI in layer B, plus `lib/chromecontrol/index.js`'s facade which exports exactly these operations (VERIFIED, read of the module's export block):

```
status · connect_existing_browser · get_capabilities · list_permitted_tabs
focus_permitted_tab · open_permitted_provider_tab · list_chrome_profiles
recover_connection · pause · resume
```

Notably absent from that list: anything that reads or extracts page content, or anything that plans a next step.

### 1.5 What it stores — VERIFIED / UNKNOWN

- **VERIFIED:** attachment mode + selected profile (`config/chromecontrol.json`), browser state machine + timeline + pauses (via `store.js` → `lib/db.js` SQLite), domain/action policy (`policy.js`), model routing + usage budget (`model-router.js`), credit approvals (`credit.js`).
- **VERIFIED:** the owner project's `data/` directory contains **only** `.js` and `.json` research output — no SQLite file is present there. The actual DB path is **UNKNOWN** (not traced; `lib/db.js` was not read line-by-line in this session).
- **VERIFIED absent:** there is **no** playbook store, **no** selector store, **no** run-journal-of-failures store and **no** lessons store anywhere in the project. Phase 4 is net-new work, not a repair.

### 1.6 Is it enabled in OpenCode — VERIFIED

Two configs, two different servers:

| Config | Server | Command | Enabled |
|---|---|---|---|
| `Northstar OS Retail Arbitrage Agent\opencode.jsonc:45-49` | `playwright` | `node …\Default Project\scripts\chromecontrol-mcp.js` | **`true`** |
| `%USERPROFILE%\.config\opencode\opencode.json:85-88` | `browser` | `npx -y @playwright/mcp@latest --browser chrome --user-data-dir …` | **`false`** |

So: the ChromeConnect *launcher* is enabled and running; the ChromeConnect *brain* is not registered as a tool source at all. The disabled global `browser` server is a third, redundant, fully-bypassing Playwright path.

---

## PHASE 2 — Why only Playwright runs

### 2.1 Every place Playwright is launched or imported directly — VERIFIED

Inside this workspace (`Northstar OS Retail Arbitrage Agent`):

| File:line | What it does | ChromeConnect involved? |
|---|---|---|
| `Northstar_backend/costco_playwright_scraper.py:6` | `from playwright.async_api import async_playwright` | **No** |
| `Northstar_backend/costco_playwright_scraper.py:12` | `async with async_playwright() as p:` — launches its own browser | **No** |
| `tools/browser_agent.py:200` | `from playwright.async_api import async_playwright` | **No** |
| `tools/browser_agent.py:214` | `async with async_playwright() as p:` — launches its own browser | **No** |
| `tools/browser_agent.py:355` | second direct import | **No** |
| `tools/browser_agent.py:409-431` | `playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")` | **No** — attaches raw to CDP |
| `tools/browser_agent.py:470` | third direct launch | **No** |
| `tools/test_chrome.py:7,10` | direct import + launch | **No** |
| this session's `tools.playwright.*` calls | straight to `@playwright/mcp` | **No** |

Additionally, the disabled global MCP server `browser` (`opencode.json:85-88`) is a direct `@playwright/mcp` launch that would also bypass everything.

### 2.2 Where Chrome Connect is called, or should be but is bypassed — VERIFIED

**Chrome Connect is never called from this workspace.** Every reference to it in either project is:

- `scripts/chromecontrol-mcp.js:6,15` — its own self-reference
- `scripts/chromecontrol.js:6-22` — its own CLI usage block and requires
- `test/chromecontrol-tests.js:18-25` — its own tests
- `test/orchestrator-tests.js:86-96, 164-258, …` — its own tests

There is **no** production caller. Nothing in `Northstar OS Retail Arbitrage Agent` invokes `scripts/chromecontrol.js`, `lib/chromecontrol`, or any chromecontrol module.

The bypass points, in order of importance:

1. `opencode.jsonc:48` registers `chromecontrol-mcp.js` as the MCP command. OpenCode therefore believes it is talking to Chrome Connect while it is actually talking to Playwright. **This is the core defect** — the naming makes the bypass invisible.
2. `tools/browser_agent.py:409-431` (`connect_over_cdp`) bypasses ChromeConnect's entire policy layer while reusing the same port 9222 ChromeControl manages.
3. `Northstar_backend/costco_playwright_scraper.py` launches a separate browser entirely.
4. Agent tool calls (`tools.playwright.*`) go straight through.

### 2.3 Root cause, stated plainly

> **`scripts/chromecontrol-mcp.js` — the only thing OpenCode loads from Chrome Connect — is a launcher, not a controller.** It resolves an attach mode from `config/chromecontrol.json`, spawns `@playwright/mcp`, and exits. Everything downstream of that (`tools.playwright.*`) is Playwright's own tool surface, so every browser action is issued by the model directly, with **no Chrome Connect decision in front of it**. The brain (`orchestrator.js`) and its CLI are fully implemented but **unreachable from the agent tool path** — only tests call them.

Two compounding facts make this worse than a missing wiring job:

- **`orchestrator.js` is not a page-content brain even when called.** `defaultReadSite` (`orchestrator.js:680-686`) returns `{ url: tab.url, title: tab.title, text: '' }` — **`text` is hard-coded empty**, and it reads from ChromeControl's own `store`, not from the live page. `defaultNavigate` (`:672-678`) just calls `facade.openPermittedProviderTab`. So `continueTask()` at `:481` feeds an always-empty string into `signin.detectLoginState`. The orchestrator can connect, verify a profile and check a login; it **cannot read, evaluate or extract anything**.
- **The policy guardrails live only inside ChromeControl.** `policy.js` defines a host allowlist (`sellersprite.com`, `sas.selleramp.com`, `selleramp.com`, `costco.com`, `costcobusinessdelivery.com`, `oracle.com`), a supplier allowlist (`primenationaldistribution.com`) and an `AMAZON_BLOCKLIST` covering 16 Amazon TLDs, with action risk classes `read_only | provider_credit_consuming | external_state_change | prohibited`. **Because nothing routes through ChromeControl, none of those controls are currently enforced on any browser action taken from this workspace.** Every `tools.playwright.*` call I have made — including in the prior turmeric study — bypassed them completely.

`model-router.js:62 routeTask()` exists and is returned from the facade, but **UNKNOWN**: I did not trace a call site that drives a per-step decision from page content. The only verified consumers are status reporting and `modelBudgetPopup` (`:111`).

---

## PHASE 3 — Proposed plan (NOT YET APPLIED, awaiting approval)

Design: **Chrome Connect decides, Playwright executes, nothing else may drive Playwright.**

### New files (all inside the owner project; no Northstar production code touched)

| # | Path | Purpose |
|---|---|---|
| 1 | `lib/chromecontrol/pw-tool.js` | The **only** module permitted to talk to Playwright MCP. Wraps `browser_navigate / click / type / press_key / snapshot / screenshot / extract`. Enforces headed, read-only default, throttle, and a per-action policy check via `policy.js`. |
| 2 | `lib/chromecontrol/agent-loop.js` | The controller. `run(task)` → plan → act → **evaluate** → decide → next step, terminating on goal-met / blocked / budget. Emits a structured `RunResult`. |
| 3 | `lib/chromecontrol/journal.js` | Append-only run journal: instruction, tool call, URL, timestamp, result, duration, outcome. |
| 4 | `lib/chromecontrol/lessons.js` | PROPOSED / APPROVED / REJECTED lesson store with `propose / approve / reject / rollback / purge`. **Nothing auto-approves. No code is ever modified by a lesson.** |
| 5 | `lib/chromecontrol/gate.js` | The refusal gate: unwrapped Playwright invocation is detected and rejected. |
| 6 | `scripts/chromecontrol-agent.js` | CLI: `node scripts/chromecontrol-agent.js run "<task>"`, `lessons list/approve/reject`, `journal tail`. |
| 7 | `test/agent-loop-tests.js` | Offline mock test (Phase 5). |
| 8 | `test/fixtures/mock-page.html` | Local page. No network. |

### Edited files (each backed up first to `*.bak.20261003`)

| # | Path | Change |
|---|---|---|
| 9 | `lib/chromecontrol/policy.js` | Add `agent:*` action classes + a `requireChromeConnect` assertion helper. Existing allowlists untouched. |
| 10 | `lib/chromecontrol/orchestrator.js` | `defaultReadSite` gains a real implementation via `pw-tool.js` instead of returning `text: ''`. Existing state machine untouched. |
| 11 | `scripts/chromecontrol.js` | Add `agent` command routing to `chromecontrol-agent.js`. |
| 12 | `Northstar …\opencode.jsonc` | Add a **separate, clearly-named** `chromeconnect` MCP entry. Keep `playwright` entry but set `enabled: false` so no unwrapped path exists. |
| 13 | `tools/browser_agent.py`, `Northstar_backend/costco_playwright_scraper.py`, `tools/test_chrome.py` | Replace direct `async_playwright` / `connect_over_cdp` use with a call into the controller. `test_chrome.py` becomes a refusal-gate test. |
| 14 | `AGENTS.md` (workspace capsule) | One line: Chrome Connect is the controller; Playwright is its tool only. |

### Explicitly NOT changed

- `config/chromecontrol.json` — no profile pinning, no billing, no provider change
- Northstar production services, databases, routes, credentials, live gates
- `lib/chromecontrol/policy.js` allowlists (contents preserved exactly; only additive assertions)
- No supplier outreach, no orders, no listing submissions, no git commits

### Rollback

Every edited file → `*.bak.20261003` byte-identical restore; every new file → delete. No migrations, no data writes outside `research/`-style journals.

---

## PHASE 4 — Learning kept safe (design)

Three reviewable artifacts, all plain files, all git-diffable:

- **Playbooks** — `playbooks/<site>.md`: navigation steps, selectors that worked/failed. Written by the controller, appended only.
- **Run journal** — `data/agent-journal/*.jsonl`: every instruction, tool call, URL, timestamp, result.
- **Lessons** — `data/agent-lessons.json`: each entry `PROPOSED` by default, promoted only by explicit owner command. `reject` and `rollback <id>` and `purge` are supported. A lesson can only ever supply *guidance text* to the prompt or *selector preference* — **it cannot alter `policy.js`, the approval gates, or any `.js` file.**

---

## PHASE 5 — Verify without going live (planned)

1. `mock-page.html` served from `file://` or a local port; **no external URL, no login, no CAPTCHA**.
2. Controller plans steps; `pw-tool` executes each; journal shows `decision → tool_call → result → decision`.
3. Negative test: a bare `tools.playwright.*` call and a bare `connect_over_cdp` are both refused/flagged by `gate.js`.

---

## Deliverable 4 — Updated Alibaba prompt (draft, no Alibaba access performed)

```
ALIBABA SUPPLIER RESEARCH — CONTROLLED BROWSER TASK

CONTROLLER: Chrome Connect (Northstar Browser Control). It plans every step,
decides what to extract, evaluates each page, handles blockers, and records
what it learned. Nothing else may drive the browser.

TOOL: Playwright is a TOOL Chrome Connect calls. It performs only
navigate / click / type / screenshot / extract. No script, no manual command
and no direct Playwright import may invoke it. A Playwright call without a
Chrome Connect instruction is refused and logged as a violation.

MODE: headed, read-only by default, throttled, single tab at a time.
BLOCKERS: CAPTCHA, login wall, rate limit or challenge → STOP and ask the
owner. Never bypass, never solve, never retry through a challenge.

SCOPE: Alibaba supplier pages only. No purchase, no RFQ send, no contact form
submission, no message to a supplier, no account change. Read and extract only.
EXTRACT: supplier name, MOQ, unit price, price tiers, shipping terms, lead
time, packaging options, certifications, and the page URL + capture timestamp
for each. Anything not visible on the page stays null — never inferred.

OUTPUT: one structured table plus the run journal. Every row must cite the
source URL. Facts not on the page are recorded as UNKNOWN, not estimated.

COST: zero spend. No paid credits, no top-ups, no account creation.
```

---

## What I need from you

Approve or amend the Phase 3 file list before I touch anything. Nothing in
`Default Project` or in this workspace has been modified.
