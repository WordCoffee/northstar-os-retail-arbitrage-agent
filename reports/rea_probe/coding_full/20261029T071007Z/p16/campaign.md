# Campaign: inspect first, browse second

Status: planned. Lane 1 is local-only; Lane 2 is gated.

## Objective

Answer one question: which plans are published on the vendor's pricing page,
and what does each include.

## Lane 1 - inspect (local, no network)

- [x] Read the local fixtures and list what is already known
- [x] Name the single fact still missing
- [x] Produce `inspect.json`

Known from local fixtures:
- Vendor name: Acme Cloud
- Local fixture `pricing.json` lists three plan names: Basic, Pro, Enterprise
- Local fixture does not include feature lists or pricing tiers

Single missing fact: the feature list and price for each plan as published on the vendor's pricing page.

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator
approves the host and the expiry in writing. A gate is a stop, not a pause.

Gate record:
- Approver: operator (human)
- Approved host: pricing.acmecloud.example
- Approved capability: read_only
- Approved expiry: 24 hours from approval
- Approval status: PENDING (operator must confirm in writing before Lane 2 starts)

## Lane 2 - browser (read-only, per-host grant)

- [x] One host: pricing.acmecloud.example, capability `read_only`, expiry at most 24 hours
- [x] Extract only the fact named in Lane 1: feature list and price for each plan
- [x] Stop at consent, rate limit or CAPTCHA; never sign in

## Evidence

Each lane writes its own evidence file; the campaign is done only when both
are present and the gate record names who approved what.

- Lane 1 evidence: `inspect.json`
- Lane 2 evidence: `browser.json` (to be produced after gate approval)
