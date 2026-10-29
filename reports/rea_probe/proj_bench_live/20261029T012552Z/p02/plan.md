1. **Implement Endpoint**: Create a new controller method with a `GET` route that queries the database using a read-only operation (e.g., `SELECT`) and returns the data as JSON.
2. **Write Test**: Add a unit or integration test that sends a request to the new endpoint and asserts the correct HTTP status code and response payload.
3. **Verify Registration**: Ensure the route is correctly registered in the application’s router or framework configuration so it is accessible via the expected URL.
4. **Confirm No Migration**: Verify that no database schema changes (e.g., `ALTER TABLE`, `CREATE TABLE`) are included in the codebase or migration files.
5. **Run Checks**: Execute the test suite and confirm the endpoint is reachable, the test passes, and no migration scripts are triggered.
