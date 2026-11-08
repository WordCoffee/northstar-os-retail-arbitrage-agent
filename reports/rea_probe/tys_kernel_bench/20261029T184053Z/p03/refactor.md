# Refactor Plan

The current report_builder.py module contains parsing, validation, summarisation, and rendering logic in a single file. This refactor will split the module into two focused modules: report_core.py for data handling and report_render.py for output generation. The split will preserve all existing behaviour while improving maintainability and testability. No public API changes will be made to ensure backward compatibility with existing tests.

## Split Details

**report_core.py** will contain:
- COLUMNS constant
- parse_rows() function
- validate_rows() function
- as_bool() helper
- summarise() function

**report_render.py** will contain:
- render_csv() function
- render_json() function
- Any rendering-specific utilities

## Migration Strategy

1. Create report_core.py with all data processing functions
2. Create report_render.py with all rendering functions
3. Update report_builder.py to import from the new modules
4. Verify all existing tests pass without modification
5. Ensure no TODO, TBD, or FIXME markers remain in the final code

## Verification

The refactor will be validated by running the existing pytest suite to confirm that all behaviour remains unchanged. The artifact refactor.md documents this plan and the subsequent split report will confirm successful completion.