# Chrome Connect → Playwright Architecture: Build, Tests, Rollback

**Date:** 2026-10-03
**Owner project:** `C:\Users\T2Hol\OneDrive\Documents\Default Project` ("Northstar Browser Control" / AutothinK ChromeControl)
**Workspace:** `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`
**Alibaba:** NOT OPENED. Preflight reports isolation is unprovable, so the run stops (see §6).

---

## 1. What was wrong, and what changed

**Root cause.** `scripts/chromecontrol-mcp.js` — the only thing OpenCode loaded from Chrome Connect — is a
**launcher**, not a controller. It resolved an attach mode and spawned `@playwright/mcp`, so the tools the model
received were Playwright's own `browser_*`. The brain (`orchestrator.js`) and its CLI existed but were reachable
only from tests. Every guardrail in `policy.js` — the domain allowlist, the 26-entry Amazon blocklist, the risk
classes — was decorative.

**Two compounding defects**, both now fixed:

1. `orchestrator.js` `defaultReadSite` returned `{ url, title, text: '' }` — a hard-coded **empty string** that
   `signin.detectLoginState()` scored as real page content. Every auth check was indeterminate *and
   indistinguishable from "the page really is blank"*.
2. `signin.detectLoginState({url='',title='',text=''})` defaulted `null` reads to `''`, so an unreadable page
   could be scored like an empty one.

**Now:** `chromeconnect` MCP server → `agent-loop` (decide) → `gate.issueInstruction` → `pw-tool` (policy-checked
Playwright call) → journal → evaluate → decide. The model gets **no browser handle at all**.

### Call chain (verified in the journal)

```
task → agent-loop.plan()        decides the next step
     → gate.issueInstruction()   the decision becomes the governing instruction
     → pw-tool.navigate()        policy re-checked on THIS action, then throttled
     → Playwright transport      performs the action
     → journal.tool_result()     URL, timestamp, duration, result
     → pw-tool.readLivePage()    reads the live page (still inside the same instruction)
     → agent-loop.evaluate()     did we get what we wanted?
     → structured output + journal
```

---

## 2. Files created (9)

**Owner project — `Default Project`**

| Path | Purpose |
|---|---|
| `lib/chromecontrol/pw-tool.js` | **The only module permitted to reach Playwright.** Policy-checked on *every* action, throttled, headed+read-only asserted, isolated-profile gate, credential-field refusal. Never imports a browser driver. |
| `lib/chromecontrol/agent-loop.js` | The controller. plan → act → evaluate → decide. Stops on refusal, blocker or budget. |
| `lib/chromecontrol/gate.js` | Invocation gate + tri-state static auditor. |
| `lib/chromecontrol/journal.js` | Append-only JSONL run journal, redacted on write. |
| `lib/chromecontrol/lessons.js` | PROPOSED-only lesson store with guardrail screening and rollback. |
| `scripts/chromecontrol-agent.js` | CLI: `run / preflight / journal / lessons / audit / guardrails`. |
| `scripts/chromecontrol-mcp-server.js` | The `chromeconnect` MCP server. Exposes 6 tools, **zero browser tools**. |
| `test/agent-loop-tests.js` | 75 offline checks (§5). |
| `test/fixtures/mock-page.html` | Local fixture. No network, no browser, no credentials. |

**Workspace — `Northstar OS Retail Arbitrage Agent`**

| Path | Purpose |
|---|---|
| `tools/chromeconnect_guard.py` | Python half of the gate: refuses `import playwright`, holds the port-9222 lock, provides `cc_call()`. |
| `tools/splice_blocks.py` + `tools/_blocks/b1..b6*.txt` | Reproducible patch mechanism for `browser_agent.py`. Content-anchored, stages to `browser_agent.staged.py`, never overwrites without `--promote`. |

## 3. Files edited (12) + backup paths

Every backup was SHA-256 verified byte-identical at creation.

