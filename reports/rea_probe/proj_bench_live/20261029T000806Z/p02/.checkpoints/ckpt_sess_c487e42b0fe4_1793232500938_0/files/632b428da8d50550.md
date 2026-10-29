1. **Define Route**: Create a new `GET` endpoint in the router configuration that returns static or cached data, ensuring it does not trigger any database schema changes.
2. **Implement Handler**: Write the controller function to fetch the required data using existing queries or services, strictly avoiding any `ALTER TABLE` or migration logic.
3. **Write Test**: Add a unit or integration test that asserts the endpoint returns the expected status code and payload structure.
4. **Verify Constraints**: Run the test suite to confirm the route is registered and the test passes, then verify via code review that no migration files were created or modified.
