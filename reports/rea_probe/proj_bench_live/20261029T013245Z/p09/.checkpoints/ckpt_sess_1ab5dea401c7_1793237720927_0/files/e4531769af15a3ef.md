1. **Simulate Change**: Trigger the external event that modifies the system state.
2. **Capture State**: Record the resulting system state immediately after the change.
3. **Assert Validity**: Verify the recorded state against expected criteria; if the state is unknown or invalid, mark the check as failed.
4. **Log Assertion**: Save the assertion result (pass/fail) to the execution log.
5. **Report Completion**: Only report "done" if the assertion check passed; otherwise, report failure.
