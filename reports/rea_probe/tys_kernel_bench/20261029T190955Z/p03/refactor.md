# Refactor Plan

The current `report_builder.py` mixes parsing, validation, and rendering in a single file, which makes it hard to test and extend. We will split it into two modules: `report_parser.py` for parsing and validation, and `report_renderer.py` for summarising and rendering. This split keeps the public API identical so existing tests remain green. The refactor preserves all behaviour and only reorganises code into logical units.

## Split Details

1. **report_parser.py** – contains `COLUMNS`, `parse_rows`, `validate_rows`, and `as_bool`.
2. **report_renderer.py** – contains `summarise` and any rendering helpers.
3. **report_builder.py** – becomes a thin re-export module that imports from the two new modules so existing imports keep working.

## Verification

After the split, `pytest` must pass without modification to `test_report_builder.py`. The artifact `refactor.md` documents the plan and the completed split.