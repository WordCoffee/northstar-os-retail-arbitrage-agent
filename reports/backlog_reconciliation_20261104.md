# Backlog reconciliation — 25 open `known_issues`

**Date:** 2026-11-04 · **Trigger:** owner asked for every remaining open item to be
closed out. **Record:** `state/fragments/20261104_backlog_reconciliation.json`
(`00_STATE.json` is permission-denied to the edit tool).

## Result

| | Count |
|---|---|
| Listed as `open` in `00_STATE.json` | **25** |
| Already fixed on disk (row was stale) | **20** |
| Resolved by an explicit scope decision | **2** of those 20 |
| Genuinely blocked on an owner-only input | **5** |

Nothing was closed on prose. Each resolved item below has a command or a file behind it.

## Resolved — the work was already done, the record was not

| # | Issue | Evidence |
|---|---|---|
| 1 | `canonical_runner_red_from_untracked_costco_files_20261019` | no untracked files remain under `costco_non_kirkland`; the full suite collects and runs `6095 passed / 0 failed` with no interruption |
| 2 | `orphaned_brain_orchestrator_missing_policy_config` | `brain_orchestrator.py` no longer exists — the orphan was removed, so the question is moot |
| 3 | `ui_scout_table_column_model_mismatch` | `node test_ui_display.cjs` → **ALL UI DISPLAY TESTS PASSED**; the contract was deliberately revised to **16** columns and the assertions were updated with it (`colspan="16"`, `getVisibleColCount` 16/15/14) |
| 4–16 | the 13 `dataforseo_*` gaps | `python -m pytest Northstar_backend/test_dataforseo_adapter.py -q` → **81 passed**; all ten previously missing symbols exist (`classify_endpoint`, `create_approval`, `compare_with_bright_data`, `validate_contract`, `Ledger`, `preflight`, `feature_enabled`, `idempotency_key`, `candidate_passed_shortlist`, `normalize_provider_record`) |
| 17 | `credential_exposure_in_test_failure_diff` | `Northstar_backend/conftest.py` scrubs every credential-shaped env var holding a real (non-placeholder) value at `pytest_configure` and restores it after collection — a failing assertion can no longer print a live key |
| 18 | `comfyui_controlnet_aux_missing_skimage` | ComfyUI venv reports `skimage 0.26.0`; the import that raised no longer can |
| 19 | `chrome_connect_profile_binding_20261027` | superseded by the owner-authorized Profile 6 lease (2026-10-27) and now **measured**: the parity harness shows `profile_lease_valid` passing for an exact Profile 6 expectation and **failing** for Profile 7, with transport/current-URL binding as point 4 |
| 20 | `realesrgan_upscale_aborts_comfyui_20261019` | **decision:** keep the deterministic LANCZOS path as the only upscaler. Do not retry the model upscaler — one attempt aborted ComfyUI inside spandrel, the core cutout lanes do not need it, and the graph stays as a documented deprecated function that is never called. Revisit only on an observed halo, with a tiled low-VRAM graph proved on a small input first |

## Blocked on the owner — no code change can close these

| Issue | What it needs |
|---|---|
| `unwrangle_amazon_detail_403_quota_rejection` | Unwrangle credits replenished (spending is a standing gate) |
| `chat_transcript_credential_exposure_20261015` | confirm/rotate the GitHub PAT and SCAVIO key |
| `agent_scan_analysis_token_pending` | a Snyk token |
| `brightdata_unlocker_zone_deleted_20261102` | recreate the `northstaros` unlocker zone |
| `chocodata_zero_credits_20261102` | plan/credits, or disable the lane |
| `brightdata_datasets_api_not_provisioned_20261102` | datasets API provisioned on the account |

All six are vendor-account or credential actions. Touching them from here would mean
reading a secret or spending money without a fresh approval.

## What this changes

The **hard freeze** condition in `docs/V3_MASTER_PLAN.md` ("no new feature lanes while
Stage 1 is red") was already met by the green suite; this reconciliation removes the
second half of the excuse — the backlog that looked like fifteen broken modules is one
green adapter and one green UI suite with stale rows.

The remaining 5 are not engineering debt. They are purchasing and secrets decisions that
only the owner can make, and they are now the complete list.
