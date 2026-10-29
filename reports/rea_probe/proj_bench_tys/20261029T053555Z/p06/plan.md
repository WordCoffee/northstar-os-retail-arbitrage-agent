# Plan: Inspect One Admin Panel Read-Only and Report the Value with Evidence

## Objective
Inspect a single admin panel in read-only mode and report a specific value with concrete evidence.

## Steps

1. **Identify Target**
   - Determine which admin panel to inspect (e.g., `admin/dashboard.html`, `admin/settings.json`, or a specific API endpoint).
   - Confirm the panel is accessible in read-only mode (no write operations).

2. **Locate the Value**
   - Open the relevant file or endpoint.
   - Identify the specific value to report (e.g., a configuration flag, user count, feature toggle, or status field).

3. **Gather Evidence**
   - Record the exact file path and line number where the value appears.
   - If the value comes from an API response, record the endpoint URL and the JSON field path.
   - Quote the exact value as it appears.

4. **Report**
   - State the value.
   - Provide the evidence: file path, line number, and the raw content snippet.
   - Confirm no modifications were made (read-only verification).

## Output Format
```
Value: <the value>
Evidence:
  File: <path>
  Line: <line number>
  Content: <exact snippet>
Read-Only: Confirmed (no writes performed)
```

## Constraints
- No tools available; rely only on provided file contents.
- If the file or value is not shown in the provided context, state: "Not available in provided context."
- Do not modify any files.
