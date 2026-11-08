# Local models in OpenCode — root cause and fix (2026-10-29)

## What was broken
The Ollama tags `northstaros-27b-coder` / `northstaros-thinking` loaded **100% CPU** and returned empty content
(finish_reason=length, 24 s for 16 tokens). With Vulkan disabled, Ollama's CUDA runner **crashes on load**:

```
llama-server process has terminated: exit status 0xc0000409 (stack-based buffer overrun)
libc++abi: terminating due to uncaught exception of type std::bad_alloc
Load failed model=...sha256-63f29a21...
```

Same signature recorded in `00_STATE.json` for this GGUF. Ollama therefore falls back to CPU (or dies), so
selecting those entries in OpenCode could never work at usable speed. Both tags were removed.

## What changed
OpenCode now points at the **llama.cpp lanes**, which are GPU-resident and verified:

| Picker entry | Provider | Endpoint | Model id |
|---|---|---|---|
| **NorthstarOS 27b Coder (GPU 64K)** | `ollama-local` | `:8080/v1` | `northstaros-27b-coder` |
| **NorthstarOS Thinking (GPU 64K)** | `northstar-thinking` | `:8081/v1` | `northstaros-thinking` |

- `scripts/start-northstar-moe.ps1` gained `-Port`, and the runtime aliases are now
  `northstaros-27b-coder` / `northstaros-thinking` (previously `coder-27b` / `creative-27b`).
- Global config backup: `~/.config/opencode/opencode.json.bak.20261029`.

## Start a lane
```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-northstar-moe.ps1 -Lane coder   -Port 8080 -Restart
powershell -ExecutionPolicy Bypass -File scripts\start-northstar-moe.ps1 -Lane creative -Port 8081 -Restart
```
`-Restart` stops the other lane first: only one 27B fits in 16 GB VRAM (coder 13.8 GiB, thinking 14.0 GiB).

## Verified
| Lane | Health | Completion |
|---|---|---|
| coder (:8080) | ok, 14,106 MiB VRAM | `OK`, finish=stop, 0.8 s |
| thinking (:8081) | ok, model loaded | `OK`, finish=stop, 0.9 s |

Both requests used `chat_template_kwargs.enable_thinking=false`; with thinking on, the model reasons first.

## Follow-up: both models under one "Ollama" provider
OpenCode shows providers by name; two lanes on two ports could not share one. Added 	ools/northstar_lane_router.py:
a single OpenAI-compatible endpoint on **127.0.0.1:8090/v1** that lists both model ids and, per request, stops the
resident lane, starts the requested one and forwards.

| Picker entry | Provider | Model id |
|---|---|---|
| NorthstarOS 27b Coder (GPU 64K) | Ollama (ollama-local) | 
orthstaros-27b-coder |
| NorthstarOS Thinking (GPU 64K) | Ollama (ollama-local) | 
orthstaros-thinking |

Verified through the router:
- thinking: OK, finish=stop, **0.7 s** (model already resident)
- coder after a lane switch: OK, finish=stop, **16.5 s** (includes stop + load), 14,380 MiB VRAM

Router start (idempotent): powershell -ExecutionPolicy Bypass -File scripts\start-northstar-router.ps1
The real Ollama provider was renamed "Ollama (bojo/vision)" so the two groups are distinguishable.
Do not run start-northstar-moe.ps1 while the router owns the lanes; the router stops all llama-server processes on a switch.

## 400/500 on OpenCode requests (2026-10-30)
Root causes found by probing the lane endpoint:
- easoning_effort: "high" is **rejected by the model's Jinja template** (accepted: xhigh, medium, low). The OpenCode config offered a high variant, so selecting it produced a template exception.
- An empty messages array also raises inside the template.
- The router masked upstream errors as lane error: HTTP Error 400 without the body.

Fixes:
- OpenCode variants are now low, medium, xhigh (the invalid high id is gone) for both models.
- Router normalizes easoning_effort: high/max -> xhigh, 
one/minimal/off -> low, unknown -> dropped.
- Empty messages returns a clear 400 (messages must be a non-empty array).
- Upstream 4xx/5xx bodies are forwarded verbatim, and every request logs path/model/field names (never content).

Verified through the router: effort_high 200, normal 200, tool-history 200, content-parts 200, empty messages 400 with the explicit message.

## Context corrected to 16K (2026-10-30)
Measured before: /props reported 
_ctx = 65536 on both lanes. The 16K figure only ever existed in the deleted Ollama Modelfiles.
Changed:
- scripts/start-northstar-moe.ps1: -Ctx default 65536 -> 16384
- 	ools/northstar_lane_router.py: lane args -c 16384
- shared/model-suite.json: local_engines.ty.context_tokens 16384

Verified after reload: coder 
_ctx=16384 (12,322 MiB VRAM), thinking 
_ctx=16384 (13,664 MiB). VRAM saving vs 64K: ~1.5-1.8 GiB per lane.
Restore 64K for a single run with scripts\start-northstar-moe.ps1 -Lane coder -Ctx 65536; the router hardcodes 16K.

## Quant upgrade at 16K: IQ4_XS-MTP replaces both IQ3 lanes (2026-10-30)
Search outcome: at <=14 GiB the Qwen3.8-27B class is still the ceiling (GLM-5.3-Air / Nemotron 30B / Coder-Next REAP-40B
need 17.5-21 GiB). 16K context freed ~1.5 GiB, which pays for one more bit per weight.

Installed: `Bucoid/Qwen3.8-27B-IQ4-XS-MTP-16GB-VRAM-GGUF` -> `Qwen3.8-27B-IQ4_XS_4BPW.gguf`, 12.95 GiB, Apache-2.0,
base Qwen/Qwen3.8-27B, MTP head in-file (log: "creating MTP draft context"). Third-party card: PPL 7.088 vs 7.112 for
UD-IQ3_K_XL; max KLD 12.1 vs 21.4.

Measured at 16K, q4_0 KV, same prompt, 512 tokens:
| Model | Decode | VRAM |
|---|---|---|
| IQ3_XXS-mtp | 62.2 t/s | 12,080 MiB |
| **IQ4_XS-MTP** | **64.9 t/s** | 15,068 MiB |

Burst bench: 112.8 t/s novel (363 tok), 95.4 t/s copy/recital.

Quality: the architect 9-file strict-TS build through the agent loop (builder + scaffold + schema) went **green in 3 steps,
119.7 s, tsc exit 0** (independently re-run). The same pipeline on IQ3_XXS stopped at 16 steps with 6 TS2300 errors.

Wiring: router + launcher now point both model ids at the IQ4 file; both ids share one server on :8080, so switching
between "coder" and "thinking" no longer reloads. model-suite records 13.9 GB weights, 14.7 GiB VRAM, 65 tok/s.
Rollback: the two IQ3 files remain on disk (9.73 + 11.29 GiB).
## Old quants removed (2026-10-30)
Deleted Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf (9.73 GiB) and Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf (11.29 GiB).
Disk free: 54.6 -> 75.6 GiB. Only Qwen3.8-27B-IQ4_XS_4BPW.gguf remains.
scripts/start-northstar-llm.ps1 was repointed at the IQ4 file (alias northstaros-27b-coder, -c 16384) so Tys Assistant's
on-demand launcher could not break on the deleted file.
Verified after removal: router restarted, coder answered OK (37.3 s including load), /props = IQ4, n_ctx=16384, 15,068 MiB.

Rollback (public, re-downloadable):
  hf download ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf --local-dir %USERPROFILE%\models\northstar-moe
  hf download ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf   --local-dir %USERPROFILE%\models\northstar-moe
