# The 13 e2e failures: adjudicated against the U0 baseline

**Verdict: all 13 are pre-existing.** Every one of them fails, or fails harder, at the U0 baseline
commit. Two of them now pass at HEAD, and one failed for a reason this rebuild deliberately created
(the Northstar rename) and is fixed in the spec. Nothing in the list is a regression introduced by
U0–U14.

## Method (so the claim is a measurement, not a memory)

| | Current tree | Baseline |
|---|---|---|
| Commit | `c93bcfff` (U14b) | `a2d12f5e` (`ns-ux-baseline`, U0) |
| App source | working tree | `git worktree` at `C:\Users\T2Hol\Desktop\ns-baseline-u0` |
| Served on | `127.0.0.1:8101` | `127.0.0.1:8102` (own Vite, own port, own `node_modules` copy) |
| Backend | `127.0.0.1:8000` | **same** backend process |
| Specs | `tests/e2e/` at HEAD | `tests/e2e/` at baseline, only `8101 → 8102` rewritten |
| Command | `npx playwright test --grep "<the 8 titles>" --timeout=45000 --reporter=json` | identical |
| Projects | `chromium-desktop`, `chromium-mobile` | identical |
| Result | **4 passed / 12 not passing** (653 s) | **2 passed / 14 not passing** (599 s) |

Raw evidence: `reports/ty/e2e_adjudication/head.json`, `baseline.json` (Playwright JSON reporters).
The baseline tree is disposable and was removed afterwards; nothing in the current tree was stashed,
reverted or re-pointed at a different port.

The grep selects the eight test titles that produced the 13 failures in the U14 full-suite run
(`reports/ty/u14_verification_20261103.md`), so the comparison is name-by-name rather than
suite-by-suite.

## Name-by-name

| # | Test | Project | Baseline `a2d12f5e` | HEAD `c93bcfff` | Verdict |
|---|---|---|---|---|---|
| 1 | `acceptance-mogra` T-auth | desktop | timed out | timed out | pre-existing |
| 2 | `acceptance-mogra` T-auth | mobile | timed out | timed out | pre-existing |
| 3 | `asset_dashboard` lists packages | desktop | **failed** | **passed** | pre-existing, fixed by the rebuild |
| 4 | `asset_dashboard` lists packages | mobile | **failed** | **passed** | pre-existing, fixed by the rebuild |
| 5 | `asset_dashboard` lane trigger | desktop | failed | failed | pre-existing |
| 6 | `asset_dashboard` lane trigger | mobile | failed | failed | pre-existing |
| 7 | `asset_picker` | desktop | failed | failed | pre-existing |
| 8 | `asset_picker` | mobile | failed | failed | pre-existing |
| 9 | `celestial10` ten compositions | desktop | passed | passed | — |
| 10 | `celestial10` ten compositions | mobile | timed out | timed out | pre-existing |
| 11 | `chat_composer_stability` | desktop | failed | failed | pre-existing |
| 12 | `chat_composer_stability` | mobile | failed | failed | pre-existing |
| 13 | `chatlab` ten chat interfaces | desktop | passed | passed | — |
| 14 | `chatlab` ten chat interfaces | mobile | timed out | timed out | pre-existing |
| 15 | `simple-designs` design picker | desktop | timed out | failed → **passed** after spec fix | caused by U1, fixed |
| 16 | `simple-designs` design picker | mobile | timed out | failed → **passed** after spec fix | caused by U1, fixed |

`asset_dashboard` "lists packages" (mobile) was in the 13 from the full-suite run and passes on
re-run at HEAD **and** failed at baseline, so it is recorded as a flake in the original run, not as a
standing failure.

## Why each group fails

**`chat-input` is not on `/ui/design-studio` (tests 1, 2, 7, 8, 11, 12).** All six wait for
`getByTestId('chat-input')` after navigating to `/ui/design-studio`. That route renders the real
Design Studio page, not the chat shell: `northstar-os-ui/src/App.jsx:202` lists
`/^\/design-studio(\/|$)/` in `SIMPLE_KEEP_ADVANCED`, and **that entry is present in the baseline
commit too** (`git show a2d12f5e:northstar-os-ui/src/App.jsx`). The chat composer now lives in the
workbench dock and in advanced view (`WorkbenchShell.jsx:145`, `MasterBrainShell.jsx:227`). These
specs were written against the pre-V3 architecture where every room sat inside the chat shell; they
were already stale at U0 and the rebuild did not touch them.

**`asset_dashboard` lane trigger (tests 5, 6).** At baseline the assertion dies on
`expect(dash-asset).toBeVisible()` — the lane control is not rendered at all, so nothing is ever
fired. At HEAD the control exists, the lane fires, and the panel reports the honest refusal:
`Cutout: failed — media_generation_disarmed (MEDIA_GEN_LIVE is not 1)`, while the spec waits 120 s
for the text `done`. So the rebuild moved this test from "the surface is missing" to "the feature is
reachable and tells you it is not armed", and the remaining failure was the standing generation gate
(`MEDIA_GEN_LIVE`), not a canvas or dashboard regression.

**Update 2026-11-03 (owner instruction: arm FLUX 3):** the lane is now armed and both tests **pass**
(`2 passed, 11.7s`). This failure is closed by configuration, not by editing the test — the spec has
not changed.

