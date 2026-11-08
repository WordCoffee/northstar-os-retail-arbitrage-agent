# Tys Assistant — overnight readiness: queue cleanup + health check

**Date:** 2026-10-30 ~01:45 local
**Branch:** `feature/chrome-connect-3.0`
**Commit:** `82038d62` — `fix(tys): accept --cache-none on start_comfyui; report runnable queue head`
**Backend:** restarted, PID 2936, `127.0.0.1:8000`, `ENVIRONMENT=development`, dev safety gate PASS
**Result:** queue clean (0 blocked, 0 awaiting-controller); 3 of 5 worker lanes live; graphics/creative serialized, not resident

---

## 1. Queue cleanup

| Task | Before | Action | After |
|---|---|---|---|
| `tys_28668c5a2b84` — Smoke A (orchestrator plan) | `blocked` (`orchestrator_plan_invalid: empty_reply`) | `POST /cancel` | `cancelled` |
| `tys_7f50857f0443` — Task B (browser step) | `awaiting_controller` (Chrome Connect assignment, cursor 2/3) | `POST /cancel` | `cancelled` |

Queue after cleanup (15 tasks): **7 done, 4 paused, 4 cancelled, 0 blocked, 0 awaiting_controller, 0 queued, 0 running.**
The 4 paused tasks are resumable checkpoints, not stuck work.

**Smoke proof of readiness:** filed and ran `tys_f387d4b64de8` (inspect-only, explicit step).
`POST /work-orders` → 200 queued; `POST /tasks/{id}/run` → 200 `done`, 1 step, `all_steps_completed`.

## 2. Coding-lane pre-authorization

- **Path discrepancy:** `backend/agent/coding_agent.py` does not exist. The real file is
  `Northstar_backend/agent_kernel/coding_agent.py` (14,319 bytes). Verified there, lines 250–251:
  > `SYSTEM DIRECTIVE: You are pre-authorized to run ['npx tsc', 'npm test', 'npm run', 'npx jest']. NEVER read coding_tools.py to check tool permissions.`
  Wording differs by one verb (`check` vs `verify`); the substance is present and injected into every system prompt.
- **Enforced allowlist** (`Northstar_backend/agent_kernel/coding_tools.py` lines 129–139):
  `python -m pytest`, `python -m py_compile`, `pytest`, `npm test`, `npm run`, `npx tsc`, `npx jest`, `git status`, `git diff`. Anything else is refused with `command not allowlisted`.
- **Dry run:** `tools/run_coding_agent.py --workspace exports/agent_healthcheck --command "npx tsc --noEmit" --required-file src/health.ts --max-steps 3 --scaffold`
  → **ok, 1 step**, acceptance `PASS: missing=[]; failures=[]`. No permission-inspection reads.
  Independent check: `npx tsc --noEmit` in the workspace → **exit 0**; `src/health.ts` = `export const HEALTH = 'ok';`
  (typescript 5.7 + @types/node installed locally in the scratch workspace; MIT/Apache-2.0, local-lane.)

## 3. Lane and VRAM state (measured)

- **Coder lane:** `llama-server.exe` PID 24596, `Qwen3.8-27B-IQ4_XS_4BPW.gguf`, `-c 17408`, `-fa on`, `-ctk/-ctv q8_0`, `--spec-type draft-mtp --spec-draft-n-max 8`, port 8080. Worker `/health` → healthy.
- **VRAM (nvidia-smi):** RTX 5080 Laptop, 16,303 MiB total, **15,392 MiB used, 612 MiB free**.
  The 17K coder lane is resident; the ~12.2 GB figure understates the measured footprint.
- **Disk:** 75.5 GB free (above the 10 GB guard).
- **Graphics:** FLUX 3 gateway `tools/flux3_gateway.py --port 8190` is running (PID 20152), weights present
  (unet 4.92 GB, text encoder 4.52 GB, VAE 0.31 GB), but ComfyUI on `:8188` is **down**, so `/health` = 503 and the
  lane reports `flux3_endpoint_unhealthy` (0.6 s probe times out against the gateway). Not green; **ready to serialize**.
- **Creative:** `media_live=False comfyui=False`.

**Serialized graphics procedure (must run with the coder lane down):**
1. `Stop-Process` the `llama-server.exe` on 8080 and wait for VRAM to free
2. `powershell -File tools/start_comfyui.ps1 --cache-none`
3. render via `tools/flux3_gateway.py` (`POST /generate`)
4. stop ComfyUI
5. restart the 17K coder lane

**Fix applied:** `start_comfyui.ps1` bakes `--cache-none` into the ComfyUI args, so the documented
`tools/start_comfyui.ps1 --cache-none` previously **failed PowerShell parameter binding**. The script now accepts
the token (still always applied) and refuses any other unknown argument. Binding test: `--cache-none` → exit 0;
`--bogus` → refused. PowerShell parser: syntax OK.

## 4. State ledger refresh

`GET /api/admin/tys/state?fresh=1` → 200.

| Lane | Available |
|---|---|
| inspect | yes |
| coding | yes (127.0.0.1:8080) |
| browser | yes (Chrome Connect controller reachable, policy enforced) |
| graphics | no — ComfyUI down, serialized |
| creative | no — media/comfy down |
| orchestrator | yes (`bojo:latest`) |

`queue.next` now reports the next **runnable/resumable** task (`tys_49fe7324d00e`, paused) instead of the oldest row.
Previously it advertised a cancelled task as the queue head — misleading in exactly this readiness check.
Source fixed and committed; the restarted backend serves it.

## Deviations / notes

- The commit also lands pre-existing uncommitted WIP in `tys_assistant.py` (`CodingWorkerAdapter.run_agent`,
  `params.mode=agent`, `northstaros-27b-coder` alias). That block was uncommitted at session start and was already
  recorded complete in `00_STATE.json`; its content was not changed.
- `00_STATE.json` was left untouched (already dirty with unrelated WIP).
- The backend was restarted to make the committed fixes live (old PID 29804 → new PID 2936); `/health` 200.
- UI at `127.0.0.1:8101/ui/` responds 200.

## Ready / not ready

- **Ready now:** coding, inspect, browser, orchestrator. Work orders can be filed and run unattended.
- **Not ready:** graphics and creative — both need the serialized ComfyUI swing (coder lane down first).
