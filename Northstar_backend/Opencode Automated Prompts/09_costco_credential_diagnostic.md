STATUS: PENDING

# BATCH 09 — Costco / Unwrangle Credential Diagnostic (Offline Only, No Live Call)

Prerequisite: Batch 08 complete and approved. This batch diagnoses the HTTP 403 from
the prior attempt on item `424976` (run_id `20260828T021658Z`). NO live provider call
is authorized in this batch.

## Step 1 — Identify required configuration
- Read `costco_api_client.py` and any related config loader to determine:
  - The exact environment variable NAME(s) required for Unwrangle/Costco
    authentication (names only — never print or reveal values).
  - Any required catalog-source flag, base URL, region/country parameter, or account
    plan/entitlement requirement.
  - Whether the client needs a specific header format (e.g., `Authorization: Bearer`)
    vs. a query-string API key.

## Step 2 — Re-examine the prior failure artifacts
- Read `data/costco-discovery-runs/20260828T021658Z/failure-manifest.json` and the
  scrubbed raw stdout artifact from that run (read-only, do not modify).
- Confirm what the client actually reported: was the required env var detected as
  present or absent at request time? What exact error/status did the client surface?

## Step 3 — Root-cause ranking
Rank, in order of likelihood, based on evidence gathered above:
  a) Required variable was not set in the process that launched the client.
  b) Wrong variable name used (client expects a different name than what's set).
  c) Credential is invalid, expired, or malformed.
  d) Account/plan does not have entitlement to this specific Costco detail endpoint.
  e) Egress/network-level block between this environment and the Unwrangle API.

## Step 4 — Produce operator remediation checklist
- For each required variable, give the exact safe PowerShell command to check
  PRESENCE only (never prints the value), e.g.:
  `if ($env:VARIABLE_NAME) { "SET" } else { "NOT SET" }`
- List the exact steps a human must take outside OpenCode to fix each ranked cause
  (e.g., "set the variable in this PowerShell session before launching OpenCode,"
  "verify the Unwrangle dashboard shows this endpoint as enabled for your plan,"
  "regenerate the API key if expired").

## Step 5 — Report and stop
- Do NOT attempt any live call in this batch, even a "test" one.
- Report the root-cause ranking and the exact remediation checklist.
- State clearly: "Batch 10 (single-item live retry) requires the operator to resolve
  the credential/config issue outside this session, then explicitly approve Batch 10."

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`10_costco_single_item_retry_LIVE.md`, append history, stop for approval.

IMPORTANT: Do not auto-advance into Batch 10 even after operator approval of THIS
batch, unless the operator's approval message also explicitly confirms the credential
issue has been fixed outside this session. If unclear, ask before proceeding.
