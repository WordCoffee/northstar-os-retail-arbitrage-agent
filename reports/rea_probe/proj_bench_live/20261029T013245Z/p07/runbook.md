# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing session against a specific host with a time-limited access grant.

## Prerequisites
1. **Host Identification**: The target host must be explicitly named in the task configuration.
2. **Expiry Configuration**: An absolute expiry timestamp (ISO 8601) must be set for the grant.
3. **Authentication Constraint**: The session must operate without login credentials (read-only public access).

## Execution Steps
1. **Validate Host**: Confirm the host name is present and valid in the task parameters.
2. **Validate Expiry**: Ensure the expiry timestamp is set and is in the future relative to the current time.
3. **Validate Access Mode**: Confirm the task is configured for read-only access and that no login flow is triggered.
4. **Execute Task**:
   - Open the browser to the specified host.
   - Perform read-only operations (e.g., viewing pages, downloading public assets).
   - Do not attempt any form of authentication or data modification.
5. **Enforce Expiry**:
   - Monitor the session duration.
   - Terminate the session immediately upon reaching the expiry timestamp.

## Verification Checks
- [ ] Host name is explicitly defined.
- [ ] Expiry timestamp is set and valid.
- [ ] No login credentials are used or required.
- [ ] Session terminates at the specified expiry time.

## Failure Handling
- If host is missing: Abort task and log error.
- If expiry is missing or in the past: Abort task and log error.
- If login is attempted: Abort task and log security violation.
