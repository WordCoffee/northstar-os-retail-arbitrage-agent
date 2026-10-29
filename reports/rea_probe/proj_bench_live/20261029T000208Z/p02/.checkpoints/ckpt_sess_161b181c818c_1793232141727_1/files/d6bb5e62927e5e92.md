```markdown
# Endpoint: GET /api/v1/users/{id}

## Overview
Adds a read-only endpoint to retrieve a single user by ID.

## Implementation
- **Route**: `GET /api/v1/users/{id}`
- **Handler**: `get_user_by_id`
- **Response**:
  - `200 OK`: Returns user object.
  - `404 Not Found`: If user does not exist.

## Test
- **File**: `tests/test_users.py`
- **Test Case**: `test_get_user_by_id`
  - Mocks database query.
  - Asserts `200` status and correct payload.
  - Asserts `404` status for non-existent ID.

## Migration
- **None**: No schema changes required.
```