| Edited file | Backup | Change |
|---|---|---|
| `DP\lib\chromecontrol\policy.js` | `policy.js.bak.20261003` | **Additive-only** `evaluateUrl(url, {allowHosts})`; Amazon check still runs **first** and unconditionally. Added frozen `IMMUTABLE_GUARDRAILS` + `fingerprint()` + `assertGuardrailsIntact()`. Allowlists themselves untouched. |
| `DP\lib\chromecontrol\orchestrator.js` | `orchestrator.js.bak.20261003` | `defaultReadSite` now reads the **live page** via pw-tool and returns `null`/`status:'UNKNOWN'` for anything unread. Returns UNKNOWN rather than reaching for a browser when no instruction is in scope. |
| `DP\lib\chromecontrol\signin.js` | `signin.js.bak.20261003` | **Fails closed**: `null` signals or `status:'UNKNOWN'` ⇒ `'unknown'`, never `'authenticated'`/`'login_required'`. |
| `DP\scripts\chromecontrol.js` | `chromecontrol.js.bak.20261003` | `agent` command routes to `chromecontrol-agent.js`; help text updated. |
| `DP\opencode.json` | `opencode.json.bak.20261003` | `playwright` entry (enabled) → `chromeconnect`; old entry disabled with the reason inline. |
| `DP\config\attachment.json` | `attachment.json.bak.20261003` | The `opencode_mcp_extension_example` block that told you to register raw `@playwright/mcp` as `browser` — **the footgun that caused this** — replaced with the `chromeconnect` form and a do-not statement. |
| `~\.config\opencode\opencode.json` | `opencode.json.bak.20261003` | Global raw `browser` MCP entry **removed**; `"mcp": {}` plus a `_mcp_removed_20261003` record. |
| `WS\opencode.jsonc` | `opencode.jsonc.bak.20261003` | `chromeconnect` entry added; `playwright` entry `enabled: false` with the reason inline. |
| `WS\AGENTS.md` | `AGENTS.md.bak.20261003` | New "Browser control (Chrome Connect)" section in the capsule. |
| `WS\tools\browser_agent.py` | `browser_agent.py.bak.20261003` | Guard installed at line 1 of imports. `cloudflare_signup` **retired** (credential entry + account creation). `connect_takeover` **refused** (raw CDP). `take_screenshot` and `costco_search` delegated to the controller. `interactive_mode` **retired** (`browser_use.Agent` self-drives). |
| `WS\tools\test_chrome.py` | `test_chrome.py.bak.20261003` | Was a live script that filled an email and a **plaintext password** into cloudflare.com. Rewritten as the refusal-gate test. |
| `WS\Northstar_backend\costco_playwright_scraper.py` | `costco_playwright_scraper.py.bak.20261003` | Own Chromium launch removed; delegates to `cc_call`. Public signature preserved. |

**Not changed:** `config/chromecontrol.json`, any Northstar production service, database, route, credential, live
gate, or provider config. No git commit. No install. No live web access.

---

## 4. The six conditions

### (1) No config exposes raw Playwright tools — final tool list

`~` = `%USERPROFILE%`

| Config | Server | Command | Enabled |
|---|---|---|---|
| `~\.config\opencode\opencode.json` | `mcp` | `{}` — raw `browser` entry **removed** | — |
| `WS\opencode.jsonc` | `chromeconnect` | `node …\scripts\chromecontrol-mcp-server.js` | **true** |
| `WS\opencode.jsonc` | `playwright` | `node …\scripts\chromecontrol-mcp.js` | **false** |
| `DP\opencode.json` | `chromeconnect` | `node scripts/chromecontrol-mcp-server.js` | **true** |
| `DP\opencode.json` | `playwright` | (command removed, reason retained) | **false** |

**Tools the model now sees:**

```
chromeconnect  (6)
  chromeconnect_preflight    report attach mode; refuse unless isolated + signed-out
  chromeconnect_run          run ONE task through the controller
  chromeconnect_status       controller / policy / gate / guardrail status
  chromeconnect_journal      decision, tool call, URL, timestamp, result
  chromeconnect_lessons      list | propose | approve | reject | rollback | purge
  chromeconnect_guardrails   prove the immutable policy tables are unchanged
```

**No `navigate` / `click` / `type` / `screenshot` tool exists in that list, by design.**

Machine-checked: every remaining `@playwright/mcp` string across all configs is now a **documentation or
explanatory note**; historical mentions remain only in `00_STATE.json`. `ACTIVE REGISTRATION: NONE`.

Live process check — exactly one browser MCP process exists, and it is the controller:

