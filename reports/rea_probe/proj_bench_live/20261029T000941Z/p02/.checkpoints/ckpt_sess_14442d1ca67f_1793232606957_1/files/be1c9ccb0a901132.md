```markdown
# Endpoint: Get User Profile

## Overview
This document describes the implementation of a new read-only endpoint for retrieving a user's profile.

## Endpoint Details
- **Method**: `GET`
- **Path**: `/api/users/{id}/profile`
- **Description**: Retrieves the public profile information for a specific user.
- **Access**: Read-only.

## Implementation
1. **Route Registration**:
   - Register the route in the main router configuration.
   - Example: `router.get('/api/users/:id/profile', getUserProfileHandler)`

2. **Handler Logic**:
   - Fetch the user by ID from the database.
   - Return the user's public fields (e.g., username, avatar, bio).
   - Handle 404 if the user is not found.

3. **No Schema Migration**:
   - This endpoint uses existing data structures.
   - No changes to the database schema are required.

## Testing
- **Test Case**: `test_get_user_profile`
  - **Setup**: Create a mock user in the database.
  - **Action**: Send a `GET` request to `/api/users/{id}/profile`.
  - **Assertion**: Verify the response status is 200 and the body contains the expected user data.
  - **Negative Test**: Verify a 404 response for a non-existent user ID.

## Files Modified
- `src/routes/userRoutes.js`: Added the new route.
- `src/controllers/userController.js`: Added the `getUserProfileHandler` function.
- `tests/userProfile.test.js`: Added the test suite for the new endpoint.

## Verification
- [x] Route is registered.
- [x] Test is present and passing.
- [x] No schema migration files were added or modified.
```
