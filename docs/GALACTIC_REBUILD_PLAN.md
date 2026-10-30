# Galactic Flux 3 Rebuild — spec vs disk

**Issued:** 2026-10-30 · **Branch:** `feature/chrome-connect-3.0` (640 commits ahead of `main`, 487 dirty files)
**Directive received:** `STAGING_HOLD=0`, `DIRECT_TO_MAIN=1`, `LIVE_DEPLOY=1`

This file records what the order asked for against what is actually on disk, before
any code was written. Nothing here is reinterpreted silently; every divergence is
stated and resolved explicitly.

---

## Phase 1 — Galactic theme engine

| Asked | On disk | Verdict |
|---|---|---|
| New `CelestialBackdrop.jsx` | **Exists** — `northstar-os-ui/src/shell/CelestialBackdrop.jsx`, 11 layered divs, mounted as the Master Brain shell background (commit `8c228029`). A second, richer canvas exists: `shell/CosmicCanvas.jsx` (512 lines, star temperature ramp, diffraction spikes, dust occlusion, shooting stars). | **EXTEND**, do not recreate |
| Deep space, high-contrast Galactic look | Partly present — `styles/celestial.css` (201 lines), `simple.css` carries the dark shell. Focus-driven tint already animates per focus. | **EXTEND** — obsidian surfaces, nebula glows, glass tokens |
| Galactic theme wired into FLUX 3 output | **Absent.** The FLUX 3 gateway (`tools/flux3_gateway.py`) is a plain text-to-image graph: prompt, width, height, steps, seed. No style/theme input. | **BUILD** — theme tokens → structured prompt block |
| Deployed live, no staging flags | No CI/CD to a cloud host. "Live" here = `scripts/launch_alpha.ps1` service tier + the existing tunnel; SPA is served from `dist/` under `/ui/`. | **BUILD** (rebuild `dist/` + restart through the launcher) |

**Guardrail:** `verify-galactic-themes.cjs` already asserts the per-focus palette contract
(auto/create/grow/research/operate/autothink) and that legibility is untouched. The
theme work must keep that contract green. Its reading-system numbers (composer 16.5px,
column 820px) are **stale** against `simple.css`, which now uses
`--simple-col: clamp(760px, 78vw, 1360px)` after the 2026-10-23 interface repair — the
harness needs reconciling, not the CSS reverted.

---

## Phase 2 — Service hub, 31 lines, 6 focuses

| Asked | On disk | Verdict |
|---|---|---|
| 31 service lines under 6 focuses | **No such registry.** `Northstar_backend/chat_tools.py:1609 SERVICES` holds **8** capability areas. `northstar-os-ui/src/data/services.js` holds **13** nav routes. Neither is 31. | **BUILD** — must be derived from real surfaces, never invented |
| 6 focuses: Auto/AutothinK, Create, Grow, Research, Operate, Infrastructure | App's canonical six are **auto, create, grow, research, operate, autothink** (`ShellContext.jsx FALLBACK_FOCUSES`, asserted by the galactic harness). Spec says *Infrastructure* where the app has *autothink*, and folds AutothinK into Auto. | **DIVERGENCE — resolved by binding to the app's six**, since those ids drive the cosmic theme. Infrastructure lines bind to `operate`; AutothinK stays its own focus because it already is one. Recorded, not silently renumbered. |
| Service selector router in Simple Mode | Focus rail exists (`MasterBrainShell.jsx`, `ShellContext`). No per-service selector. | **BUILD** (additive: rail stays) |
| Bojo loads target repo context on service select | **Absent.** System prompt is built in `chat_adapter`; no repo-context loader. | **BUILD** — `service_context.py`, fail-closed, path-scoped |
| Inject favorited assets + brand prefs into FLUX conditioning | Assets and brand prefs exist (asset store, brand profile). Conditioning path does not. | **PARTIAL** — prompt-level injection possible; true image conditioning is not |
| Live web-scraped visual references into FLUX conditioning | FLUX 3 gateway has **no image-conditioning input**. Only Chrome Connect may drive a browser, and it is operator-gated. | **BLOCKED as specified.** Delivered as: a reference slot fed by a Chrome Connect result, plus documented gap for an img2img/IP-Adapter graph that is not installed |

