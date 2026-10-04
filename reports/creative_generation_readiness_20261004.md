# Creative Generation Readiness Architecture (2026-10-04)

> Branch `feature/creative-cluster-launch`. Commits: backend readiness route,
> UI wiring, this report. **Readiness ≠ activation.**

## What was built (read-only, provider-neutral)

**Route:** `GET /api/v1/foundation/creative/readiness`
(`Northstar_backend/foundation/api/creative.py`, mounted additively in
`foundation/app.py` and `main.py`). Authenticated via the standard
`get_context` dependency; read-only; no writes.

**Contract (no secrets):**
```
{ "generation": "local_available" | "provider_gated" | "planned_not_armed"
                | "unavailable" | "probe_failed",
  "armed": bool, "media_live": bool,
  "backend": "local" | "cloud" | "none",
  "local_engine": { "state": "reachable" | "unreachable" | "unknown",
                    "kind": "comfyui" | "none" },
  "cloud_key_present": bool,        // presence only — never the value
  "provider_gated": bool,
  "reason": "media_gate_off" | "ok" | "cloud_key_present" | "engine_unreachable" | "no_backend",
  "probe": "performed",
  "checked_at": "<iso8601>",
  "notes": "Readiness only — does not activate generation, publish, or transfer media." }
```

**State machine:** `armed=false` → `planned_not_armed` (default);
`armed=true` + local reachable → `local_available`; armed + cloud key →
`provider_gated`; else `unavailable`; probe error → `probe_failed`.

**The only probe** is a bounded 0.3 s **localhost** TCP reachability check of the
operator's own engine (default ComfyUI at `COMFYUI_URL`). It never installs,
starts, loads a model, arms `MEDIA_GEN_LIVE`, contacts a provider, or consumes
credits. Never raises. The module returns **no** env values, tokens, URLs, or
provider configuration — only booleans and safe identifiers.

## UI truth wiring
- `northstar-os-ui/src/foundation/api.js`: `mediaReadiness()`.
- `CreativeStudio.jsx`: probes once on mount; renders the live contract
  (state / backend / local-engine / media gate / reason / checked-at); falls back
  to the static checklist with an explicit **"route not reachable"** note when
  the route is unavailable. Legend extended with **UNAVAILABLE** and **PROBE
  FAILED**. No prompt box, render/upload control, or generated-asset output added.

## Generation activation status
**UNCHANGED — PLANNED / NOT ARMED.** `MEDIA_GEN_LIVE` remains false; no engine is
installed/started; no render/generation route is exposed; no provider is called.
SocialPulse publishing/analytics stay provider-gated; AdPilot stays sample-static.
**Readiness does not equal activation** (stated in the contract `notes`, the UI,
and the docs).

## Validation
- `python -m pytest Northstar_backend/foundation/tests/test_creative_readiness.py`
  → **9 passed** (pure contract + probe-failure + no-secret-leak + one
  authenticated route test; offline, no network).
- `npm run build` → 0 errors.
- `verify-smoke` **42/0** · `verify-guards` **11/0** · `verify-acceptance` **32/0**.
- `capture-creative-cluster.cjs` **82/0** (adds live-contract render + fallback
  assertions).
- `git diff --check` clean.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/` (untracked):
`creative-studio-desktop-readiness-live.png` (live contract),
`creative-studio-desktop-media-truth.png` (fallback/static) + desktop/390px set.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `530b322` (backend route + mount + tests, UI wiring; this report)
**Readiness routes inspected/added:** inspected `foundation/api/router.py` (no creative route), `foundation/app.py`/`main.py` mounts, `model_router` gate helpers, `data_rights.image_generation=NOT_INTEGRATED`; **added** `GET /api/v1/foundation/creative/readiness`
**Readiness contract:** `generation` (5 states) + `armed`/`media_live` + `backend` + `local_engine{state,kind}` + `cloud_key_present` (presence bool) + `provider_gated` + `reason` + `probe` + `checked_at` + `notes`; no secrets/env values/URLs/provider config
**UI truth wiring:** `foundationApi.mediaReadiness()`; Creative Studio probes on mount, renders live states, falls back to the static checklist with a "route not reachable" note; legend adds UNAVAILABLE + PROBE FAILED
**Generation activation status:** UNCHANGED — PLANNED / NOT ARMED; `MEDIA_GEN_LIVE` false; no render route; no provider call; no credits; readiness ≠ activation
**Tests/builds run:** backend readiness tests 9/0 (offline) · `npm run build` 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 82/0 · `git diff --check` clean
**Screenshots captured:** `creative-studio-desktop-readiness-live.png` (live contract), `creative-studio-desktop-media-truth.png` (fallback) + desktop/390px set
**Remaining generation gates:** owner arming decision — install ComfyUI + weights, set `MEDIA_GEN_LIVE=1`, expose a render route; cloud provider selection/spend caps; asset store for outputs
**Blocked items:** none beyond the deliberate owner arming gate (not requested here)
**Recommended next action:** keep readiness live-only; when the owner approves arming, add a render route behind `MEDIA_GEN_LIVE` that returns `provider_required` when the engine is unreachable, and flip the readiness state to `local_available` only when the engine is genuinely reachable — no UI capability should change until then.
