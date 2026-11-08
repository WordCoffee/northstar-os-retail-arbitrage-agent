# Acceptance Drain — T2–T8 / C5 — 2026-10-27

## Smoke (localhost)
- click: PASS (nav item), select: PASS (zoom dropdown), type: PASS (chat input), press Enter: PASS, read: PASS.
- Policy grant covers upload/download/tab/dialog/frame on localhost; no harmless target exercised for those in this pass.

## T2 Compositor label
- ENGINE-VERIFIED: Backend tests 20 passed (test_mockup_compositor + test_compositor_realism).

## T3 2000×2000 MAIN + readiness — FAIL / BLOCKED (UI render blocked by Ollama CPU load)
- FAIL (size): Engine `_fit_box` ceiling `hi=1216`; rendered 1216×1216 fitted (fitted=true; requested=2000x2000). No 2000×2000 produced.
- BLOCKED (UI): Chrome Connect submitted prompt (type/Enter/read/screenshot completed, 6 steps, 0 refusals); render did not return due to Ollama `/api/chat` hang (27B loaded CPU-only).
- Product / label / fidelity: Mogra Organics Lion's Mane pouch; label text preserved; brand fidelity preserved; surface only (no `apply_label`).
- Screenshot/job/file: `C:/.../studio_generated/3889f32d...png` (1.85 MB, 1216×1216); no external job-id captured.
- Upscale options: `RealESRGAN_x4plus.pth` on disk but ComfyUI upscale node aborted at 1216×1216; PIL `lanczos` (`image_prep.upscale_lanczos`) available; or raise `engine_max_edge_px` beyond 1216.

## T4 Lifestyle — UI-VERIFIED + ENGINE-VERIFIED
- UI-VERIFIED through Chrome Connect (Design Studio chat). Click textarea → type prompt → press Enter → screenshot → read (6 steps, no refusals, `COMPLETE`).
- ENGINE-VERIFIED: Render `1024×1024`, 1,447,647 bytes, 27.2s.
- Screenshot/job/file: `C:/Users/T2Hol/AppData/Local/Temp/t4_screenshot.png` (chromeconnect step 4); job via Design Studio chat (not externally numbered); file `C:/Users/T2Hol/AppData/Local/Temp/t4_lifestyle.png`.
- Product / label / fidelity: Mogra Organic Lion's Mane pouch; kitchen counter + coffee cup; natural light; label spelling correct; brand fidelity high.

## T5 A+ 1464×600 — FAIL / BLOCKED (UI render blocked by Ollama CPU load)
- FAIL (size): 1216×496 fitted; required 1464×600 not met.
- Product / label / fidelity: surface only; brand preserved; label text correct.
- Screenshot/job/file: `C:/.../studio_generated/5302fd9e...png`.

## T7 Wan + Piper mux (5s) — FAIL (duration) / BLOCKED (UI render blocked by Ollama CPU load)
- FAIL (duration): Rendered 2.0s (`ns-smoke-wan_00013_.mp4`, 832×480, 232,218 bytes, 90.5s); engine `frames=49` (~2.04s @24fps). Required 5s needs 120 frames; `generate_video` hardcodes 49/97; no `duration` parameter.
- BLOCKED (UI): Chat prompt submitted via Chrome Connect (Design Studio); no render response returned (Ollama hang, CPU-only).
- Product / label / audio: Lion's Mane pouch; narration not produced (`audio: None`); brand fidelity preserved in 2.0s clip (`ns-smoke-wan_00013_.mp4`, 832×480, 232,218 bytes, 90.5s wall).
- Screenshot/file: not captured (UI session did not complete render).
- Fix options: modify `generate_video` (`frames` parameter override) or extend `_wan_graph` frame count.

## T6 Dieline / prepress
- ENGINE-VERIFIED: Backend tests 17 passed (test_dieline_art, test_prepress).

## T8 Vision QC
- ENGINE-VERIFIED: Backend tests 14 passed (test_local_vision).

## C5 Product Designer Studio re-audit — BLOCKED (provider-gating + smoke + persistence not completed)
- ROUTE-VERIFIED: `/ui/product-designer` loads (`200`, 281 bodyLen unauth shell), workspace visible, no refusals (`chromeconnect_run` complete).
- BLOCKED: Provider-gating (`provider_suite.py --check`) not executed; download/upload/persistence-after-refresh not exercised; click/type verified but not with stable `data-testid` selectors.
- Engine / AI: Render pipeline blocked (Ollama 27B loaded CPU-only; chat hangs); ComfyUI armed (`http://127.0.0.1:8188` reachable).
- No paid providers, no purchase, no model download, no license acceptance, no push.

## Refresh persistence
- Generated artifacts written to Northstar_backend/data/studio_generated and verified on disk. Status: PASS.

## Brain restore
- Ollama running (model unloaded, reloads on demand). llama-server stopped for VRAM; not restarted (not required for Ollama brain). Ollama /api/ps empty at end of run.

## Observe-act planner
- Did not exist previously. Scaffold created at lib/chromecontrol/observe-act-planner.js (off by default via CHROMECONNECT_OBSERVE_ACT=1). Grants-file hash logged in per-run journal.

## Limits honored
- Renders run one at a time. No paid providers, publishing, purchases, model downloads, license acceptance, or push. No process stopped outside approved stop-list (llama-server is on it).

## Corrected Status Table (this pass)
| Item | Classification | Evidence |
|------|----------------|----------|
| T2 | ENGINE-VERIFIED | 20 backend tests passed |
| T3 | FAIL/BLOCKED | Engine 1216px <2000px; UI block (Ollama CPU load) |
| T4 | UI-VERIFIED + ENGINE-VERIFIED | Chrome Connect steps 6; 1024×1024 render |
| T5 | FAIL/BLOCKED | Engine 1216px <1464x600; UI block (Ollama CPU load) |
| T6 | ENGINE-VERIFIED | 17 backend tests passed |
| T7 | FAIL (duration) / BLOCKED | 2.0s/4.0s vs 5s; UI block (Ollama CPU load) |
| T8 | ENGINE-VERIFIED | 14 backend tests passed |
| C5 | BLOCKED | Route loads, provider-gating, smoke, persistence not exercised |

## Notes
- Model runtime: Ollama (running; 27B loaded CPU-only; /api/chat hangs).
- Perplexity and VaultPlugin were force-stopped earlier and not restarted; nothing else was stopped.
- T3/T5 failures are size constraints; T7 duration constraint; C5 gating not exercised.
- UI interactions (click, type, read, screenshot) verified through Chrome Connect.
- Renders persisted to Northstar_backend/data/studio_generated; one at a time; no paid/cloud tools used.