```
PID 62880  node "...\scripts\chromecontrol-mcp-server.js"
```

The old `chromecontrol-mcp.js → @playwright/mcp --extension` chain is gone.

> **Important finding:** `enabled: false` alone is **not** sufficient. The global `browser` entry had
> `enabled: false` yet its 45 tools stayed advertised to the model — dead handles the model could still try to
> call. The entry had to be **deleted**, not disabled. The project-level `playwright` entry now carries an inline
> reason so nobody re-enables it.

### (2) Policy checked before EVERY action, not the first

`pw-tool.invoke()` is the single choke point. Per call, in order: gate instruction → risk class → **URL re-check
against the *current* page URL** → headed/read-only → isolated profile → throttle → journal → execute.

The URL check uses the live `currentUrl` for `click` / `type` / `extract`, so a redirect cannot smuggle an action
onto a refused host. Test **C6** proves it: navigate to an allowlisted host succeeds, then the page redirects to
`amazon.com`, then `click` is refused with `url_refused:amazon_prohibited` and Playwright is never reached.

### (3) Attach mode for the Alibaba task — **NOT SATISFIED, STOPPING**

Live `chromeconnect_preflight({require_isolated:true})`:

```json
{ "attach": { "mode": "extension", "profile": "(unpinned)", "pinned": false,
              "isolated": null, "signed_in": null },
  "isolated_signed_out_satisfied": false,
  "instruction": "STOP AND ASK THE OPERATOR to select an isolated, signed-out Chrome profile.
                  ChromeConnect cannot prove isolation from outside the browser and will refuse
                  the first action rather than assume." }
```

| Question | Answer |
|---|---|
| Attach mode | `extension` |
| Profile | **unpinned** — attaches to whichever profile the operator happens to select |
| Isolated research profile | **Cannot be proven** (`null`) |
| Signed out | **Cannot be proven** (`null`) |
| Verdict | **NOT SATISFIED** |

Isolated mode **cannot be used** in the current configuration, so per your instruction I have **stopped and am
asking** rather than proceeding. To unblock: configure a dedicated isolated Chrome profile with no session, set
`CHROMECONNECT_TRANSPORT_MODULE` to a Playwright bridge attached to *that* profile, and pin it. Alibaba is not in
`DOMAIN_ALLOWLIST` and must be added by you as an operator decision — lessons cannot add it, by design.

### (4) Python drivers refuse direct Playwright / CDP; port-9222 lock

- `import playwright` **raises** `DirectPlaywrightUseRefused` outside a controller instruction.
- `connect_takeover()` returns `(None, None, None)` and says why. It previously **silently fell back to launching
  a fresh browser** — that silent fallback is how the bypass survived unnoticed. It is gone.
- Port 9222 is an exclusive, pid-tracked lock (`WS\.chromeconnect\cdp_9222.lock`); a second holder is refused.
- `costco_search()` no longer guesses a `/SearchDisplay` URL. It opens the site root and lets the controller use
  the site's own search box. Output is prefixed **`DISCOVERY ONLY - not sourcing evidence`** and unread fields
  stay `null`.

### (5) Lessons are PROPOSED-only and cannot relax a guardrail

Lifecycle `propose → PROPOSED` → `approve` (operator only) → `rollback` → `purge`. PROPOSED lessons never reach
the prompt. Two independent barriers: field/text screening, **and** a SHA-256 fingerprint of the immutable policy
tables checked on every write.

Test D fires **11 attack lessons** — allowlist injection, domain override, credit-limit raise, "without owner
approval", "disable the gate", "remove the amazon blocklist", throttle bypass, force-click, solve-captcha,
external-state flag, budget overrun. **11/11 rejected**, fingerprint identical before and after
(`e5ef83da855c860d…`).

### (6) `readSite` reads the live page; UNKNOWN instead of empty

`pw-tool.readLivePage()` returns `{status:'READ'|'UNKNOWN'}` with `text: null` when nothing was read. It never
returns `''`. `signin.detectLoginState` now fails closed on `null`/`UNKNOWN`. Tests E1–E7 cover: empty transport,
blank strings, a real read, login detection on each, and extraction nulling absent fields.

---

## 5. Test results (offline only — no browser, no network, no Alibaba)

