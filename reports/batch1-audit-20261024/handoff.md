# Batch 1 — handoff report (2026-10-25)

## Root cause of the controller hang (evidence)

Trace of a single navigation, correlated by journal seq + timestamp:

| Stage | Evidence | Result |
|---|---|---|
| request received | agent journal seq 1 `run_started`, task + url present | OK |
| target selected | seq 2 `decision` action=navigate, goal=`load http://127.0.0.1:8101/ui/` | OK |
| command dispatched | seq 3 `tool_call` pw_tool=navigate, policy_action=navigate_allowed_host, risk=read_only, url matches | OK |
| browser operation started | Playwright MCP child pid logged (`[cc-bridge] mcp connected: pid=… tools=25`); `browser_navigate` invoked | NO RESPONSE |
| navigation outcome | journal stops here; `session.call('tools/call', {name:'browser_navigate'})` never resolves | HUNG |
| response emitted | none — `_withTimeout` only fires at `timeoutMs` (now 30 000 ms) | HUNG→TIMEOUT |
| caller received response | agent loop awaits `pw.navigate(...)` indefinitely; after the fix it receives `McpSessionError(TIMEOUT)` then `EXTENSION_RECONNECT_REQUIRED` | explicit failure |

Observed pattern (from `smoke-results` attempts and prior runs):
- Cycle A: navigate returned in 19 s (success).
- Cycle B: navigate never returned; journal frozen at the navigate tool_call for ≥180 s.
- No leftover Playwright MCP processes; the extension relay is the stall point.
- The Playwright MCP extension serves one client at a time; a dropped relay leaves
  `browser_navigate` pending with no answer.

Conclusion (evidence-supported): the browser operation itself stalls inside the
Playwright MCP extension relay — not a readiness wait, not a stale target, not a
transport disconnect, and not a lost response. The readiness wait and the SPA
rendering are not the cause; the page loads fine when the call returns.

## Fix applied (smallest evidence-supported)

Chrome Connect repo (commit `f2ec1f5`):
- `lib/chromecontrol/mcp-session.js`: default `timeoutMs` 240 000 → 30 000
  (still overridable via `CHROMECONNECT_MCP_TIMEOUT_MS`).
- `scripts/chromecontrol-playwright-bridge.js`: `transport()` now quarantines the
  session (`close()` + cache eviction) on `TIMEOUT` or `EXTENSION_RECONNECT_REQUIRED`
  before rethrowing, so the next action gets a fresh connection instead of a
  stuck one. Also carries the in-progress bindProfile / probe-route fixes.

A caller-side timeout alone would have left the half-dead connection in the cache;
the quarantine is what makes the next action recoverable.

## Regression / real-connection results

- Controller unit tests: `node test/chromecontrol-tests.js` → **78 passed, 0 failed**.
- Bounded-deadline behaviour verified: a hung navigate now fails in ~30 s with
  `McpSessionError(TIMEOUT)` instead of hanging for 4 min.
- **20-cycle smoke test: NOT COMPLETED.** The Playwright MCP extension relay
  stalled on cycle 2 and did not recover within the bounded window across three
  consecutive attempts. No smoke screenshots were produced. This is a controller
  (extension-relay) defect, not a product defect; it cannot be manufactured into
  a pass without bypassing Chrome Connect, which is forbidden.
- Induced-timeout regression: the quarantine path is exercised by the failing
  cycles (session closed + cache evicted), but a clean "induce → recover → pass"
  sequence could not be demonstrated because the relay did not recover.

## G1–G6 outcomes

All BLOCKED. No generation was started; no credits spent; no Generate clicked
successfully. The plan card for G1 is present in the transcript
(`Generate draft 34 cr` / `Generate final 71 cr`, local lane) but no artifact
was produced.

| Gate | Status | Evidence |
|---|---|---|
| G1 3D pouch mockup → draft → inline image | BLOCKED | controller relay stall |
| G2 portrait 896×1344 | BLOCKED | controller relay stall |
| G3 main-style + lifestyle | BLOCKED | controller relay stall |
| G4 A+ pack | BLOCKED | controller relay stall |
| G5 5-second ad | BLOCKED | controller relay stall |
| G6 tip calculator | BLOCKED | controller relay stall |

## Product-side work (verified, committed, not acceptance)

Product repo commits (local, no push):
- `09f350cd` — honest artifact states (D7), effects wired, voice honesty (D4),
  one display-scale control (D2/D3).
- `8520824b` — WebGL context-loss fallback (D8).
- `12278014`, `4fc42848` — audit docs.

Checks (all green):
- `npm run build` → 0 errors
- `HARNESS_BASE_URL=http://127.0.0.1:8101/ui/ node verify-shell-v3.cjs` → 28 passed, 0 failed
- `python -m pytest test_chat_plan.py -q` → 18 passed
- `node test/chromecontrol-tests.js` → 78 passed, 0 failed

## Remaining blockers / approval requirements

1. **Controller relay (hard blocker for all UI evidence):** the Playwright MCP
   extension in the "Work" profile must be clicked to reconnect, or the extension
   must be reinstalled/re-paired. This is an operator action; the agent cannot do
   it. Until it recovers, no UI-verified product test is possible.
2. **Credentials:** the app is signed in now (Operator), but the session TTL is
   short; if it expires again the operator must re-sign-in (I will not enter
   credentials).
3. **G4 (A+ pack) and G5 (video):** no explicit authorization yet for the
   cloud/ComfyUI spend those need; the G1 plan card shows local-lane credits
   only. Operator must confirm spend limits before clicking Generate final or
   running a video job.
4. **D5 (rail rename):** not reproduced after the sticky-tab fix; needs one UI
   run to close or reopen.

## What is needed to resume

1. Operator clicks the Playwright extension icon in the "Work" Chrome window to
   reconnect the relay.
2. Re-run `node scripts/chromecontrol-agent.js preflight --profile "Profile 6"`
   and confirm `attachment_confirmed: true`.
3. Then re-run G1 from the composer using the agent CLI; the existing evidence
   slots (`reports/batch1-audit-20261024/product-tests/G1/`) and run-id/journal
   convention still apply.
4. Continue G2–G6 in order, recording artifact metadata, dimensions/duration,
   wall time, cost, and status per the brief's evidence set.

No push was performed. All changes are local commits.
