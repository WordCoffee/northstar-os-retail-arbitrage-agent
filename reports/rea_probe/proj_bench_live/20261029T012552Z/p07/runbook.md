# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing session against a specific host with a time-bound access grant.

## Prerequisites
1. **Host Identification**: The target host must be explicitly named in the task configuration.
2. **Expiry Configuration**: A specific expiry timestamp (ISO 8601) must be set for the grant.
3. **Authentication Constraint**: The session must be configured for **no login** (anonymous/read-only access only).

## Execution Steps
1. **Validate Configuration**:
   - Confirm the `host` field is populated.
   - Confirm the `expiry` field is set and is in the future.
   - Confirm the `auth_mode` is set to `none` or `read_only`.

2. **Initialize Session**:
   - Launch the browser instance.
   - Apply the read-only policy (disable form inputs, file uploads, and state-changing requests).
   - Set the session timeout to match the `expiry` timestamp.

3. **Execute Task**:
   - Navigate to the specified host.
   - Perform read-only operations (e.g., viewing pages, downloading static assets).
   - Monitor session status; terminate automatically upon reaching `expiry`.

4. **Cleanup**:
   - Close the browser instance.
   - Revoke the access grant.
   - Log the session duration and accessed resources.

## Verification Checks
- [ ] Host is explicitly named.
- [ ] Expiry timestamp is set.
- [ ] No login credentials are provided or used.
- [ ] Session terminates automatically at expiry.

## Failure Handling
- If host is not named: **Abort** with error `MISSING_HOST`.
- If expiry is not set: **Abort** with error `MISSING_EXPIRY`.
- If login is attempted: **Abort** with error `UNAUTHORIZED_LOGIN_ATTEMPT`.
