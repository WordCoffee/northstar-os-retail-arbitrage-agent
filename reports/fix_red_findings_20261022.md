# Three red findings — fixed and verified

**Date:** 2026-10-22 · **Branch:** `feature/v4.1-mesh` · **Lane:** local · **Spend:** $0

All three issues logged during the deep clean are closed with live evidence, not assertions.

---

## 1. The local 27B model now loads — root cause was context, not CUDA

**Symptom:** `POST /api/generate` → 500. Log: `CUDA error: shared object initialization failed` at
`ggml-cuda.cu:109` in `launch_fattn`, then `llama-server terminated exit status 0xc0000409`.

**What it was not:** not VRAM (15.6/16.3 GB free at the time), not the CUDA stack (the 0.6b embedding
model answered on the same runner), not flash attention per se.

**What it was:** the model's Modelfile baked `PARAMETER num_ctx 64576`. At that context the flash-attention
kernel's `cudaOccupancyMaxActiveBlocksPerMultiprocessor` call fails on this 16 GB Blackwell laptop.

Bisection (all with the operator's `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`):

| ctx | result |
|---|---|
| 8,192 | OK — 11.8 s, 12.9 GB VRAM |
| 16,384 | OK — 10.8 s, 13.2 GB |
| 32,768 | OK — 35.7 s |
| 64,576 | **crash** |

Two dead ends recorded because they were real: `FLASH_ATTENTION=0` fails with
`quantized V cache requires flash_attn to be enabled`; `FLASH_ATTENTION=0 + KV=f16` OOMs once ComfyUI
is holding VRAM (the product needs both processes, so that combination is not viable).

**Fix:** model recreated with `num_ctx 16384`, every other parameter byte-identical
(`num_predict 6000`, `repeat_penalty 1.1`, `temperature 0.35`, `top_p 0.9`, `min_p 0.05`).
Original preserved as tag `northstaros-qwen3.8:27b-ctx64k-orig` — manifest only, same blob, no extra disk.

```
DEFAULT_PATH_OK: 'We need to respond exactly "OK".' in 10.5s
NAME                       SIZE    PROCESSOR    CONTEXT   UNTIL
northstaros-qwen3.8:27b    13 GB   100% GPU     16384     Forever
```

No options override, no env hacks — the path the app actually uses.

---

## 2. Studio now talks to the ComfyUI that exists

`studio_generation.DEFAULT_COMFYUI_URL` was `http://127.0.0.1:8199`, from a doc note describing a
"dev/diagnostic port" split. Nothing listened on 8199; every real run is 8188. No test asserted it.

Changed to `8188` in `studio_generation.py` (constant + docstring), `render_studio_plates.py`
setdefault, and the `docs/MEDIA_STACK_2026-10.md` runtime section. `COMFYUI_URL` still overrides.

```
default url: http://127.0.0.1:8188
ComfyUI ready on 8188 (0.40.0, 1376 nodes, 9 UltraTex nodes, all 4 LTX extra paths)
```

## 3. Local vision — my original diagnosis was wrong, and the correction matters

I had logged "`qwen2.5vl:7b` is not installed". The truth is subtler: `model_router`'s literal
`LOCAL_MODELS` says `qwen2.5vl:7b`, but the `shared/model-suite.json` overlay **replaced every V tier
with `northstaros-qwen3.8:27b`**. That model *is* installed — it just has no projector:

```
ollama show northstaros-qwen3.8:27b → Capabilities: tools, thinking, completion   (no vision)
```

So the local vision tier was pointing at a text-only model. Three-part fix:

1. `shared/model-suite.json` V1/V2/V3 `understand.local` → `qwen2.5vl:7b`.
2. `ollama pull qwen2.5vl:7b` → 6.0 GB, capabilities now include `vision`.
3. `model_router.resolve_vision(..., installed=...)` returns `local_model_not_installed` when the
   configured model is absent, and `catalog()` now exposes `vision_local_status` so the UI cannot
   show a vision tier as available without weights behind it.

Live proof on a real Northstar plate (17.1 s):

> "Two bags of organic mushroom powder, one labeled "Organic Lion's Mane" and the other "Organic
> Shiitake," are displayed on a wooden surface in a greenhouse setting."

```
vision_local_status: {'V1': 'ok', 'V2': 'ok', 'V3': 'ok'}
/api/v1/models local.installed includes qwen2.5vl:7b
```

---

## Verification

```
python -m pytest test_model_router.py test_provider_suite.py -q   49 passed
npm run build                                                     0 errors
```

Test changes are deliberate and recorded: `test_local_defaults_by_tier` and
`test_resolve_vision_understand_local` now expect `qwen2.5vl:7b` for V tiers (the 27B is text-only),
plus two new tests for the installed-aware path and `vision_local_status`.

## New state of the box

```
C: free            92.6 GB
Ollama             0.40.4 · 27B loads at 16k, 100% GPU · qwen2.5vl:7b vision live
ComfyUI            0.40.0 on 8188 · 1376 nodes · UltraTex + LTX wired
Studio default     http://127.0.0.1:8188
```

## Remaining honest note

`northstaros-qwen3.8:27b` still carries a **stale SYSTEM prompt baked into the Modelfile** (the
pre-provider-suite capsule text). When the app sends its own system message this is inert; when it
does not, the model answers from the old constitution. Rebuilding that SYSTEM block is a separate,
deliberate change — it alters model behaviour, so it is not being done inside a bug-fix pass.
