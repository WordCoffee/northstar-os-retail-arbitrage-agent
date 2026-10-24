# Native Picker + Live Attachment Check — 2026-10-04

**Authorized scope:** enable picker-on-demand; launch the native picker; operator
selects profile + approves extension; use the operator-selected directory for this
session only; verify the live connection; resume preflight.

**Not done:** no cookie/credential/session-DB access; no profile creation/clearing/
replacement/autonomous selection; no Chrome shutdown; no Alibaba navigation,
supplier research or allowlist change; no dependency upgrade; no token-based
auto-approval.

---

## Capability check (before connecting)

Installed `@playwright/mcp` **0.0.83** supports both:
- CLI `--profile-dir-name <name>` ("name of the profile directory in the user data
  dir to connect to with --extension … Defaults to the last used …")
- env `PLAYWRIGHT_MCP_PROFILE_DIR_NAME`

Used via `--profile-dir-name` for **this session only** (env
`CHROMECONNECT_SESSION_PROFILE_DIR`, never config, never last-used). No upgrade.

## Flow observed

1. `CHROMECONNECT_PICKER_ON_DEMAND=1` set in `opencode.jsonc` (chromeconnect env).
2. Native picker launched (`launchChromeDeElevated` / Explorer de-elevation). The
   picker browser process (PID 73516) kept its original command line
   (`--profile-picker …`) — it declares no `--profile-directory`, so process-diff
   cannot name the selection.
3. Operator selected a profile; extension status window present.
4. First attempt showed **no approve button** because the pinned `--extension`
   server was not yet listening. Started it:
   `node @playwright/mcp/cli.js --extension --profile-dir-name "Profile 7"`.
5. Extension approved; the pinned session read the current page successfully.

---

## The six items

**1. Operator-selected profile.** `Profile 7` — display name **"Northstar Research"**,
Chrome identity signed out. Basis: native-picker selection (fresh `active_time`
266 s, corroborated by `last_used`), then confirmed by the pinned session actually
connecting. (Not a hard-coded default: the selection came from the operator's
picker click.)

**2. Configured transport target.** Session argv:
```
node …\@playwright\mcp\cli.js --extension --profile-dir-name "Profile 7"
```
Persistent-session key `Profile 7`, child PID 5924, tools=25. Configuration/selection
is **not** attachment proof.

**3. Observed live connection and binding evidence.** The pinned session executed a
browser action and the extension in Profile 7 answered:
```
url   = chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html
title = Playwright Extension Status      (text length 260; content not read)
```
Relay window present; exactly one Chrome browser process. → attachment **VERIFIED**.

**4. Chrome identity.** `signed_out` (authoritative `Local State`
`profile.info_cache["Profile 7"].user_name === null`).

**5. Site-authentication evidence.** `UNKNOWN` — no target site was opened; the
current tab is the extension status page. Nothing inferred.

**6. Overall isolation status.** `isolated: false` → **UNKNOWN**.
`browser_attachment: verified`; `failed_checks: []`;
`unavailable_checks: [browser_process_identity, no_sensitive_session_cookies]`.
- `browser_process_identity` UNKNOWN: the picker-launched browser declares no
  `--profile-directory` (unavailable evidence, not a conflict).
- `no_sensitive_session_cookies` UNKNOWN: cookie metadata inspection not authorized.

---

## Remaining gate

Attachment is now **proven** — the transport capability that was missing is no
longer missing (`--profile-dir-name` works and bound the session to the operator's
profile). Overall isolation stays UNKNOWN only because:

1. `no_sensitive_session_cookies` is a required gate but is **not authorized**
   (I am not requesting that permission to force a pass), and
2. `browser_process_identity` is UNKNOWN by construction in picker mode.

This is now a **policy** decision, not a missing capability. No redesign performed.
Selection preserved for this session only; `config/chromecontrol.json` unchanged;
Chrome left running.