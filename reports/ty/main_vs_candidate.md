# Main at `82097ac1` versus the staging candidate, by test name

Asked for: run the full suite on main at `82097ac1` and report **by test name** against the staging
candidate. The short answer is that **main cannot run the suite yet**, and the reason is worth more
than the count.

## What happened when the suite ran on main

| ref | result |
|---|---|
| main `82097ac1` (the four-slice promotion) | **4 collection errors**, run aborted in 14 s: `ModuleNotFoundError: adapters.reasoning_provider` (`tests/test_reasoning_provider.py`, `tests/test_reasoning_tasks.py`, `tests/test_ads_report_download_guard.py`, `tests/test_amazon_auth_gate.py`) |
| main `b4792612` (after 16 more slices) | **8 collection errors**, run aborted in 8 s: `ModuleNotFoundError: Northstar_backend.ui_serving` (`foundation/tests/test_auth_session.py`, `test_demo_dataset.py`, `test_frontend_gate.py`, `test_golden_goose_routes.py`, `test_owner_credentials.py`, `test_owner_test_mode*.py`) |

Main is missing modules that exist only on staging. Promoting four slices, then twenty, did not make
it self-consistent, because **code slices depend on each other**.

## Why the rest of the slices did not go

The promotion runs the repository's own pre-commit hook, and it refuses:

```
REFUSED slice_commit_failed: pre-commit BLOCKED: gitleaks found potential secrets in staged changes.
Fix or remove them; for reviewed false positives add an allowlist entry to .gitleaks.toml.
```

Three slices are blocked — `Northstar_backend-data` (262 paths), `Northstar_backend-root`
(586 paths, the one holding `ui_serving.py`) and `Northstar_backend-static` (2 paths) — with **24
findings between them**. That is the same class of problem as **DIR-1** in `needs_you.md`: credentials
already committed in chat exports. Bypassing the hook would be a policy bypass, so the slices stay put.

`149` of the `169` code slices are therefore still on staging only.

## The by-name comparison that *can* be made

From `tools/main_vs_candidate.py` (candidate idlist `_idlist_candidate10_20261109.txt`, 7,452 ids):

| | ids | modules |
|---|---|---|
| candidate ids with their module **on main** | **3,601** | 214 |
| candidate ids with their module **missing from main** | **3,851** | 316 |

The missing modules are named in `reports/ty/main_vs_candidate_by_name.json` — the first of them are
`test_ad_formats.py`, `test_adapter_registry_completeness.py`, `test_adpilot_api.py`,
`test_agent_context_window.py`, `test_agent_kernel.py`, `test_amazon_egress_guard.py`,
`test_aplus_*` (6 files), `test_asset_*`, `test_ast_edit.py`, and 301 more.

**The staging candidate itself is green**: `staging-candidate/20261109-2135` at `6658f7c2`,
**7333 passed, 0 failed, 117 skipped, 2 xfailed** in 19 m 11 s
(`reports/ty/_fullsuite_candidate10_20261109.txt`).

## What would make main green

1. **DIR-1**: rotate the three committed credentials, then purge them from history. After that the
   gitleaks hook stops refusing `Northstar_backend-data` and `-root`, the last 149 slices promote,
   and main becomes collectable.
2. Or, if those specific findings are false positives, add reviewed `.gitleaks.toml` allowlist
   entries — a decision that needs a human, which is why it is not taken here.

Until one of those happens, "main is behind staging" is the accurate statement, and the number that
matters is **149 slices**, not a test count.
