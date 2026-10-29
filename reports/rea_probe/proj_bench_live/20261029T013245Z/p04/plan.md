1. Define a feature flag configuration with a default value of `false`.
2. Implement the feature logic to check the flag state and execute the code only when enabled.
3. Write a unit test asserting the feature is inactive when the flag is at its default state.
4. Write a unit test asserting the feature is active when the flag is explicitly set to `true`.
5. Run the test suite to verify both states behave as expected.
