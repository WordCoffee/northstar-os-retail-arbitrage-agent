# Campaign: inspect first, browse second

Status: complete. Both lanes are finished and the gate has been cleared.

## Objective

Answer one question: which plans are published on the vendor's pricing page, and what does each include.

## Lane 1 - inspect (local, no network)

- [x] Read the local fixtures and list what is already known
- [x] Name the single fact still missing
- [x] Produce `inspect.json`

The local fixtures contain the vendor's plan names and their feature lists. The single fact still missing is the exact price for each plan as published on the live pricing page.

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator approves the host and the expiry in writing. A gate is a stop, not a pause.

The gate was approved by the operator on 2024-01-15, granting read-only access to the host `pricing.vendor.com` with an expiry of 24 hours.

## Lane 2 - browser (read-only, per-host grant)

- [x] One host, capability `read_only`, expiry at most 24 hours
- [x] Extract only the fact named in Lane 1
- [x] Stop at consent, rate limit or CAPTCHA; never sign in

The browser lane accessed `pricing.vendor.com` with a read-only grant expiring in 24 hours. It extracted the exact prices for each plan and stopped immediately when a rate limit was encountered. No sign-in was attempted at any point.

## Evidence

Each lane writes its own evidence file; the campaign is done only when both are present and the gate record names who approved what.

The evidence files `inspect.json` and `browse.json` are both present. The gate record confirms that the operator approved the host `pricing.vendor.com` with a read-only capability and a 24-hour expiry.
