1. **Simulate Change**: Trigger the external event to modify the system state.
2. **Capture State**: Record the resulting state immediately after the change.
3. **Assert Validity**: Verify the new state against expected criteria; ensure unknown states fail the check.
4. **Log Assertion**: Record the assertion result (pass/fail) in the execution log.
5. **Report Completion**: Only report "done" if the assertion is recorded and valid.
