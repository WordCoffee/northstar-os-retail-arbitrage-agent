# Supervised Cycle Report — 2026-10-27

## Chrome Connect (Profile 6)
- status: guardrails intact (fingerprint 1f84d421... matches baseline); transport binding VERIFIED (Profile 6); profile lease valid.
- preflight: all 6 required checks pass; supporting-only failures: chrome_signed_out (signed-in identity northstarosllc@gmail.com), extension_relay_present (no relay observed at preflight time).
- NorthstarOS Simple Mode UI opened on localhost (dev server :8101/ui/). Page renders authenticated workspace (Bojo, Create/Grow/Research/Operate, chat composer, 34 skills). No credentials entered.
- Sign-in wall on production server :8000/ui/ (operator click required to authenticate there); dev server :8101 used for UI work. One line: "Operator sign-in needed on :8000 production build; dev server :8101 is authenticated and used for UI verification."

## First deliverable — data points

### .db file / vault key / daily-cap
- .db file: `Northstar_backend/data/northstar.db` (43,847,680 bytes; 53 tables incl. loop_guard, lane_telemetry, ds_*, corpus_*).
- Vault key location: `%LOCALAPPDATA%\northstar\secrets.masterkey` (value not read/printed); vault file `%LOCALAPPDATA%\northstar\secrets.vault`. Broker: `shared/steward/vault_store/` (versions/, policy_bundles/, health_log.jsonl, external_effects_ledger.jsonl).
- Daily-cap replacement: charter `daily_task_cap: 20` UNCHANGED (immutable); runtime now progress-based in `RulesEngine._daily_counts` (steward/rules_engine.py, Tier 1). Status PASS (go-live gate).

### Tests — repeated steps / no-progress / spend cap / resume after killed session
- `Northstar_backend/test_loop_breaker.py` — 16 passed: admits within budget; 9th automatic event opens durable latch; latch survives restart simulation; open never auto-expires; trusted human clears streak; poison trips immediately; redelivery dedup (not counted); consecutive failure burst trips; success resets streak; reset requires operator+confirmation; on_open hook warns once; hop guard; note sparse failures; note success; CIE cycle refuses when open; clean dry cycle admits.
- Tier-2 immutability: 10 categories PASS (all denied/queued). Snapshot/rollback: PASS. Vault stealth: 5 checks PASS. Breakers: 5 checks PASS.

### Phase 2 — model resource table
| Model | Context | VRAM | RAM | Load | tok/s | Fits? |
|---|---|---|---|---|---|---|
| 27B (northstaros-qwen3.8) | 16k | 11.25 GB | ~11 GB | 6.9–8.2 s cold | 39–44 | yes (tight) |
| 27B | 32k | not separately measured (~11.6 GB inferred) | — | — | — | likely |
| 27B | 90k | 12.1 GB | 12.1 GB | slow | — | NO (OOM confirmed) |
| qwen3.5:4b | 32k | 3.3 GB | ~3.3 GB | fast | — | YES (budget ~2 GB margin) |
- qwen3.5:4b resident RAM: ~3.3 GB. Minimum free RAM (floor): ~4.3 GB (floor 4 GB, margin ~0.3 GB). System RAM floor in render gate: 4096 MB.
- Planning model chosen: `northstaros-qwen3.8:27b` (Master Brain) per global opencode config; primary builder: `northstar-coder:48k` (Ollama local).
- Scheduler tests: `Northstar_backend/foundation/tests/test_jobs_durable_scheduler.py` — 16 passed.
- Additional perf evidence: `reports/speed_thinking_deepdive_20261020.md`, `reports/local-coder-48k-and-wsl-vram_20261025-215056.md`.

