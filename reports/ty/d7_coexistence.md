# D7 — coexistence test: what actually fits on 16 GB

Measured 2026-11-07 with `tools/coexist_probe.py`. Every row is one probe: VRAM from
`nvidia-smi`, RAM from `GlobalMemoryStatusEx`, `capture_ms` as the UI-responsiveness
proxy (median of three real desktop grabs through the vision capture path, so it measures
what the desktop is actually doing). Raw rows: `state/director/coexist.json`.

| step | VRAM used | VRAM free | RAM free | capture | resident |
|---|---|---|---|---|---|
| 0 idle baseline | 0.00 | 15.63 | 6.97 | 91 ms | — |
| 1 Bojo + embeddings resident | **5.15** | 10.48 | 5.40 | 89 ms | bojo + embeddings, both 100% GPU |
| 2 27B `llama-server` up (Ollama drained) | **14.32** | **1.31** | **0.04** | 114 ms | 27B only |
| 3 27B stopped | 0.00 | 15.63 | 7.68 | 92 ms | — |
| 4a before ComfyUI render | 0.00 | 15.63 | 7.61 | 88 ms | — |
| 4b after ComfyUI render | **4.25** | 11.38 | 7.14 | 99 ms | ComfyUI models retained |
| 5 restored: Bojo + embeddings | **9.41** | 6.22 | 5.42 | 94 ms | bojo + embeddings + ComfyUI |

ComfyUI rendered three media in this run, not one: `flux3` 28.3 s (`ns-smoke-flux3_00001_.png`),
`wan` 84.5 s (`ns-smoke-wan_00015_.mp4`), `tts` 24.1 s. `seedvr2` skipped: files not
staged. Evidence: `reports/comfy_media_smoke_20261107_230415.json`.

## Conclusions, with the number that decides each

1. **Bojo + embeddings on the GPU together is confirmed safe.** 5.15 GB VRAM and
   5.40 GB RAM free, with the desktop unchanged (89 ms vs 91 ms idle). This is the
   resident set the lock manager keeps.
2. **The 27B cannot coexist with anything.** At `-ngl 99 -c 17408` it takes 14.32 GB of
   VRAM and leaves **0.04 GB of RAM free** — 40 MB, far below the 2 GB floor, and the
   reason the historical pin existed. It must be an **exclusive lease**: everything else
   is drained first and restored afterwards. Capture still answered in 114 ms, so the
   window station did not die, but this is not a state to leave the machine in.
3. **ComfyUI and the resident set do coexist.** After a render ComfyUI keeps 4.25 GB;
   with Bojo + embeddings reloaded the total was 9.41 GB used, 6.22 GB free, RAM 5.42 GB,
   capture 94 ms. Nothing was OOM-killed and every budget check passed.
4. **Nothing ran out of memory at any step.** No allocation failure, no process death,
   no swap-driven timeout. The only failure was the *budget verdict* at step 2, which is
   the check doing its job rather than a crash.
5. **The UI stayed responsive throughout** (88-114 ms capture, a 1.3x spread). The
   27B step is the only one that visibly costs, and it is the exclusive one.

## Budgets set from these numbers

| role | measured VRAM | budget | why |
|---|---|---|---|
| Bojo | 3.07 | 3.5 | measured + headroom |
| embeddings | 2.08 | 2.5 | measured + headroom |
| coder (`qwen3:8b`) | 6.63 | 7.0 | measured + headroom |
| vision (`qwen2.5vl:7b`) | 7.41 | 8.0 | 65k context, q4_0 KV |
| image (ComfyUI) | 4.25 resident, ~10.5 peak during flux3 | 11.0 | the peak is the binding number |
| 27B | 14.32 | 14.5, **exclusive** | plus the RAM floor failure above |

`OLLAMA_MAX_LOADED_MODELS` is now 2 in the User environment (was 1), which is what makes
the resident pair possible. It is recorded in `reports/ty/gpu_env_restore.md` with the
rest of the old values.

## The trap this test fell into twice, and the lesson it proves

The first two attempts at step 1 put both models back on the CPU. The User-scope pins had
been cleared, but **every new shell inherited `OLLAMA_LLM_LIBRARY=cpu` and
`OLLAMA_NUM_GPU=0` from the parent process**, and `Start-Process` handed that inherited
environment to the server. Clearing the variables in the launching shell is what fixed it;
clearing them in the registry alone was not enough. The same was true of
`OLLAMA_MAX_LOADED_MODELS`, which meant two models evicted each other even after the User
value was raised.

This is the concrete case behind lesson L1: a diagnosis run that inherits environment pins
is not independent evidence.
