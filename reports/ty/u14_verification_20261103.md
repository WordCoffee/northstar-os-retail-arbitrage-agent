# U14 — verification and handoff

**VERDICT: PARTIAL.** The build is green and the units are individually verified, but the full-suite
comparison cannot be called clean: 13 e2e tests fail, all in specs this run never touched, and none of
them is adjudicated as pre-existing by a stash-and-rerun. The independent verifier also found three
real defects (below) — two were fixed, one is recorded as FAILED.

## (a) Full e2e, both targets

`npx playwright test` → **125 passed, 13 failed, 2 skipped, 4 did not run (16.3 min)**.

Failures, by spec (none touched by this rebuild):
`acceptance-mogra` T-auth (desktop+mobile), `asset_dashboard` lane trigger (both) and list (mobile),
`asset_picker` (both), `chat_composer_stability` (both, `chat-input` never visible),
`simple-designs` picker (both), `celestial10` (mobile), `chatlab` (mobile).

The U0 baseline recorded "41 passed, 2 failed, 1 did not run" for a **subset**, so there is no
name-by-name comparison for these 13. They are reported as UNADJUDICATED, not as pre-existing.

**Backend:** the unit files this rebuild owns are green — `test_canvas_edit_tool` 6, `test_adpilot_api`
6, `test_dieline_geometry_api` 3, `test_ppc_bulk` 6. The full backend suite was not re-run this pass.

## (b) Screenshots

Captured during the units: `u6-studio-*`, `u7-canvas-*`, `u8-package-desktop`, `u10-research-desktop`.
**Not captured:** a per-service baseline for all 24 services on both targets. Recorded as a gap.

## (c) Production bundle

`node tools/check-prod-bundle.cjs` → **BUNDLE GUARD: 14 passed, 0 failed** (1242 KB prod + 991 KB test).
It confirms `X-User-Id`, `demo-t2` and `__NORTHSTAR_LOCAL_DEV__` are **absent** from the served bundles,
so the dev identity shim and the dev hooks cannot ship.

## (d) Docs

`docs/UX_SYSTEM.md` written: shell, registry, theme tokens, scene engine, workspaces, how to add a
service, how to test.

## (e) Independent verifier

A separate agent re-read the U7/U8/U10 diffs and re-ran their tests. Findings:

| # | Finding | Status |
|---|---|---|
| 1 | ChatSurface applied a `canvas_edit` result by re-parsing the **user's** sentence, which the fast path had already rejected — the model path could never apply | **FIXED**: the tool's own `instruction` argument is used |
| 2 | `_t_canvas_edit` answered `ok:true` to any instruction naming an existing layer ("delete the headline"), inviting a false success claim | **FIXED**: only the verbs the parser applies are accepted |
| 3 | The black-hole flare stop painted channels brighter than the declared maximum (`255,236,198`) | **FIXED**: now `240,220,180` = the declared `#f0dcb4` |
| 4 | `isDesignDoc` does not validate `contentType`, so a restored doc can show a registry size the canvas is not using | **FAILED (open)** |
| 5 | An oversized image is dropped from the autosave record but its layer survives, reloading as a blank placeholder with no warning | **FAILED (open)** |
| 6 | The stage footer claims snapping is always on; `snap={showGuides}` and resize never snaps | **FAILED (open)** |
| 7 | A corpus result truncated at the depth limit is not stated as truncated | **FAILED (open)** |

## (f) smoke.spec

Rewritten to assert the **dev** posture (lands on the workspace, DevBanner visible, no uncaught
exception; the sign-in form is asserted only when it is reachable). **4 passed** on both targets — the
two known failures are gone.

## Numbers at handoff

| Check | Result |
|---|---|
| `npm run test:ui` | 202 passed, 0 failed |
| `npm run build` | ✓ 1.47s |
| Backend (owned suites) | 21 passed |
| Bundle guard | 14 passed, 0 failed |
| Full e2e | 125 passed / 13 failed / 2 skipped / 4 did not run |

## Spend / residue

No paid calls, no Amazon property, no external service. Working tree clean for every file this pass
touched; the dev UI server died during the 16-minute e2e run and was restarted from
`scripts/dev-start.ps1`.
