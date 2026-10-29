1. **Define Route**: Create a new read-only endpoint (e.g., `GET /api/resource`) in the router/controller layer, ensuring it only performs `SELECT` queries.
2. **Implement Logic**: Write the handler function to fetch data from the database without modifying any state or triggering schema changes.
3. **Write Test**: Add a unit/integration test that asserts the endpoint returns the expected status code (200) and data structure.
4. **Verify Constraints**: Confirm the route is registered in the application's route table and verify that no migration files or schema alterations are included in the changeset.
5. **Run Checks**: Execute the test suite to ensure the new test passes and existing tests remain green.
