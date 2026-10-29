# Refactor Plan for report_builder.py

## Current State
`report_builder.py` contains:
- `COLUMNS` constant
- `parse_rows(raw_lines)` – CSV-like parsing
- `validate_rows(rows)` – validation returning problem list
- `as_bool(value)` – helper
- `summarise(rows)` – aggregation
- `render_text(...)` and `render_json(...)` – renderers

## Split Plan
1. **`report_core.py`** – data layer:
   - `COLUMNS`
   - `parse_rows`
   - `validate_rows`
   - `as_bool`
   - `summarise`
2. **`report_render.py`** – presentation layer:
   - `render_text`
   - `render_json`
   - imports from `report_core`
3. **`report_builder.py`** – thin re-export shim so existing imports keep working:
   - re-exports all public names from the two new modules

## Behaviour
No logic changes; only module boundaries move. Tests in `test_report_builder.py` must remain green.
