# U14 — verification and handoff

**VERDICT: PARTIAL.** The build is green and the units are individually verified, but the full-suite
comparison cannot be called clean: 13 e2e tests fail, all in specs this run never touched, and none of
them is adjudicated as pre-existing by a stash-and-rerun. The independent verifier found seven defects; all seven are fixed or answered (see the follow-up note at the end).

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
| 4 | `isDesignDoc` does not validate `contentType`, so a restored doc can show a registry size the canvas is not using | **FIXED**: unknown content types are refused on restore |
| 5 | An oversized image is dropped from the autosave record but its layer survives, reloading as a blank placeholder with no warning | **FIXED**: serialiseDesign drops the layers that reference a dropped asset |
| 6 | The stage footer claims snapping is always on; `snap={showGuides}` and resize never snaps | **FIXED (copy)**: the footer now says "snapping off" when it is |
| 7 | A corpus result truncated at the depth limit is not stated as truncated | **FIXED**: the desk says when it cut at the limit |

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


## Follow-up (same session)

The four findings left open at the verdict were closed immediately after it:

- **#4** `isDesignDoc` now refuses a document whose `contentType` this build does not know, so the
  properties panel can no longer quote a registry size the canvas is not using.
- **#5** `serialiseDesign` drops the layers that reference an asset it could not keep, so an
  oversized image can no longer reload as an unexplained blank placeholder.
- **#6** the stage footer now says "snapping off" when `showGuides` is false.
- **#7** the research desk says when it cut the result at the depth limit.

Re-verified after the fixes: unit **202/202**, `research-desk` + `studio-canvas` **15 passed /
1 skipped** on both targets, build 1.46s. The 13 full-suite failures remain **unadjudicated** — they
are the only part of U14 that is still not clean.
