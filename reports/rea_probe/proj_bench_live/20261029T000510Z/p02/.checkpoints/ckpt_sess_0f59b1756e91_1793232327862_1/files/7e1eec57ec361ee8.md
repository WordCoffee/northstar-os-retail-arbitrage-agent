```markdown
# Endpoint: GET /api/v1/users/{id}

## Description
Retrieves a single user by their unique identifier. This endpoint is read-only and does not modify any data.

## Implementation

### Route Registration
The route is registered in `routes.py`:

```python
from flask import Blueprint, jsonify, request

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    # Simulate fetching user from database
    user = db.session.query(User).get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200
```

### Test
The test is located in `tests/test_users.py`:

```python
import pytest
from app import app, db
from models import User

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def user():
    with app.app_context():
        u = User(id=1, name='Test User', email='test@example.com')
        db.session.add(u)
        db.session.commit()
        return u

def test_get_user(client, user):
    response = client.get('/api/v1/users/1')
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == 1
    assert data['name'] == 'Test User'
    assert data['email'] == 'test@example.com'

def test_get_user_not_found(client):
    response = client.get('/api/v1/users/999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['error'] == 'User not found'
```

## Notes
- No schema migration is required as the `users` table already exists.
- The endpoint is strictly read-only (GET method only).
- Error handling returns a 404 status code with a JSON error message for non-existent users.
```
