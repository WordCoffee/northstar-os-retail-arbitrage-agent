1. **Simulate Change**: Apply the simulated external modification to the target system or data structure.
2. **Capture State**: Record the resulting state immediately after the change is applied.
3. **Assert Validity**: Execute the assertion logic to verify the new state matches the expected outcome.
4. **Handle Failure**: If the assertion fails or the state is unknown, halt execution and report an error; do not proceed.
5. **Report Completion**: Only if the assertion succeeds, log the success and report the task as done.
