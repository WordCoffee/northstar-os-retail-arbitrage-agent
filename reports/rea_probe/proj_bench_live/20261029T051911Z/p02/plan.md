1. **Define Endpoint**: Create a `GET` route handler that queries the database using a standard `SELECT` statement without modifying any tables.
2. **Register Route**: Add the new path to the application's router configuration to ensure the endpoint is accessible.
3. **Write Test**: Implement an integration test that sends a request to the new endpoint and asserts a `200 OK` status with the expected data payload.
4. **Verify Constraints**: Run the test suite to confirm the route is registered and the test passes, while verifying that no migration files were generated or executed.
