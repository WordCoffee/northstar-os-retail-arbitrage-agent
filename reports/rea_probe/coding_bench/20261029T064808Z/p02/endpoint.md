# Read-Only Endpoint Design

## Route
`/api/v1/items/{item_id}`

## Method
`GET`

## JSON Response Shape
```json
{
  "id": "string",
  "name": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

## Status Codes
- `200` – item found
- `404` – item not found
