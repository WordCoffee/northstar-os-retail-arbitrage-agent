# Local sign-in — round 2: the concurrency race that was the real blocker

**Date:** 2026-10-18 · **Branch:** `feature/v4.1-mesh`
**Trigger (operator):** sign-in still failed after the round-1 repair ("error when
using username T2 and password …").

Round 1 (`reports/local_signin_repair_20261018.md`) fixed the *empty* foundation
store (unpinned `FOUNDATION_DB_PATH`) and provisioned the missing local operator
account. That was necessary but **not sufficient** — the live log showed the
operator's real login attempts still failing. This report covers the three
remaining causes, all measured.

---

## 1. The real blocker — a concurrency race in the foundation data layer

`foundation/db.py` opened **one** `sqlite3` connection for the whole process:

```python
self.conn = sqlite3.connect(path, check_same_thread=False)
```

FastAPI runs synchronous endpoints in a worker threadpool (`anyio.to_thread`), so
the SPA's parallel context calls (`/me` + `/environment` + `/preview/active`) hit
that one connection from several threads at once. Two distinct failures follow:

| Failure | Mechanism | Observed |
|---|---|---|
| **HTTP 500** | CPython's sqlite3 keeps a *per-connection* statement cache; concurrent statement creation corrupts it | `sqlite3.InterfaceError: bad parameter or other API misuse` at `foundation/db.py:691 in get`, reached via `deps.py:187 _block_blocking_lifecycle → repositories.py:370` |
| **Silent empty reads** | a concurrent `commit()` **resets** any cursor that is mid-read on the same connection, so a committed row can vanish from a SELECT | reproduced in a synthetic test: `db.list(...)` returned `[]` for a committed row |

The second one is the nastier: an empty `memberships` read looks exactly like
"not a member" — flaky, message-less sign-in failures. The operator's log recorded
**16× 403** (shim path) and **7× 429** before the process was restarted, and the
500 was captured verbatim.

### Fix (`Northstar_backend/foundation/db.py`)

1. **`_SerializedConnection`** — a facade over the single connection that takes one
   re-entrant lock for every statement (`execute`, `executemany`, `executescript`,
   `cursor`, `commit`, `rollback`, `close`). This covers *every* caller, including
   the ~198 direct `db.conn.execute(...)` call sites outside this module.
2. **`@_serialized`** on all 13 `FoundationDB` operations — a whole operation
   (execute + fetch + commit) is atomic, so no cursor can be reset mid-read.
3. **`atomic_claim_job`** additionally holds `FoundationDB.lock` across its
   `BEGIN IMMEDIATE … COMMIT`, since `BEGIN` is connection-scoped: an interleaved
   thread would otherwise join (and commit) that transaction.

Nesting is expected and safe (RLock): `upsert → get/insert`,
`table_counts → count`, and any caller holding `db.lock` explicitly.

### Evidence

| Check | Before | After |
|---|---|---|
| `test_db_concurrency.py` (8 threads × 200 read/write iterations; 4 threads racing one atomic claim) | failed — `TypeError`/empty reads | **2 passed** |
| Live probe: 60 concurrent foundation calls (`/me`, `/environment`, `/preview/active`) with a cookie | 500 / 403 mix | **60 × HTTP 200** |
| Foundation suite `Northstar_backend/foundation/tests` | — | **761 passed, 1 failed, 59 skipped** |
| Browser journey (`verify-stale-shim-signin.cjs`) | `/me` → 500, bounced to sign-in | **8 passed / 0 failed** |
| V3 gate `tools/verify-shim-fail-closed.cjs` | — | **8 passed / 0 failed** |

The single foundation-suite failure is **pre-existing and unrelated**:
`test_frontend_gate.py::test_v3_shell_invariants` asserts *48* routes in
`App.jsx` while the file has 52 — a file this work never touched.

---

## 2. A stale dev-shim identity silently poisoned real sessions

Any shim attempt calls `session.updateDev(...)`, which **persists**
`ns-dev-session` in localStorage. `foundation/api.js` then attaches
`X-User-Id` / `X-Org-Id` to **every** foundation request, and
`foundation/api/deps.py` resolves

```python
org_id, role, is_platform_admin = _resolve_org_and_role(
    state, user_id, requested_org=(x_org_id or org_claim))
```

So even with a valid session cookie (which does take precedence for *identity*),
the request kept asking for the demo organization `org-t2` — which is not one of
the real account's memberships — and failed closed with
`403 cross_organization_access_denied`. The SPA's `refresh()` failed, and
`SignIn.jsx` navigated to `/home` regardless, so `RouteGuard` bounced the operator
straight back to `/sign-in` **with no message at all**.

### Fix (`northstar-os-ui/src/pages/public/SignIn.jsx`)

The real-credential path now clears the persisted dev identity first
(`setDevSession({ userId: '', orgId: '', … })`, the same call `signOut` already
used), so the cookie is the sole identity after a real login.

New harness `northstar-os-ui/verify-stale-shim-signin.cjs` reproduces the
operator's exact state end to end: prefilled demo pair fails closed → the demo
identity is confirmed *persisted* → typing a real account signs in anyway → the
session survives a reload. **8 passed / 0 failed.**

This also keeps the shim contract intact: `tools/verify-shim-fail-closed.cjs`
still passes 8/0 (the demo pair must never authenticate, and it never reaches the
credential endpoint).

---

## 3. The password + the misleading message

- **Password:** the operator asked twice for the password to be `T2`, and was
  demonstrably typing it (two browser logins returned `401`). The local operator
  account `t2` is now rotated to the literal **`T2`** via
  `Northstar_backend/seed_local_operator.py --rotate`. The seeder now prints a
  **non-blocking** warning when a password is below the 12-character floor the
  owner bootstrap enforces, so the deviation is always visible in the output.
- **Message:** the shim alert claimed the API might be containerized, which was
  misleading here (the API *was* on loopback in development posture). It now names
  the actual cause and tells the operator to type a real account, while keeping
  the two phrases the V3 gate asserts (`could not authenticate`,
  `Nothing was sent to the credential endpoint`).

---

## 4. Rate limiting (local testing session)

The live log showed the edge limiter returning **429** on the SPA's *own* polling
endpoints (`/me`, `/environment`, `/preview/active`, `/v1/models`), which turns a
busy page load into spurious failures. The backend for this local testing session
therefore runs with `NORTHSTAR_DISABLE_RATE_LIMIT=1`. Restore the strict posture
with `=0`; the documented launchers (`tools/start-local.ps1`,
`scripts/launch_alpha.ps1`) set their own value and are unaffected.

---

## 5. Operator summary

- **Sign in with `t2` / `T2`** at <http://127.0.0.1:8101/ui/sign-in>.
- Ignore the prefilled pair (`T2` / `123abc`) — that is the demo/shim identity and
  it is *supposed* to fail closed (the V3 gate asserts it).
- Everything else verified this round: 60/60 concurrent API calls 200, foundation
  suite 761/1 (pre-existing), `npm run build` 0 errors.

## 6. Residual (surfaced, not hidden)

Direct `db.conn.execute(...)` callers *outside* `FoundationDB` (e.g.
`jobs_durable.py`, `demo_dataset.py`, `billing/service.py`, `jobs_scheduler.py`)
now get **statement-level** serialization (no statement-cache corruption), but not
whole-operation atomicity — a long `execute → fetchall` there could still be reset
by a concurrent commit. The entire foundation **request** path goes through
`FoundationDB` and is fully atomic. Extending the `@_serialized` treatment to
those modules is available on request.
