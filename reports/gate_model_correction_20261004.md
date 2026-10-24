# Scoped Gate-Model Correction — 2026-10-04

**Scope:** one gate-model correction. No research started. No target-site
navigation, supplier research, allowlist change, profile change, browser
shutdown, account action, or configuration persistence. No cookie metadata
inspection capability. Target-site signed-out status is NOT claimed.

## 1. Changed files (this pass)

| File | Change |
|---|---|
| `lib/chromecontrol/profile-isolation.js` | Added `class` (REQUIRED / SUPPORTING_ONLY) + `evaluated` to every check; added REQUIRED `transport_profile_binding`; reclassified `browser_process_identity` and `extension_attachment_profile` to SUPPORTING_ONLY; `no_profile_fallback` REQUIRED and evaluated only when the process owns a session; rewritten `summarise()` to gate on REQUIRED only and expose classifications. |
| `lib/chromecontrol/mcp-session.js` | Per-session `sessionNonce` (connection-instance id) + `lastToolCallOk` (set when the extension answers a tool call); both in `report()`. |
| `scripts/chromecontrol-playwright-bridge.js` | `currentTransportBinding()` now returns liveness, `--extension`/`--profile-dir-name` argv flags, nonce, and `extension_answered`; `available` is true only in a session-owning process; wired into `runVerifyIsolation`. |
| `scripts/transport-evidence.js` | Updated for the async binding + gate classifications. |
| `scripts/gate-model-report.js` | New read-only verdict generator. |
| `test/sourcing-policy-tests.js` | Gate-model tests (REQUIRED blocks; SUPPORTING_ONLY never blocks; NOT_EVALUATED without a session). |

## 2. The required check

`transport_profile_binding` passes only when ALL hold:
configured dir == bound dir == expected; active session key == expected;
MCP child PID alive; child argv has `--extension` AND
`--profile-dir-name <expected>`; a non-empty session nonce identifies the live
connection; the extension answered one harmless current-page metadata action.

Evaluated **only** in the session-owning process. A process that owns no active
session reports it `NOT_EVALUATED` (never judged UNKNOWN/FAILED).

## 3. Test commands and results

| Command | Result |
|---|---|
| `node --check` × 5 changed files | 0 errors |
| `node test/sourcing-policy-tests.js` | **43 passed, 0 failed** |
| `node test/mcp-session-tests.js` | **27/27** |
| `node test/chromecontrol-tests.js` | **58 passed, 0 failed** |
| `node test/orchestrator-tests.js` | **63 passed, 0 failed** |
| `node test/agent-loop-tests.js` | **145/145** |
| `node test/run-tests.js --no-browser` | **15 passed, 0 failed** |
| `node test/preflight-validation.js` (offline) | **21/21** |
| `node scripts/gate-model-report.js` | final verdict (below) |

Live note: a fresh `scripts/transport-evidence.js` run timed out because the
Profile 7 extension window was no longer open at that moment (visible Chrome
windows were "Welcome" / "OpenCode"). No fresh live read is available now, so the
verdict uses the **last observed verified session evidence** for the transport
binding/relay and **live** Local State + live (unauthorized) cookie state.

## 4. Gate classification

| Gate | Class | Status |
|---|---|---|
| `local_state_readable` | REQUIRED | VERIFIED |
| `selected_directory_exact` | REQUIRED | VERIFIED |
| `display_name_exact` | REQUIRED | VERIFIED |
| `chrome_signed_out` | REQUIRED | VERIFIED (signed_out) |
| `extension_relay_present` | REQUIRED | VERIFIED |
| `no_sensitive_session_cookies` | REQUIRED | **UNKNOWN** |
| `transport_profile_binding` | REQUIRED | **VERIFIED** |
| `no_profile_fallback` | REQUIRED | VERIFIED |
| `browser_process_identity` | SUPPORTING_ONLY | UNKNOWN (non-blocking) |
| `extension_attachment_profile` | SUPPORTING_ONLY | UNKNOWN (non-blocking) |

`required_failed: []` ; `required_unavailable: [no_sensitive_session_cookies]` ;
`required_not_evaluated: []`.

## 5. Final result

`overall_isolated: false` (UNKNOWN). **Cookie evidence is explicitly UNKNOWN**
(`cookie_metadata_inspection_not_authorized`). That single REQUIRED gate is the
only thing preventing a VERIFIED isolation verdict. No cookie permission was
requested; the gate was not altered.

Strict controls preserved: no cookie/storage inspection, no navigation, no
supplier research, no allowlist change, no profile change, no browser shutdown,
no account actions, no configuration persistence. Target-site signed-out status
is not claimed.