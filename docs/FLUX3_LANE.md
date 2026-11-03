# The FLUX 3 lane — armed, and what it is allowed to do

**Status: armed and verified end to end on 2026-11-03.** `MEDIA_GEN_LIVE=1` (repo-root `.env`), the
gateway answers on `127.0.0.1:8190`, ComfyUI is the runtime on `127.0.0.1:8188`, and a real product
render completed in **24–27 s at 1024×1024**.

## Why it is shaped this way

This box has no CUDA PyTorch outside ComfyUI's virtualenv, so **ComfyUI is the inference runtime**,
not an optional extra. One process (`tools/flux3_gateway.py`) puts a tiny, stable contract in front of
it — `GET /health`, `POST /generate` — and exactly one model behind it: **FLUX 3 Image Klein**
(nvfp4 UNET 4.92 GB + Qwen3-VL-4B encoder 4.52 GB + FLUX VAE). The gateway never starts ComfyUI; if
the runtime is down it reports `503` and the lane blocks, which is the honest behaviour.

FLUX.2 and the other text-correcting vision models were removed on 2026-10-29. There is **no silent
fallback** to another image model, and `tests/test_flux3_failure.py` now pins that.

## Start / stop

```powershell
powershell -File scripts/start-flux3.ps1     # idempotent; starts ComfyUI if needed, then the gateway
powershell -File scripts/start-flux3.ps1 -Stop
```

`scripts/dev-start.ps1` starts the lane with the rest of the dev stack and stops it on exit, so
`MEDIA_GEN_LIVE=1` can no longer point at a gateway nobody launched. Set `NORTHSTAR_NO_MEDIA=1` to
skip it for headless test runs that never generate.

House floors are enforced before a model is loaded: **free disk ≥ 10 GB** and **free RAM ≥ 3 GB**
(refused with a named reason), plus the gateway's own VRAM/temperature guard, which refuses rather
than letting Windows kill a render halfway.

## Who uses it, automatically

| Entry point | Behaviour |
|---|---|
| `POST /api/design-studio/generate` | the studio lane; `provider: local:comfyui`, `cost 0`, credits 0 |
| `chat_tools.generate_image` | Bojo's image tool; refuses with `media_generation_disarmed` when unarmed |
| `tys_ops.routing` | intercepts **visual** requests to the `graphics` lane and runs them here, never on the coding model |
| `tys_ops.graphics` | speaks `GET /health` + `POST /generate` against `FLUX3_SERVER_URL` (default `:8190`) |

When the lane is unarmed every one of those paths says so. Nothing fabricates a render.

## Two render modes, and which one a listing needs

- **Rich brief** (`text_safe` off): the brief goes to the model as written. Good for concept and
  lifestyle imagery. **It will invent lettering on packaging** — measured: a "plain kraft pouch, no
  text or logos" brief came back with `APBDE MUSOROM COFFEE` printed on it.
- **Text-safe brief** (`text_safe: true`): typographic demands are stripped, the model is told
  explicitly to paint no lettering, and the result is **OCR-checked** (RapidOCR, local). The response
  carries the verdict: `text_free` / `text_present` / `text_cleared`. Measured: the same brief
  produced a genuinely blank kraft pouch, `contains_text: false`, 0 boxes.

That is the architecture: **the render supplies a clean photographic plate; typography is composited
afterwards as vector text** on the canvas. It is why the packaging lane can promise sharp,
kerning-correct copy while the diffusion model cannot.

### The bug this exposed (fixed 2026-11-03)

`sanitize_brief_for_render` used to drop an entire clause whenever it mentioned lettering. A
one-clause brief ("…matte kraft pouch…, no text or logos") lost **its subject**, so the render prompt
was the suppression phrase alone and the model answered with an unrelated object (a wheel hub). The
fix strips the *phrase* and keeps the art direction; a **positive** demand ("must read …") still drops
the clause. And when nothing but the demand remains, the lane now **refuses** with
`422 text_safe_brief_empty` instead of rendering a plausible-looking wrong thing.

## Honest limits

- **One model, text-to-image only.** No inpainting/edit lane is declared here (`models.edit: null`);
  the edit/cutout/upscale models on disk are separate lanes with their own entry points.
- **The GPU is shared.** A render needs the local brain unloaded first (`unload_brain`); if it will
  not free in time the render refuses with `vram_busy` rather than thrashing.
- **Quality is per-subject.** Photoreal product shots on white are strong (see
  `reports/ty/shots/flux3_api_proof_text_safe_v2.png`). Fine typography, hands and multi-object scenes
  are exactly where this class of model fails, which is why copy is a separate layer.
- **Local only.** Nothing is sent to any provider and nothing is billed; that is also why the hosted
  deployment cannot use this lane as-is.
