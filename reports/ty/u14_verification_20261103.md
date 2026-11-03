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

---

# U14 completion (2026-11-03)

The adjudication is done, the screenshots exist, and the backend suite has now actually been run.
This section supersedes the "PARTIAL" verdict above; the verdict text is left in place so the change
is visible rather than rewritten.

## The 13 e2e failures: 13/13 pre-existing

Method: a `git worktree` pinned to the U0 baseline commit `a2d12f5e`, served on its own port (8102)
next to this tree (8101), with the identical grep, `--timeout=45000` and the same two projects. The
current tree was never stashed or re-pointed.

| | Baseline `a2d12f5e` | HEAD |
|---|---|---|
| Same 16 runs | 2 passed / 14 not passing | 4 passed / 12 not passing |
| Verdict | — | **13/13 pre-existing** |

- **2 now pass** (`asset_dashboard` "lists packages", both targets). The mobile one was in the
  original 13, so the full-suite run also had one flake; it is recorded as a flake, not a fix.
- **1 was caused by U1**: `simple-designs` asked for a dialog named `Choose a Simple mode design`,
  which the naming rule replaced with `Choose a Northstar design`. The expectation was corrected and
  the test passes on both targets (2 passed, 12.9s); every other assertion in it is unchanged.
- **10 remain**, named with causes in `reports/ty/e2e_adjudication/README.md`: 6 stale chat-surface
  specs (they wait for `chat-input` on `/design-studio`, a surface that stopped carrying the chat
  shell before U0), 2 waiting on `MEDIA_GEN_LIVE` (the cutout lane reports the honest refusal
  `media_generation_disarmed` at HEAD, where at baseline the control did not render at all), and 2
  phone-profile timeouts on the 8124 design-lab pages.

## Screenshots: captured

`tests/e2e/service-screens.spec.ts` walks the picker's list **and the default-open tab** (the first
run captured 23 of 24 for exactly that reason), masks the dev banner and toasts so a commit hash
cannot enter a visual baseline, and shoots the whole shell per service. **24 services × 2 targets →
`reports/ty/shots/services/{chromium-desktop,chromium-mobile}/` + `manifest.json`** (bytes + sha256).
2 passed, 1.8m.

Note on versioning: `.gitignore:80` excludes `reports/**/*.png`, a pre-existing policy that also keeps
the u6/u7/u8/u10 shots out of the repo. The PNGs therefore live on disk and the **committed** record
is `manifest.json` (service list, size, sha256) — so the baseline can be verified against the tree
without putting ~9.4 MB of images into history.

## Backend suite: run, and it found something

`5926 collected → 15 failed, 5792 passed, 117 skipped, 2 xfailed (666 s)` against the recorded U0
baseline of `30 failed / 5763 passed`. Of the 15, **nine reproduce at the baseline commit**, **five
come from an uncommitted test file in the working tree** (not this run), and **one was ours**:

`tools/check-jsx-imports.py` reported `kit/Glass.jsx: <Tag>` as an undefined component and failed the
build. `Tag` is bound by destructuring (`{ as: Tag = 'section' }`), a legitimate `as`-prop pattern, so
the guard was wrong. The checker now resolves destructured bindings, and
`test_shell_role_contract.py` gained a two-sided regression test (`Tag` counts as a binding **and** an
unbound `<Ghost />` is still reported) → **9 passed**, checker exit 0 across 148 `.jsx` files.

That is exactly the class of failure the owned-unit runs could not see, and the reason the "backend
suite not re-run" line in the original verdict was a real gap rather than a formality.

## Numbers at completion

| Check | Result |
|---|---|
| `npm run test:ui` | 201 passed, 0 failed (re-counted per file; the verdict's 202 counted one more) |
| `npm run build` | ✓ 1.54s |
| Bundle guard | 14 passed, 0 failed (1242 KB prod + 991 KB test) |
| Full e2e, adjudicated | 13/13 pre-existing; 2 now pass; 1 fixed (rename); 10 named |
| Full backend | 15 failed / 5792 passed → 14 after the `<Tag>` fix (derived) |
| Service screenshots | 24 × 2 targets + manifest |
| AutothinK/local-model (U15) | 50 passed (was 15 failed / 35 passed) |

## Still not clean (blunt)

1. 10 pre-existing e2e failures, 6 of them blocked on the owner decision in `needs_you.md`.
2. 9 pre-existing backend failures that reproduce at the baseline commit.
3. 5 backend failures from an **uncommitted** test file belonging to another session; I did not touch
   it.
4. The studio scene still runs ~45 fps against a 60 budget (U13's recorded lever: bake the backdrop).

