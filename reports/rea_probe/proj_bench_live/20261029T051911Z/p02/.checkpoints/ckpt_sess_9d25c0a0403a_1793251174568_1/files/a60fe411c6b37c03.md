# Endpoint: GET /api/v1/status

## Description
A read-only endpoint that returns the current application status.

## Route Registration
```python
# app/routes.py
from flask import Blueprint, jsonify

status_bp = Blueprint('status', __name__)

@status_bp.route('/api/v1/status', methods=['GET'])
def get_status():
    return jsonify({"status": "ok"}), 200
```

## Test
```python
# tests/test_status.py
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_status_endpoint(client):
    response = client.get('/api/v1/status')
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "ok"}
```

## Schema Migration
None. This endpoint does not require any database schema changes.
