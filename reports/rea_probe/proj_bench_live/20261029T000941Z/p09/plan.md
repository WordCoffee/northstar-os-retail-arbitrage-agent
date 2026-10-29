1. **Simulate Change**: Trigger the external event to modify the system state.
2. **Capture State**: Record the resulting state immediately after the change.
3. **Assert Validity**: Verify the recorded state against expected values; flag any unknown or invalid results as failures.
4. **Report Outcome**: Only report "done" if the assertion passes; otherwise, report the failure.
