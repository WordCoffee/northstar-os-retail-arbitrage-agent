# Refactor Plan

The current report_builder.py module contains parsing, validation, summarisation, and rendering logic in a single file. This refactor splits the module into two focused modules: report_parser.py for input handling and report_renderer.py for output generation. The split preserves all existing behaviour and keeps the public API stable for downstream consumers.

## Split Plan

1. **report_parser.py** will contain: COLUMNS constant, parse_rows(), validate_rows(), and as_bool() functions.
2. **report_renderer.py** will contain: summarise() and any rendering functions that produce the final digest output.
3. **report_builder.py** will become a thin re-export module that imports from both new modules to maintain backward compatibility.

## Behaviour Preservation

All function signatures, return values, and error messages remain identical. The pytest suite must pass without modification after the split. No TODO, TBD, or FIXME markers are introduced in the finished files.