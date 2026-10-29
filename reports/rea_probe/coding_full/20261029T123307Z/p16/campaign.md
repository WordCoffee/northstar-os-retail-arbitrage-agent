# Campaign: inspect first, browse second

Status: planned. Lane 1 is scoped; Lane 2 is scoped and gated.

## Objective

Answer one question: which plans are published on the vendor's pricing page,
and what does each include.

## Lane 1 - inspect (local, no network)

Scope: local fixtures only; no network access.

- [ ] Read the local fixtures and list what is already known
- [ ] Name the single fact still missing
- [ ] Produce `inspect.json`

## Gate 1 - human review

The run stops here and waits. Lane 2 does not begin until the operator
approves the host and the expiry in writing. A gate is a stop, not a pause.

Gate record:
- Approver: <operator name>
- Approved host: <host>
- Approved expiry: <timestamp, at most 24 hours from approval>
- Approved scope: read-only, single host

## Lane 2 - browser (read-only, per-host grant)

Scope: one host, capability `read_only`, expiry at most 24 hours.

- [ ] Use the approved host and expiry from Gate 1
- [ ] Extract only the fact named in Lane 1
- [ ] Stop at consent, rate limit or CAPTCHA; never sign in

## Evidence

Each lane writes its own evidence file; the campaign is done only when both
are present and the gate record names who approved what.

- Lane 1 evidence: `inspect.json`
- Lane 2 evidence: `browser.json`
