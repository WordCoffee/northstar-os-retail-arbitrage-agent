# Local coder: 16K -> 48K, and why WSL2 was the real problem

**Date:** 2026-10-25 21:50 - **Host:** MSI Vector 16 HX AI - RTX 5080 Laptop 16 GB - 15.4 GB RAM - Windows 11 26200 / WSL 2.7.3

---

## 1. Executive answer

You did not need a different model. You needed a different **host** for Ollama and a correct **chat template**.

| | Before | After |
|---|---|---|
| Context | 16 384 | **49 152** (3x) |
| GPU offload | 100% | 100% |
| Throughput | ~39 tok/s | **~37-40 tok/s** |
| Tool calling | broken (agent loop span forever) | **works** (verified multi-step) |
| Thinking leakage | yes | no |
| Runs where | WSL2 | **Windows native** |

Measured on `northstar-coder:48k`, 6/6 sequential requests clean, 2.0 GB VRAM headroom.

---

## 2. Three root causes found (all measured, not guessed)

### 2.1 WSL2 silently costs ~4.7 GiB of VRAM

Measured max single `cuMemAlloc` on the same GPU, same idle desktop:

| State | Max single GPU allocation |
|---|---|
| WSL VM shut down (`wsl --shutdown`) | **15 872 MiB** |
| WSL VM running, GPU touched once | **11 008 MiB** |

An *idle* WSL VM costs nothing (15 872 either way). The moment any WSL process opens `/dev/dxg` or CUDA, the VM commits roughly 4.7 GiB of the WDDM budget and **keeps it until `wsl --shutdown`, even after the process exits**. `nvidia-smi` inside and outside WSL both keep reporting `15 1xx MiB free` the whole time -- the number lies.

Consequence: a 13 GB / 27 B model can never fully load inside WSL2 on this machine. That is why 16K was tight, 32K OOM'd and 64K OOM'd.

**Rule: Ollama runs on Windows. WSL2 is a client only.**

### 2.2 Orphaned `llama-server` processes eat the whole GPU

A failed load leaves a `llama-server.exe` holding 13.5 GB. `ollama ps` reports *nothing loaded* while `nvidia-smi` shows 13 596 MiB used. Every subsequent load then fails with `cudaMalloc failed: out of memory`, and the situation looks like "the model does not fit any more".

Detected live: `PID 22152 llama-server` holding 13.5 GB with `ollama ps` empty.

**Rule: if VRAM looks wrong, check `Get-Process llama-server` before anything else.**

### 2.3 The model's chat template was `TEMPLATE {{ .Prompt }}`

`ollama show --modelfile qwen3.8-27b-coder:latest`:

```
FROM C:\Users\T2Hol\.ollama\models\blobs\sha256-8c2a45ff...
TEMPLATE {{ .Prompt }}
```

No `<|im_start|>` / `<|im_end|>` markers at all, and no tool-call grammar. The base blob was converted from a GGUF that carries `{{ .Prompt }}` as its `tokenizer.chat_template`, so every rebuild that omits an explicit `TEMPLATE` inherits it.

That single line explains the original symptom: `opencode run` printing `> build - qwen3.8-27b-coder` forever. With no chat framing the model can never emit a valid tool call, so the agent loop has nothing to terminate on.

Verified after the fix (`/v1/chat/completions`, tools declared):

```
finish_reason = tool_calls
tool_calls    = {"name":"read","arguments":"{\"path\":\"README.md\"}"}
```

### 2.4 Contributing factor: stale OLLAMA_* env in `HKCU:\Environment`

```
OLLAMA_CONTEXT_LENGTH   = 16384   <- hard cap on every model
OLLAMA_KEEP_ALIVE       = -1      <- models never unload (feeds 2.2)
OLLAMA_MAX_LOADED_MODELS= 2       <- two 13 GB models can be admitted
OLLAMA_KV_CACHE_TYPE    = q8_0    <- 2x the KV cost needed
```

Now set to `65536 / 30m / 1 / q4_0`, plus `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_HOST=0.0.0.0:11434`.

---

## 3. Why 48K and not 64K -- real measurements

`Qwen3.8-27B` config (`Qwen/Qwen3.8-27B`): 27.78 B dense, **64 layers**, hybrid attention with `full_attention_interval = 4` -> only **16 full-attention layers**, `num_key_value_heads = 4`, `head_dim = 256`.

KV per token, full layers only: `2 x 16 x 4 x 256 x 2 bytes = 64 KiB/token` (f16).

Measured against llama.cpp's own accounting (q8_0, 64K):

