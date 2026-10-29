# GET /period

## Route
- Method: GET
- Path: /period
- Response: JSON object with a single key `period` (string, e.g. "2024-Q1")

## Test
- `test_period.py` asserts that a GET to `/period` returns 200 and a JSON body containing `period`.

## Constraints
- Read-only; no schema migration.
- JSON only.
