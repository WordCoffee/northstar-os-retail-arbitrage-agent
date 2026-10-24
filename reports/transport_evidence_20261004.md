# Transport-Binding Evidence Pass — 2026-10-04

**Scope:** final read-only transport-evidence pass. Unchanged: Profile 7 session,
Chrome running, per-session `--extension --profile-dir-name "Profile 7"` routing,
no cookie authorization, no profile changes/shutdown/allowlist change/navigation/
supplier research/sign-in/account action.

## Invariant added (narrowly scoped)

`PersistentMcpSession` now carries a non-sensitive `session_nonce`
(connection-instance id). The bridge exposes `currentTransportBinding()`, which
ties the **active session key** to the **actual Playwright MCP server OS process**
and records whether that process's command line carries the profile pin.

Captured fields (non-sensitive only): configured profile directory, bound profile
directory, session key, session nonce, MCP child PID, MCP session state, and a
boolean for `--profile-dir-name <dir>` on the child argv. No tokens, cookies,
credentials, storage, page content or extension status-page text is read.

Files touched: `lib/chromecontrol/mcp-session.js`, `scripts/chromecontrol-playwright-bridge.js`
(new `currentTransportBinding()`, included in the isolation report), `scripts/transport-evidence.js` (new, read-only).

## Result — the six items

**1. Configured profile directory.** `Profile 7`.

**2. Bound session key and MCP child PID.** Session key `Profile 7`; MCP child PID
`79264` (re-run), prior pass `65044`.

**3. Observed extension connection state.** `CONNECTED`; the extension answered a
harmless read of the current page on the first attempt (`url_present: true`,
`title_present: true`, `text_length: 260` — content not read).

**4. Direct bridge-to-active-transport association.** **VERIFIED.**
```
configured_profile_directory : Profile 7
bound_profile_directory      : Profile 7
session_key                  : Profile 7
session_nonce                : 0970015e803bc597   (prior pass c61019b8f23f14a2)
mcp_child_pid                : 79264
mcp_session_state            : CONNECTED
child_argv_has_profile_pin   : true
association                  : VERIFIED
```
The active session key is bound to a live OS process launched with
`--extension --profile-dir-name "Profile 7"`, and that process's extension answered.

**5. Remaining isolation gates (live preflight, server process holds no session):**

| Gate | Status |
|---|---|
| `local_state_readable` | VERIFIED |
| `selected_directory_exact` | VERIFIED |
| `display_name_exact` | VERIFIED |
| `chrome_signed_out` | VERIFIED (chrome_identity = signed_out) |
| `extension_relay_present` | VERIFIED |
| `browser_process_identity` | **UNKNOWN** (picker-launched browser declares no `--profile-directory`) |
| `no_sensitive_session_cookies` | **UNKNOWN** (not authorized — unchanged) |
| `extension_attachment_profile` | **UNKNOWN** (extension does not self-report a directory) |
| `no_profile_fallback` | **UNKNOWN** in the server-process preflight (no active session bound there); VERIFIED only inside the session-owning process |
| failed_checks | none |
| **overall `isolated`** | **false → UNKNOWN** |

## Notes

- `extension_attachment_profile` stays UNKNOWN by design: the association proven
  here is bridge→child-argv pin + extension answered, **not** the extension
  self-reporting its directory. These are different evidence classes.
- The transport-binding invariant is VERIFIED in the process that owns the active
  session. The OpenCode MCP server's `chromeconnect_preflight` evaluates in a
  process that holds no session, so it reports `no_profile_fallback` and
  `extension_attachment_profile` UNKNOWN there.
- The cookie-evidence gate is unchanged and overall isolation is **not** claimed
  verified.
- Chrome left running (browser PID 73516); no lingering MCP child; no profile,
  allowlist or config change.