```
llama_kv_cache: CUDA0 KV buffer size = 2040.00 MiB
                size = 2176.00 MiB (65536 cells, 16 layers)
```

2.04 GiB / 65 536 tokens = **32 KiB/token** -- exactly 64 KiB halved. The cost model is correct.

| Config | KV @ 65536 | Result |
|---|---|---|
| f16 (no FA) | 4.0 GiB | OOM |
| q8_0 + FA | 2.04 GiB | loads, then FA kernel dies |
| **q4_0 + FA** | **1.15 GiB** | loads, runs, then `std::bad_alloc` on prompt-cache save |
| q4_0 + FA @ **49152** | **0.86 GiB** | **stable, 6/6, 100% GPU, 2.0 GB free** |

The 64K failure is **not** OOM -- the KV cache allocates fine. It dies later:

```
srv prompt_save: saving prompt with length 263, total state size = 154.256 MiB
libc++abi: terminating due to uncaught exception of type std::bad_alloc
```

That is **host RAM** (15.4 GB total, ~5.2 GB free), not VRAM. With a 13 GB GGUF mmap'd on a 15.4 GB machine, Ollama's prompt-cache saves have nowhere to go. 48K keeps ~1 GiB more headroom and stops the crash.

`56320` (55K) and `98304` (96K) both load but report `6%/94% CPU/GPU` and drop to ~31 tok/s -- the CPU spill you said is too slow. 48K is the last 100%-GPU setting.

---

## 4. What was actually built

```
FROM C:\Users\T2Hol\.ollama\models\blobs\sha256-8c2a45ff...
TEMPLATE  ChatML (im_start / im_end), Qwen XML <tool_call>, <tool_response> in user turns,
          assistant prefix pre-filled with an EMPTY think block to force thinking OFF.
          The template ends with:  <|im_start|>assistant\n<think>\n\n</think>\n\n
PARAMETER num_ctx 49152
PARAMETER temperature 0.2
PARAMETER top_p 0.95
PARAMETER top_k 20
PARAMETER min_p 0
PARAMETER repeat_penalty 1.0
SYSTEM  senior engineer, complete runnable code, no placeholders
```

The empty-think prefill is the mechanism -- verified directly with a raw-prompt A/B:

```
with prefill    :  ```python\ns[::-1]\n```
without prefill :  <think>\nThe user wants a Python one-liner...\n</think>\n```python\ns[::-1]
```

`think: false` on `/api/generate` does **not** stop it (the model just reasons inside `response` instead of the `thinking` channel). The template prefill is the only thing that works.

Verified end-to-end through OpenCode (`opencode run --model ollama/northstar-coder:48k`), a 4-step agentic loop in 50 s:

```
Write fizzbuzz.py            -> created
Read fizzbuzz.py             -> read back
python -m py_compile ... &&  -> PowerShell error
retry with ';' separator     -> COMPILE_OK
summary                      -> correct
```

---

## 5. Current state on disk

| Item | Value |
|---|---|
| Ollama | **0.40.4, Windows native**, `0.0.0.0:11434` |
| Model | `northstar-coder:48k` (27.3 B Q3_K_L, 13 GB) |
| Env (HKCU, persistent) | `FLASH_ATTENTION=1`, `KV_CACHE_TYPE=q4_0`, `CONTEXT_LENGTH=65536`, `KEEP_ALIVE=30m`, `MAX_LOADED_MODELS=1`, `HOST=0.0.0.0:11434` |
| OpenCode | v2.0.32, default model `ollama/northstar-coder:48k` |
| OpenCode server | `--hostname 0.0.0.0 --port 4096`, password in `%TEMP%\opencode\serve2.out` |
| Phone URL | `http://192.168.1.170:4096` (Wi-Fi) or `http://100.101.52.118:4096` (Tailscale) |
| Global config backup | `%USERPROFILE%\.config\opencode\opencode.json.bak.20261025-213836` |

Project `opencode.json` was restored to its tracked chromeconnect config (it had been overwritten earlier this session).

---

## 6. Blocker (needs your admin shell, once)

Windows Firewall rule creation failed without elevation. The phone cannot connect until this runs:

```powershell
# elevated PowerShell
New-NetFirewallRule -DisplayName "OpenCode Server 4096" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 4096 -Profile Private
New-NetFirewallRule -DisplayName "Ollama 11434" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 11434 -Profile Private
```

---

## 7. Model research -- what else fits 16 GB with more context

