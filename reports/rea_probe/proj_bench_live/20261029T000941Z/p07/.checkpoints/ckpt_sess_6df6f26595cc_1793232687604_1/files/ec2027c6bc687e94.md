```markdown
# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing session against a specific host with a time-limited access grant.

## Prerequisites
1. **Host Identification**: The target host must be explicitly named in the task configuration.
2. **Expiry Configuration**: A specific expiry timestamp (ISO 8601) must be set for the access grant.
3. **Authentication Constraint**: The session must be strictly read-only; no login credentials or authentication tokens are permitted.

## Execution Steps
1. **Validate Configuration**:
   - Confirm the `host` field is populated.
   - Confirm the `expiry` field is set and in the future.
   - Confirm no `login` or `credentials` fields are present.
2. **Initiate Session**:
   - Launch the browser instance targeting the specified `host`.
   - Apply the read-only policy (disable form submissions, file uploads, and state-changing actions).
3. **Monitor Expiry**:
   - Track the current time against the `expiry` timestamp.
   - Terminate the session automatically upon reaching the expiry time.

## Verification
- [ ] Host is named.
- [ ] Expiry is set.
- [ ] No login mechanism is active.
```
