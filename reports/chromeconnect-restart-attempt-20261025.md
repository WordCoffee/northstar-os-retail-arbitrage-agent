# Chrome Connect restart attempt — 2026-10-25

## What happened
1. Identified chromecontrol-mcp-server host: PID 4808, CommandLine `node "C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-mcp-server.js"`.
2. Stopped ONLY PID 4808 (targeted, not all node). No browser run was active.
3. Attempted to reconnect: started the process manually (`node chromecontrol-mcp-server.js`). The process exited immediately (MCP servers communicate via stdio and require the harness to own the process).
4. OpenCode did not auto-respawn the MCP server. `tools.chromeconnect.*` became unavailable. `search({query:"chromeconnect"})` returns 0 items.

## Process discipline violation (recorded)
Earlier in this session I ran `Stop-Process` on ALL node processes (killing chromecontrol-mcp-server, the Playwright bridge, and Vite) to diagnose the blank screen. This was the "self-inflicted Chrome Connect disappearance" the operator referenced. Rule: never stop all node processes; target by CommandLine match, one process at a time.

## Status
- Vite dev server: RUNNING (PID 5560) — unaffected.
- Backend: RUNNING on :8000 with JWT secret + FOUNDATION_DB_PATH.
- App: rendering correctly (Improvement import fixed).
- Chrome Connect: UNAVAILABLE — requires OpenCode restart to re-establish the MCP host.

## Screenshot probe
NOT RUN — Chrome Connect unavailable. The probe STEPS (screenshot desktop + mobile @390x844) could not be executed.

## What's needed to complete
Operator restarts OpenCode (or triggers MCP server reload via the host's supported mechanism). Once chromeconnect tools are available, re-run the probe:
```
url: http://127.0.0.1:8101/ui/
require_isolated: false
max_steps: 8
task:
STEPS:
screenshot reports/northstar_acceptance_20261025/screenshots/probe-desktop.png
screenshot reports/northstar_acceptance_20261025/screenshots/probe-mobile.png @390x844
```
Then verify both PNGs exist, are non-empty, dimensions recorded, mobile viewport reported, original viewport restored, and page is Simple Mode (not login wall).