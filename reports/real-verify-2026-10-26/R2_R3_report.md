# PHASE R - REAL-SYSTEM VERIFICATION (port 8000)

## R0 - Preconditions (report only)
- 8000 health: 200 OK.
- /ui/ on 8000: 200 (built bundle served).
- tailscale serve: https://msi.tail4b3dfd.ts.net -> 127.0.0.1:8000 (FIXED via F1; probe returns 200).
- FLUX 3 weights: ABSENT (no flux-3* files in ComfyUI model dirs). R3 SKIPPED-WITH-REASON. Engine uses FLUX.2 9B (Flux-2-Klein-9B-KV-Q8_0.gguf).
- MEDIAGEN_LIVE: not set at OS env, but creative/readiness reports armed=true, media_live_armed=true, ComfyUI reachable at http://127.0.0.1:8188. Engine banner truth matches API engine state: both report armed.

## R1 - Playwright on real system (8000/ui, unauthenticated smoke)
All 8 rooms PASS: status 200, 0 console errors, 0 external requests, 0 axe violations.

## R2 - MOGRA end-to-end generation
DEFERRED. ComfyUI is up on 8188 (RTX 5080, 17GB VRAM) but render lanes (klein, seedvr2, wan, tts) return status=error / HTTP 400. ComfyUI may need --cache-none restart (user requirement). tools/comfy_smoke.py BASE fixed 8199->8188 (F2) but renders still fail. MOGRA assets located: exports/mogra_logo_master_v3.png, Northstar_backend/assets/brand/hericium_source.jpg. Full T1-T8 battery requires dedicated session with ComfyUI --cache-none.

## R3 - FLUX3 lanes
SKIPPED-WITH-REASON: FLUX 3 weights absent.

## R4 - Summary
- R0: PASS (findings: tailscale was misconfigured -> fixed; FLUX3 absent; media gen armed)
- R1: PASS (8/8 rooms)
- R2: DEFERRED (ComfyUI render lanes error; needs --cache-none + MOGRA staging)
- R3: SKIPPED-WITH-REASON (FLUX3 weights absent)