| Suite | Result |
|---|---|
| `test/agent-loop-tests.js` (new) | **75 / 75 passed** |
| `test/chromecontrol-tests.js` (existing) | **58 passed, 0 failed** — no regression |
| `test/orchestrator-tests.js` (existing) | **63 passed, 0 failed** — no regression |
| `tools/test_chrome.py` (refusal gate) | **8 / 8 passed** |
| `node --check` × 12 JS files | all OK |
| `py_compile` × 5 Python files | all OK |
| `chromeconnect-agent.js audit` × 9 files | **live=0**, 5 suppressions all with stated reasons |

**Required cases:**

| # | Case | Result |
|---|---|---|
| a | Brain → tool call chain visible in logs | **A2–A5 PASS** — journal order `decision → tool_call → tool_result → decision(evaluate)`, all bound to the same `instruction_id`, with URL, timestamp, policy action, duration. Transport saw exactly `navigate, readLivePage, extract, readLivePage` — evaluate after every action. |
| b | Direct Playwright call refused | **B1–B6 PASS** — unwrapped `navigate()` → `GateRefusal: no_controller_instruction`, 0 transport calls; spoofed caller → `caller_not_trusted`; refused again once the instruction closes. |
| c | Blocklisted + non-allowlisted refused | **C1–C9 PASS** — 4 Amazon URLs refused; an additive `allowHost` **cannot** unblock Amazon (`allowed=false, amazon_prohibited`); ebay → `host_not_allowlisted`; costco allowed; credential field refused. |
| d | Guardrail-relaxing lesson rejected | **D0–D9 PASS** — 11/11 attacks rejected; fingerprint unchanged. |

Additional: **E** UNKNOWN-not-empty (7), **F** isolated signed-out profile (6), **G** CAPTCHA stops the run and is
not retried past (3), **H** journal redaction (4), **I** static auditor (9).

**CLI proofs**

```
$ python tools/browser_agent.py --signup-cloudflare --email a@b.invalid --password x
REFUSED: --signup-cloudflare is retired.
Chrome Connect never enters credentials and never creates an account.
Credential entry and account creation are prohibited by policy.js.
exit code 2
```

`grep -n playwright tools/browser_agent.py` → **no live import**; every occurrence is prose or a refusal message.

**Live MCP path exercised in this session:** `chromeconnect_guardrails` → `intact: true`,
fingerprint `e5ef83da855c860d…`; `chromeconnect_status` → `model_owns_browser: false`,
`transport_configured: false` (fails closed).

### Three real bugs the tests caught

1. **`journal.append` minted a new timestamped filename per call**, scattering one run's records across hundreds
   of files. Fixed with a per-run memo.
2. **`agent-loop` cleared the gate instruction in a `finally` *before* `readLivePage()`**, so every page
   evaluation ran as an unwrapped call and was silently refused — every run "completed" with `data: null`. The
   instruction now stays open through the read and the evaluation.
3. **The planner called `readLivePage()` itself**, outside any instruction. It now receives the page from the
   previous step.

---

## 6. Rollback

Nothing was committed to git. To revert completely:

```powershell
# 1. Restore the 12 edited files (paths in §3)
$p = "C:\Users\T2Hol\OneDrive\Documents\Default Project"
$w = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
foreach ($f in @(
  "$p\lib\chromecontrol\policy.js", "$p\lib\chromecontrol\orchestrator.js",
  "$p\lib\chromecontrol\signin.js", "$p\scripts\chromecontrol.js",
  "$p\opencode.json", "$p\config\attachment.json",
  "$env:USERPROFILE\.config\opencode\opencode.json",
  "$w\opencode.jsonc", "$w\AGENTS.md",
  "$w\tools\browser_agent.py", "$w\tools\test_chrome.py",
  "$w\Northstar_backend\costco_playwright_scraper.py"
)) { Copy-Item "$f.bak.20261003" $f -Force }

# 2. Delete the new files
Remove-Item "$p\lib\chromecontrol\{pw-tool,agent-loop,gate,journal,lessons}.js"
Remove-Item "$p\scripts\{chromecontrol-agent,chromecontrol-mcp-server}.js"
Remove-Item "$p\test\agent-loop-tests.js", "$p\test\fixtures\mock-page.html"
Remove-Item "$w\tools\chromeconnect_guard.py", "$w\tools\splice_blocks.py"
Remove-Item "$w\tools\_blocks" -Recurse -Force
Remove-Item "$w\tools\browser_agent.staged.py" -ErrorAction SilentlyContinue
Remove-Item "$w\.chromeconnect" -Recurse -Force -ErrorAction SilentlyContinue

# 3. Restart OpenCode so the MCP tool set reloads.
```