---

## Phase 3 — Studio photography pipeline

| Asked | On disk | Verdict |
|---|---|---|
| Purge wireframes/dielines/flat nets from default generation | Dielines are already **opt-in** tools (`create_dieline`, `build_package`), not the default image path. No purge needed; needs an explicit "print intent" guard so they can never leak into a commercial render prompt. | **BUILD** (guard + tests) |
| Studio-lit commercial pouch renders | `pouch_label.py` + `mockup_compositor.py` composite real text/logo deterministically; the plate itself comes from the image model. No studio-render prompt template. | **BUILD** — `studio_prompt.py` |
| ≥85% canvas fill | No such gate. `image_prep.upscale_lanczos` exists (PIL-only, capped 4x); prepress `max TAC` check exists. | **BUILD** — `render_quality.py` |
| ≥2000px white-background cutout | Upscaler exists; white-bg measurement does not (`package_readiness` was referenced in state but no `def package_readiness` exists on disk — a doc that lies about the code). | **BUILD** — measure, do not assume |
| Exact brand logo compositing | **Exists** — `apply_label`, logo frame-crop + field-colour detection, real fonts. | **REUSE**, assert it ran |

---

## Phase 4 — Simple Mode enhancements, Bojo avatar

| Asked | On disk | Verdict |
|---|---|---|
| One-click "Enhance" beside the prompt | **Absent.** | **BUILD** — deterministic template expander first, model second, labelled honestly |
| Style-transfer overlays + iteration history | **Absent.** Asset registry and asset_meta exist; no per-turn version chain. | **BUILD** |
| Animated Rottweiler avatar, IDLE sitting / WORKING pacing | **Absent.** Only a 30px initials circle in `TopNav.jsx`. No mascot asset, no animation. | **BUILD** — inline SVG (no licence risk, no external fetch), state-driven, reduced-motion safe |

---

## Phase 5 — Verification and deploy

| Asked | Reality | Verdict |
|---|---|---|
| `npm test`, `npx jest` | **Neither exists.** `northstar-os-ui/package.json` has only `dev`, `build`, `preview`. UI is verified by `npm run build` (0 errors) plus ~35 `verify-*.cjs` Playwright harnesses. | **SUBSTITUTE, and say so.** Adding jest with no tests would be fake green. Run the real verifier: `npm run build` + the node harnesses + `pytest`. |
| Full test suites green | Baseline is **not** fully green: `test_dataforseo_adapter.py` (classify/approval/compare missing), 4 untracked `costco_non_kirkland` files that break collection, `test_frozen_file_boundary_is_a_static_rule` drift, 23 pre-existing `test_proof_batch*` fixture failures. | **REPORT HONESTLY** — new work must add zero failures; pre-existing red is listed, not hidden |
| Direct deploy to live | Live tier is started by `scripts/launch_alpha.ps1`. | **BUILD** |
| `DIRECT_TO_MAIN=1` | `main` is 640 commits behind this branch with a dirty tree. Capsule rule: a merge to `main` requires a passing verifier run **and** a `rollback/` tag immediately before it. | **CONDITIONAL** — rollback tag + verifier; merge only if green. A 640-commit merge is a separate decision and will be reported as such |

---

## What this work will not do

* It will not claim `npm test`/`jest` ran.
* It will not scrape a live site into FLUX conditioning (no img2img graph; browser is
  Chrome Connect's, operator-gated).
* It will not delete the print/dieline lane — the order says remove it from *default
  product generation*, and that lane is a paying deliverable.
* It will not invent 31 services. Each line cites the real route or tool it binds to.
* It will not touch Amazon or spend money.
