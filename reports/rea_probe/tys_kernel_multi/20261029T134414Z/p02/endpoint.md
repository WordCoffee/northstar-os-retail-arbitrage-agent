# Endpoint: GET /ledger/period

## Route
- Method: GET
- Path: /ledger/period

## Response
- Content-Type: application/json
- Status: 200
- Body:
```json
{
  "period": "2024-Q1",
  "currency": "USD"
}
```

## Test
- `test_endpoint.py` will call the route and assert the JSON shape.

## Migration
- None. Read-only; no schema changes.
