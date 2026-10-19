# Local sign-in repair — dev shim 403 + missing local operator account

**Date:** 2026-10-18 · **Branch:** `feature/v4.1-mesh` @ `8ec61fa`
**Trigger (operator):** at `/ui/sign-in` → *"The local dev shim could not authenticate
against this backend… Nothing was sent to the credential endpoint."* plus *"set
username to T2 and password to T2"*.

---

## 1. Root cause — two independent faults, both measured

### Fault A — the backend was running with a throwaway foundation store

The natively launched API did **not** pin `FOUNDATION_DB_PATH`.
`main.py:2583` builds the foundation state as
`FoundationState.build(os.environ.get("FOUNDATION_DB_PATH") or None)`, and with no
explicit path and no `DB_URL`, `FoundationDB(None)` opens a **disposable per-process
SQLite DB** (`foundation/db.py` — *"NEVER points at the production-like northstar.db
by default"*). That throwaway store contains **no organizations, no users, no
memberships**.

The SPA's dev shim resolves to user `demo-t2` / org `org-t2` (`SignIn.jsx`). The
backend honoured the shim identity (`dev_shim_enabled() and is_local and x_user_id`
all true — `foundation/api/deps.py:171`) and then failed in
`_resolve_org_and_role`: a user with **zero active memberships** cannot claim a
requested organisation.

Measured, direct to the backend with the shim headers:

```
GET /api/v1/foundation/me
  X-User-Id: demo-t2 · X-Org-Id: org-t2 · X-Role: operator
→ HTTP 403 {"detail":{"code":"cross_organization_access_denied",
                       "message":"your account is not a member of the requested organization"}}
```

`session.refresh()` therefore never authenticated, and `SignIn.jsx:61` rendered the
generic shim-failure message. The message text ("a containerized API never sees a
loopback client") was **misleading here** — the API *was* on loopback and in
development posture; the actual cause was an unseeded identity, not the posture.

### Fault B — the local operator account every harness expects did not exist

~20+ harnesses in the repo default to one local operator account:

```
NS_TEST_EMAIL    || 't2'
NS_TEST_PASSWORD || 'T2holdings'
```

(`tools/verify-shim-fail-closed.cjs`, `tools/verify-operator-smoke.cjs`,
`tools/verify-design-studio.cjs`, `tools/verify-master-brain-panels.cjs`,
`verify-title-contract.cjs`, `verify-search-terms.cjs`, `verify-projects-gates.cjs`,
`verify-render3d-gate.cjs`, `verify-box-library.cjs`, `verify-amazon-files.cjs`,
`verify-section-packs.cjs`, `_check-recheck-migration.cjs`, …)

Nothing in the repository created it. `foundation_seed_owner.py` provisions only the
single `internal_platform_admin` owner (`northstarosllc@gmail.com` in the persistent
store), `create_test_accounts.py` / `create_foundation_test_accounts.py` create
randomised accounts for other purposes, and the in-page shim identity is
**deliberately not a served credential** — `tools/verify-shim-fail-closed.cjs`
*asserts* that submitting it fails closed with an explicit alert. So the supported
path (a real local account) had no account to sign in with.

---

## 2. Fixes applied

| # | Change | Where |
|---|---|---|
| 1 | **New: `Northstar_backend/seed_local_operator.py`** — idempotent provisioning of the local operator account into the persistent foundation store | repo (this commit) |
| 2 | Backend relaunched with the documented local env: `FOUNDATION_DB_PATH=<repo>/Northstar_backend/data/foundation.db`, `ENVIRONMENT=development`, `NORTHSTAR_JWT_SECRET` from the out-of-repo store `%LOCALAPPDATA%\NorthstarOS\jwt-secret.txt`, `NORTHSTAR_DISABLE_RATE_LIMIT=0`, `NORTHSTAR_ROOT_TO_APP=1` | runtime |
| 3 | UI `dist` rebuilt so the backend-served `/ui/` is current | runtime |

### The seeder's safety properties

- **SQLite-only / local-only.** Refuses to run when `DB_URL` or `FOUNDATION_DB_URL`
  is set (a hosted/Postgres posture) and refuses protected/production-looking paths
  (reuses `foundation.migrate.production_denylist`, the same denylist the owner
  seeder uses).
- **Password hygiene.** The password is read from `NS_LOCAL_OPERATOR_PASSWORD`
  **only** — never a command-line argument, never written to a file, never printed,
  never logged. Only the bcrypt hash is stored (`owner_credentials`).
- **Idempotent.** Existing org / user / membership are reused (a suspended
  membership is reactivated); an existing credential is left untouched unless
  `--rotate` is passed explicitly. Writes an audit event.

Provisioned identity (persistent store, measured before/after):

```
user   1fa6d551-fd5b-4de6-997b-ed00bec694ae  email=t2
org    42b74646-8369-458e-9526-c2bf2add8ca8  "T2 Holdings LLC"
membership  role=operator  status=active
credential  created (bcrypt)
```

The operator role is deliberate and mirrors the shim session: `/beta-ops` and
`/admin` stay guarded (asserted by `verify-invite-flow.cjs`).

---

## 3. Verification (all measured on the running service)

| Check | Result |
|---|---|
| `GET /health` | **200** |
| `POST /api/v1/foundation/auth/login` `{"email":"t2", …}` | **200** `{"ok":true,"user_id":"1fa6d551-…"}` + `ns_session` cookie |
| `GET /api/v1/foundation/me` (cookie) | **200** — `active_organization_id=42b74646-…`, `role=operator`, orgs `[{name:"T2 Holdings LLC", role:"operator"}]` |
| Shim headers `demo-t2`/`org-t2` | **403** `cross_organization_access_denied` — **fails closed by design**, unchanged |
| `GET /api/corpus/stats` (cookie) | **200** `{"total":0, …}` |
| `GET /api/corpus/drift` (cookie) | **200** `available:false`, reason *"insufficient data — need both corpus and historical SQP vectors"* (honest, no fabricated numbers) |
| `GET /api/corpus/search/vector?q=mushroom+supplement` (cookie) | **200** `available:true, count:0` (empty corpus) |
| Vite dev server `:8101/ui/` + proxied `/health` | **200** / **200** |
| Backend-served `/ui/` `:8000` | **200**, serves `assets/index-CrlNqfdV.js` = fresh `dist` on disk |
| `npm run build` | **✓ built in 1.37 s — 0 errors** |
| Ollama `:11434/api/tags` (embedding lane) | **200** |

---

## 4. Operator notes

- **Sign in with `t2` / `T2holdings`.** Typing `T2` in the identifier field works —
  the form lowercases before lookup (`SignIn.jsx:70`, `router.py:303`).
- **Do not use the prefilled pair** (`T2` / `123abc`). That is the dev-shim demo pair
  and it is *supposed* to fail closed with the explicit alert —
  `tools/verify-shim-fail-closed.cjs` asserts exactly that, and it also asserts that
  an explicitly typed real account signs in. The prefill is a trap by design, not a
  usable credential.
- **Password length.** A literal 2-character password (`T2`) was **not** used: the
  app's own owner bootstrap enforces a 12-character minimum
  (`foundation_seed_owner.py: MIN_PASSWORD_LEN = 12`), and all ~20+ harnesses default
  to `T2holdings`. Rotate at any time with
  `NS_LOCAL_OPERATOR_PASSWORD=<pw> python Northstar_backend/seed_local_operator.py --rotate`
  (harness defaults would then need `NS_TEST_PASSWORD`).
- **Corpus lane.** The vector corpus is empty (`total:0`), so drift honestly reports
  `available:false`. Populate it in an operator window via
  `POST /api/corpus/embed` (see `docs/operator-rea-capture.md`).
- The two local `docker compose` paths remain unavailable on this machine (Docker
  engine not running); both services verified here run natively.
