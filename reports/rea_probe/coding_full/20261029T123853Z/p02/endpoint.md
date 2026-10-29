# Read-Only Endpoint

## Route
- **Method:** GET
- **Path:** `/api/v1/health`
- **Description:** Returns a simple health-check status.

## Implementation

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/api/v1/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
```

## Test

```python
from app import app

def test_health_endpoint():
    client = app.test_client()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```

## Notes
- No schema migration required.
- Endpoint is read-only (GET only).
- Route is registered in the Flask app.
