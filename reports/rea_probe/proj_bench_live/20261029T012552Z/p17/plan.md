1. **Capture State**: Immediately log the failed assertion details and snapshot the current plan version to ensure the old version is retained for audit.
2. **Diagnose Root Cause**: Analyze the failure to determine if it is a data, logic, or environment issue, avoiding blind retries.
3. **Generate New Plan**: Create a revised execution plan that incorporates the diagnostic findings and adjusts the strategy accordingly.
4. **Validate & Version**: Verify the new plan against the original constraints and assign a new version number while keeping the old version accessible.
5. **Execute Revised Plan**: Proceed with the new plan, monitoring for further assertions to trigger the re-planning loop if necessary.
