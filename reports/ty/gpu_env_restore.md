# Ollama environment — what was there, why, and how to put it back

Recorded 2026-11-07 before changing anything else. **Read this before touching the GPU.**

## Why the pins existed (evidence, not a story)

`OLLAMA_LLM_LIBRARY=cpu` and `OLLAMA_NUM_GPU=0` were a deliberate workaround, not an
accident. Commit `01d97bfb` (2026-10-27, *"T1 FLUX render verified; VRAM root cause;
Ollama restarted"*) records both the reason and the pin:

> "Root cause of the battery failure: 16 GB VRAM cannot hold both the 27B chat LLM
> (~12 GB) and ComfyUI's FLUX model (~9 GB)."
>
> "Ollama restarted after the render (CPU mode; `OLLAMA_NUM_GPU=0` persisted in user
> env)."

A later session (`00_STATE.json`, key `ty_autonomy_gate_20261101`) diagnosed the same
thing and chose **not** to change it: *"operator_env_untouched: OLLAMA_LLM_LIBRARY=cpu /
OLLAMA_NUM_GPU=0 left as-is; restored after the session"*. That session proved GPU
inference another way — a campaign-scoped `ollama serve` with GPU environment — and
measured `bojo:gpu-orig` at 2.244 GB VRAM with 3.777-4.642 GB of RAM free (FLOOR-MET).

So: no single "who", and no hidden actor. The laptop's owner config was set to protect
ComfyUI renders from VRAM contention with the 27B, and two later sessions treated it as
operator-owned configuration.

## Values found on 2026-11-07 (all **User** scope, Machine scope empty)

| variable | value found | changed by D7? |
|---|---|---|
| `OLLAMA_CONTEXT_LENGTH` | `65536` | no |
| `OLLAMA_FLASH_ATTENTION` | `1` | no |
| `OLLAMA_HOST` | `0.0.0.0:11434` | no |
| `OLLAMA_KEEP_ALIVE` | `30m` | no |
| `OLLAMA_KV_CACHE_TYPE` | `q4_0` | no |
| **`OLLAMA_LLM_LIBRARY`** | **`cpu`** | **cleared** |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | no (raised only for the coexistence test, then restored — see below) |
| **`OLLAMA_NUM_GPU`** | **`0`** | **cleared** |
| `OLLAMA_NUM_PARALLEL` | `1` | no |

Also changed, outside the environment: `bojo:latest` had `PARAMETER num_gpu 0` baked
into its Modelfile. It was copied to **`bojo:cpu-quarantine`** before being rebuilt
without that line. `bojo:cpu-quarantine` is still installed; nothing was deleted.

## Restore to the previous CPU-only behaviour (one command)

```powershell
# scripts/restore-ollama-cpu.ps1
[Environment]::SetEnvironmentVariable('OLLAMA_LLM_LIBRARY','cpu','User')
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU','0','User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS','1','User')
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^ollama' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe" -ArgumentList '--hide'
# and, if Bojo must go back to CPU:
#   ollama cp bojo:cpu-quarantine bojo:latest
```

The script exists at `scripts/restore-ollama-cpu.ps1` so this is executable, not advice.

## What to know before restoring

Restoring puts every local model back on the CPU: the vision model then occupies 7.4 GB
of **system RAM** and leaves 0.5-0.9 GB free, which is why the autonomy work stalled on a
RAM floor for a week. The GPU workaround that made ComfyUI + the 27B coexist was manual
stop/restore. The replacement for both is the residency plan in
`tools/gpu_budget.py` plus the measured coexistence table in
`reports/ty/d7_coexistence.md` — one owner for "what is resident", instead of a global
pin.
