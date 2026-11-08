# Runbook: read the published pricing limits

Status: authorised for a single read-only pass.

## Intended task

Read the published plan limits from the public pricing page. Read-only: no
account, no cart, no form submission, no download.

## Host

The single host this run may touch is `pricing.example.com`, as listed in `hosts.txt`.

## Grant

The capability granted for this run is `read_only`, and the expiry is set to 2025-01-01T12:00:00Z, which is at most 24 hours out.

## Refusals

- Never sign in, never solve a CAPTCHA, never enter credentials.
- Stop and report at consent, rate limit, paywall or a CAPTCHA.
- Never submit a form; the grant covers reading only.
