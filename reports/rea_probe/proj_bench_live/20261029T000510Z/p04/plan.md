1. Define a feature flag variable (e.g., `ENABLE_FEATURE`) with a default value of `false` in the configuration module.
2. Implement the feature logic by wrapping the new code in a conditional check against the flag.
3. Write a unit test that asserts the feature is inactive when the flag is `false` (default state).
4. Write a unit test that asserts the feature is active when the flag is explicitly set to `true`.
5. Run the test suite to verify both states pass and confirm the default behavior remains off.