Pulled from the Hugging Face API (trending + downloads, GGUF + coder filters) and read from each model's real `config.json`, not from blog claims. The number that matters is **KV bytes per token**, because hybrid / linear-attention architectures differ by 5x.

| Model | Params | Full-attn layers | KV/token f16 | Q4 size | Practical max ctx @ 16 GB | Verdict |
|---|---|---|---|---|---|---|
| **Qwen3.8-27B** (yours) | 27.8 B dense | 16 of 64 | 64 KiB | 13 GB @ Q3_K_L | **48K** | best quality that fits |
| **Qwen3.5-9B** / **Ornith-1.5-9B** | 9.65 B dense | 8 of 32 | 32 KiB | ~5.8 GB | **128K+** | best context headroom, 2x faster |
| **Gemma-4-12B** (QAT q4_0) | 11.96 B dense | 8 of 48 + SWA-1024 | 64 KiB on 8 layers | ~7.2 GB | **64K** | best quality below 27B |
| **LFM2.5-24B-A2B** | 24.0 B MoE / 2 B active | 14 of 40 | 28 KiB | ~13.5 GB | 32-48K | fast, but no context win |
| **Qwen3.6-35B-A3B** | 36.0 B MoE / 3 B active | 10 of 40 | 20 KiB | ~21 GB | no | will not fit 16 GB at a usable quant |
| **Qwen3.8-Flash-Next** | 180 B MoE | 12 of 48 | 8 KiB | n/a | no | different weight class entirely |

Notes:
- `Qwen3.8-Flash-Next` is **180 B total** -- the name suggests "small", the config says otherwise. Not a candidate.
- `Qwen3.6-35B-A3B` only fits at Q2_K (~12.5 GB), which is a bad trade on a MoE.
- All Qwen3.5 / 3.6 / 3.8 architectures use `linear_attention` for 3 of every 4 layers, which is why their KV cost is a quarter of a classic transformer's. That is the single biggest lever on this hardware.

### If you want more than 48K on the same model
Nothing left without a trade. `q4_0` KV is already at the bottom of llama.cpp's range; the weights are already Q3_K_L; host RAM is already the binding constraint at 64K. The only real upgrade is **+16 GB DDR5** (~$80), which fixes the `std::bad_alloc` and lets 64K run on the same model.

### If you want a genuinely different coder
`Qwen3.5-9B` or `Ornith-1.5-9B` at Q4_K_M gives ~128K context, ~70-90 tok/s, and ~5.8 GB -- you could run it *alongside* the 27B and switch per task. Quality is below the 27B, but for repo-wide reads it beats a 27B truncated to 16K.

Not recommended as a daily driver: any 9B-class coder. Nothing in the 9-14 B band matches a 27 B model on SWE-bench-style work; the research surfaced no exception.

---

## 8. How to reproduce from scratch

```powershell
# Windows, once
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE","q4_0","User")
[Environment]::SetEnvironmentVariable("OLLAMA_HOST","0.0.0.0:11434","User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE","30m","User")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","65536","User")

ollama create northstar-coder:48k -f <modelfile in section 4>

# Park WSL's GPU budget, then verify
wsl --shutdown
nvidia-smi --query-gpu=memory.free --format=csv,noheader
```

WSL2 can still reach the model -- it just must not host it:

```
$ wsl -d Ubuntu bash -c 'curl -s http://$(ip route show default | awk "{print \$3}"):11434/api/version'
{"version":"0.40.4"}
```

If you ever want `localhost:11434` inside WSL, add `%USERPROFILE%\.wslconfig` with `[wsl2]` / `networkingMode=mirrored`, then point OpenCode's `baseURL` at `http://localhost:11434/v1`. Not done: mirrored networking changes the WSL network identity and was out of scope for a coder-model fix.

---

## 9. Evidence log

| Check | Command | Result |
|---|---|---|
| WSL VRAM tax | `cuMemAlloc` probe | 15 872 MiB -> 11 008 MiB |
| Orphan leak | `Get-Process llama-server` + `nvidia-smi` | 13 536 MiB held, `ollama ps` empty |
| KV math | llama.cpp log | `KV buffer 2040.00 MiB (65536 cells, 16 layers)` |
| 64K crash | ollama server log | `std::bad_alloc` at `prompt_save` |
| Template | `curl /v1/chat/completions` + tools | `finish_reason=tool_calls` |
| Stability | 6 sequential `/api/chat` | 6/6 clean, 100% GPU |
| Agent loop | `opencode run` fizzbuzz | 4 tools, 50 s, `COMPILE_OK` |
