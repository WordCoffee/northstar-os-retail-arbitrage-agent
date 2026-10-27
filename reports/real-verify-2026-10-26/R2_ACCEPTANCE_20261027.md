# MOGRA Acceptance Battery — 2026-10-27 (R2 corrected)

Status: **BLOCKED on browser profile binding / manual auth**. Non-browser deliverables (safety stack, encoder trace, C3 unauthenticated surface) are VERIFIED and committed.

## Scope
T1–T8 MOGRA creative battery + C3 (creative surface audit) + C4 (fix C3 findings) + C5 (Product Designer Studio re-audit) against the authenticated Design Studio on `127.0.0.1:8000/ui`, plus render-safety hardening (cross-process lock, safe stop-list, encoder pairing guard).

## Commits in scope
- `e0e83199` — fix: remove stray `PY` identifier in `ChromeConnect.jsx` (SPA crash on all creative routes).
- `2086ebb4` — fix(studio): cross-process render lock, safe stop-list, encoder pairing guard.

## Verified (non-browser)

### Render safety stack (`Northstar_backend/studio_generation.py`)
- `_CrossProcessRenderLock`: file-based lock (`.studio_render.lock`) with `fcntl`-equivalent semantics via `msvcrt`/`fcntl`, PID liveness check, stale reclamation after `max_render_time + 60s`, never restores/replays an ambiguous timed-out job.
- Timed-out render keeps the lock and writes `status="orphaned"` to the state file; `restore_pending_session()` runs at app startup (wired in `main.py` lifespan) and only reports, never replays.
- Stop-list limited to owned idle inference processes (`llama-server`, `llama-cli`, `llama.cpp`, `ollama_llama_server`, `ollama`). Docker/infra/product listener/Chrome/OpenCode explicitly excluded (regression test `test_studio_ram_gate.py` asserts `dockerd.exe` is NOT stopped).
- `RenderSession.mark_render_started/finished`, crash recovery, duplicate-submission rejection all wired into `generate_image`/`generate_video`.
- Tests: `test_render_session.py` 11 passed, `test_model_compat.py` 11 passed, `test_studio_ram_gate.py` 8 passed, `test_studio_render_guard.py` 7 passed. Total 37 passed this session.

### Encoder pairing (production config)
- 9B lane: `Flux-2-Klein-9B-KV-Q8_0.gguf` + `qwen_3_8b_fp8mixed.safetensors` (enforced by `validate_configured_pairing`).
- 4B lane: `flux-2-klein-4b-Q8_0.gguf` + `qwen_3_4b_fp8_mixed.safetensors`.
- `resolve_text_encoder` rejects mismatched pairs with a clear error (e.g. `mat1 512x7680 vs weight 12288x4096` crash prevented).
- Production call paths all route through `sg.generate_image`: `chat_tools._t_generate_image` (line 392), `design_studio_api.py` (line 1957), `creative_execute.py` → `chat_tools.run_tool("generate_image")`. No alternate graph bypasses the guard.

### C3 creative surface audit (unauthenticated)
Route loads re-verified on `127.0.0.1:8000` (real bundle, `dist/` rebuilt 2026-10-26 23:35) for all six creative rooms:

| Route | status | console errors | external requests | axe | h1 | main | bodyLen |
|---|---|---|---|---|---|---|---|
| /design-studio | 200 | 0 | 0 | 0 | 1 | 1 | 281 |
| /creative-studio | 200 | 0 | 0 | 0 | 1 | 1 | 281 |
| /socialpulse | 200 | 0 | 0 | 0 | 1 | 1 | 281 |
| /listingforge | 200 | 0 | 0 | 0 | 1 | 1 | 281 |
| /adpilot | 200 | 0 | 0 | 0 | 1 | 1 | 281 |
| /product-designer | 200 | 0 | 0 | 0 | 1 | 1 | 281 |

`bodyLen=281` on every route = the unauthenticated sign-in gate shell. Route-level accessibility is clean; the actual creative workspace is NOT visible without auth (see BLOCKED).

### Resource telemetry (baseline, no render executed)
- RAM: 15791 MB total, 5516 MB free (65.1% used).
- Swap: 21714 MB total, 3170 MB used.
- GPU (nvidia-smi): 16303 MiB total, 10920 MiB free, 5084 MiB used.
- VRAM/commit-during-render: UNAVAILABLE (no render executed this pass).

