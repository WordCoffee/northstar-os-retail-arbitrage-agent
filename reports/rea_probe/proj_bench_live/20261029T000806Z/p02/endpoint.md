```markdown
# Endpoint: Get User by ID

## Overview
This document describes the implementation of a new read-only endpoint to retrieve a user by their unique identifier.

## Endpoint Details
- **Method**: `GET`
- **Path**: `/users/{id}`
- **Description**: Retrieves a single user record by ID.
- **Permissions**: Read-only.

## Implementation
### Route Registration
The route is registered in the application's router configuration.

```python
# app/routes.py
from flask import Blueprint, jsonify, request
from app.models import User

users_bp = Blueprint('users', __name__)

@users_bp.route('/users/<int:id>', methods=['GET'])
def get_user_by_id(id):
    user = User.query.get(id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200
```

### Test
A unit test is included to verify the endpoint's functionality.

```python
# tests/test_users.py
import pytest
from app import create_app
from app.models import User

@pytest.fixture
def client():
    app = create_app()
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_user(client):
    with client.application.app_context():
        user = User(id=1, name='Test User', email='test@example.com')
        client.application.db.session.add(user)
        client.application.db.session.commit()
        return user

def test_get_user_by_id(client, sample_user):
    response = client.get('/users/1')
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == 1
    assert data['name'] == 'Test User'
    assert data['email'] == 'test@example.com'

def test_get_user_not_found(client):
    response = client.get('/users/999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['error'] == 'User not found'
```

## Schema Migration
No schema migration is required for this endpoint. The `User` model and its corresponding database table already exist.

## Verification
- **Route Registered**: The route `/users/<int:id>` is registered in `app/routes.py`.
- **Test Present**: Tests are included in `tests/test_users.py`.
- **No Migration**: No changes to the database schema are needed.
```
