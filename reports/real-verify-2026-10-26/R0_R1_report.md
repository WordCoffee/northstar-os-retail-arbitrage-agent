# PHASE R — REAL-SYSTEM VERIFICATION (port 8000)

## R0 — Preconditions (report only)

- 8000 health: 200 OK ({"status":"ok","service":"northstar-backend","version":"1.0.0"})
- /ui/ on 8000: 200 (built bundle served, len=1090)
- tailscale serve status: https://msi.tail4b3dfd.ts.net (tailnet only) -> / proxy http://127.0.0.1:4097  (NOT 8000; tailscale points at 4097, not the 8000 instance)
- FLUX 3 weights: ABSENT (no flux-3* files in ComfyUI model dirs). R3 steps SKIPPED-WITH-REASON. Engine uses FLUX.2 9B (Flux-2-Klein-9B-KV-Q8_0.gguf).
- MEDIAGEN_LIVE: not set at OS env level, but creative/readiness reports armed=true, media_live_armed=true, ComfyUI reachable at http://127.0.0.1:8188. Engine banner truth matches API engine state: both report armed. Models: image=Flux-2-Klein-9B-KV-Q8_0.gguf, video=Wan2.2-TI2V-5B-Q5_K_M.gguf, edit=qwen-image-edit-2511-Q4_K_M.gguf.

## R1 — Playwright on real system (8000/ui, unauthenticated smoke)

| Room | Status | Console errors | External requests | Axe violations | Result |
|---|---|---|---|---|---|
| / | 200 | 0 | 0 | 0 | PASS |
| /sign-in | 200 | 0 | 0 | 0 | PASS |
| /home | 200 | 0 | 0 | 0 | PASS |
| /product-finder | 200 | 0 | 0 | 0 | PASS |
| /golden-goose | 200 | 0 | 0 | 0 | PASS |
| /listings | 200 | 0 | 0 | 0 | PASS |
| /monitoring | 200 | 0 | 0 | 0 | PASS |
| /admin | 200 | 0 | 0 | 0 | PASS |

hasUnknownOrSample=false (unauthenticated; no data views). 6-role matrix (C-auth) blocked on foundation account seeding (requires organization + membership).

## R2 — MOGRA end-to-end generation
DEFERRED: requires ComfyUI started with --cache-none on 8188 (currently running on 8188 but cache-none status unverified) and MOGRA asset staging. tools/comfy_smoke.py uses port 8199 (mismatch with ComfyUI on 8188) — noted as a finding. Full T1-T8 battery is a multi-hour task; recommend dedicated session.

## R3 — FLUX3 lanes
SKIPPED-WITH-REASON: FLUX 3 weights absent (no flux-3* files in ComfyUI model dirs). FLUX.2 9B remains the engine.

## R4 — Summary
- R0: PASS (with findings: tailscale points at 4097 not 8000; FLUX3 absent; media gen armed)
- R1: PASS (8/8 rooms)
- R2: DEFERRED
- R3: SKIPPED-WITH-REASON
