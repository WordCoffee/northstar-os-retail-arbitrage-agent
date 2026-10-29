# Refactor Plan: Split report_builder.py

## Goal
Split the monolithic `report_builder.py` into two focused modules without changing behaviour.

## Split

### 1. `report_core.py` — parsing, validation, summarising, sorting, filtering
- `COLUMNS`
- `parse_rows`
- `validate_rows`
- `as_bool`
- `summarise`
- `sort_rows`
- `filter_rows`

### 2. `report_render.py` — rendering and report assembly
- `render_markdown`
- `render_csv`
- `build_report`
- `healthy`
- `merge_reports`

## Compatibility
`report_builder.py` will re-export all public names from the two new modules so existing imports keep working.

## Verification
Run `python -m pytest -q` — all tests must stay green.
