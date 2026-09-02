# Follow-up Issue: Full-pytest Collection Blocker (Pre-existing, Out-of-Scope)

**Status:** OPEN — pre-existing, not introduced by the Master Brain deliverable.
**Scope:** OUT OF SCOPE for the Master Brain task (2026-08-22).
**Owner of remediation:** future adapter-only work (not Master Brain).
**Do NOT fix in this task:** `AmbiguousTransportError`, `dataforseo_adapter.py`,
`test_compare.py`, `test_validation_run.py`, `test_dataforseo_adapter.py`.

## Summary
Running the full suite via `python -m pytest` (no explicit file list) aborts
during **collection** with 8 errors. These are unrelated to the Master Brain
work and were present before it.

## Evidence
```
ERROR collecting test_compare.py
ERROR collecting test_dataforseo_adapter.py
ERROR collecting test_validation_run.py
  ImportError: cannot import name 'AmbiguousTransportError'
               from 'dataforseo_adapter'
               (...\Northstar_backend\dataforseo_adapter.py)
ERROR collecting test_out.txt      -> UnicodeDecodeError: 'utf-8' ... byte 0xff
ERROR collecting test_output.txt   -> UnicodeDecodeError
ERROR collecting test_rerun.txt    -> UnicodeDecodeError
ERROR collecting test_run.txt      -> UnicodeDecodeError
ERROR collecting test_summary.txt  -> UnicodeDecodeError
```

Verified root cause:
- `dataforseo_adapter.py` does **not** define `AmbiguousTransportError`
  (`python -c "import dataforseo_adapter as d; print('AmbiguousTransportError' in dir(d))"`
  → `False`). The three failing test modules import that symbol.
- `test_*.txt` files are stray artifact files that pytest attempts to collect
  as test modules.

## Why out of scope
- The Master Brain task explicitly froze the relevant core modules and defined
  the test gate as: `pytest` (engine + brain subset) `&&` `node test_ui_display.cjs`
  `&&` `python brain_orchestrator.py --cohort benchmark_10 --dry-run`.
- None of the new Master Brain modules (`scanner_data.py`, `enricher.py`,
  `brain_orchestrator.py`, `config/brain_policy.json`, `test_brain_orchestrator.py`)
  import `dataforseo_adapter` or reference `AmbiguousTransportError`.
- Instructions for this step: leave `AmbiguousTransportError`,
  `dataforseo_adapter.py`, and the validation-run tests untouched.

## Required test gate (satisfied, green)
- `pytest test_fee_engine.py test_demand_estimator.py test_product_analysis.py test_brain_orchestrator.py` → **129 passed**.
- `node test_ui_display.cjs` → **ALL UI DISPLAY TESTS PASSED** (1185 assertions).
- `python brain_orchestrator.py --cohort benchmark_10 --dry-run` → valid,
  no live calls, no false approvals.

## Proposed future adapter-only remediation (separate task)
1. Define `AmbiguousTransportError` in `dataforseo_adapter.py` (or correct the
   import name in the three test modules) so they collect.
2. Either relocate the stray `test_*.txt` files out of the collection root or
   add a `pytest` ignore pattern (`test_*.txt`) / `[tool.pytest.ini_options]
   collect_ignore_glob` so they are not treated as test modules.
3. Re-run the full `python -m pytest` collection and confirm zero collection
   errors; keep the 129-targeted subset green.
4. This remediation must NOT touch Master Brain deliverables and must preserve
   the existing test gate above.

## Master Brain deliverable preservation
- All Master Brain outputs are intact and non-destructive:
  - `config/brain_policy.json`
  - `scanner_data.py`
  - `enricher.py` (read-only, no live provider calls)
  - `brain_orchestrator.py`
  - `test_brain_orchestrator.py` (11 tests, green)
  - `data/enrich/brain-runs/<brain_run_id>/audit-snapshot.json`
  - `data/enrich/brain-runs/audit.log.jsonl`
  - `data/scanner-search-cache.enriched-candidate.json`
- Frozen core (`fee_engine.py`, `demand_estimator.py`, `product_analysis.py`,
  `finance.py`, `pricing.py`, CSVs, benchmark/source data, fee values) unchanged.
