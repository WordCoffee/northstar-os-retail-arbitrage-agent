# Read-Only Endpoint Design

## Route
`/api/v1/items`

## Method
`GET`

## JSON Response Shape
```json
{
  "data": [
    {
      "id": "string",
      "name": "string",
      "created_at": "string (ISO 8601)"
    }
  ],
  "meta": {
    "count": "integer"
  }
}
```