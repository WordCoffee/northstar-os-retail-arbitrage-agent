# Refactor Plan: Split report_builder.py

## Goal
Split the monolithic `report_builder.py` into two focused modules without changing behaviour.

## Split

### Module 1: `report_core.py`
- `COLUMNS` constant
- `parse_rows(raw_lines)`
- `validate_rows(rows)`
- `as_bool(value)`
- `summarise(rows)`
- `sort_rows(rows, reverse=False)`
- `filter_rows(rows, ok_only=False, lane=None)`

### Module 2: `report_render.py`
- `render_markdown(summary)`
- `render_csv(rows)`
- `build_report(raw_lines)`
- `merge_reports(reports)`
- `healthy(report)`

## Compatibility
`report_builder.py` will re-export all public names from the two new modules so existing imports keep working.

## Verification
Run `python -m pytest -q`; all tests must pass.
