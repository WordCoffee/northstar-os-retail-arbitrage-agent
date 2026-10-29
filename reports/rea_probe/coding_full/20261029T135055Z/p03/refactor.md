# Refactor Plan: Split report_builder.py

## Goal
Split the monolithic `report_builder.py` into two focused modules without changing behaviour.

## Proposed Modules

### 1. `report_core.py`
- **Responsibility:** Data parsing, validation, and summarisation.
- **Functions moved here:**
  - `parse_rows(raw_lines)`
  - `validate_rows(rows)`
  - `as_bool(value)`
  - `summarise(rows)`
- **Constants:** `COLUMNS`

### 2. `report_render.py`
- **Responsibility:** Rendering the digest (CSV and JSON output).
- **Functions moved here:**
  - `render_csv(rows)`
  - `render_json(rows)`
- **Imports:** `csv`, `io`, `json`

## Compatibility Layer
- `report_builder.py` will remain as a thin re-export module:
  - Imports all public names from `report_core` and `report_render`.
  - Preserves the original public API so existing imports (`from report_builder import ...`) continue to work.

## Behaviour Preservation
- No logic changes; only code relocation.
- All existing tests in `test_report_builder.py` must pass unchanged.

## Verification
- Run `python -m pytest -q` to confirm all tests remain green.
