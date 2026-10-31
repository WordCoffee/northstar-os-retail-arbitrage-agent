# Phase II — presentation reconciliation + hardware guardrail

**Date:** 2026-10-30
**Model policy:** DeepSeek V4.1 Flash (OpenCode Go) for all code and reasoning. Local lanes stopped,
per the owner: they are the reserve for when the subscription runs out, not the default. FLUX 3
reserved for visual work; no raster run this pass.

---

## 1. Phase 2 — the four reconciliation items, all done

| # | Item | Before | After | Verified |
|---|---|---|---|---|
| 1 | No user-visible "Simple" | `ShellModeToggle` rendered `<span>Simple</span>` always | Standard / Advanced switch; non-entitled tiers get a static **Standard** chip, not a dead control | Vite serves the module with `Standard`; build 0 errors |
| 2 | Studio default depth unlabelled | `Chrome.jsx` tab `label: 'Simple'` | `label: 'Standard'` (id stays `simple`) | build |
| 3 | Shell switch location | In the top navigation, between search and quick-create | New `shell/SettingsModal.jsx`, opened by a gear in `TopNav`; Escape/backdrop close, focus moves in and returns | `TopNav` module serves with `SettingsModal` |
| 4 | Capability entitlement | `mover` (Keystone) **and** `autothink` carried `advanced_view` | Keystone's `ui_gates` is now `[]`; AutoThinK alone carries `advanced_view`; catalog bumped v4 → **v5** with a dated note | `test_plans_route` + `test_chat_plan`: **23 passed** |

Two further visible strings were changed for consistency: `ChatSurface` sub-line
`Simple view` → `Standard view`, and the display-scale tooltip `(Simple and AutothinK)` →
`(Standard and AutothinK)`. The internal mode id stays `simple` on purpose — routes, gates and the
stored preference all key off it, and renaming state to rename a label is how a shell breaks.

## 2. Phase 4 — hardware guardrail, wired into the render path

`Northstar_backend/hardware_guard.py` implements the rule as arithmetic, so it is testable without a
GPU:

```
used / total < 0.88      and      temp < 85 C
```

- `decide_batch(n, ratio, temp)` → `(batch, reason)`; the batch steps **down** 4→2→1→**0**, and 0 is a
  refusal.
- Unknown VRAM → **refuse**. A box that cannot report is a box that must not be asked to render.
- Thermal ceiling → refuse; within 5 °C of it → run but say so.
- `snapshot()` is the only I/O (`nvidia-smi`), never raises, returns `ok=False` with a reason.

**Wired:** `tools/flux3_gateway.py` calls `plan_render(1)` before it submits to ComfyUI and returns
**503 `hardware_guard`** with the ratio and temperature instead of starting a render it cannot finish.
A missing guard degrades to no-guard rather than breaking the gateway.

**Tests:** `Northstar_backend/test_hardware_guard.py` — **13 passed** (step-down, refusal, thermal,
near-ceiling, unknown, totality).

## 3. Perpetual prompt deployed as a skill

`skills/creative-services-loop/SKILL.md` — the five-stage loop (quality/prompt audit, workflow
optimisation, memory sync, UI/trust compliance, action log), with the rules tightened to what this
repo can actually verify: prepress tolerances, pure-white main images, the text-fidelity gate,
`hardware_guard` before batch renders, and "verified result quotes a measurement, never an opinion".

## 4. Verification

| Check | Result |
|---|---|
| `npm run build` | **0 errors, 1.35 s** |
| `npm test` (UI) | 58 assertions + 11 contrast pairs |
| `pytest test_hardware_guard.py` | **13 passed** |
| `pytest test_plans_route.py test_chat_plan.py` | **23 passed** |
| `flux3_gateway.py` | parses; guard import degrades safely |

## 5. Honest limits — what Phase II still needs

1. **Phase 1 (creative engine scale) is not built.** Multi-angle dieline synthesis beyond the
   existing SVG/PDF renderers, FLUX 3 depth-guided projection onto 3D geometry, the A+ module
   generator and lifestyle ingestion are each a build, not a config change. What exists today:
   `design_studio_print.py` (dielines SVG/PDF), `mockup_compositor.py` (logo + type on a measured
   plate), `studio_generation` (FLUX 3 image), `text_fidelity` (OCR gate), `prepress`. The gap is
   **automation and 3D projection**, not a missing renderer.
2. **Phase 3 (operating-loop integration) is untouched.** Margin/keyword input before a render,
   automatic ListingForge hand-off, and brand memory written into render prompts are all still
   manual. The Memory Bank module exists; the wiring does not.
3. **Phase 4 trust layer is half-built.** The hardware half is now real and tested. "All visual
   verification routes through backend data points" is true for `package_readiness` /
   `text_fidelity` / `prepress`, but storefront and live-listing preview checks do not exist yet.
4. **No render was produced.** ComfyUI is stopped and the GPU is free (16,003 MiB); the gateway is
   not running, so the first FLUX 3 pass still needs `tools/start_comfyui.ps1 --cache-none`.
5. **pass@3 aborted, not failed.** The local lane was stopped mid-attempt-1 on the owner's
   instruction; there is no local result to report, and attempt 1's partial tree is not evidence of
   anything.
