# Creative Generation Architecture — Path B (2026-10-04)

> Owner-approved **Path B: CLOUD-PRODUCTION GENERATION ARCHITECTURE**.
> Branch `feature/creative-cluster-launch`. Provider-neutral, **UNARMED**.
> No ComfyUI install, no weights, no `MEDIA_GEN_LIVE`, no render route, no
> provider contact, no credits.

## What was built

### `Northstar_backend/media_providers.py` (new)
The hosted image/video generation **interface**:
- **Provider registry** derived from `shared/model-suite.json` (fal, OpenRouter,
  Replicate) — capability kinds, models, planning costs, key **presence** bool,
  and armed state. No env values, tokens, URLs, or provider config returned.
- **Capability descriptors** — `image.generate`, `image.edit`, `video.generate`
  (aspects, durations, text-in-image, audio).
- **Capability→cost routing hooks** — `route(kind, quality)` returns the cheapest
  matching provider entry; `estimate_cost(unit, unit_cost, seconds)`.
- **Generation plan** — `plan_generation(...)` returns only a status
  (`not_armed` | `provider_required` | `ready`) plus the routing/cost metadata.
  It **never** contacts a provider or generates.
- **Planning spend caps** — `SPEND_CAPS` (`per_call`, `per_image`,
  `per_video_clip`, `per_day`; `enforced=False`). Not written to any ledger; the
  authoritative ledger records only real provider-returned usage.

### `foundation/api/creative.py` (extended)
`GET /api/v1/foundation/creative/readiness` now also returns `providers`,
`capabilities`, `routing_hooks`, and `spend_caps` — metadata only, still no
secrets, still unarmed.

### UI (`CreativeStudio.jsx`)
Provider Readiness (live branch) lists the provider roster with capability kinds
and `gated` / `no key` state, plus planning spend caps, explicitly labelled
**unarmed** and **planning, not enforced**. No prompt/render/upload control is
added.

## Generation activation status
**UNCHANGED — PLANNED / NOT ARMED.** `MEDIA_GEN_LIVE` false; no engine; no render
route; no provider contacted; no credits. Path B prepares the production path
without arming it.

## Validation
- `python -m pytest Northstar_backend/foundation/tests/test_creative_readiness.py
  Northstar_backend/foundation/tests/test_media_providers.py` → **16 passed**
  (roster secret-free, routing, cost math, unarmed plan, authenticated route
  with providers/spend_caps; offline).
- `npm run build` → 0 errors.
- `verify-smoke` 42/0 · `verify-guards` 11/0 · `verify-acceptance` 32/0.
- `capture-creative-cluster.cjs` 82/0 (live contract + provider roster +
  spend caps).
- `git diff --check` clean.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/creative-studio-desktop-readiness-live.png`
(untracked) — live readiness with the unarmed provider roster + spend caps.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `3cf83a5` (backend `media_providers.py` + extended readiness; UI roster; this report)
**Readiness routes inspected/added:** existing `GET /api/v1/foundation/creative/readiness` extended (no new route); `model_router` suite/gate reused; `shared/model-suite.json` is the config source
**Readiness contract:** adds `providers[]` (label, kinds, key_present bool, armed bool, models with planning costs), `capabilities[]`, `routing_hooks{}`, `spend_caps{}` (`enforced:false`) — still no secrets/env values/URLs/provider config
**UI truth wiring:** Provider Readiness live branch shows the unarmed provider roster + planning spend caps; no generation control; room stays PLANNED / NOT ARMED
**Generation activation status:** UNCHANGED — PLANNED / NOT ARMED; `MEDIA_GEN_LIVE` false; no render route; no provider contact; no credits
**Tests/builds run:** backend 16/0 (offline) · `npm run build` 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 82/0 · `git diff --check` clean
**Screenshots captured:** `creative-studio-desktop-readiness-live.png` (unarmed roster + spend caps)
**Remaining generation gates:** explicit provider approval (select provider, provide key, set `MEDIA_GEN_LIVE`), then a render route returning `provider_required` when unavailable; asset store for outputs; ledger-backed spend enforcement
**Blocked items:** none beyond the deliberate provider-approval gate
**Recommended next action:** keep generation unarmed. When a provider is approved, wire `media_providers.route/plan_generation` into a render route behind `MEDIA_GEN_LIVE` + key presence, enforce `SPEND_CAPS` against the foundation credit ledger, and flip readiness to `provider_gated`/`local_available` only when genuinely reachable.
