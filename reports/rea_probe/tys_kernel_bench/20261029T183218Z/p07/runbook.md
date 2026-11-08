# Runbook: read the published pricing limits

Status: authorised for a single read-only pass against the public pricing page.

## Host

The only host this run may touch is `pricing.example.com`, which is the single host named in `hosts.txt` for this task.

## Grant

The grant is `read_only` and expires at `2025-06-15T12:00:00Z`, which is at most 24 hours from the time of authoring.

## Refusals

- Never sign in, never solve a CAPTCHA, never enter credentials.
- Stop and report at consent, rate limit, paywall or a CAPTCHA.
- Never submit a form; the grant covers reading only.