Verify: `git status` clean for tracked files; `node scripts/chromecontrol-agent.js audit <files>` no longer exists
(rolled back); suites back to 58 / 63.

**Partial rollback:** the guardrails are additive and fingerprint-checked, so reverting only `policy.js` will not
corrupt state. `lessons.json` and `data/agent-journal/` are new artifacts — safe to delete wholesale.

**Least-risk rollback order if you need the browser working immediately:** restore the four `opencode.json*`
files first. That reinstates a working (unguarded) MCP path while the controller code sits idle.

---

## 7. Deliverable 4 — updated Alibaba prompt

```
ALIBABA SUPPLIER RESEARCH — CONTROLLED BROWSER TASK

CONTROLLER: Chrome Connect. It plans every step, decides what to extract,
evaluates each page, detects blockers, and records what it learned. Nothing
else may drive the browser.

TOOL: Playwright is a TOOL Chrome Connect calls — navigate / click / type /
screenshot / extract. You do not get a browser handle. There is no navigate,
click, type or screenshot tool available to you, by design. State a task with
chromeconnect_run and receive structured output. A Playwright call without a
Chrome Connect instruction is refused and logged.

PREFLIGHT — MANDATORY, DO THIS FIRST:
  chromeconnect_preflight({require_isolated: true})
Requires an ISOLATED, SIGNED-OUT Chrome profile: a dedicated research profile
with no session, no logged-in account, no reused personal profile.
If isolation or signed-out state cannot be proven, STOP AND ASK THE OPERATOR.
Do not proceed on a signed-in profile, and do not infer that "extension mode"
means isolated. Current status: NOT SATISFIED.

MODE: headed, read-only by default, throttled, one tab at a time.
DOMAINS: only hosts the operator has added to the allowlist. Alibaba must be
added by the operator before this task can run. Amazon and all Amazon-related
hosts are always refused.

BLOCKERS: CAPTCHA, login wall, rate limit, consent wall or access denied →
STOP and ask the owner. Never bypass, never solve, never click through, never
retry past a challenge.

SCOPE: Alibaba supplier pages only.
NO purchase · NO RFQ send · NO contact-form submission · NO message to a
supplier · NO account change · NO login · NO credential entry · NO cost.

EXTRACT (read and record only): supplier name, MOQ, unit price, price tiers,
shipping terms, lead time, packaging options, certifications, and the page URL
plus capture timestamp for every row. Anything not visible on the page is
recorded as UNKNOWN (null) — never inferred, never estimated, never filled in
from a similar supplier.

OUTPUT: one structured table plus the run journal. Every row cites its source
URL and capture time. Label the output "DISCOVERY ONLY - not sourcing
evidence" unless the owner has independently verified the rows.

LEARNING: Chrome Connect may propose lessons (hints, selectors that worked,
notes on why a page blocked us). Lessons start as PROPOSED and are used only
after the owner approves them. A lesson can never relax a policy, gate,
allowlist, spend rule or approval step; such attempts are rejected and logged.
Review and approve with chromeconnect_lessons; roll back with rollback.
```

---

## 8. Open items — not done, needs your decision

1. **Alibaba is not run.** Preflight says isolation is unprovable and Alibaba is not allowlisted. Both need an
   operator decision.
2. **`CHROMECONNECT_TRANSPORT_MODULE` is not set.** The controller has no way to call Playwright yet, so
   `chromeconnect_run` returns `BLOCKED: no_playwright_transport` and fails closed. Wiring this is the last
   mechanical step before live browser work, and it must point at the isolated profile from item 1.
3. **Restart OpenCode** to reload the MCP tool set in the UI. The server is already correct and running.
4. `DP\config\attachment.json` still documents `browser_approved` attachment, which I did not touch — it was
   outside the approved file list and is loaded by nothing.
