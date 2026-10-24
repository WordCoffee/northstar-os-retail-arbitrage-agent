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

## Second pass (2026-10-16, same day) — remaining RE-plan items shipped

### 4. Public API + webhooks — `Northstar_backend/design_studio_openapi.py`
- **API keys**: session endpoints `POST/GET /api/design-studio/api-keys`, `DELETE .../api-keys/{id}`. Format `nsk_<48 hex>`; the store (`data/api_keys.jsonl`) keeps **sha256 digests only** plus a display prefix; revocation is a persisted tombstone. No plaintext is ever recoverable.
- **Open endpoints** (`X-Api-Key` or Bearer): `POST /api/open/2026-10/packaging-design` (202, async submission through the async lane — identical engine gate (409) and credit policy (402)), `POST /api/open/2026-10/dielines` (synchronous layered SVG+PDF assets — our differentiator vs Packify's photoshoot-only API), `GET /api/open/2026-10/jobs/{job_id}`.
- **Webhooks**: any submission may carry `callback_url` (http(s), validated). Completion/failure delivers a JSON payload (`job_id, status, asset_ids, asset_urls, provenance`) with the bounded retry policy — immediate → 1s → 4s, success = HTTP 2xx — and the delivery record is stored on the job's params. Webhook failure never fails the job.

### 4b. Credit meter endpoints — same module
- `GET /api/design-studio/credits` (balance, costs, last 20 entries, enforce flag) and `POST /api/design-studio/credits/grant` (idempotent first-use plan allotment; unknown plans → 400).

### 2. Mockup scene/product gallery — `Northstar_backend/design_studio_scenes.py`
- `GET /api/design-studio/scenes` — 8 curated scenes × 8 product types (templates cross-checked against the print catalog in tests).
- `POST /api/design-studio/mockup/plan` — deterministic `[PRODUCT]/[SCENE]/[CUSTOM PROMPT]/[NEGATIVE]` assembly (DYP's recipe, explicit); `enqueue=true` submits to the async lane.

### 3. Dieline/print frontend — `northstar-os-ui`
- New Design Studio section **"Dielines & Print"** (`src/pages/internal/design-studio/Dielines.jsx`, registered in `DesignStudio.jsx`): live layered-SVG preview, param editor driven by the template catalog, Download SVG/PDF, Save-to-library (SVG+PDF assets), project ZIP export link, and the Mockup planner card (scene/product selects + custom prompt → assembled prompt + optional queue).
- `Packaging.jsx` rule text updated: "Dielines are drafted in Dielines & Print" (the old "out of scope" claim is no longer true).

## Test evidence (second pass, real runs)
- `python -m pytest test_design_studio_scenes.py test_design_studio_openapi.py` → **11 passed**
- Regression: `test_design_studio_print/async/agent/re_ext` → **24 passed** (35 total for the RE build)
- Webhook delivery is exercised against a **local HTTP receiver**: success = 1 attempt/200; failure = exactly 2 bounded attempts on a 500 responder.
- Key store proves digest-only storage on disk; verify/revoke/reload lifecycle covered.
- `npm run build` (northstar-os-ui) → **built successfully** (pre-existing chunk-size warning only).
- Live E2E smoke (`python _re_ext_e2e_smoke.py`) now also covers: key create → 401 without key → open dielines with key (2 assets) → open design accepted-or-gated (202/409) → revoke → revoked key rejected.

## Operator runbook (additions)

```powershell
# UI: open /design-studio?section=dielines (Dielines & Print)
# Open API quick probe (session cookie needed for key minting; key call needs no session):
#   POST /api/design-studio/api-keys {"label":"desk"}       -> { key: { key: "nsk_...", id } }
#   POST /api/open/2026-10/dielines {"template_id":"rsc_box"}      X-Api-Key: nsk_...
#   POST /api/open/2026-10/packaging-design {"prompt":"...","callback_url":"https://..."}
#   GET  /api/design-studio/credits   /  POST /api/design-studio/credits/grant
```

## Files (second pass)
- New: `Northstar_backend/design_studio_scenes.py`, `design_studio_openapi.py`
- New tests: `test_design_studio_scenes.py`, `test_design_studio_openapi.py`
- Rewritten: `Northstar_backend/design_studio_async.py` (callback_url + `deliver_webhook` + job webhook records)
- Edited: `Northstar_backend/main.py` (router wiring ×2), `Northstar_backend/_re_ext_e2e_smoke.py` (open-API section), `00_STATE.json`
- New UI: `northstar-os-ui/src/pages/internal/design-studio/Dielines.jsx`; edited `DesignStudio.jsx`, `Packaging.jsx`

## Text-Fidelity pipeline (2026-10-16, later same day)

**Problem reported:** renders carried garbled lettering ("MUSHROOMPOWEER"); the documented blueprint rule ("never let the model draw letters") was not being enforced in the generation lane, and under VRAM contention ComfyUI OOM'd mid-render.

**Shipped (`text_fidelity.py` + lane wiring + `studio_generation.py` hardening):**
1. **Pre-render guard** — `sanitize_brief_for_render`: strips typographic demands (brand names incl. TitleCase, quoted strings, ALL-CAPS runs, weights, barcode/QR/Supplement-Facts lines, dimension callouts) while keeping art direction (materials, palette hexes, illustration style, format). Demand lines are handled at **clause level** — a sentence that also carries art direction ("…warm charcoal-black matte instead of green. Text reads …") keeps the art clause and drops only the typographic one. A `hard` escalation removes every remaining capitalized word and digit.
2. **Post-render check** — real offline OCR (rapidocr, CPU): `POST /api/design-studio/text-check/{asset_id}` + automatic per-render verdicts (`text_free` / `text_present` / `text_cleared` / `text_reduced`).
3. **Bounded auto-rerun** — on detected lettering, ONE retry with the hardened prompt (new composition), both attempts recorded.
4. **Deterministic cleanup (the "fix")** — 4B models keep hallucinating decorative glyphs; `clean_text_regions` detects glyph zones and clears them with locally-sampled median fills (feathered), then re-checks. Stored asset ships as a **clean plate** for the real vector text layer.
5. **VRAM hardening** — `unload_brain` now *verifies* Ollama eviction (`/api/ps` poll) before rendering; OOM failures trigger exactly one re-eviction + ComfyUI cache release + retry; failed renders always release ComfyUI's cache (the old code left it crammed → instant-OOM death spiral). All covered by `test_studio_render_guard.py`.

**Live E2E (real MOGRA 4.5k-char brief, through the Cloudflare URL, async lane):**
`running → done (40s)` · attempt 1 lettering detected ("Organic Shitake", "Mussham Prowver"…) · hardened rerun → pseudo-glyphs only · **cleanup: 14 zones cleared, 14 → 0 boxes** · final verdict **`text_cleared`** · stored asset re-checked **contains_text: False**. Asset `def590e2-0ad0-4ed8-b6a7-47affb24c22a`.

**UI:** "Text-safe render" checkbox (ON by default) in the studio Generate card; rows show `· text-free ✓ / · ⚠ text seen / · text cleared (auto-rerun)`; generation now goes through the async lane with polling, so long renders can't be cut by tunnel timeouts.

**Test evidence:** 52/52 across the RE suite (`test_text_fidelity.py` 15 incl. OCR + cleanup + guard tests; `test_studio_render_guard.py` 4; existing 33).

## Mockup compositor — the typography pass (service, UI, tests)

**The gap this closes:** clean-plate renders had no lettering (by design) and the operator's real logo / real words never made it onto the pouch. The compositor is the deterministic finishing lane.

**Shipped:**
- `Northstar_backend/mockup_compositor.py` — reusable core: exact 4-point homography warp (numpy, bilinear, shading-blended into the plate's luminance), feathered circular + rectangular erases (ring-median colour, no halos), logo preparation (frame-crop + field-colour detection), extracted line-art glyph recolouring, vector-drawn certification icons (organic sprout, Non-GMO butterfly, gluten-free wheat+slash, fruiting-body mushroom), Playfair/Inter typography with tracking, panel templates (`mogra-forest-dusk` first).
- `Northstar_backend/design_studio_compose.py` — session API: `GET /api/design-studio/compose/templates`, `/presets`, `POST /compose/mockup` (plate asset + template + optional SKU/quads/erase overrides + `logo_data_url`; writes the composed PNG + registers it as a studio asset).
- `data/compose_presets.json` — per-plate geometry preset (quads, erase circles/rects, glyph box, SKU texts, operator logo path). Honest limitation: a NEW plate needs its own quad pass (grid overlay) before composing.
- **UI:** CreativeStudio queue rows now offer **“✦ Type pass”** on finished renders that have a preset — one click composites the real logo + fonts + icons and adds a `Composed — …` row with the link.
- Fonts committed with OFL notice under `Northstar_backend/assets/fonts/` (Playfair Display, Inter).
- Tests: `test_mockup_compositor.py` (homography corner-exactness, circular + rect erase, panel content, icons, compose e2e on synthetic plate, service endpoint incl. auth/404/happy path). Suite total: **61 passed**.

**Live results (real plate 44318b, real operator logo, via the service):**
- v2 asset `e1fbc729-…-e1fbc729` → then icon-row fix → v3 asset **`db9cc274-fcc3-48a5-8db5-513537f54628`** (single drawn icon row, real logo roundel, real typography, gold engraving, weight footers).

**Also fixed this pass:** pytest sessions now default `NORTHSTAR_DISABLE_RATE_LIMIT=1` in `conftest.py` (matching `scripts/run_all_tests.ps1`) — the anonymous 30 req/min token bucket made larger ad-hoc suites order-dependent.

## Dieline-art lane — true-scale print sheets without any model text

**Why (operator: "its still generating like shit" on the dieline sheet):** diffusion renders of "print-ready sheets" carry ghost blurs where text was and rotated micro-text OCR cannot read — a render can never be the print deliverable. The deterministic lane that CAN be it now exists:

- `dieline_art.py`: panel-art ops in **millimetre space** rendered two ways — **300-dpi PNG** preview and a **true PDF** (reportlab, embedded Playfair/Inter, real logo image) — drawn on top of the `doypack` dieline geometry (front/back/gusset grounds in the SKU colourway, 3 mm bleed, weld/fold/zip marks). Front: cream logo roundel with the operator's real lockup + gold ring, Playfair product name, tracked subtitle, **four drawn certification icons**, weight footer with rules. Back: title, description, **reserved Supplement-Facts block (65×110 mm, white with black rules)**, **reserved QR + UPC boxes**, storage/origin/distributed-by lines. Gusset carries the wordmark line.
- Layout regression-tested: panel grounds painted first (front pixel = kraft), title ink present, **facts block never overlaps the QR/UPC row** (that overlap was caught in the first draft), PDF magic + size.
- `build_doypack` now exposes `meta.panels` (front/gusset/back rects + zip line) for downstream composition.
- Sheets registered as studio assets (`dieline-art`): Lion's Mane `55a47062…` (PNG) / `3ace8166…` (PDF); Shiitake `f973f54f…` (PNG) / `8f14d6d1…` (PDF).

**Honest remainders:** no mushroom motif on the front yet (the model's engraved mushroom crops in as the art layer next); PDF type is embedded, not outlined; presentation sheet pending. Suite: 14/14 lane tests (63+ total).

## Status vs the RE plan
All four items closed: (1) public API + webhooks ✅, (2) scene/product gallery ✅, (3) frontend dieline section ✅, (4) credit admin endpoints ✅. Remaining optional follow-ups: fabric.js-style freeform canvas editing on top of the layered SVG (the current editor is param-driven by design), and wiring the enforced-credit mode to a real PSP (pricing rails stay test-mode per repo posture).
