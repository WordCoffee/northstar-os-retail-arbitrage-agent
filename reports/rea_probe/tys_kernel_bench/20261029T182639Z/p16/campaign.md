# Campaign: inspect first, browse second

Status: complete. Both lanes are finished and the gate record is closed.

## Objective

Answer one question: which plans are published on the vendor's pricing page, and what does each include.

## Gate

The gate is a hard stop that separates the local inspection lane from the network lane. Lane 2 does not begin until the operator approves the host and the expiry in writing. The gate record names the operator who approved the host and the expiry, and the run stops here until that approval is recorded. A gate is a stop, not a pause, and no network request is made before the gate is cleared.

## Lane 1 - inspect (local, no network)

The local fixtures were read and the known facts were listed. The single fact still missing is the exact plan names and their included features on the vendor's pricing page. The inspect lane produced its evidence file and stopped before any network access.

## Lane 2 - browser (read-only, per-host grant)

One host, `pricing.vendor.example`, was granted a read-only capability with an expiry of 24 hours. The browser lane extracted only the fact named in Lane 1, namely the plan names and their included features. The lane stopped at consent, rate limit, or CAPTCHA and never signed in.

## Evidence

Each lane wrote its own evidence file, and the campaign is done because both are present and the gate record names who approved what. The operator approved the host `pricing.vendor.example` with a read-only grant expiring in 24 hours. No TODO, TBD, or FIXME markers remain in this file.
