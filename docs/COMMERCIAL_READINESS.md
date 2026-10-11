# Commercial Readiness (Phase 7) — built vs owner-only

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **0 new / 0 known-active (baseline empty) / 231 allowlisted.**
- This document maps the Phase 7 checklist to (a) controls that already exist
  in the foundation, (b) controls built in this workstream, (c) proposals for
  the build, and (d) items only the owner can do. Nothing here is claimed
  built unless marked BUILT.

## 1. AuthN / AuthZ

| Item | Status |
|---|---|
| Invite-only accounts | EXISTING (foundation invites + acceptance flow) |
| Short-lived sessions | EXISTING (JWT access tokens w/ expiry/revocation + HttpOnly session cookie); proposal below tightens lifetimes for beta |
| RBAC (admin/customer) | EXISTING (permission matrix; roles resolved from DB memberships) |
| MFA | PROPOSED (TOTP; owner decision — needs an operator workflow + recovery codes design) |
| Per-tenant API keys, hashed at rest | PROPOSED (design): key format `ns_<tenant>_<32B random>`; store only `sha256(pepper + key)` + lookup prefix + created/last-used/revoked-at; never log the full key; rotation + revocation endpoints; display-once at creation. Implementation = owner OK (adds key lifecycle) |

## 2. Transport & storage

| Item | Status |
|---|---|
| TLS everywhere | EXISTING for hosted posture (Caddy 80/443 in `docker-compose.hosted.yml`); local dev is HTTP by design |
| Encryption at rest | PROPOSED plan: hosted = PG/volume disk encryption at the provider layer + secret store via `NORTHSTAR_ENV_FILE` (loader reads only through the variable); key material stays operator-owned. Keychain backend remains a plug-in slot |
| Backups tested for restore | EVIDENCE: local SQLite drill re-run today — `test_backup_restore_drill.py` **2 passed** (round-trip parity + integrity_check + disposable-name guard); Postgres `deploy/backup.sh`/`restore.sh` execution remains DEPLOY-track (blocked on hosting) |
| Key rotation plan | PROPOSED: provider/env-file keys rotated by the owner (already exercised 2026-10-11); per-tenant API keys rotate via revoke + reissue |

## 3. API protection

| Item | Status |
|---|---|
| Input validation | PARTIAL/EXISTING (pydantic models; store + policy validators added in this build) |
| Rate limiting | EXISTING (foundation/legacy middleware) + per-domain limits in the policy kernel |
| CORS locked down | EXISTING (`CORS_ORIGINS` config; same-origin default) |
| CSRF protection | EXISTING (double-submit cookie for session auth) |
| Security headers | EXISTING (foundation app middleware; legacy `security.py`) |
| Request size caps | PARTIAL: gateway enforces response-size caps + per-run byte budgets; a global request-body cap for the legacy API surface is PROPOSED (not wired) |

## 4. Privacy

| Item | Status |
|---|---|
| Data inventory | `docs/COMMERCIAL_READINESS.md` §4a below |
| Retention + deletion path | PROPOSED: per-tenant delete routine across foundation tables + snapshot store (tenant-filtered deletes); retention defaults = operator decision |
| No customer data to model providers | BY DESIGN: default model lane is LOCAL (Ollama); cloud lanes are gated (`CLOUD_MODEL_LIVE` + `OPENROUTER_API_KEY`) with explicit consent flags; provider identity stays internal |
| Redacted security alerts | EXISTING (observability `redact()` + audit scrub) + policy kernel audit chain |

### 4a. Data-flow inventory (what leaves the machine, if anything)

| Data | Where it lives | Leaves the machine? |
|---|---|---|
| Credentials (provider keys, JWT secret) | operator env file (path via `NORTHSTAR_ENV_FILE`; never in code/reports) | No (used only by their client at call time) |
| Snapshot store rows (web snapshots) | local SQLite (`northstar/store`, tenant-filtered) | No |
| Gateway fetch targets | approved hosts only (policy kernel allowlist) | The URL request itself goes to the target host (its robots/ToS honored); nothing else is sent |
| Foundation customer data (beta) | local SQLite / hosted PG | No — model lanes for customer surfaces are local by default; cloud model calls (if ever enabled by the operator) are gated + consent-recorded |
| Audit log (hash-chained) | local (gateway + brain) | No |

## 5. Supply chain / CI

| Item | Status |
|---|---|
| Lockfiles with hashes | BUILT: `Northstar_backend/uv.lock` (committed; hashes) — **Docker path switched to `uv export` (build-verify PENDING — needs one approved `docker build` run)** |
| pip-audit / npm audit in CI | BUILT: `security.yml` audit job (advisory first cycle; flip to blocking after triage) |
| SBOM in CI | BUILT: SPDX artifact via `anchore/sbom-action` |
| Secret scanning | BUILT: offline scanner (fingerprint-exact gate; 0/0/231) + gitleaks (pinned, advisory job) |
| Actions hardening | BUILT: SHA-pinned actions, least privilege, timeouts, concurrency |

## 6. Compliance prep

| Item | Status |
|---|---|
| AGPL obligations (Lightpanda) | RUNS UNMODIFIED as a separate process over the network (loopback); no linking, no forking, no bundled source obligation triggered by mere use. Formal legal review = OWNER |
| Scraping ToS / Acceptable Use | BUILT controls: robots enforced (gateway + kernel), source allowlist default-deny, no stealth/evasion, Amazon hard-block; terms review per source = OWNER (required before widening the Phase 3b list) |
| Incident response runbook | PROPOSED outline (detect → contain via kill switch → preserve audit chain → report); owner sign-off needed |
| Vulnerability disclosure contact | OWNER (publish address/process) |
| Privacy policy | OWNER |

## 7. Owner-only checklist (do not fake)

1. Independent penetration test (before public beta) — scope + vendor selection.
2. Legal review: AGPL use + scraping terms + privacy policy.
3. Incident-response runbook sign-off.
4. Vulnerability-disclosure contact/process.
5. MFA decision + recovery design.
6. Approval to implement per-tenant API keys (hashing, rotation, display-once).
7. One approved `docker build` run to build-verify the uv.lock Docker path.
