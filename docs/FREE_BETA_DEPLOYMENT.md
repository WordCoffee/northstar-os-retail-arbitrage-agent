# FREE PRIVATE-BETA DEPLOYMENT — OCI Always Free ($0 infrastructure)

Status: DEPLOY-F1 local preflight (2026-09-29). No Oracle account or cloud
resource has been created. Infrastructure spend target: **$0**. This document is
preparation only; DEPLOY-F2+ require owner action and explicit approval packets.

Authority: `docs/OPERATING_CONSTITUTION.md` wins. This track does not authorize
paid AI/data, provider calls, Amazon access, purchases, or any external side
effect.

## 1. Intended architecture

```
Internet
  -> approved stable free hostname (DuckDNS candidate)
  -> Caddy (public 80/443, auto-TLS)
  -> Docker private network
       |-- ui (built static, served by Caddy)
       |-- api      (FastAPI foundation, internal 8000)
       |-- worker   (durable jobs, no inbound)
       |-- scheduler(no inbound)
       |-- migrate  (one-shot, exit 0)
       |-- postgres (internal 5432 only)
```

Only Caddy exposes public ports. PostgreSQL (5432), FastAPI internal port (8000),
worker/scheduler interfaces, Docker socket/API, metrics/debug ports, and admin
dashboards are never publicly exposed.

## 2. Public and private ports

| Service | Public | Private |
|---|---|---|
| Caddy | 80, 443 | — |
| api | none | 8000 (compose network) |
| postgres | none | 5432 (compose network) |
| worker/scheduler | none | none |
| SSH (host) | owner-approved CIDR only | 22 |

## 3. Service dependencies

`postgres (healthy)` -> `migrate (exit 0)` -> `api`, `worker`, `scheduler`;
`api` -> `caddy`. `caddy` serves the SPA under `/ui/` and reverse-proxies `/api/*`
to `api`.

## 4. Migration ordering

Forward-only files in `Northstar_backend/migrations_foundation/` applied in
filename order by `foundation_migrate.py`; `schema_migrations` ledger records
filename + sha256; drift refuses. Current forward set: 001..010. The api startup
check fails closed in hosted environments if any forward migration is missing.

## 5. Persistent volumes

| Volume | Purpose |
|---|---|
| `postgres-data` | database data directory |
| `caddy-data` | certificates + ACME state |
| `caddy-config` | Caddy runtime config |

## 6. Secret names only (never values)

