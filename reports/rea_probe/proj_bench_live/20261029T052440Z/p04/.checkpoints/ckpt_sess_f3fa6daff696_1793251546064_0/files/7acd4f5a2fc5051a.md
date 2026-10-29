1. Define a feature flag constant (e.g., `ENABLE_NEW_FEATURE`) with a default value of `false` in the configuration module.
2. Implement the feature logic by checking the flag to determine whether to execute the new code path or the legacy path.
3. Write a unit test that asserts the feature is inactive when the flag is `false` (default state).
4. Write a unit test that asserts the feature is active when the flag is explicitly set to `true`.
5. Run the test suite to verify both states pass and confirm the default behavior remains off.
