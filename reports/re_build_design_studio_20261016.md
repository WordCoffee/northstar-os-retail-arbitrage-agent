# RE Build — Design Studio: print lane, async lane, design agent

- **Date:** 2026-10-16
- **Source:** implementation of the missing pieces identified in `reports/competitor_re_packify_dyp_20261016.md` (Packify.ai / DYP.ai teardown, evidence commit `297f90a`).
- **Scope shipped this pass:** the three highest-value gaps from the RE plan — no frontend work, no provider spend, engine gates unchanged.

## What shipped

### 1. Print lane — `Northstar_backend/design_studio_print.py`
The keystone gap ("build does not generate dielines" — until now).
- Pure parametric geometry → **layered** vector art: `bleed / trim / fold / safe / marks / info` as real SVG groups (`id="layer-*"`), mm units. The "layered editable dieline" trick, our version, zero AI required.
- **Native PDF renderer via reportlab** (no svglib/cairo added) — single-page, same geometry, dashed folds, rounded rects via `roundRect`.
- 8-template catalog: 5 labels (`rounded_rectangle, rectangle, square, circle, oval`) + 3 cartons (`rsc_box` FEFCO 0201-style, `tuck_end`, `sleeve`) with strict per-template param validation (unknown keys and out-of-range values → 422).
- Every artifact carries the honesty note: *draft geometry — confirm dims/flap depths/bleeds with the manufacturer*.
- Endpoints: `GET /api/design-studio/print/templates`, `GET .../print/health`, `POST .../print/dielines` (persist=True stores SVG+PDF as studio assets; `include_svg`/`include_pdf` inline for previews), `GET .../print/projects/{pid}/export.zip` (asset files + `manifest.json`).

### 2. Async generation lane + credit metering — `Northstar_backend/design_studio_async.py`
The sync `/generate` stays untouched; this adds the missing queued lane.
- `POST /api/design-studio/generate-async` (202) → creates a `queued` ds job, executes on a bounded worker pool (`ds-gen` ×2); `GET /generate-async/{job_id}` to poll (+ live balance when enforced).
- Same engine gate as sync (`MEDIA_GEN_LIVE` + ComfyUI) — no new live surface, no provider, no spend.
- **Credit mechanic is real:** `reserve → commit` on success, `release` on failure, persisted JSONL ledger (`data/credit_ledger.jsonl`), first-use plan allotment per account (idempotent, aligned with the `/api/v1/credits/me` display contract).
- **Policy switch:** default `DESIGN_CREDITS_ENFORCE=0` = meter-only (job records planned cost; `credits_used: 0` — matches current alpha). With `DESIGN_CREDITS_ENFORCE=1` it is fail-closed: insufficient balance → HTTP 402.

### 3. Design agent — `Northstar_backend/design_studio_agent.py`
Chat → structured brief (Packify "Initial Analysis" / DYP `[PRODUCT]/[SCENE]` assembly, our deterministic version).
- `POST /api/design-studio/agent/brief` → `{reply, brief, enqueued}`; brief = palette (8 keyword-mapped palettes), suggested dieline templates from message/product keywords, copy blocks, directives, negative prompt, and an assembled `[PRODUCT]/[FORMAT]/[PALETTE]/[COPY]/[DIRECTIVES]/[NEGATIVE]` prompt.
- `enqueue=true` submits the assembled prompt to the async lane (same gates/credits).
- Optional local-LLM sharpening via `DESIGN_AGENT_LLM=1` (AutothinK adapter); **fail-open** — deterministic default.

### Wiring
`Northstar_backend/main.py`: guarded imports + `include_router` for all three modules (same pattern as the existing design-studio router).

## Test evidence (real runs)

- Unit + endpoint suites: **24 passed, 0 failed**
  `python -m pytest test_design_studio_print.py test_design_studio_async.py test_design_studio_agent.py` → 20 passed
  `python -m pytest test_design_studio_re_ext.py` → 4 passed (auth boundary 401, templates, dieline roundtrip + 422s, agent brief)
- Live E2E smoke against the dev DB + file store (`python _re_ext_e2e_smoke.py`, run from `Northstar_backend/`): **ALL PASS** —
  project created → 2 dielines persisted (4 SVG+PDF assets) → all files served (1.5–2.7 KB each) → ZIP export contained all 4 assets + `manifest.json` → agent brief mapped "stand-up pouch" → `label_rounded_rectangle` → cleanup OK.

## Operator runbook

```powershell
# tests (no engine, no network)
cd "Northstar OS Retail Arbitrage Agent\Northstar_backend"
python -m pytest test_design_studio_print.py test_design_studio_async.py test_design_studio_agent.py test_design_studio_re_ext.py -q

# live E2E against the dev store (repeatable; cleans up its project)
python _re_ext_e2e_smoke.py

# async lane end-to-end with the real local engine
$env:MEDIA_GEN_LIVE = "1"            # + ComfyUI reachable at COMFYUI_URL
$env:DESIGN_CREDITS_ENFORCE = "1"    # real reserve/commit/release; unset for meter-only
# then, in the UI session: POST /api/design-studio/generate-async {"brief": "...", "kind": "image"}
# poll GET /api/design-studio/generate-async/{job_id}
```
All endpoints resolve the strict org-scoped session (`studio_account`) — call them with the UI session cookie/Bearer, or a `studio_account` dependency override in tests (see `test_design_studio_re_ext.py`).

## Not shipped yet (from the RE plan, in order)
1. Public API keys + webhook callbacks with retry policy (Packify-style `/api/open/<version>/...`) carrying compliance evidence.
2. Mockup scene/product gallery on the existing compositor.
3. Canvas-editor frontend wiring (fabric.js-style) consuming the layered SVG + canvas_data persistence.
4. Optional: expose plan-grant + balance admin endpoints for the enforced-credit mode.

## Files
- New: `Northstar_backend/design_studio_print.py`, `design_studio_async.py`, `design_studio_agent.py`
- New tests: `test_design_studio_print.py`, `test_design_studio_async.py`, `test_design_studio_agent.py`, `test_design_studio_re_ext.py`
- New (manual runbook script): `Northstar_backend/_re_ext_e2e_smoke.py`
- Edited: `Northstar_backend/main.py` (router wiring), `00_STATE.json` (known_issues entry, resolved)
- RE evidence/teardown: commit `297f90a` + `research/packify_dyp_re_20261016/`
