# Refactor Plan: Split report_builder.py

## Current State
`report_builder.py` contains:
- `COLUMNS` constant
- `parse_rows()` – CSV-like line parser
- `validate_rows()` – validation returning problem list
- `as_bool()` – helper
- `summarise()` – aggregation
- `render_text()` – text renderer
- `render_json()` – JSON renderer

## Target Modules

### 1. `report_core.py`
- `COLUMNS`
- `parse_rows()`
- `validate_rows()`
- `as_bool()`
- `summarise()`

### 2. `report_render.py`
- `render_text()`
- `render_json()`
- imports from `report_core`

### 3. `report_builder.py` (thin re-export)
- Re-exports all public names from the two modules so existing imports keep working.

## Behaviour
No logic changes; only file organisation. Tests must remain green.
