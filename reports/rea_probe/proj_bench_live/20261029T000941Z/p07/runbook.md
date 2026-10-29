# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing task against a specific host with a time-limited access grant.

## Prerequisites
- Target host name is explicitly defined.
- Expiry timestamp is set for the access grant.
- No login or authentication credentials are required or used.

## Steps
1. **Define Host**: Specify the exact host name for the target resource.
2. **Set Expiry**: Configure the access grant to expire at a specific timestamp.
3. **Initiate Session**: Open a browser session to the host in read-only mode.
4. **Verify Constraints**:
   - Confirm the host name matches the defined target.
   - Confirm the session expires at the set time.
   - Confirm no login prompt or credential entry is required.
5. **Execute Task**: Perform the read-only browsing actions within the grant window.
6. **Terminate**: Close the session upon task completion or expiry.

## Checks
- [ ] Host name is explicitly named.
- [ ] Expiry timestamp is set.
- [ ] No login is required or performed.
