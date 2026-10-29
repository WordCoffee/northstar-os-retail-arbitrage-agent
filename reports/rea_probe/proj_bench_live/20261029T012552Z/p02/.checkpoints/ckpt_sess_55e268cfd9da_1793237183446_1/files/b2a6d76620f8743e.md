```markdown
# Endpoint: GET /api/v1/users/{id}

## Overview
This document specifies the addition of a new read-only endpoint to retrieve a single user by their unique identifier. This endpoint is designed to be lightweight and stateless, requiring no changes to the database schema.

## Implementation Details

### 1. Route Registration
The route is registered in the main application router. It is defined as a `GET` request to the path `/api/v1/users/:id`.

**Code Example (Express.js):**
```javascript
// routes/users.js
const express = require('express');
const router = express.Router();
const userService = require('../services/userService');

// GET /api/v1/users/:id
router.get('/:id', async (req, res) => {
    try {
        const userId = req.params.id;
        const user = await userService.findById(userId);
        
        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }
        
        res.status(200).json(user);
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
```

### 2. Service Layer
The `userService` is responsible for fetching the user from the database. Since this is a read-only operation, it uses a simple `SELECT` query.

**Code Example:**
```javascript
// services/userService.js
const db = require('../db');

const findById = async (id) => {
    const result = await db.query('SELECT * FROM users WHERE id = $1', [id]);
    return result.rows[0];
};

module.exports = {
    findById
};
```

### 3. Testing
A unit test is added to verify the endpoint's functionality. The test mocks the database layer to ensure the route correctly handles both successful retrieval and 404 scenarios.

**Code Example (Jest):**
```javascript
// __tests__/users.test.js
const request = require('supertest');
const app = require('../app');
const userService = require('../services/userService');

// Mock the service
jest.mock('../services/userService');

describe('GET /api/v1/users/:id', () => {
    it('should return 200 and user data if user exists', async () => {
        const mockUser = { id: '123', name: 'John Doe' };
        userService.findById.mockResolvedValue(mockUser);

        const response = await request(app).get('/api/v1/users/123');

        expect(response.status).toBe(200);
        expect(response.body).toEqual(mockUser);
    });

    it('should return 404 if user does not exist', async () => {
        userService.findById.mockResolvedValue(null);

        const response = await request(app).get('/api/v1/users/999');

        expect(response.status).toBe(404);
        expect(response.body).toEqual({ error: 'User not found' });
    });
});
```

## Schema Migration
**None.**
This endpoint is strictly read-only and
