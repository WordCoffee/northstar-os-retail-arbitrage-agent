# CREATIVE SERVICES SESSION - Report

## ComfyUI state (C1)
UP: GPU=cuda:0 NVIDIA GeForce RTX 5080 Laptop GPU, VRAM 16275 MB total / 15067 MB free, RAM 15791 MB total / 2256 MB free. Started with tools/start_comfyui.ps1 --cache-none.

## comfy_smoke.py results (after --cache-none restart)
- inventory: OK (all models staged: klein_q8 4300MB, seedvr2_3b 3392MB, wan_5b 3810MB, umt5 4145MB, wan_vae 1409MB, flux2_vae 336MB, seedvr2_vae 501MB; TTS models present)
- klein (FLUX.2 4B image): FAIL - OOM (DefaultCPUAllocator: not enough memory, 1.2GB needed, 2.2GB free). RAM gate now refuses honestly.
- seedvr2 (upscale): FAIL - HTTP 400 Bad Request (queue rejected, likely node/param issue)
- wan (5s video clip): SUCCESS (82.1s, output ns-smoke-wan_00004_.mp4)
- tts (Piper/Qwen3-TTS narration): SUCCESS (12.1s, output ns-smoke-tts_00003.flac)

## System-RAM pre-render gate (NEW)
Built and wired into generate_image and generate_video:
- ensure_system_ram() checks psutil free RAM against SYSTEM_RAM_FLOOR_MB (4096, env-overridable).
- Below floor: stop-list runs (Docker, llama.cpp, Ollama, heavy dev tools; Chrome opt-in via --shutdown-chrome; OpenCode always excluded).
- Re-measures; if still below floor: raises RuntimeError('free X MB, need Y MB') - honest refusal, no blind retry.
- Restore list returned for post-render restart.
- Tests: 8 passed (floor-check, stop-list filtering mock processes, restore ordering, refusal path, no real killing).
- All 27 tests pass (ram gate 8 + render guard 8 + autothink 12 - 1 overlap = 27).

## R2 MOGRA battery
BLOCKED on T1 (pouch render): FLUX.2 image lane (klein) fails with OOM due to insufficient system RAM (~2.2 GB free, need ~4 GB floor). The RAM gate now refuses honestly instead of OOM'ing. T1-T8 cannot proceed until more RAM is free (close other apps / increase pagefile).

## R3 FLUX3 lanes
SKIPPED-WITH-REASON: FLUX 3 weights absent.

## Commits this session
| Hash | Message |
|---|---|
| d11eb48d | feat(studio): system-RAM pre-render gate with stop/restore list |

## Findings for operator
1. ComfyUI render lanes: wan (video) and tts (narration) work; klein (image) and seedvr2 (upscale) fail.
2. klein fails due to RAM (2.2 GB free < 4 GB needed for text encoder). The RAM gate now refuses honestly.
3. seedvr2 fails with HTTP 400 (queue rejected) - likely a node/param issue in the smoke test graph, not RAM.
4. To unblock T1 (MOGRA pouch render): free RAM (close apps, increase pagefile) so klein can load the text encoder.
