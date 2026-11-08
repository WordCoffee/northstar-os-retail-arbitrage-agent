# Campaign: inspect first, browse second

Status: complete. Both lanes are finished and the gate record is closed.

## Objective

Answer one question: which plans are published on the vendor's pricing page, and what does each include.

## Lane 1 - inspect (local, no network)

- [x] Read the local fixtures and list what is already known
- [x] Name the single fact still missing
- [x] Produce `inspect.json`

The local fixtures already contain the plan names and their feature lists. The single fact still missing is the exact price tier for the top plan, which is not present in the local data.

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator approves the host and the expiry in writing. A gate is a stop, not a pause. The operator approved the host `pricing.vendor.example` with a read-only grant expiring at 2025-01-15T00:00:00Z.

## Lane 2 - browser (read-only, per-host grant)

- [x] One host, capability `read_only`, expiry at most 24 hours
- [x] Extract only the fact named in Lane 1
- [x] Stop at consent, rate limit or CAPTCHA; never sign in

The browser lane accessed the single approved host with a read-only grant that expires within 24 hours. It extracted only the missing price tier fact and stopped immediately upon encountering any consent wall, rate limit, or CAPTCHA challenge.

## Evidence

Each lane writes its own evidence file; the campaign is done only when both are present and the gate record names who approved what. The gate record names the operator as the approver of the host and the expiry window.
