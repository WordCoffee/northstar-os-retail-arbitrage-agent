# Campaign: inspect first, browse second

Status: complete. Both lanes are finished and the gate record is closed.

## Objective

Answer one question: which plans are published on the vendor's pricing page, and what does each include.

## Gate

The gate is a stop, not a pause. Lane 2 does not begin until the operator approves the host and the expiry in writing. The gate record names the approver, the host, the capability, and the expiry. The gate remains a hard stop until the operator signs off in writing.

## Lane

Lane 1 is the inspect lane. It reads the local fixtures and lists what is already known. Lane 2 is the browser lane. It uses a read-only grant on a single host and extracts only the fact named in Lane 1.

### Lane 1 - inspect (local, no network)

- [x] Read the local fixtures and list what is already known
- [x] Name the single fact still missing
- [x] Produce `inspect.json`

### Lane 2 - browser (read-only, per-host grant)

- [x] One host, capability `read_only`, expiry at most 24 hours
- [x] Extract only the fact named in Lane 1
- [x] Stop at consent, rate limit or CAPTCHA; never sign in

## Evidence

Each lane writes its own evidence file. The campaign is done only when both are present and the gate record names who approved what.

## Gate Record

- Approver: operator
- Host: vendor-pricing.example.com
- Capability: read_only
- Expiry: 24 hours from approval

## Summary

The gate is a stop and the lane is the work. Lane 1 inspected the local fixtures and named the missing fact. Lane 2 used a read-only grant on a single host with a 24-hour expiry. The gate record names the approver, the host, the capability, and the expiry. Both lanes are complete and the campaign is finished.
