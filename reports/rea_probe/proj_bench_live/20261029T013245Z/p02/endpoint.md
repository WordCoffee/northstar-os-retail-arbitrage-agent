# Endpoint: GET /api/v1/health

## Description
A read-only endpoint that returns the current health status of the service.

## Route Registration
```python
# app/routes.py
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/v1/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200
```

## Test
```python
# tests/test_health.py
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "ok"}
```

## Schema Migration
None. This endpoint does not interact with the database and requires no schema changes.
