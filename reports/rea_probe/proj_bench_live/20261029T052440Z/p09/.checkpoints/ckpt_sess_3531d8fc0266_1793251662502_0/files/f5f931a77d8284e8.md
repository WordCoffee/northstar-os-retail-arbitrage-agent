1. **Simulate External Change**: Trigger the predefined event or input that modifies the system state.
2. **Capture New State**: Record the resulting system state immediately after the change.
3. **Execute Assertion**: Verify that the captured state matches the expected new state.
4. **Handle Failure**: If the assertion fails or the state is unknown, halt execution and report an error.
5. **Report Completion**: If the assertion passes, log the success and report the task as done.
