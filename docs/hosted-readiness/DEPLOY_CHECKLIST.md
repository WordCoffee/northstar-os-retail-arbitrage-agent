# Deploy checklist (private beta, free tier)

Order matters: posture first, then secrets, then the compose overlay, then
verification. Every step names its verification command. Nothing here contacts
a paid provider or arms generation.

## 0. Preconditions

- [ ] `deploy/hosted.env` exists on the VM, **untracked**, `chmod 600`,
  root-owned, filled from `deploy/hosted.env.example` (names only in the
  example). `git status` shows it as ignored, never staged.
- [ ] `deploy/images.lock` pins the image digests the deploy is built from.

## 1. Posture

- [ ] `ENVIRONMENT=staging` (in `deploy/hosted.env`).
- [ ] `NORTHSTAR_OWNER_TEST_MODE=0` and `NORTHSTAR_OWNER_SELF_APPROVAL=0`.
- [ ] `NORTHSTAR_DISABLE_RATE_LIMIT=0` (the hosted overlay pins this itself —
  a "1" anywhere is a failed deploy).
- [ ] `NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS=0` (refused outright in
  staging/production by the login throttle).

Verify: `node tools/check-compose-deploy.cjs` — the deploy composition publishes
no port besides 80/443, no opt-out is set to 1, the rate-limit pin is present.

## 2. Secrets

- [ ] `NORTHSTAR_JWT_SECRET` generated on the VM (≥32 random bytes), never
  reused from dev, never committed.
- [ ] `NORTHSTAR_JWT_ISSUER`, `NORTHSTAR_JWT_AUDIENCE`, `NORTHSTAR_JWT_ALGORITHMS`
  set to the canonical values for the domain (see `SECRET_HANDLING.md`).
- [ ] `DOMAIN` and `PUBLIC_BASE_URL` set to the real hostname. Security links
  are built from these, **never** from request headers.
- [ ] No generation arming flag (`CLOUD_MODEL_LIVE`, media arming) is set.

## 3. Compose

- [ ] Deploy with the overlay: `docker compose -f docker-compose.yml -f docker-compose.hosted.yml up -d --build`.
- [ ] The API container is healthy; Postgres healthy; Caddy serving.
- [ ] The API port is **not** published: `docker compose ... ps` shows no host
  mapping for the api service.

## 4. Verification after boot

- [ ] `GET /readyz` through the proxy returns ready.
- [ ] `GET /api/design-studio/generation-status` returns `media_live_armed:
  false` (or the state is reported UNARMED with its reason).
- [ ] A fresh sign-in with a real account works; the dev shim does not
  authenticate.
- [ ] `node tools/check-no-third-party.cjs` passes against the built UI (no
  external font/CDN request).
- [ ] Anonymous requests to a tenant-scoped studio route are refused 401
  (`tools/verify-d10-live.cjs` covers this pattern; run it against the deployed
  base URL with the harness account).

## 5. Backups

- [ ] `deploy/backup.sh` configured (destination approved, key file in place)
  and one backup taken; a restore drill into a disposable database passes
  (`deploy/restore.sh`). See `BACKUP_RESTORE.md`.

## 6. Rollback

- [ ] Previous image digests are still on the VM (`deploy/images.lock` records
  the current ones; keep the prior lock file).
- [ ] `docker compose ... down` + re-`up` with the previous lock restores the
  previous build; the database schema is additive, so a rollback does not need
  a data migration in the beta window.

## What this checklist deliberately does NOT do

- It does not arm any generation provider.
- It does not enable any Amazon integration: there is no Amazon sign-in, no
  SP-API, no Ads API, no OAuth, no credentials anywhere in the product.
- It does not publish any port besides the proxy.
