# Refactor Plan: Split report_builder.py

## Goal
Split `report_builder.py` into two focused modules without changing behaviour.

## Proposed Modules

### 1. `report_core.py`
- `COLUMNS` constant
- `parse_rows(raw_lines)`
- `validate_rows(rows)`
- `as_bool(value)`
- `summarise(rows)`

### 2. `report_render.py`
- `render_text(summary)`
- `render_json(summary)`

## Steps
1. Create `report_core.py` with parsing, validation, and summarisation.
2. Create `report_render.py` with the two renderers.
3. Update `report_builder.py` to re-export from the two new modules (backwards-compatible).
4. Run `python -m pytest -q` to confirm tests stay green.

## Acceptance
- `python -m pytest -q` passes.
- No behavioural change: same public API, same outputs.
