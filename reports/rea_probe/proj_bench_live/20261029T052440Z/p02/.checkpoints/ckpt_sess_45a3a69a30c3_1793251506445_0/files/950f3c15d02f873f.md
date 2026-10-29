1. **Define Route**: Create a new `GET` endpoint in the router configuration that queries the database using a standard `SELECT` statement.
2. **Implement Handler**: Write the controller function to execute the query and return the result as a JSON response, ensuring no write operations are performed.
3. **Write Test**: Add a unit or integration test that mocks the database layer or uses a test database to verify the endpoint returns the expected data and status code.
4. **Verify Constraints**: Confirm the route is registered in the application's route table and ensure no migration files or schema changes are included in the diff.