**`celestial10` and `chatlab` on the phone profile (tests 10, 14).** Both drive the design-lab pages
on `127.0.0.1:8124` through ten tabs and hit the 45 s test budget only on `chromium-mobile`. Desktop
passes on both sides. Baseline behaves identically.

**`simple-designs` design picker (tests 15, 16).** At baseline the trigger was never reached inside
45 s. At HEAD the dialog opens and the failure is an exact string: the assertion asked for
`getByRole('dialog', { name: 'Choose a Simple mode design' })` while the shell now renders
`aria-label="Choose a Northstar design"` (`MasterBrainShell.jsx:200`) — the U1 naming rule renamed
it on purpose. That expectation was updated, and the test now passes on both targets (`2 passed,
12.9s`). The rest of the assertions (dialog visible, design applies, `data-simple-design` changes)
are unchanged, so nothing was weakened to make it green.

## What this changes

- U14's `e2e_full` line is now adjudicated, not deferred: **13/13 pre-existing**, 2 of them now
  passing, 1 fixed because the rename invalidated its expected copy.
- **10 pre-existing failures remain** (6 × stale chat surface, 2 × cutout lane disarmed by the
  generation gate, 2 × phone-profile timeouts). They are left in place per the work order ("leave
  other pre-existing failures untouched") and are listed here by name instead of being hidden behind
  a number.

---

# The backend suite, same treatment

The U14 verdict said the full backend suite was not re-run. It has been now, and it was worth it: it
found one regression of ours that every owned-unit run missed.

## Numbers

| | Collected | Failed | Passed | Skipped | xfail | Duration |
|---|---|---|---|---|---|---|
| U0 recorded baseline (2026-11-02) | 5912 | 30 | 5763 | 117 | 2 | 635 s |
| HEAD `c93bcfff` + U15 (2026-11-03) | 5926 | **15** | 5792 | 117 | 2 | 666 s |
| HEAD after the fix below | 5926 | **14** | 5793 | 117 | 2 | derived, not re-run |

`reports/ty/e2e_adjudication/backend_head.txt`.

## Name-by-name attribution

The U0 recorded baseline has counts but not names, so the baseline commit (`a2d12f5e`) was run
**in its own worktree**. That run is **not** a like-for-like environment — `dist/`, the data stores and
the UI `node_modules` are gitignored, so it produced 77 failures (23 of them artifact-only, e.g.
`test_ui_assets_served`, the `foundation/test_frontend_gate` build assertions). It is therefore used
for one question only: *does this failure also exist at the baseline commit?* A failure that
reproduces in a **different** environment is at minimum not caused by this rebuild.

Of the 15 HEAD failures:

| Failure | Also fails at `a2d12f5e`? | Verdict |
|---|---|---|
| `foundation/test_frontend_gate::test_v3_shell_invariants` | yes | pre-existing — asserts a hard-coded route count of 53; it was already 57 at baseline and is 58 now |
| `test_autonomy_hitl_pathlike::test_hitl_counts_accepts_a_string_root` | yes | pre-existing |
| `test_coding_guardrails::test_pressure_clears_when_a_non_write_tool_creates_the_artifact` | yes | pre-existing |
| `test_generation_guards::test_the_edit_and_video_lanes_call_the_guard` | yes | pre-existing |
| `test_hitl_counts::test_counts_pending_approved_denied` | yes | pre-existing |
| `test_provider_suite::test_provider_suite_endpoint_envelope` | yes | pre-existing (order-dependent: passes alone and with its neighbouring files, 41 passed) |
| `test_shell_modes::test_ui_gates_are_advanced_view_on_top_tiers_only` | yes | pre-existing |
| `test_shell_modes::test_user_ui_gates_read_plan` | yes | pre-existing |
| `test_ui_route_contract::test_every_ui_api_path_resolves` | yes | pre-existing (`HitlQueue.jsx` → `/api/v1/hitl/sample/sample` does not resolve; same at baseline) |
| `test_shell_role_contract::test_no_undefined_jsx_components` | **no** | **ours — fixed** (below) |
| `test_session_cookie_contract::DevShimSessionTests` ×5 | **class does not exist at baseline** | not this run: the class is in an **uncommitted** working-tree change by another session, and it fails with `KeyError: 'app'` because its hand-built `Request` scope has no `"app"` entry |

## The one regression, and the fix

`tools/check-jsx-imports.py` reported `kit/Glass.jsx: <Tag>` as an undefined component and failed the
build. `Tag` is bound by destructuring — `{ as: Tag = 'section', ... }` — a legitimate `as`-prop
pattern, so the guard was wrong, not the component.

The checker now resolves capitalised destructured aliases (parameter lists and
`const/let/var {…} =` declarations). `Northstar_backend/test_shell_role_contract.py` gained a
two-sided regression test: `Tag` must count as a binding **and** a genuinely unbound `<Ghost />` must
still be reported. `test_shell_role_contract.py` → 9 passed; `python tools/check-jsx-imports.py` →
0 undefined references across 148 `.jsx` files, exit 0.

The documented trade-off: an object literal inside a call (`f({ key: Ghost })`) is also read as a
binding, which can only hide a component referenced as a *value* — a `ReferenceError` at module load,
the loudest failure there is — while removing a false positive that blocked a correct build.

