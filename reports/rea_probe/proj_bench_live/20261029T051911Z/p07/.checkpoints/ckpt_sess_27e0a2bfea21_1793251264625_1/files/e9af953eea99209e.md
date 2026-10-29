# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing session against a specific host with a time-limited access grant.

## Pre-Conditions
1. **Host Identification**: The target host must be explicitly named (e.g., `example.com`).
2. **Grant Validation**: A valid, per-host access grant must be issued.
3. **Expiry Check**: The grant must have a defined expiry timestamp.
4. **Authentication Constraint**: The task must be executed **without** login credentials (read-only mode).

## Procedure
1. **Verify Host**: Confirm the target host is explicitly defined in the task configuration.
2. **Check Grant**: Ensure the access grant is active and scoped to the specified host.
3. **Validate Expiry**: Confirm the current time is before the grant's expiry timestamp.
4. **Initiate Session**: Launch the browser in read-only mode (no login, no write operations).
5. **Execute Task**: Perform the required read-only operations (e.g., viewing pages, downloading public data).
6. **Terminate**: Close the session before the grant expires.

## Constraints
- **No Login**: Do not attempt to authenticate or log in.
- **Read-Only**: No modifications, submissions, or state-changing actions are permitted.
- **Host-Specific**: Access is limited to the named host only.

## Failure Handling
- If the host is not named, abort the task.
- If the grant is expired or invalid, abort the task.
- If login is attempted, abort the task.
