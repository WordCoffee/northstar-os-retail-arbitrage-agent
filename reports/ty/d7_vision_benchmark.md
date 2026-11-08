# D7 — vision benchmark: three installed candidates, one usable

Measured 2026-11-07 on the RTX 5080 with the pins removed (all candidates ran 100% GPU).
The task was the V1 screen-awareness prompt against a live 2560×1600 desktop, downscaled
to 1280 wide before encoding.

## Results

| candidate | licence / source | device | answer to "describe this screen" | JSON prompt | verdict |
|---|---|---|---|---|---|
| `qwen2.5vl:7b` | Ollama library, Apache-2.0 | 100% GPU | `" the ``` image"` | `" screenshot windows"` | **unfit — degenerate** |
| `moondream:latest` | Ollama library, Apache-2.0 | 100% GPU | `"xtop."` | not attempted | **unfit — degenerate** |
| `llava:7b` | Ollama library, Apache-2.0 (LLaVA weights: Llama-2 community licence) | 100% GPU | "The screen displays a computer monitor with a chat window open…" | `{"apps":[{"name":"Visual Studio Code","purpose":"Code editor","focus":true}],"foreground":""}` | **chosen** |

`qwen2.5vl:7b` was tested at `num_ctx` 4096, 8192 and 65536, at temperature 0.0, with and
without `format: json`, and with `repeat_penalty` 1.1. It returned a word fragment every
time. This is not a new finding: `ty_83b_gpu_evaluation_20261101` recorded the same model
producing "Rencontre Rencontre Rencontre…" *"on the GPU and on the CPU alike"*. Two
independent measurements now agree, on two different machines-worth of configuration.

## What was fixed on the way

- **The frame was too big.** A 2560×1600 PNG made the multimodal encoder fail with
  `mtmd_batch_encode: std::bad_alloc` while Bojo and embeddings were resident. Frames are
  now downscaled to 1280 wide before encoding; app identification does not need native
  resolution and the cost scales with pixels.
- **Vision needed a companion rule.** Bojo + embeddings + vision (12.56 GB) left the
  encoder with too little working memory. `COMPANIONS["vision"] = ("bojo",)` keeps Bojo and
  evicts the embedding model, which is reloadable in under a second.

## Acceptance, with the number

| test | result |
|---|---|
| **V1** screen awareness, no browser | **pass** — valid JSON, `Visual Studio Code`, 0.8 s, 100% GPU |
| **V2** find a named element and read it | **pass** — 20/20 against a real WinForms window; field value read back as `typed value` |
| **V8** vision + Bojo resident, VRAM/RAM recorded | **pass** — 10.29 GB VRAM used / 5.33 GB free, RAM 6.09 GB free, capture 89 ms, no OOM, lock respected |

## Budget consequences

`llava:7b` is 5.19 GB resident versus `qwen2.5vl:7b`'s 7.41 GB, so the vision budget drops
from 8.0 to 6.5 and Bojo + vision together now sit at 10.29 GB with 5.33 GB to spare —
enough for ComfyUI to reload between vision calls.

## What this means for the candidate list in the work order

UI-TARS 1.5, OmniParser and ShowUI are **not installed** and were not benchmarked. They are
the right next candidates for *grounding* (click coordinates), which `llava:7b` is weak at:
it describes a screen well enough for V1 but it is not a GUI-grounding model. That is a D16
model-scout job with a fixed eval set, not a D7 blocker — V2 is served by UI Automation,
which is deterministic and needs no model at all.

---

# CORRECTION 2026-11-08 (D8): the qwen2.5vl verdict was an artefact of the server config

Owner instruction on 2026-11-08: *retest qwen2.5vl:7b on a clean server (no KV-cache
quantisation, num_ctx about 8192); overwrite the old verdict if it changes.* It changed.

The 2026-11-07 run was made against a server whose environment carried
`OLLAMA_KV_CACHE_TYPE=q4_0` and `OLLAMA_CONTEXT_LENGTH=65536`. That is a quantised KV cache
and an eight-times-larger context than the task needs; on a 16 GB card it is also the most
likely cause of the encoder failure the D7 notes blamed on frame size.

Clean server: `OLLAMA_KV_CACHE_TYPE=f16`, `OLLAMA_CONTEXT_LENGTH=8192`, one loaded model,
ComfyUI stopped so the GPU was actually free (10.0 GB free at load).

| model | warm latency | JSON | what it named | verdict |
|---|---|---|---|---|
| `qwen2.5vl:7b` | **0.47–0.75 s** | valid | `OC \| Ty director finish order` — the real terminal window title | **coherent; now the default** |
| `llava:7b` | 1.89–1.91 s | valid | `Visual Studio Code`, `Windows Start Menu`, `Control Panel`, `Action Center` — none of them open | coherent-sounding, factually wrong |

The window list at that moment held a Windows Terminal titled `OC | Ty director finish
order`, Settings, the Realtek Audio Console and Chrome. qwen2.5vl named the terminal
exactly; llava invented four plausible-sounding windows. That is a clear margin on the only
thing that matters — reading the screen that is actually there — and it is 3× faster.

Evidence files: `reports/ty/d8_qwen25vl_clean11434.json`,
`reports/ty/d8_vision_retest.json`, `reports/ty/d8_vision_retest_llava.json`.
`tools/vision/understand.py` now defaults to `qwen2.5vl:7b` with `num_ctx` 8192;
`llava:7b` is kept as `MODEL_FALLBACK`. V1 was re-run after the swap and still passes
(`test_vision_structure.py`: 9 passed).

Two things this does **not** claim: qwen2.5vl is still not a grounding model (the 40-screen
grounding benchmark is in `reports/ty/d8_grounding.md`), and moondream was not retested —
nothing about the q4_0 cache would explain `"xtop."` on a 1.7 GB model, so the old verdict
stands for it.
