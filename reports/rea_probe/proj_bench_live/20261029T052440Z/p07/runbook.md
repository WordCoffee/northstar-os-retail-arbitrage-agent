# Runbook: Read-Only Browser Task

## Objective
Execute a read-only browsing task on a specific host with a time-limited access grant.

## Prerequisites
- Target host is explicitly named.
- Access grant is configured with a defined expiry timestamp.
- No login credentials are required or used.

## Steps
1. **Verify Host Configuration**
   - Confirm the target host is explicitly named in the task configuration.
   - Ensure the host is reachable and accessible without authentication.

2. **Validate Grant Expiry**
   - Check that the access grant has a defined expiry timestamp.
   - Confirm the current time is before the expiry timestamp.

3. **Execute Read-Only Task**
   - Open the browser to the specified host.
   - Perform only read-only actions (e.g., viewing pages, downloading public resources).
   - Do not attempt any login or authentication.

4. **Monitor Expiry**
   - Track the remaining time until the grant expires.
   - Terminate the task immediately upon expiry.

## Checks
- **Host Named**: The target host must be explicitly specified.
- **Expiry Set**: The access grant must have a defined expiry timestamp.
- **No Login**: The task must not require or use any login credentials.

## Notes
- This runbook is for read-only tasks only.
- Any attempt to log in or modify resources is prohibited.
- The task must terminate automatically upon grant expiry.
