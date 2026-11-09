# Staging candidate `20261109-0158` — freeze, suite, slices

Frozen and tested, then stopped at gate 1. Nothing was promoted.

## Candidate

| | |
|---|---|
| candidate tag | `staging-candidate/20261109-0158` (annotated) |
| candidate sha | `433c5d87d5efc23ae1ceaabd1c110b4417fdd7ae` |
| `staging` head when tagged | `433c5d87` |
| `staging` head now | `9657cd96` — **moved while the suite ran** (other lanes merged `a410813d`, `9657cd96`) |
| verified clean | yes: `git rev-parse HEAD` = tag sha, no tracked modifications |

The suite command, run from `Northstar_backend` on the detached tag with no xdist:

```
python -m pytest -q -p no:cacheprovider -p pytest_idlist --idlist ..\reports\ty\_idlist_20261109.txt
```

- log: `reports/ty/_fullsuite_20261109.txt` (exit code 1, `reports/ty/_fullsuite_exit_20261109.txt`)
- ids: `reports/ty/_idlist_20261109.txt`

The tag was created after the run started, on the sha that was tested. It names the
tested commit, not the branch it used to point at.

## Suite result: RED — 32 failed

```
32 failed, 7189 passed, 125 skipped, 2 xfailed, 17 warnings, 125 subtests passed in 1339.23s (0:22:19)
```

Name diff against `reports/ty/_idlist_20261107.txt`:

| | count |
|---|---|
| baseline ids | 6,736 |
| run ids | 7,348 |
| added by name | **612** |
| removed by name | **0** |

Counted outcomes (7,189 + 125 skipped + 2 xfailed + 17 warnings do not include failures)
reconcile as 7,316 outcomes vs 7,348 ids — the 32 failures, by name, are that gap.

### Why it is red

Three classes, from the tracebacks in the log:

- **19 need the built UI bundle** (`northstar-os-ui/dist`, gitignored, absent in a fresh
  worktree): `FileNotFoundError: ...\northstar-os-ui\dist\assets`,
  `AssertionError: northstar-os-ui production build missing`.
- **8 need `.env`** (gitignored, absent in a fresh worktree):
  `AssertionError: missing env file: ...\stageslice\.env`.
- **5 are genuine at this commit**, not environment:
  `pages/roomAdapters.jsx: <Component>` (undefined JSX component), two composite-fidelity
  verdicts, one compositor-realism verdict, one format-integration box quad.

