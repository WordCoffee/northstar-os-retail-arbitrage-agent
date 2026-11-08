# Runbook: read the published pricing limits

Status: authorised for a single read-only pass.

## Intended task

Read the published plan limits from the public pricing page. Read-only: no
account, no cart, no form submission, no download.

## Host

The single host this run may touch is `pricing.example.com`, as listed in
`hosts.txt`. No other host is in scope for this runbook.

## Grant

The capability granted is `read_only`, and the grant expires at
2025-01-01T12:00:00Z, which is at most 24 hours out from the time of
authorisation. The grant covers reading only and does not permit any
write, submit, or sign-in action.

## Refusals

- Never sign in, never solve a CAPTCHA, never enter credentials.
- Stop and report at consent, rate limit, paywall or a CAPTCHA.
- Never submit a form; the grant covers reading only.