Provided via a dedicated **untracked** hosted env file (`deploy/hosted.env`,
names in `deploy/hosted.env.example`): `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `DB_URL`, `NORTHSTAR_JWT_SECRET`, `NORTHSTAR_JWT_ISSUER`,
`NORTHSTAR_JWT_AUDIENCE`, `DOMAIN`, `PUBLIC_BASE_URL`, `NORTHSTAR_JWT_ALGORITHMS`.

## 7. Local vs hosted configuration

| Dimension | Local dev | Hosted (free beta) |
|---|---|---|
| ENVIRONMENT | `development` | `staging` |
| Remote dev override | allowed locally | **never** (`NS_FOUNDATION_ALLOW_REMOTE_DEV=0`) |
| Owner Test Mode | allowed only in `development`/`test` | **disabled in staging** |
| JWT secret | shell-injected dev key | independently generated, file-based |
| Env file | malformed root `.env` (owner fixing) | `deploy/hosted.env` (untracked) |
| Cookies | http (not Secure) | HTTPS, Secure + HttpOnly + SameSite=strict |

`docker-compose.hosted.yml` overrides the base compose for hosted posture.

## 8. Required owner account actions (DEPLOY-F2)

Oracle signup, identity + card verification, password, MFA, recovery, legal
acceptance, home-region selection; DuckDNS login + exact hostname approval;
interactive owner-password bootstrap on the VM. The owner never pastes a
password/token in chat.

## 9. ARM64 compatibility evidence

Target: supported 64-bit ARM Linux (OCI Ampere A1, `linux/arm64`).

| Image | Arch support | Evidence |
|---|---|---|
| python:3.12-slim | multi-arch | official image; built `linux/arm64` (see images.lock) |
| node:20-alpine | multi-arch | official image; built `linux/arm64` |
| caddy:2-alpine | multi-arch | official image; built `linux/arm64` |
| postgres:15-alpine | multi-arch | official image; digest recorded |

Python deps: `psycopg[binary]`, `cryptography`, `bcrypt`, `croniter` — pure-wheel
or manylinux/aarch64 wheels on CPython 3.12. **Not yet run on a real ARM64
target**; local buildx emulation is an early signal only (see §10).

## 10. ARM build evidence + local emulation caveat

Built under Docker buildx + QEMU (emulated `linux/arm64`) as an EARLY SIGNAL:
- `ns-api-arm64:f1`  (Dockerfile.api) manifest-list sha256:9e290bd3e4fabfc4d3878567e9326f25b19dff9a81cb4b608be161bf5bcd091d
- `ns-ui-arm64:f1`   (Dockerfile.ui)  manifest-list sha256:1997722139c413157a8e34c02beb2521693a3b5ca91e419d922d39f10d9f732e
- arm64 import smoke (psycopg, cryptography, bcrypt, croniter, fastapi, foundation.api.state): **ok**

Local emulation is an EARLY SIGNAL ONLY. Final ARM acceptance requires running
migrations + app smoke on a real ARM64 VM (DEPLOY-F5/F6). Emulation is never the
hosted production runtime.

## 11. Proposed OCI resources (DEPLOY-F3 packet; create none yet)

One Always-Free-eligible ARM VM + minimum boot volume; one VCN; one public
subnet; one internet gateway; one route table; one application NSG; one verified
free-eligible public IP; Object Storage only if explicitly free-eligible and
needed for backups. No load balancer, NAT gateway, Kubernetes, Autonomous DB,
managed PostgreSQL, bastion, second VM, paid backup/reserved IP/logging, or any
trial-credit resource.

## 12. Free-tier verification procedure

For every resource: inspect in the owner's OCI console; confirm explicit Always
Free eligibility; confirm displayed estimated cost = $0; confirm no trial-credit
consumption; record non-secret evidence (shape/region/size); owner approval;
recheck immediately before creation. Any non-zero cost, unclear eligibility,
trial consumption, paid add-on, upgrade requirement, or ambiguous storage/backup
charge => `BLOCKED_COST_AMBIGUITY`. Billing alerts are monitoring only.

## 13. Deployment procedure (DEPLOY-F5)

Clean committed release -> checksummed bundle over SSH -> verify checksum ->
write `deploy/hosted.env` (root-owned, 0600) -> `docker compose -f
docker-compose.yml -f docker-compose.hosted.yml up -d` -> migrate exits 0 ->
health checks -> validate `/ui/*` and `/api/*` over HTTPS.

## 14. Rollback procedure

Distinguish: (a) application rollback (redeploy prior release image, only if the
migrated schema is backward-compatible), (b) configuration rollback (restore
prior compose/env), (c) database restore (from verified backup), (d) complete VM
reconstruction (new VM, reinstall, restore volumes). Never describe an
application rollback as safe if the DB is not backward-compatible.

## 15. Backup procedure

Nightly `pg_dump` -> client-side encrypt -> off-VM (approved free-eligible
destination) -> retention/pruning -> integrity verification. A copy on the VM
boot volume alone is NOT a backup. `deploy/backup.sh` (see §17).

## 16. Restore procedure

`deploy/restore.sh` restores a dump into a DISPOSABLE database and verifies row
counts/integrity. A restore drill MUST pass before real testers are invited.

## 17. Scripts

- `deploy/backup.sh` — dump + encrypt + upload (destination/creds via env names).
- `deploy/restore.sh` — restore a dump into a disposable DB and verify.

## 18. Complete-VM reconstruction procedure

New ARM VM -> OS hardening -> install Docker -> place `deploy/hosted.env` ->
pull release bundle (verify checksum) -> `up -d` (migrate applies) -> restore
latest verified database backup -> health + acceptance spot checks.

## 19. Room readiness

Not all rooms must be complete for private staging, but readiness is labeled
explicitly (WORKING / WORKING-WITH-LIMITS / BLOCKED) and never overstated.
Testers are not invited into rooms claimed to work when they do not.

## 20. Beta limitations

- Free capacity not guaranteed; OCI may reclaim/stop the VM (record event,
  measure recovery, report honestly; never auto-create a paid replacement).
- Object Storage backup is OFF-VM / SAME-ACCOUNT, not full disaster recovery.
- No public signup; manual owner-shared invite links only.
- Manual email fallback (DEPLOY-F8 blocked without approved sender domain).
- Brand provisional.

## 21. Known blockers

- DEPLOY-F2..F8 require owner action, capacity, hostname approval, and approvals.
- Root `.env` line 98 malformed (owner fixing); hosted path does not use it.
- Real ARM64 acceptance requires the VM (DEPLOY-F5/F6).
- No approved email sender domain (DEPLOY-F8 = BLOCKED_SENDER_CONFIGURATION).

## 22. Security headers (after HTTPS, DEPLOY-F4)

Add CSP, Referrer-Policy, X-Content-Type-Options, frame policy, Permissions-Policy
in a controlled card; test when added. HSTS only once hostname + HTTPS are
stable; no includeSubDomains unless safe; no preload without owner decision.
Token-bearing invitation URLs must not appear in logs/analytics/referrers/state.

## 23. Verification ledger (actually executed vs pending)

EXECUTED locally:
- Merged-config validation (`docker compose -f docker-compose.yml -f docker-compose.hosted.yml --env-file deploy/hosted.env.example config`).
- Port-exposure regression test `Northstar_backend/foundation/tests/test_hosted_compose.py`: only Caddy publishes 80/443; api/postgres/worker/scheduler/migrate publish nothing; no 5432/8000/2375/2376.
- Guardrail checks: hosted api ENVIRONMENT=staging, NS_FOUNDATION_ALLOW_REMOTE_DEV=0, NORTHSTAR_OWNER_TEST_MODE=0, NORTHSTAR_OWNER_SELF_APPROVAL=0.
- ARM64 **emulated** build of api + ui under QEMU + arm64 import smoke (early signal only).
- Prerequisite subset: 165 passed / 7 skipped / 0 failed.

NOT executed (do not claim):
- `deploy/backup.sh` and `deploy/restore.sh` (no restore drill has run).
- Any certificate issuance / HTTPS.
- Any OCI resource eligibility or provisioning.
- Real ARM64 runtime or migration run (requires the VM).
- Any hosted runtime behavior.

A backup script existing is NOT a passing restore drill. Free capacity is NOT
guaranteed. `P2-T5` hosted sign-in and `P2-T6` remain PARTIAL until hosted
acceptance passes on the real HTTPS hostname.