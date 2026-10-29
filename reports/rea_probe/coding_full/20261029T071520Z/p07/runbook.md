# Runbook: read the published pricing limits

Status: authorised for a single read-only pass.

## Intended task

Read the published plan limits from the public pricing page. Read-only: no
account, no cart, no form submission, no download.

## Host

pricing.example.com

## Grant

- capability: read_only
- expiry: 2025-06-15T12:00:00Z (within 24 hours of issue)

## Refusals

- Never sign in, never solve a CAPTCHA, never enter credentials.
- Stop and report at consent, rate limit, paywall or a CAPTCHA.
- Never submit a form; the grant covers reading only.
