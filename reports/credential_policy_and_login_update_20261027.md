# Credential policy + local test login update — 2026-10-27

## Part 1 — Owner-controlled credential policy (replaced blanket prohibition)

Files edited (owner-controlled instructions/policy):
- AGENTS.md (capsule) — Guardrails bullet "Credential hygiene" replaced with
  "Credential hygiene — authorized operations" (full authorized-operations text).
- docs/OPERATING_CONSTITUTION.md — §3 first guardrail bullet replaced; §2 line
  "never touching credentials..." updated to allow owner-authorized credential
  operations; §2B line "Actual credential VALUES are never..." updated.

Restrictions originating OUTSIDE owner-controlled project files (NOT changed by
me, identified only):
- Harness/system-prompt capsule injection and Chrome Connect tool descriptions
  ("Never enter credentials, solve a CAPTCHA, or bypass a login") are
  platform/harness-level; not editable here. Chrome Connect host allowlist,
  Amazon blocklist, capability grants, budget caps, audit-hash chain remain
  operator-owned and untouched.

Chrome Connect permissions and other unrelated policies (SECRET_HANDLING.md
product secret handling, LOCAL_RUNBOOK.md gitignore reminder, etc.) were NOT
weakened.

## Part 2 — NorthstarOS local test/operator account update

Target account (resolved, not ambiguous):
- Store: Northstar_backend/data/foundation.db (local SQLite; DB_URL/FOUNDATION_DB_URL
  unset; production_denylist path check passed).
- Account: email/identifier "t2", user_id 1fa6d551-fd5b-4de6-997b-ed00bec694ae,
  role = operator, active = 1, org = "T2 Holdings LLC" (42b74646-...).
- Supported path used: seed_local_operator.py --rotate (reads password from
  NS_LOCAL_OPERATOR_PASSWORD env var; never CLI; never printed).
- Password hashing: bcrypt via foundation.credentials.hash_password (existing
  supported hasher). No plaintext password in code or tracked files.
- No login bypass, shared universal password, or startup reset routine introduced.

Exposure check (before applying):
- Tailscale: not connected (NoState); no serve/funnel config → no Tailscale
  remote exposure.
- Process ENVIRONMENT: unset → defaults to development (authn.environment()).
- Dev server: Vite binds 0.0.0.0:8101 (LAN-reachable) proxying to 127.0.0.1:8000;
  backend itself loopback-only.
- Account role: operator (not internal_platform_admin; lacks platform_admin,
  manage_org, purchase, write_external). Not an admin account.
- Org environment column defaults to "production" (model default).
- Owner confirmed applying the weak test credential despite LAN reachability.

## Part 3 — Verification

- Credential layer: verify_password(<requested test password>, stored_hash) == True  (account can sign in).
- Invalid password: verify_password(<incorrect test password>, stored_hash) == False.
- Protected route: GET /api/v1/foundation/me without session cookie → 401
  authentication_required (protected routes still require auth).
- No credential value printed, logged, or committed; password handled via env var
  and bcrypt hash only. Temp verification scripts containing the value were deleted.
- Note: foundation login endpoint currently returns 503 auth_unconfigured on the
  running backend because NORTHSTAR_JWT_SECRET is not set in this environment.
  This is a pre-existing environment condition, not caused by this change; the
  credential itself is valid and verifiable at the credential layer.
PY