# Refactor Plan: Split report_builder.py

## Current State
`report_builder.py` contains all logic in one module:
- `COLUMNS` constant
- `parse_rows()` – CSV-like line parser
- `validate_rows()` – validation returning problem list
- `as_bool()` – helper
- `summarise()` – aggregation
- `render_text()` / `render_json()` – renderers

## Split Plan

### Module 1: `report_core.py`
Contains the data-handling logic:
- `COLUMNS` constant
- `parse_rows()`
- `validate_rows()`
- `as_bool()`
- `summarise()`

### Module 2: `report_render.py`
Contains the rendering logic:
- `render_text()`
- `render_json()`
- Imports from `report_core` as needed

### Module 3: `report_builder.py` (facade)
Re-exports everything from the two modules so that existing imports (`from report_builder import ...`) keep working unchanged.

## Behaviour Preservation
- No logic changes; only file reorganisation.
- `report_builder.py` re-exports all public names.
- Tests in `test_report_builder.py` import from `report_builder`, so they remain green without modification.

## Verification
Run `python -m pytest -q` after the split to confirm all tests pass.
