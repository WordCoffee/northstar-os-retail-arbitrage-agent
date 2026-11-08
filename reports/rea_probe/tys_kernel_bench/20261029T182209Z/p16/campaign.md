# Campaign: inspect first, browse second

Status: stub. No lane is authorised yet.

## Objective

Answer one question: which plans are published on the vendor's pricing page,
and what does each include.

## Lane 1 - inspect (local, no network)

- [ ] TODO: read the local fixtures and list what is already known
- [ ] TODO: name the single fact still missing
- [ ] Produce `inspect.json`

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator
approves the host and the expiry in writing. A gate is a stop, not a pause.

## Lane 2 - browser (read-only, per-host grant)

- [ ] TODO: one host, capability `read_only`, expiry at most 24 hours
- [ ] TODO: extract only the fact named in Lane 1
- [ ] Stop at consent, rate limit or CAPTCHA; never sign in

## Evidence

Each lane writes its own evidence file; the campaign is done only when both
are present and the gate record names who approved what.
