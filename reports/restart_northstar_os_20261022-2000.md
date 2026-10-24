# Northstar OS — full stop and restart (2026-10-22 20:00)

## What was running before the stop
| Port | Process | PID | Command |
|------|---------|-----|---------|
| 8000 | python.exe | 20632 | `C:\Python314\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000` |
| 8101 | node.exe (vite) | 16576 (parent cmd 13012) | `vite --port 8101 --strictPort` |
| 8188 | python.exe (ComfyUI) | 6652 | `main.py --listen 127.0.0.1 --port 8188 --cache-none` |
| 11434 | ollama.exe | 18788 | Ollama server |

Pre-stop baseline: backend `/health` 200, UI `/` 200. Docker daemon was **down**, so the compose stack
(`tools/start-local.ps1`, port 80) was not the live tier and was left alone.

## Actions
1. Hard-stopped the Northstar OS app tier: backend PID 20632, vite PID 16576, its `cmd` parent 13012.
   ComfyUI (8188) and Ollama (11434) were **deliberately left running** — they are shared engines, not part
   of the app tier, and a ComfyUI restart costs a 1–2 min reload budget (see known issue
   `creative_edit_lane_ram_ceiling_20261022`, which requires `--cache-none` on every start).
2. Verified both ports free before restarting (no zombie listeners; no force-kill of unrelated PIDs).
3. Restarted from the same binaries + working directories, so the same `.env` is read and sessions remain
   valid (`NORTHSTAR_JWT_SECRET` is not in User/Machine env; it resolves from backend config as before).
   - backend: PID 17596, logs `%TEMP%\opencode\northstar-run\backend.{out,err}.log`
   - UI: npm PID 14040 → node PID 5960, logs `%TEMP%\opencode\northstar-run\ui.{out,err}.log`

## Verification after restart
| Check | Result |
|-------|--------|
| `GET :8000/health` | 200 `{"status":"ok","service":"northstar-backend","version":"1.0.0"}` |
| backend startup log | `Application startup complete` / `Uvicorn running on http://127.0.0.1:8000` |
| `GET :8101/` | 200 |
| `GET :8101/ui/` | 200 (Vite v5.4.21 ready in 306 ms) |
| Vite → API proxy `GET :8101/api/v1/provider-suite` | 200 |
| `GET :8000/api/v1/provider-suite` | 200 |
| `GET :8000/api/ops/status` | 401 — authenticated route, no session in a bare request (correct) |
| `GET :8000/api/design-studio/lanes/status` | 401 — same auth gate (correct) |
| ComfyUI `:8188/system_stats` | 200, v0.40.0, 14.6 GB VRAM free |
| Ollama `:11434/api/ps` | 200, 0 models resident (VRAM idle) |

Only startup warning: pre-existing Pydantic `Field name "copy" in "APlusPackIn" shadows an attribute`
in `Northstar_backend/design_studio_api.py:1407`. Non-fatal, unchanged by the restart.

## Access
- Suite: http://127.0.0.1:8101/ui/ (sign in at `/ui/sign-in`)
- Backend API: http://127.0.0.1:8000
- AutothinK on 8100 is **not** part of this tier and remains stopped (`launch-all.ps1` owns that port).

## Open follow-ups (not touched)
- `scripts/run_all_tests.ps1` backend suite still parses RED because of four untracked
  `costco_non_kirkland` files (known issue `canonical_runner_red_from_untracked_costco_files_20261019`).
- The `docs/LOCAL_RUNBOOK.md` compose path is untestable until Docker Desktop is started.
