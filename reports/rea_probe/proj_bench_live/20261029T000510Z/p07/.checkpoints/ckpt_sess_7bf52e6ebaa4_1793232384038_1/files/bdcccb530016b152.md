```markdown
# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing session against a specific host with a time-bound access grant.

## Prerequisites
- **Host Named**: The target hostname must be explicitly defined in the task configuration.
- **Expiry Set**: The access grant must include a defined expiration timestamp.
- **No Login**: The session must not require or perform any authentication/login steps.

## Steps
1. **Define Host**: Specify the target host in the task parameters.
2. **Set Expiry**: Configure the grant expiration time.
3. **Initiate Session**: Launch the browser task in read-only mode.
4. **Verify Constraints**:
   - Confirm host is named.
   - Confirm expiry is set.
   - Confirm no login is attempted.
5. **Execute**: Perform read-only operations (e.g., view, scrape, screenshot).
6. **Terminate**: End the session upon expiry or task completion.

## Checks
- [ ] Host named
- [ ] Expiry set
- [ ] No login
```
