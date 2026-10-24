# Isolation & Attachment Correction Pass — 2026-10-04

**Scope:** correct the Chrome Connect profile-isolation implementation before any
further research. No supplier page was opened. No credential/session inspection
was added. No policy table, allowlist or guardrail fingerprint was changed.

**Files changed (owner project `Default Project`):**

| File | Change |
|---|---|
| `lib/chromecontrol/profile-isolation.js` | Rewritten evidence semantics: fail-closed cookie check, authorization gate, removed DB copy fallback, demoted corroboration, separated Chrome identity / attachment / cookie states. (backup `.bak.20261004`) |
| `scripts/chromecontrol-playwright-bridge.js` | `runVerifyIsolation` no longer auto-binds `expect` and no longer fabricates `liveAttachment.profile_directory`; attachment profile comes from the relay process only. Added `launchProfilePicker()` (native picker; no kill). (backup `.bak2.20261004`) |
| `scripts/chromecontrol-mcp-server.js` | Preflight surfaces the native picker on demand when no profile is selected; corrected instruction text. |
| `test/sourcing-policy-tests.js` | Rewritten isolation tests + 8 new regressions. (backup `.bak.20261004`) |
| `test/preflight-validation.js` | Assertions now match the corrected evidence model. |
| `test/cookie-inspect.js`, `test/cookie-names.js` | **Removed** — standalone unauthorized cookie-DB readers. |

---

## 1. False-pass logic removed

- **Locked/unreadable cookie store** now returns `available:false`
  (`cookie_store_unreadable`). It can never be read as clean.
- **Absence of a hand-written auth-cookie name is no longer a pass.** A readable
  store with sensitive-host cookies that do not match the indicator list is
  reported as `unclassified` and left **UNKNOWN**, never "no session".
- **`last_used` + activation + single-instance corroboration no longer
  satisfies any check.** They are recorded as `corroborating_signals` only.
- **The bridge no longer fabricates evidence.** Previously
  `runVerifyIsolation` set `liveAttachment.profile_directory = expect.directory`
  whenever any extension window existed, and auto-bound `bound.profile = expect`.
  Both were false passes; both are removed.

## 2. Evidence semantics (separated states)

| State | Field | Values |
|---|---|---|
| Chrome browser identity | `chrome_identity` | `signed_in` / `signed_out` / `unknown` |
| Browser↔profile attachment | `browser_attachment` | `verified` / `mismatch` / `unknown` |
| Cookie indicators | `no_sensitive_session_cookies.observed` | `known_authentication_related` / `unclassified_sensitive_hosts` |
| Overall isolation | `isolated` | true only when every check is available **and** passes |

`browser_process_identity` is process-level evidence only. `extension_attachment_profile`
requires the live connection to *report* the expected directory.

## 3. Access expansion stopped

- Removed the whole-cookie-database **copy fallback** (`copyFileSync` + temp dir).
  Only an in-place read-only open remains.
- Cookie metadata inspection is now gated behind
  `CHROMECONNECT_COOKIE_METADATA_AUTHORIZED=1`. Without it the check is
  `cookie_metadata_inspection_not_authorized` (UNKNOWN). "Names only" is no longer
  assumed to be permission.
- No new credential/session inspection mechanism added. No Google/PayPal/account
  page was visited to probe login state.

## 4. Attachment proof corrected

Inspected bridge/session APIs: `runningChromeProfiles()` (process cmdline),
`PersistentMcpSession.report()` (no profile field), `verifyAttachment()` (process
heuristic). There is **no** API by which the extension itself reports a profile
directory. The closest trustworthy association is the relay chrome process's own
`--profile-directory`; that is used when present, otherwise attachment is UNKNOWN.
Conflicting-profile and multi-window-in-one-process cases are covered by tests.

## 5. Browser flow

`launchProfilePicker()` wraps the existing `profile-flow` native picker. The bridge
never creates, clears, replaces or hard-codes a profile and never kills Chrome. An
existing valid selection (`Profile 7`) is preserved. With
`CHROMECONNECT_PICKER_ON_DEMAND=1`, preflight surfaces the picker instead of asking
the operator to open a profile by hand.

## 6. Tests run

| Suite | Result |
|---|---|
| `node --check` × 4 changed files | 0 errors |
| `test/sourcing-policy-tests.js` | **40 passed, 0 failed** |
| `test/chromecontrol-tests.js` | **58 passed, 0 failed** |
| `test/orchestrator-tests.js` | **63 passed, 0 failed** |
| `test/agent-loop-tests.js` | **145/145** |
| `test/mcp-session-tests.js` | **27/27** |
| `test/run-tests.js --no-browser` | **15 passed, 0 failed** |
| `test/preflight-validation.js` (offline) | **21/21** |
| `assertGuardrailsIntact()` | `3595c933…` unchanged |

New regressions: locked store unavailable; unclassified names not "no session";
missing auth-name match does not prove logged out; known auth cookie fails;
shared process / multiple profile windows; `last_used` match while extension
attaches elsewhere; browser absent after shutdown; no credential-DB copying;
no unauthorized inspection; no autonomous profile selection.

## 7. Remaining gate (UNRESOLVED)

Live preflight now reports honestly:

```
isolated: false            chrome_identity: signed_out
browser_attachment: unknown
failed_checks:      [browser_process_identity, extension_relay_present]
unavailable_checks: [no_sensitive_session_cookies, extension_attachment_profile, no_profile_fallback]
verdict: cookie_metadata_inspection_not_authorized; extension_profile_not_reported;
         browser absent; no transport binding
```

Three independent evidence gaps, all outside what code may self-grant:

1. **Cookie metadata inspection not authorized** → `no_sensitive_session_cookies`
   is UNKNOWN. Smallest authorization: set
   `CHROMECONNECT_COOKIE_METADATA_AUTHORIZED=1` (host_key + name only; values are
   never read or copied), or supply independent signed-out evidence.
2. **No live attachment evidence** → the extension must be connected in the
   selected window so the relay process reports its `--profile-directory`.
3. **Chrome is not running** → no browser process, no relay. The native picker can
   be surfaced automatically (`CHROMECONNECT_PICKER_ON_DEMAND=1`); the operator
   selects the profile in the picker, never manually opening one.

No supplier research was performed; the isolation gate genuinely cannot pass yet.

## 8. No expansion

No allowlist/origin was added. No account action, purchase, listing, pricing or
transaction. No supplier certification was claimed. The commerce guardrail
fingerprint is unchanged.
