# Read-Only Endpoint

## Route
- **Method:** GET
- **Path:** `/api/v1/status`
- **Description:** Returns the current system status in a read-only manner.

## Response
- **Status Code:** 200
- **Content-Type:** application/json
- **Body:** `{ "status": "ok" }`

## Test
- A test is included in `test_endpoint.py` that asserts the route is registered and returns the expected payload.

## Migration
- No schema migration is required for this endpoint.
