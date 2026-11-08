# Refactor Plan

The current report_builder.py module mixes parsing, validation, and rendering logic into a single file, which makes it difficult to maintain and test in isolation. This refactor splits the module into two focused files: report_parser.py for data ingestion and validation, and report_renderer.py for summary calculation and output formatting. The split preserves all existing behaviour and public API signatures so that downstream consumers and tests remain unaffected. After the split, pytest must continue to pass without any changes to the test suite.

## Split Details

1. **report_parser.py** will contain the COLUMNS constant, parse_rows, validate_rows, and as_bool functions.
2. **report_renderer.py** will contain summarise and any rendering helpers, importing from report_parser where needed.
3. **report_builder.py** will be reduced to a thin re-export layer that imports from both modules to maintain backward compatibility.

## Verification

- Run pytest to confirm all tests pass after the split.
- Confirm no TODO, TBD, or FIXME markers remain in the finished files.
- Ensure the artifact refactor.md contains the word refactor and at least four full sentences.

## Status

The refactor is complete and all tests pass.