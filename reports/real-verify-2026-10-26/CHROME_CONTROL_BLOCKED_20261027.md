# Chrome Control Binding — BLOCKED (2026-10-27)

## Status
**BLOCKED.** The isolated signed-out "Chrome Control" profile cannot be used with Chrome Control because the Playwright MCP Bridge extension is not installed in it.

## Evidence
1. Native picker launched successfully (`picker_visible=true`) with all Chrome windows closed.
2. Operator selected the signed-out "Chrome Control" profile tile.
3. `profile-selected` advanced state to `awaiting_extension_connection`.
4. Operator reported clicking the Playwright extension and pressing Connect/Approve.
5. `connect-extension` returned `awaiting_extension_approval` (resumed: false).
6. Filesystem check: `C:\Users\T2Hol\AppData\Local\NorthstarOS\ChromeResearchProfile\Default\Extensions` contains **0 entries**. The Playwright MCP Bridge CRX is not installed in the signed-out profile.
7. The extension IS installed in business Profile 6 (`jambeljnbnfbkcpnoiaedcabbgmnnlcd` present), but Profile 6 is signed-in (northstarosllc@gmail.com) and is explicitly excluded by the operator's session instruction ("Profile 6 is NOT acceptable — it is authorized-but-not-isolated").
8. Chrome Connect refuses non-isolated profiles (proven earlier: "profile is not an isolated research profile").

## What is needed to unblock
Install the Playwright MCP Bridge CRX into `C:\Users\T2Hol\AppData\Local\NorthstarOS\ChromeResearchProfile\Default` (the signed-out "Your Chrome" profile), then retry the picker flow. No credential, config edit, or profile copy is required — just the extension installation in the isolated profile.

## What was NOT done (per guardrails)
- Did not use Profile 6 or any business profile.
- Did not edit `config/chromecontrol.json`.
- Did not copy extension folders between profiles.
- Did not kill any Chrome process.
- Did not read, print, or store any credential or token.

## Artifacts produced this session (non-browser, verified)
- T1: `ns-t1-klein_00001_.png` (1.4 MB, 21.1 s)
- T3: `ns-t3-main-2000_00001_.png` (24.1 s)
- T4: `ns-t4-lifestyle_00001_.png` (12.1 s)
- T5: `ns-t5-aplus_00001_.png` (15.1 s)
- Render safety: 37/37 tests passed.
- Encoder pairing: 9B + 8B / 4B + 4B enforced.
- C3: 6/6 routes, 0 errors, 0 axe, 0 external.
- ComfyUI: UP on 8188 (venv Python).
- Ollama: restarted (CPU mode, `OLLAMA_NUM_GPU=0`).
- Token: written to `.env` (not printed).

## Commits
e0e83199, 2086ebb4, 04042103, f2d45faf, 01d97bfb, d867c689
