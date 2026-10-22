# Chrome Connect — profile recognition fix + MCP wiring (2026-10-22)

Chrome Connect **was installed** (`C:\Users\T2Hol\OneDrive\Documents\Default Project`)
but it was **not registered in this repository**, which is why the
`chromeconnect_*` tools did not exist in the session. Both problems are fixed.

## What was broken

### 1. Duplicate display names had no unique key
Chrome lets several profiles share a display name. This machine has **three**
called **"Work"**:

```
Default    "T2"                t2holdingsltd@gmail.com
Profile 1  "Ty"                mediablitz07@gmail.com
Profile 2  "Work"              t2holdingsltd2@gmail.com
Profile 3  "Work"              fishandcheeseent@gmail.com
Profile 4  "Mogra"             mograorganics@gmail.com
Profile 5  "The Johnsons"      mrandmrstj07@gmail.com
Profile 6  "Work"              northstarosllc@gmail.com
Profile 7  "Northstar Research"
```

Selecting by name was either a silent guess or a dead end.

### 2. The selection did not carry its Chrome installation
`resolveMcpArgs` passed `--profile-dir-name` without `--user-data-dir`, so a
profile resolved against one Chrome user-data directory could be attached inside
another. That is the "it picked the wrong profile sometimes" symptom.

### 3. Picker detection could never confirm a forwarded picker
Chrome forwards `--profile-picker` into the running instance, so the chooser
appears in an **existing** window. Detection only looked for a *new* window
handle and therefore always answered `no_visible_picker_window`.

## What changed

| area | change |
|---|---|
| profile rows | now carry `email` (from Local State `user_name`) and `user_data_dir` |
| resolver | order: directory → `#N` (1-based) → **email** → legacy 0-based index → display name |
| ambiguity | a duplicated name returns `ambiguous: true` with every candidate **and its email** — never a guess |
| selection | stores `extension_profile_email`, `extension_profile_display_name`, `user_data_dir` |
| MCP args | `--user-data-dir <root>` is passed before `--profile-dir-name` |
| CLI | `profiles` prints `[#N] [dir] "name" <email>`; `use-profile` reports *matched by* and the user-data dir |
| picker | one visible Chrome window after a picker request is reported as the picker surface (`single_window_after_request`) and raised |

## Evidence

Resolver matrix against the real installation:

```
"#4"                          -> Profile 3 via index
"Work"                        -> AMBIGUOUS via name:
                                 Profile 2/t2holdingsltd2@gmail.com,
                                 Profile 3/fishandcheeseent@gmail.com,
                                 Profile 6/northstarosllc@gmail.com
"mograorganics@gmail.com"     -> Profile 4 via email
"t2holdingsltd2@gmail.com"    -> Profile 2 via email      <- the right "Work"
"Profile 6"                   -> Profile 6 via directory
"nobody@example.com"          -> no match
```

Selection receipt:

```
Selected extension profile: Profile 4 "Mogra" <mograorganics@gmail.com> (matched by email)
  user data dir: C:\Users\T2Hol\AppData\Local\Google\Chrome\User Data
MCP args: --extension --user-data-dir <root> --profile-dir-name Profile 4
```

Picker, run directly in a fresh process:

```
{ "result": "picker_visible",
  "method": "single_window_after_request",
  "reason": "single_chrome_window_present_after_picker_request" }
```

Tests: `node test/profile-resolve-tests.js` → **10 passed** (directory, `#N`,
email, duplicate-name ambiguity, unique name, legacy index, unknown refs, MCP
args, empty selection, second installation). No browser required.

## MCP wiring for Northstar

Added `opencode.json` in this repository registering the same controller:

```json
{ "mcp": { "chromeconnect": {
  "type": "local",
  "command": ["node", ".../scripts/chromecontrol-mcp-server.js"],
  "environment": { "CHROMECONNECT_TRANSPORT_MODULE": ".../chromecontrol-playwright-bridge.js" }
} } }
```

It is the *same* controller, so the allowlist, Amazon blocklist and policy gates
are unchanged (guardrail fingerprint verified intact:
`75977709…25895c87`, matching the operator baseline).

## One thing you must do

**Restart this OpenCode session.** The old MCP server had cached the pre-fix
modules, so it was stopped to force a clean reload; the `chromeconnect_*` tools
return on the next start with the fixed code.

After the restart:

1. `chromeconnect_status` — expect `guardrails.intact: true`.
2. `chromeconnect_preflight` — expect the picker reported visible and the
   instruction to choose a profile.
3. Click your profile tile in Chrome and approve the Playwright extension.
4. `chromeconnect_run` with a read-only task, for example:
   *"Open https://sellersprite.com and report the page title and the first
   heading. Do not sign in, do not submit any form."*

## Rollback

- ChromeControl project (its own git repo): commit `1829de0`, plus
  `*.bak.20261022` beside every edited file.
- Northstar: delete `opencode.json` to unregister the MCP server; nothing else in
  the repo changed.
