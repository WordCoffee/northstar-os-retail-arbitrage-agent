# Refactor Plan: Split `report_builder.py`

## Current State
`report_builder.py` contains four logical concerns:
1. **Parsing** – `parse_rows()`
2. **Validation** – `validate_rows()`, `as_bool()`
3. **Summarisation** – `summarise()`
4. **Rendering** – `render_csv()`, `render_json()`

## Target Layout

### `report_builder.py` (kept as the public entry point)
- Re-exports `parse_rows`, `validate_rows`, `as_bool`, `summarise`, `render_csv`, `render_json` from the two new sub-modules so that existing imports (`from report_builder import ...`) continue to work unchanged.
- Keeps the `COLUMNS` constant.

### `report_parser.py` (new)
- `parse_rows()`
- `validate_rows()`
- `as_bool()`
- `COLUMNS` constant

### `report_renderer.py` (new)
- `summarise()`
- `render_csv()`
- `render_json()`

## Behavioural Guarantee
- No function signature changes.
- No logic changes; code is moved verbatim.
- `report_builder.py` re-exports everything, so `test_report_builder.py` (which imports from `report_builder`) stays green without modification.

## Verification
- Run `python -m pytest -q` after the split; all existing tests must pass.
