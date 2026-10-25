# Batch 1 — requirements matrix (2026-10-24)

Scope: Simple Mode as the primary customer experience, proven through the visible
UI via Chrome Connect, plus the AutothinK Simple variant.

Status vocabulary (used exactly):
- **PASS (UI-verified)** — driven by typing/clicking Northstar's own controls in the
  browser through Chrome Connect, artifact inspected in the transcript.
- **FAIL** — ran through the UI and the observable result did not meet the bar.
- **BLOCKED** — could not be executed; exact reason recorded.
- **BACKEND-ONLY** — measured with python/curl/queue endpoints for diagnosis only;
  never counted as a pass.
- **untested** — no run attempted.

## Session / environment (step 0)

| Item | Value | How measured | Status |
|---|---|---|---|
| Signed in | Yes — "Operator", Subject "1" in the rail | Chrome Connect read of `http://127.0.0.1:8101/ui/` | PASS (UI-verified) |
| App mounted | Yes — title "NorthstarOS — Retail Arbitrage Suite", composer + rail + telemetry present | Chrome Connect read | PASS (UI-verified) |
| Backend healthy | `GET http://127.0.0.1:8000/health` → 200 | PowerShell probe | BACKEND-ONLY |
| ComfyUI running | `:8188` listening (pid 7504, `main.py --port 8188 --listen 127.0.0.1 --cache-none`) | `Get-NetTCPConnection` | BACKEND-ONLY |
| No active job | `{"queue_running": [], "queue_pending": []}` | `GET :8188/queue` | BACKEND-ONLY |
| RAM | 15.4 GB total, 3.9 GB free | `Win32_OperatingSystem` | BACKEND-ONLY |
| Disk C: | 67.12 GB free | `Get-PSDrive C` | BACKEND-ONLY |
| New session | Created by sending the G1 prompt; rail title is the prompt text, rename to `TEST-20261024` pending | Chrome Connect read | PARTIAL (see defect D5) |
| One heavy job at a time | Honoured (ComfyUI queue empty before the first run) | queue probe | PASS |

## Generations (operator brief, G1–G6)

| ID | Requirement | Evidence | Status |
|---|---|---|---|
| G1 | 3D pouch mockup → plan card → Generate draft → inline image artifact; then "apply the real Mogra Organics label" | Plan card rendered with draft/final options (screenshot `product-tests/G1/g1-02-plan-card.png`); the Generate click never executed | BLOCKED — Chrome Connect MCP server exited mid-run (see D1) |
| G2 | Portrait 896×1344 render with disclosed fitted dimensions (~816×1216) | none | BLOCKED — same controller outage |
| G3 | Main-style + lifestyle image; photo editing only with an approved store photo | none | BLOCKED — same controller outage |
| G4 | A+ pack (1464×600, 150×300, 200×200), save → reload → reopen | none | BLOCKED — same controller outage |
| G5 | 5-second ad, ONE job, measured real duration (2.04 s precedent) | none | BLOCKED — same controller outage |
| G6 | Tip calculator artifact, opened and driven with values | none | BLOCKED — same controller outage |

None of G1–G6 may be marked complete. No artifact claim is made for any of them.

## Visible defects found in this batch (see defects.md)

| ID | Defect | State |
|---|---|---|
| D1 | Chrome Connect MCP server exits; catalog loses `chromeconnect_*` tools | OPEN (controller, blocks all UI tests) |
| D2 | Display Scale control rendered twice side by side (`100%▾ 100%▾`) | FIXED (verified by build + shell gate, needs UI re-shoot) |
| D3 | Display scale applied with `zoom` on the same element that carries `height:100dvh` | FIXED (restructured; needs UI measurement) |
| D4 | Voice advertised as "live voice" while only dictation+spoken replies exist | FIXED (build + gate pass; label change is visible in the next screenshot) |
| D5 | Rail rename control does not open an input | OPEN (needs a UI run) |
| D6 | Controller reports `FAILED … typed_text_not_in_transcript` for a turn that plainly succeeded | OPEN (evidence-integrity defect in the controller) |
| D7 | Missing artifact had one collapsed state instead of four distinct ones | FIXED + unit-tested (`18 passed`) |

## Executable checks run in this batch

| Check | Command | Result |
|---|---|---|
| UI production build | `npm run build` | pass, 1.27 s, 0 errors (pre-existing chunk-size warning) |
| Shell/product gate | `HARNESS_BASE_URL=http://127.0.0.1:8101/ui/ node verify-shell-v3.cjs` | **28 passed, 0 failed** |
| Backend chat/plan tests | `python -m pytest test_chat_plan.py -q` | **18 passed** |
| Chrome Connect controller tests | `node test/chromecontrol-tests.js` | **78 passed, 0 failed** |

A gate pass is not a UI product test. It is not counted as evidence for G1–G6.