### Smoke artifacts (prior session, VERIFIED real)
- `ns-smoke-klein_00005_.png` (~1.37 MB), `ns-smoke-wan_00013_.mp4` (832×480 h264, 2.04 s), `ns-smoke-tts_00009.flac` (24000 Hz, 6.54 s).

## Blocked

### B-AUTH / B-BROWSER — Chrome Control profile binding (BLOCKED)
Chrome Connect (`chromeconnect_preflight` with `require_isolated: true`) formally reports `isolated_signed_out_satisfied: false`.

Evidence:
- Bound profile directory = `Default` in `C:\Users\T2Hol\AppData\Local\Google\Chrome\User Data` (the business Chrome user-data-dir), display name `T2`, signed-in identity `t2holdingsltd@gmail.com`.
- Required checks failed: `display_name_exact` (observed `T2`, expected `Your Chrome`), `chrome_signed_out` (signed-in `t2holdingsltd@gmail.com`). `no_sensitive_session_cookies` UNAVAILABLE (cookie inspection not authorized).
- `selection_source: config_pin` — the pin is `Default`/T2, which is the defect the orchestrator code comment describes.
- `ChromeResearchProfile\Default` (signed-out `Your Chrome`, the profile the preflight expects) has **no extensions** installed, so the Playwright MCP Bridge never answers there.
- The native picker (`scripts/chromecontrol.js launch-picker`) is launched with **no `--user-data-dir`**, so it can only ever open the business Chrome and its profile tiles; it structurally cannot reach `ChromeResearchProfile`.
- `start-browser.ps1` (the approved automation launcher) successfully launched `ChromeResearchProfile` on CDP 9222 in this session, but the operator closed that window (CDP 9222 now down) and reported it opened "a random profile".

Operator constraints honored: business profile T2 was never used for navigation; no credentials were read; `config/chromecontrol.json` was not edited; no persistent pin was created.

Required operator action to unblock: install the Playwright MCP Bridge CRX into `C:\Users\T2Hol\AppData\Local\NorthstarOS\ChromeResearchProfile\Default` (signed-out `Your Chrome`) and confirm, OR approve running the T1–T8 battery against `127.0.0.1:8000` using the repository's localhost-only Playwright Test exception (`tests/e2e/` entry points, all URLs `127.0.0.1`), with the operator signing in manually in the automation Chrome window. No credential value is requested or recorded in either case.

### T1–T8 battery — NOT RUN (blocked on auth)
T1 pouch render, T2 compositor label, T3 2000×2000 MAIN + readiness, T4 lifestyle, T5 A+ 1464×600, T6 dieline/prepress, T7 Wan+Piper mux with measured playback, T8 vision QC, plus refresh-persistence check — all require an authenticated session in Design Studio. None executed this pass.

### C5 Product Designer Studio re-audit — NOT RUN (blocked on auth)
C3/C4 results above are unauthenticated route-level only. "Actual workspace visible" (the C5 criterion) requires auth and was not verified.

## C4 findings
No defects found in the unauthenticated creative surface (0 axe violations, 0 console errors, 0 external requests on all six routes after the `PY` removal). C4 = no code changes required in this pass; the only C3 defect (stray `PY` SPA crash) was already fixed in `e0e83199`.

## SeedVR2 / FLUX 3 exclusions (preserved)
- SeedVR2: UNSUPPORTED-WITH-REASON (missing custom nodes) — untouched.
- FLUX 3 Image Klein: SKIPPED-WITH-REASON (weights absent on disk; `STUDIO_USE_FLUX2=1` fallback) — untouched.
- No arbitrary node installs performed.

## Changed files (this pass)
- `northstar-os-ui/src/pages/internal/ChromeConnect.jsx` (PY removal) — committed `e0e83199`.
- `Northstar_backend/studio_generation.py`, `main.py`, tests — committed `2086ebb4`.
- This report + `00_STATE.json` update — pending commit.

## Remaining blockers / approvals (unchanged from prior state)
B11/B12/B14 (operator actions), Unwrangle credit replenishment, SeedVR2 custom nodes, FLUX 3 weights, DataForSEO adapter repair — all outside this pass.
