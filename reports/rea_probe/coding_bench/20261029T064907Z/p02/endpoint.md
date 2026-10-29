# Read-Only Endpoint Design

## Route
`GET /api/v1/status`

## Method
`GET`

## JSON Response Shape
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2025-01-01T00:00:00Z"
}
```