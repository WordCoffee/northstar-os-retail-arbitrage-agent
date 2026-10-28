# Dev Login — LOCAL ONLY

## Purpose
Dev builds skip the sign-in page and route straight to `/home` using a demo
session (`userId demo-t2 / orgId org-t2 / role operator`). A banner reading
"DEV: AUTH DISABLED" is shown at the top of every page in dev mode.

## When it is active
Only when **all** of the following are true:
- `ENVIRONMENT=development`
- Backend bound to `127.0.0.1` (not `0.0.0.0`, not any LAN address)
- Vite `host=127.0.0.1` (port 8101)
- No Tailscale funnel or serve active
- No Cloudflare tunnel / ngrok / tailscale agent referencing ports 8000/8101

## When it is NOT active
- Production (`ENVIRONMENT=production` or `staging`)
- Any bind host other than `127.0.0.1`
- Any tunnel/funnel/serve exposure of ports 8000/8101
- Any non-development environment

## How to start
```
$env:ENVIRONMENT="development"
.\scripts\dev-start.ps1
```

The script runs `scripts\check_dev_safety.py` first. If any exposure
condition is detected, it exits with code 2 and does not start the servers.

## Safety gate
`scripts\check_dev_safety.py` inspects (read-only):
- `ENVIRONMENT` must equal `development`
- No listener bound non-loopback on ports 8000/8101
- Tailscale funnel / serve must not target dev ports
- No cloudflared/ngrok/tailscale agent referencing dev ports

Exit codes: `0` = safe, `2` = refused. Do not override.

## Banner
The "DEV: AUTH DISABLED" banner appears at the top of every dev page. It
is built-time gated via the `LOCAL_DEV` constant and is **not** shipped in
the production bundle (`npm run build` asserts the marker is absent).

## Route behavior in dev
- `/ui/sign-in` → redirects to `/ui/home` (no click, no credentials)
- `/ui/home` → opens directly with demo session
- `/me` → returns demo-t2 identity without password check

## What is NOT a real account
`demo-t2` / `org-t2` is a **demo identity only**. It exists only in dev
builds and only on loopback. It has no password, no real permissions outside
dev, and never appears in production.