The JSX failure was fixed by `9657cd96` ("roomAdapters used a JSX tag for an argument
component") — a commit that landed on `staging` **after** this candidate, which is itself
evidence that the candidate is genuinely behind. The suite is not hermetic: it reads
`.env` and the built bundle from the working tree, so a clean worktree manufactures the
first two classes. That is a finding about the suite, recorded, not waived.

### The 32 failure names

```
foundation/tests/test_1c06_gate.py::test_gate_ui_is_canonical_and_served
foundation/tests/test_1c06_gate.py::test_gate_no_provider_calls_on_load
foundation/tests/test_1c06_gate.py::test_gate_security_and_bundle
foundation/tests/test_e2e_matrix.py::test_17_get_creates_no_jobs
foundation/tests/test_e2e_matrix.py::test_37_frontend_bundle_no_secrets
foundation/tests/test_frontend_gate.py::test_build_exists_and_is_canonical
foundation/tests/test_frontend_gate.py::test_ui_root_served
foundation/tests/test_frontend_gate.py::test_ui_assets_served
foundation/tests/test_frontend_gate.py::test_spa_fallback_deep_link
foundation/tests/test_frontend_gate.py::test_built_bundle_contains_no_secrets
foundation/tests/test_frontend_gate.py::test_page_load_creates_no_jobs
foundation/tests/test_frontend_gate.py::test_ui_cache_controls
foundation/tests/test_frontend_gate.py::test_v3_shell_invariants
foundation/tests/test_local_production.py::test_bundle_scan_no_secrets
test_amazon_search.py::BrightDataSearchTests::test_request_uses_zone_url_and_bearer
test_bright_data_client.py::ProductDetailTests::test_request_uses_zone_url_and_bearer
test_composite_fidelity.py::test_a_placement_outside_the_frame_is_a_named_failure
test_composite_fidelity.py::test_a_refused_region_names_the_product_region_and_never_passes
test_compositor_realism.py::test_warp_panel_with_maps_uses_realism_and_legacy_still_works
test_contract_check.py::test_end_to_end_contract_run_on_a_fresh_backend
test_env_parseability.py::test_env_files_exist
test_env_parseability.py::test_root_env_parses_with_all_keys
test_env_parseability.py::test_backend_env_parses
test_env_parseability.py::test_no_unparsable_lines_in_root_env
test_env_parseability.py::test_required_keys_present_by_name
test_format_integration.py::test_non_pouch_formats_use_a_measured_quad[box]
test_live_containment.py::LiveContainmentTests::test_ui_assets_mount_serves_disk_only_zero_provider_calls
test_scanner_completeness.py::ContainmentReassertTests::test_ui_assets_lookup_offline
test_shell_role_contract.py::test_no_undefined_jsx_components
test_ui_assets_served.py::test_ui_index_served
test_ui_assets_served.py::test_ui_deep_link_served
test_ui_assets_served.py::test_ui_assets_are_served
```

## Slices

Full table (187 rows): `reports/ty/item5_slices.md`. Per-slice gate verdicts for this
candidate: `reports/ty/staging_review_20261109_slices.json`.

`main..staging-candidate/20261109-0158` = 10,723 changed paths, one bundle:

| | |
|---|---|
| slices | 187 |
| code-only | 169 |
| visual/creative | 18 (262 rendering paths) |

### Visual slices (review pack each)

| slice | paths | rendering | pack |
|---|---|---|---|
| `renders-root` | 16 | 16 | `reports/ty/review/renders-root_20261109.md` |
| `ui-assets` | 10 | 10 | `reports/ty/review/ui-assets_20261109.md` |
| `ui-chat` | 6 | 6 | `reports/ty/review/ui-chat_20261109.md` |
| `ui-components` | 33 | 33 | `reports/ty/review/ui-components_20261109.md` |
| `ui-context` | 1 | 1 | `reports/ty/review/ui-context_20261109.md` |
| `ui-data` | 5 | 5 | `reports/ty/review/ui-data_20261109.md` |
| `ui-foundation` | 20 | 20 | `reports/ty/review/ui-foundation_20261109.md` |
| `ui-galactic` | 6 | 6 | `reports/ty/review/ui-galactic_20261109.md` |
| `ui-hooks` | 3 | 3 | `reports/ty/review/ui-hooks_20261109.md` |
| `ui-kit` | 2 | 2 | `reports/ty/review/ui-kit_20261109.md` |
| `ui-lib` | 52 | 24 | `reports/ty/review/ui-lib_20261109.md` |
| `ui-pages` | 74 | 74 | `reports/ty/review/ui-pages_20261109.md` |
| `ui-scene` | 9 | 9 | `reports/ty/review/ui-scene_20261109.md` |
| `ui-services` | 2 | 2 | `reports/ty/review/ui-services_20261109.md` |
| `ui-shell` | 15 | 15 | `reports/ty/review/ui-shell_20261109.md` |
| `ui-src` | 2 | 2 | `reports/ty/review/ui-src_20261109.md` |
| `ui-studio` | 35 | 35 | `reports/ty/review/ui-studio_20261109.md` |
| `ui-styles` | 15 | 15 | `reports/ty/review/ui-styles_20261109.md` |

Each pack carries 10 image links (5–10 required), the scorecard delta
(`staging-candidate/20261109-0158:ty/scorecards.json` vs `main`, absent on `main` so every
score is new), the exact changed paths, and two commands. `ui-pages`, for example:

```
python tools/promote_staging.py --source staging-candidate/20261109-0158 --slice ui-pages --promote --candidate staging-candidate/20261109-0158 --approve-visual "<what you looked at and accepted>"

python tools/promote_staging.py --slice ui-pages --revert promote/20261109-ui-pages-433c5d87
```

### Promotable now: none

Every one of the 187 slices is refused by gate 1 (`suite_red`) because the candidate is
red. Of those:

- 133 code slices are refused **only** by the suite — they become promotable the moment a
  green candidate exists;
- 36 code slices are also refused by `verifier_failed_unit_in_bundle`;
- 18 visual slices are refused by `slice_visual` as designed (packs above).

A candidate that is red cannot promote any slice, however small: the suite is the
evidence that the slice is safe to carry, and it does not exist for this sha.

## What was not done

- No merge into `main`, whole branch or slice.
- No tag other than the candidate tag; no force-push.
- `staging` was not touched from here; it advanced from another lane during the run.