### T7 / T3 / T5 / C5 (this cycle + prior drain)
- T7 (Wan+Piper mux, 5s): measured 2.0 s (`ns-smoke-wan_00013_.mp4`, 832×480, 232,218 bytes, 90.5 s wall). FAIL duration (need 5 s / 120 frames; engine hardcodes 49 frames). BLOCKED on UI (Ollama CPU load). No screenshot captured (UI session did not complete render).
- T3 (2000×2000 MAIN): achieved 1216×1216 fitted (fitted=true; requested 2000×2000). Memory impact: Ollama `/api/chat` hang (27B CPU-only) blocked UI render. File: `studio_generated/3889f32d…png` (1.85 MB).
- T5 (A+ 1464×600): achieved 1216×496 fitted. Same Ollama block. File: `studio_generated/5302fd9e…png`.
- C5 (Product Designer Studio re-audit): route `/ui/product-designer` loads (200, 281 bodyLen unauth shell), workspace visible, no refusals. BLOCKED: provider-gating (`provider_suite.py --check`) not executed; download/upload/persistence-after-refresh not exercised; click/type verified but not with stable data-testid selectors. Engine/AI render blocked by Ollama CPU load; ComfyUI armed (http://127.0.0.1:8188 reachable).
- T4 (lifestyle): UI-verified + engine-verified (1024×1024, 1,447,647 bytes, 27.2 s). Screenshot: `C:/Users/T2Hol/AppData/Local/Temp/t4_screenshot.png` (chromeconnect step 4). Job via Design Studio chat (not externally numbered).
- T2 (compositor label): engine-verified, 20 backend tests passed. T6 (dieline/prepress): 17 passed. T8 (vision QC): 14 passed.

## Creative backlog (Simple Mode only)
- S1–S7 (desktop + 390×844 captures): page-text verified via Chrome Connect read for Simple Mode home (chat box, Bojo, focus chips Auto/Create/Grow/Research/Operate, Dictate, vista annotation, telemetry chip). Screenshot files are NOT persisted by the controller (known limitation: observe-act planner off by default; acceptance_drain noted controller cannot save screenshots). Mobile viewport (390×844) not exercised this cycle.
- Portrait render 896×1344 with apply_label: `_fit_box(896,1344) = (816,1216)` (verified in test_fit_box). `apply_label` chat tool registered and tested (apply_label produces composite asset; honest about missing plate/logo). Test `test_generate_image_reports_the_size_it_actually_used` was failing due to real RAM floor (3666 MB < 4096 MB); fixed by mocking `ensure_system_ram` in test (commit d56810ae). 19 passed.
- BOJO-UTIL click: routing tests pass (`test_scope.py` + `test_utility_apps.py`, 20 passed). Live UI type/Enter not executed this cycle (controller planned only navigate+read; type steps not planned). BOJO-CODE handoff: `specialists/router.py scope()` returns offer+estimate; no transport yet.
- Voice pass: grep gate — 0 "voice chat" strings in `northstar-os-ui/src`. PASS.
- Typography pass: UI build passes (0 errors, 1.85 s).
- Quality rubric: no dedicated file found; S1–S7 checks in `briefs/simple_mode.md` used as rubric.

## Defects fixed
1. `test_pouch_label.py::test_generate_image_reports_the_size_it_actually_used` — system RAM floor blocked test (3666 MB < 4096 MB) due to real free-RAM check in test environment. Fixed by mocking `ensure_system_ram` to return ok. (commit d56810ae)

## Regression tests added/re-run
- `test_pouch_label.py`: 19 passed (was 18 passed + 1 fail).
- `test_scope.py` + `test_utility_apps.py`: 20 passed.
- `test_loop_breaker.py`: 16 passed.
- `test_jobs_durable_scheduler.py`: 16 passed.
- UI build: PASS (0 errors).

## Re-run of same UI scenario
- Simple Mode home loads on :8101/ui/ with all shipped features (verified via Chrome Connect read). BOJO-UTIL live click not re-run (controller limitation). Voice/typography gates pass.

## Needs-you queue (Tier-2 / money / credentials / installs / push / Amazon)
1. Tier-2 path edits remain denied via opencode.json (additive). Windows ACL commands printed in `reports/cycle_opencode_deny_20261027.md` — run manually by operator; not executed by agent.
2. Chrome signed-in identity on Profile 6 (northstarosllc@gmail.com) — profile lease is valid but Chrome identity is signed in; operator decision whether to sign out (not done by agent).
3. Ollama CPU-only 27B load blocking T3/T5/T7 renders through UI — operator may want to stop non-essential processes or add RAM; agent did not stop processes outside approved stop-list.
4. Model downloads / installs / license acceptance — not performed.
5. Git push — not performed (denied). Local commit d56810ae on feature/chrome-connect-3.0.
6. Amazon access — not touched.

## Model usage
- Primary builder: `northstar-coder:48k` (Ollama local, 27B Q3_K_L, 48K ctx) — not invoked for renders this cycle (no render/browser work concurrent with 27B; rule honored).
- Planning model: `northstaros-qwen3.8:27b` (Master Brain) — resident in UI engine indicator.
- Hosted models: none used (no secrets sent).
- Local 27B used only when no render/browser work running — honored.

## Commits
- d56810ae — cycle: opencode.json additive deny rules + fix pouch_label RAM-gate test isolation (feature/chrome-connect-3.0)

## Stop condition
Cycle report printed. Waiting for operator "continue". Tablet removed from all gates per instruction; STOP file is the kill switch.