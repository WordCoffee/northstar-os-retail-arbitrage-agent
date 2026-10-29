# GET /ledger/period

## Route
- **Method:** GET
- **Path:** `/ledger/period`
- **Registered:** Yes (added to the router in `main.go`)

## Request
- No query parameters required.
- No request body.

## Response
- **Status:** 200 OK
- **Content-Type:** `application/json`
- **Body shape:**
```json
{
  "period": "2024-06",
  "currency": "USD"
}
```

## Test
- `TestGetLedgerPeriod` in `main_test.go` issues a GET to `/ledger/period` and asserts:
  - status code is 200
  - `Content-Type` is `application/json`
  - the JSON body contains a non-empty `period` string and a `currency` string

## Migration
- **None.** This endpoint is read-only and does not alter the schema.
