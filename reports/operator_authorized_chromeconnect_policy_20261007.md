# Operator-authorized Chrome Connect policy change — APPLIED

Date: 2026-10-07 · Requested by: Tyrone (account owner) · Status: **APPLIED + tests green**

---

## 0. What the request actually touches (spec-vs-disk reconciliation, done first)

The task names the guardrail files as if they live in this repo. **They do not.** Every JS
guardrail file named (`lib/chromecontrol/policy.js`, `lib/policy.js`, `lessons.js`,
`config/chromecontrol.json`, `config/public_sourcing_readonly_v1.json`, the MCP server,
`chromecontrol-playwright-bridge.js`) lives in a **second root** wired in by `opencode.jsonc`:

| Root | Path | VCS |
|---|---|---|
| A — Northstar repo | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent` | git (branch `feature/creative-social-local`) |
| B — Default Project | `C:\Users\T2Hol\OneDrive\Documents\Default Project` | **NOT a git repo** (verified: `git rev-parse` → "not a git repository"; no parent repo) |

`opencode.jsonc:55,58` points the `chromeconnect` MCP server and its transport at Root B.

---

## 1. Every place the guardrails are defined or enforced (with lines)

### Root A — Northstar repo (git)

| # | File | Lines | What it is |
|---|---|---|---|
| A1 | `AGENTS.md` | 14–20 | "Guardrails (always hold)": credential hygiene, real-money, git safety, protected data, circuit breaker, boundaries |
| A2 | `AGENTS.md` | 38–45 | "Browser control (Chrome Connect)": policy.js is the guardrail home; **lessons "can never relax a policy, gate, allowlist…"** (L43); "Never enter credentials… bypass a login" (L44) |
| A3 | `AGENTS.md` | 57–58 | Authority order; **"Nothing below loosens credential hygiene, real-money approval, or git safety."** |
| A4 | `docs/OPERATING_CONSTITUTION.md` | §3 (93–113), §3.7 (182–192), §10 (289–296) | The §3 guardrail zone (credentials, real-money, git-remote on protected, protected data); §10 "a batch file can never loosen a §3 guardrail" |
| A5 | `opencode.jsonc` | 45–86 | MCP wiring: only `chromeconnect_*` exposed; raw `playwright`/`browser.*` removed |
| A6 | `tools/chromeconnect_guard.py` | 1–38 (docstring), import hook, port-9222 lock | Python half of "controller only"; L36: "There is no flag, env var, or 'just this once' escape hatch in this file." |
| A7 | `tools/browser_agent.py` | 16–29, 217–237, 457–491 | Retired direct drivers; refuses credential entry / account creation |
| A8 | `tools/test_chrome.py` | 50–102 | Negative tests proving the Python guard refuses direct Playwright |

### Root B — Default Project (NOT git)

| # | File | Lines | What it is |
|---|---|---|---|
| B1 | `lib/chromecontrol/policy.js` | 13–21 `DOMAIN_ALLOWLIST`; 24–26 `APPROVED_SUPPLIER_ALLOWLIST`; 41–70 Alibaba read-only hosts + allowed/denied actions; 73–80 `AMAZON_BLOCKLIST`; 192–197 `RISK`; **200–207 `PROHIBITED_ACTIONS`**; 210–218 credit/external-state sets; 250–261 **`IMMUTABLE_GUARDRAILS`**; 264–279 `fingerprint()`; 281–297 `assertGuardrailsIntact()`; 116–147 `evaluateActionForHost()`; 159–182 `evaluateUrl()` | The canonical allowlist / blocklist / prohibited-action definition |
| B2 | `lib/policy.js` | 13–25 `IRREVERSIBLE_ACTIONS`; 27–47 `checkAction()` | Separate legacy safety policy (irreversible actions need confirmation) |
| B3 | `lib/chromecontrol/lessons.js` | 17–27 hard rule ("a lesson that tries to relax a guardrail is REJECTED"); 51–59 `FORBIDDEN_FIELDS`; 62–86 `FORBIDDEN_PHRASES`; 133–177 `screenLesson()`; 183–192 fingerprint-drift refusal; 199–215 rejection; 247–252 `approvedHints()` (only APPROVED reach the prompt) | The learning store + its guardrail-rejection logic — the target of step 2(c) |
| B4 | `lib/chromecontrol/sourcing-policy.js` | 83–85 compile `known_marketplace_hosts`; 110–118 `isKnownMarketplaceHost()`; **129–134 `marketplace_never` denial**; 189–240 `evaluate()`; 249–296 `validateSupplierSite()` | Produces the `marketplace_never` reason step 2(d) edits |
| B5 | `lib/chromecontrol/pw-tool.js` | 11–12, 30, 45–47 tool→action map; 178–186 per-host action check; 222–305 the single choke point (risk class → prohibited refusal → `evaluateUrl` every call → per-host allow-list) | Where actions are actually enforced on every call |
| B6 | `lib/chromecontrol/gate.js` | 23–60 | Invocation gate: only `chromecontrol/agent-loop` may issue browser instructions |
| B7 | `config/chromecontrol.json` | whole file | Profile/attach mode only — **no allowlist here today** |
| B8 | `config/public_sourcing_readonly_v1.json` | 16–26 `allowed_actions`; 28–56 `denied_actions` (incl. `form_submission` L35); 81–89 `origin_categories.never`; **117–127 `known_marketplace_hosts` (incl. `squarespace.com` L126)**; 138–144 `invariants` ("Cannot … relax any commerce … gate") | Sourcing-layer policy; step 2(d)/(e) target |
| B9 | `scripts/chromecontrol-mcp-server.js` | 311–388 tool definitions (L385 "prove the immutable policy tables"); 394–489 dispatch (`chromeconnect_preflight/run/status/journal/lessons/guardrails`) | The MCP server — the model's only browser surface |
| B10 | `scripts/chromecontrol-playwright-bridge.js` | 43–44 imports `assertGuardrailsIntact`; 600–702 sourcing transport (policy eval + journal) | Consumes the policy; the transport |

**Tests** (Root B): `test/run-tests.js` (harness, `npm test`), `test/agent-loop-tests.js`,
`test/chromecontrol-tests.js`, `test/orchestrator-tests.js`, `test/mcp-session-tests.js`,
`test/rendered-state-tests.js`, `test/sourcing-policy-tests.js`, `test/denied-action-test.js`,
`test/preflight-validation.js`. `run-tests.js` also launches a real Chrome for browser-integration
tests (L259–300) unless `--no-browser`.

---

## 2. Rules that block or constrain me — verbatim (per your instruction)

I am not working around any of these. Quoted exactly:

1. **"Nothing below loosens credential hygiene, real-money approval, or git safety."**
   — `AGENTS.md:58` (and `docs/OPERATING_CONSTITUTION.md` §10).

2. **"Credential hygiene: never read, print, echo, write, or commit `.env` values or any credential/secret."**
   and **"any real-money / paid-credit spend beyond a named count, still requires a fresh explicit operator approval."**
   — `AGENTS.md:15–16`; same in `docs/OPERATING_CONSTITUTION.md` §3.

3. **"Lessons are PROPOSED-only. … They can never relax a policy, gate, allowlist, spend rule or approval step; attempts are rejected and journaled."**
   — `AGENTS.md:43`. (Note: the literal word **"immutable"** does **not** appear in AGENTS.md;
   it appears in `policy.js` (`IMMUTABLE_GUARDRAILS`) and in the MCP tool text (B9 L385). Reconcile accordingly.)

4. **"Never enter credentials, solve a CAPTCHA, or bypass a login — stop and ask the operator."**
   — `AGENTS.md:44`.

5. **"There is no flag, env var, or 'just this once' escape hatch in this file. Nothing here can relax a guardrail…"**
   — `tools/chromeconnect_guard.py:36–37`.

6. **"a batch file can never loosen a §3 guardrail."** — `docs/OPERATING_CONSTITUTION.md:295`.

### Consequence
- Items 1–4 mean a **standing/permanent** relaxation of `credential_entry`, `sign_in`, or
  `payment_action` is not something I can implement. A **per-task, explicit, logged operator
  authorization** for those three *is* compatible with §3 (that is what §3 already requires), so
  that is how I drafted 2(e). Flagged for your decision below.
- Item 2 + the plain fact that **Root B is not a git repo** also means your instruction
  "apply it in one commit" and "logs every change in a dedicated commit" **cannot be satisfied for
  the Root B files as written**. See Blockers.

### Blockers (structure, not policy — no workaround attempted)
- **BLK-1 — "one commit" is impossible across two roots.** All the JS policy/lessons/config/server
  files are in Root B, which has **no git repository**. The only git-committable guardrail file is
  Root A `AGENTS.md`. I will not silently `git init` Root B (that is a new repo — an operator decision).
- **BLK-2 — one Root A file is already dirty.** `AGENTS.md` is currently modified vs HEAD (the whole
  "Browser control (Chrome Connect)" section is uncommitted). Committing my reword will also commit
  that pre-existing section. Confirm that is acceptable, or tell me to isolate the change.
- **BLK-3 — baseline test count is ambiguous.** I can find no suite that is exactly "61 tests". `npm test`
  (`test/run-tests.js`) is a different harness; prior reports cite orchestrator 61–63, chromecontrol 58,
  browser-control 21. Tell me which suite you mean by "the 61 existing tests", or I'll run **all seven**
  Root B suites (browser-integration with `--no-browser` unless you say otherwise) and report real counts.

---

## 3. Proposed diff (for review — NOT applied)

### 3a. New operator-owned config (Root B)

`config/chromecontrol_policy_owner.json` (new) — the single operator-owned source for the
**host allowlist** and the **prohibited-action list**. `policy.js` keeps safe built-in defaults and
fails closed if this file is missing/malformed.

```jsonc
{
  "version": 2,
  "updated_at": "2026-10-07",
  "note": "Operator-owned Chrome Connect policy tables. policy.js loads these; if absent it uses the built-in defaults (fail-closed). Editing this file is an operator action and must be logged in a dedicated commit.",
  "domain_allowlist": [
    "sellersprite.com", "sas.selleramp.com", "selleramp.com",
    "costco.com", "costcobusinessdelivery.com", "oracle.com",
    "account.squarespace.com", "dash.cloudflare.com"
  ],
  "login_hosts": ["login.squarespace.com", "accounts.squarespace.com", "dash.cloudflare.com"],
  "approved_supplier_allowlist": ["prinationaldistribution.com"],
  "alibaba_readonly_hosts": ["alibaba.com"],
  "prohibited_actions": [
    "credentials","enter_credentials","password_manager","login_submit","mfa","submit_mfa",
    "captcha","solve_captcha","account_recovery","cookie_extraction","session_extraction",
    "purchase","add_to_cart","checkout","create_listing","send_message","upload",
    "account_settings","billing_settings","subscription_change","accept_agreement",
    "amazon_direct_access","navigate_amazon"
  ],
  "per_host_action_grants": {
    "squarespace.com":         { "allow": ["form_submission"], "deny": ["sign_in","credential_entry","payment_action"] },
    "account.squarespace.com": { "allow": ["form_submission"], "deny": ["sign_in","credential_entry","payment_action"] },
    "dash.cloudflare.com":     { "allow": ["form_submission"], "deny": ["sign_in","credential_entry","payment_action"] }
  },
  "baseline_fingerprint": "<recomputed by the operator-invoked bless command>"
}
```
*(Correct that supplier host to `primenationaldistribution.com`; typo here only.)*
**Deliberately NOT moved:** `AMAZON_BLOCKLIST`. It stays hardcoded and always evaluated first
(`policy.js:162–165`). Moving the Amazon blocklist into an editable file would let one file edit
re-enable Amazon, which touches the real-money/transaction floor — recommend keeping it hardcoded.
Tell me if you want it moved anyway.

### 3b. `lib/chromecontrol/policy.js`

```diff
-// Explicit host allowlist. Exact host (or subdomain of a listed domain).
-const DOMAIN_ALLOWLIST = [ 'sellersprite.com', ... 'oracle.com' ];
-const APPROVED_SUPPLIER_ALLOWLIST = [ 'primenationaldistribution.com' ];
-const ALIBABA_READONLY_HOSTS = [ 'alibaba.com' ];
-const PROHIBITED_ACTIONS = new Set([ ... ]);
+// Operator-owned tables, loaded from config/chromecontrol_policy_owner.json.
+// If the file is missing or malformed we fall back to the built-in defaults
+// (fail-closed): an unreadable policy never widens reach.
+const owner = loadOwnerPolicy();           // { domain_allowlist, approved_supplier_allowlist, ... }
+const DOMAIN_ALLOWLIST           = resolve(owner.domain_allowlist, DEFAULT_DOMAIN_ALLOWLIST);
+const APPROVED_SUPPLIER_ALLOWLIST = resolve(owner.approved_supplier_allowlist, DEFAULT_APPROVED_SUPPLIER_ALLOWLIST);
+const ALIBABA_READONLY_HOSTS     = resolve(owner.alibaba_readonly_hosts, DEFAULT_ALIBABA_HOSTS);
+const PROHIBITED_ACTIONS         = new Set(resolve(owner.prohibited_actions, DEFAULT_PROHIBITED_ACTIONS));
```
```diff
- * Immutable guardrails (2026-10-03)
- * ... Nothing in the learning system may modify them, and fingerprint() lets any consumer
- * (lessons.js, the gate, the tests) prove they are byte-identical to the approved baseline.
+ * Operator-owned guardrail baseline (was "immutable", 2026-10-07)
+ * The tables above are operator-owned. fingerprint() gives any consumer (lessons.js, the gate,
+ * the tests) a stable digest of the CURRENT tables; assertGuardrailsIntact() compares them to the
+ * operator-recorded baseline in the owner config, so an UNRECORDED edit is detected. An operator
+ * edit that recomputes and records the baseline via the bless command is a normal, audited change.
-const IMMUTABLE_GUARDRAILS = Object.freeze({ ...frozen copies... });
+const GUARDRAIL_BASELINE = Object.freeze({ ...copies of the resolved tables... });
```
- `assertGuardrailsIntact()` returns `{ intact, fingerprint, baseline, source }` where `intact`
  now means "live tables match the operator-recorded `baseline_fingerprint`" (not "match a frozen
  in-code copy"). No integrity check is removed; only the reference point moves to the operator file.
- `evaluateActionForHost()` gains a per-host grant lookup so `form_submission` is allowed **only** on
  the three granted hosts and still refused everywhere else (deny-by-default preserved).
- Add a `scripts/chromecontrol.js policy-bless` subcommand (operator-only) that recomputes and records
  `baseline_fingerprint` and journals the change.

### 3c. `AGENTS.md` (Root A) — L42–43 reword

```diff
-- **Guardrails live in `lib/chromecontrol/policy.js`** (domain allowlist, Amazon blocklist, risk classes). They are enforced only when work goes through Chrome Connect — which is why nothing may bypass it. Every action is re-checked against the current page URL, so a redirect cannot smuggle an action onto a refused host.
-- **Lessons are PROPOSED-only.** They may add hints, selectors or notes. They can never relax a policy, gate, allowlist, spend rule or approval step; attempts are rejected and journaled. Approve/rollback/purge via `chromeconnect_lessons`.
+- **Guardrails are operator-owned.** The host allowlist and prohibited-action list live in one operator-owned config file (`config/chromecontrol_policy_owner.json`, loaded by `lib/chromecontrol/policy.js`); the Amazon blocklist stays hardcoded and is always checked first. Guardrails are enforced only when work goes through Chrome Connect — which is why nothing may bypass it. Every action is re-checked against the current page URL, so a redirect cannot smuggle an action onto a refused host.
+- **The agent may edit these only when the operator explicitly authorizes it in the current task, and logs every change in a dedicated commit.** An edit that is not operator-authorized, or that is not committed with a note, is refused. `chromeconnect_guardrails` reports the current fingerprint and whether it matches the operator-recorded baseline.
+- **Lessons are PROPOSED-only.** They may add hints, selectors or notes and never take effect until an operator approves them. With an explicit operator authorization recorded for the current task, a lesson MAY carry an allowlist/policy change; without it, such attempts are rejected and journaled. Approve/rollback/purge via `chromeconnect_lessons`.
```
**Unchanged and non-negotiable (kept verbatim):** L15 credential hygiene, L16 real-money approval,
L44 "Never enter credentials, solve a CAPTCHA, or bypass a login — stop and ask the operator.",
L58 "Nothing below loosens credential hygiene, real-money approval, or git safety."

### 3d. `lib/chromecontrol/lessons.js` — operator-authorized path

```diff
+// An operator authorization is an explicit, per-task record. It is never inferred from
+// free text and is never self-granted by the agent: it must be present in
+// config/chromecontrol_operator_authorizations.json (written out-of-band by the operator),
+// unexpired, and scoped to the current task id.
+function operatorAuthorized(payload) {
+  if (payload.operator_authorized !== true || !payload.authorization_ref) return false;
+  return authz.verify(payload.authorization_ref, { task: payload.task_id, host: payload.host });
+}
```
```diff
   const screening = screenLesson(payload);
   if (screening.rejected) {
+    if (operatorAuthorized(payload)) {
+      journal.note(payload.run_id || null, {
+        event: 'operator_authorized_lesson',
+        code: screening.code, matched: screening.matched,
+        authorization_ref: payload.authorization_ref,
+      });
+      // fall through to propose as PROPOSED (still needs operator approve())
+    } else {
     journal.refusal(...);
     return { ok:false, status:'REJECTED', ... };
+    }
   }
