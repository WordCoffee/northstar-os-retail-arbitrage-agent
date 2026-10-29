1. **Reproduce the Failure**
   Run the specific failing unit test to capture the exact error message, stack trace, and assertion details.

2. **Isolate the Root Cause**
   Analyze the test logic and the corresponding production code to identify the discrepancy between expected and actual behavior, focusing on logic errors rather than test setup.

3. **Implement the Fix**
   Modify the production code (or test setup, if applicable) to resolve the identified issue, ensuring the logic aligns with the test's intent.

4. **Verify and Validate**
   Re-run the target test to confirm it passes, then execute the full test suite to ensure no regressions were introduced.

5. **Final Compliance Check**
   Review the diff to confirm that the test assertion remains unchanged and only the implementation or non-assertion test logic was modified.
