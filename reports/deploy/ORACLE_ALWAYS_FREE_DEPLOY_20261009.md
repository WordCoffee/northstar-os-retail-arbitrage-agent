# Northstar OS — Oracle Always Free deploy package

**Prepared:** 2026-10-09 · **Branch:** `feature/overnight-remediation-20261009`
**Shape:** ONE service (A2 default applied). The API serves the built SPA at
`/ui/`, the AutothinK workspace at `/autothink/`, and every `/api/*` route from
`main:app`.

---

## 1. What changed (why this is now deployable)

| Audit finding | Status |
|---|---|
| **P0-01** a plain GET made 19 live Bright Data connections | **CLOSED.** `SCANNER_LIVE_ALLOWED=0` and `live_gate.assert_live_posture()` refuses to boot an unbounded live mode. |
| **P0-02** hosted-reasoning UI 404'd | **CLOSED.** UI calls `/api/v1/reasoning/*`; the legacy spelling is aliased. 19/19 UI routes resolve in the container. |
| **P0-03** hosted served a smaller API than local | **CLOSED.** `Dockerfile.api` runs `uvicorn main:app` and builds the SPA in-image. |
| **P0-04** `/api/autothink/*` was public | **CLOSED.** Strict `require_session`; tenant-scoped history/usage/cancel. Verified 401. |
| **P0-05** concurrent writers | **REPORTED as UNATTRIBUTED, not killed.** See evidence file. |

## 2. Build and run

```bash
# Build the single-service image (builds the SPA inside it).
docker build -f Dockerfile.api -t northstar-api:latest .

# Run it. No secret is baked in; all config comes from the environment.
docker run -d --name northstar \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e NORTHSTAR_JWT_SECRET="<a persistent random 64-char secret>" \
  -e SCANNER_LIVE_ALLOWED=0 \
  northstar-api:latest
```

**Required for hosted mode:**

| Variable | Why |
|---|---|
| `NORTHSTAR_JWT_SECRET` | **Required in staging/production.** `auth.assert_jwt_secret_posture()` refuses to boot an ephemeral secret, because it would invalidate every session on restart. |
| `SCANNER_LIVE_ALLOWED` | Must be `0` (the default in compose). A live provider lane exists only for one operator-armed run. |
| `NS_LIVE_PER_RUN_ARMED` / `NS_LIVE_PER_RUN_CAP_CENTS` | Only set together with `SCANNER_LIVE_ALLOWED=1`, for one bounded run. |
| `NORTHSTAR_ALLOW_SQLITE_FALLBACK` | Set `1` only if you deliberately want SQLite when a Postgres URL is configured but unreachable. Otherwise the app refuses to boot rather than silently degrade. |

## 3. Single-service shape for Always Free

The Oracle Always Free tier (A1.Flex, 1 OCPU / 6 GB) runs one compute
instance. The whole stack is therefore one container:

```
caddy (optional, TLS only)  ->  northstar-api  (main:app)
                                   ├── /api/*      every route
                                   ├── /ui/*       the SPA (built in-image)
                                   └── /autothink* the AutothinK workspace
```

`docker-compose.yml` keeps `worker`, `scheduler` and `postgres` as separate
services for a larger host. On Always Free, run the API alone (SQLite) and add
the worker later:

```bash
docker compose -f docker-compose.yml up -d api caddy   # full shape
docker run ... northstar-api:latest                    # Always-Free shape
```

## 4. Health and readiness

| Probe | Path | Used by |
|---|---|---|
| API liveness | `GET /health` | Docker `HEALTHCHECK` |
| API detail | `GET /health/detailed` | carries `live_posture_ok`, `live_posture_problems`, `adapter_load_failures` |
| Worker readiness | `GET :8090/healthz` / `/readyz` / `/status` | compose healthcheck |
| Scheduler readiness | `GET :8091/healthz` / `/readyz` / `/status` | compose healthcheck |

## 5. Verify after deploy

```powershell
# 1. The live gate is disarmed.
python tools\live_test_runner.py --disarm

# 2. Every UI-called route resolves through the container.
powershell -ExecutionPolicy Bypass -File tools\verify-hosted-container.ps1

# 3. The route contract (static, no server needed).
cd Northstar_backend && python -m pytest test_ui_route_contract.py test_env_parseability.py -q
```

## 6. What is NOT ready for production

These are open and must not be presented as done:

1. **Postgres is unproven.** The Postgres branch was dead code that silently
   served SQLite. It now fails loudly instead, which is safe — but no hosted
   Postgres run has been performed. Run a migration + connection test on the
   real host before going live.
2. **Invite email is still a stub.** `invites.send_invite_email` logs a line;
   no provider is connected. The 50-tester invite flow works mechanically but
   nobody receives an email until that is wired.
3. **Media generation is unarmed.** `creative/readiness` reports
   `armed: false` and the studio never sends an image/video request. Video stays
   disabled.
4. **Backups and scheduled jobs** are verified only at the code level here
   (`test_backup_restore_drill.py`, scheduler tests), not against the live host.
5. **No real hosted Postgres cost/run data exists**, so no claim about hosted
   throughput or unit cost is made.