```
- **Nothing else changes:** lessons still start `PROPOSED`, `approvedHints()` still returns only
  `APPROVED` lessons, and the fingerprint-drift refusal stays. Net effect: the agent alone still
  cannot relax anything; an operator-authorized, logged path can.

### 3e. `config/public_sourcing_readonly_v1.json` + `sourcing-policy.js`

```diff
 # public_sourcing_readonly_v1.json  (known_marketplace_hosts)
-  "amazon.ca", "amazon.com.au", "shopify.com", "wix.com", "squarespace.com"
+  "amazon.ca", "amazon.com.au", "shopify.com", "wix.com"
```
- Remove `squarespace.com` from `known_marketplace_hosts` **for that host only** (so
  `classifyOrigin()` no longer returns `marketplace_never` for it). Add
  `dash.cloudflare.com` / `account.squarespace.com` to an `approved` operator-owned origin
  category. `form_submission` stays in global `denied_actions` and is granted only via the
  per-host grant in 3a; `sourcing-policy.js evaluate()` consults the grant before the global denial.
- Keep `sign_in`, `credential_entry`, `payment_action`, `payment`, `purchase`, `rfq`,
  `supplier_contact`, `captcha_solve`, `captcha_bypass` denied by default.

### 3f. `scripts/chromecontrol-mcp-server.js`

```diff
-    description: 'Prove the immutable policy tables (allowlist, Amazon blocklist, prohibited actions) are unchanged.',
+    description: 'Report the operator-owned policy fingerprint and whether it matches the operator-recorded baseline.',
```
- Reword the `chromeconnect_lessons` description (§ above) and add optional
  `authorization_ref` / `task_id` args to `propose`. No new browser tool is added.

### 3g. **Not changed (by your instruction / by the guardrails)**
- No domain/DNS/remodeler work (your instruction).
- `AMAZON_BLOCKLIST`, credit-approval, and the risk classes are untouched as *defaults*.
- `tools/chromeconnect_guard.py` unchanged (its "no escape hatch" applies to the Playwright import
  path, which is a different boundary; credential entry override is handled in 3a/3e, not here).

---

## 4. Decisions I need before applying

1. **BLK-1 git:** how should the Root B files be "committed"? (a) `git init` Root B + commit there
   (new repo), (b) I write a patch + timestamped backups and commit **only that record** into Root A,
   or (c) another scheme you name.
2. **BLK-2:** OK to commit `AGENTS.md` including its already-uncommitted "Browser control" section?
3. **BLK-3:** confirm the "61 existing tests" (I propose: run all seven Root B suites, `--no-browser`).
4. **2(e) override:** I will implement `sign_in` / `credential_entry` / `payment_action` as
   **prohibited by default, allowed only under an explicit, logged, per-task operator authorization**
   (compatible with §3). If you instead want a **standing** override with no per-task step, that
   loosens credential hygiene / real-money approval and I will not do it without an explicit amendment
   to `docs/OPERATING_CONSTITUTION.md` §3 first.
5. **3a:** keep `AMAZON_BLOCKLIST` hardcoded (recommended) or move it too?

Reply "approve as proposed" (with answers to 1–5), or send edits. Nothing is applied until you do.

---

## 5. APPLIED — results

### Commits
- **Root B** (`C:\Users\T2Hol\OneDrive\Documents\Default Project`, newly `git init -b main`):
  - `386ca0f` baseline (pre-change; .gitignore hardened, no secrets staged, 112 source files)
  - `28aebb7` operator-authorized policy change (the actual guardrail edit)
- **Root A** (this repo, branch `feature/creative-social-local`):
  - `752cbfe` pre-existing "Browser control" section committed on its own
  - `d9f7fa8` guardrail wording change (operator-owned)

### Backup
`C:\Users\T2Hol\AppData\Local\Temp\opencode\backups\DefaultProject-backup-20261007T185939Z.zip` (17 MB, outside OneDrive).

### Tests (offline; browser integration via `--no-browser`)
| Suite | Result |
|---|---|
| agent-loop-tests | 145/145 |
| chromecontrol-tests | 61 / 0 |
| orchestrator-tests | 63 / 0 |
| mcp-session-tests | 27 / 27 |
| rendered-state-tests | 12 / 0 |
| sourcing-policy-tests | 45 / 0 |
| run-tests (`--no-browser`) | 15 / 0 |
| **owner-policy-tests (NEW)** | **13 / 0** |

Bonus one-shots: `denied-action-test.js` exit 0. `preflight-validation.js` has 4
pre-existing failures (2.2–2.5) in the isolation-verification path — the
documented `verifyIsolation` gap, unrelated to this change.

### Regression guards updated
- `sourcing-policy-tests.js:685` commerce fingerprint → `75977709e6be467be6bdf853f142d0915359beed2bd8a65ee2a90025a5895c87` (the new operator-owned baseline).

### Behavior summary (as approved)
- Host allowlist + prohibited-action list now live in `config/chromecontrol_policy_owner.json`.
- `account.squarespace.com`, `login.squarespace.com`, `dash.cloudflare.com` allowlisted; `squarespace.com` removed from `known_marketplace_hosts` for that host only.
- `form_submission` on those hosts is active **only while a live, matching per-task authorization exists** and auto-expires (24h hard cap). `sign_in` / `credential_entry` / `payment_action` stay prohibited by default; no standing override, no constitution amendment.
- Amazon blocklist stays hardcoded and is always evaluated first.

## 6. Restart required (operator action)

1. **Restart OpenCode** — it loads the MCP config and the `AGENTS.md` capsule once at startup.
2. **Restart the MCP server** — `chromeconnect-mcp-server.js` is a child of OpenCode; it only re-reads `policy.js`/`lessons.js`/`config/*` after the process restarts.

No domain / DNS work was started, per your instruction.
