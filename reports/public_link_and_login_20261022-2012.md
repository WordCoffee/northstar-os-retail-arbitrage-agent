# Public link + T2 login (2026-10-22 20:12)

## Live public URL
**https://insurance-amendment-responsibility-devel.trycloudflare.com**

- Root `/` 307s into the workspace (`NORTHSTAR_ROOT_TO_APP=1`), so the phone-friendly entry is
  `https://insurance-amendment-responsibility-devel.trycloudflare.com/ui/`
- Sign-in: `https://insurance-amendment-responsibility-devel.trycloudflare.com/ui/sign-in`
- Quick tunnel (ephemeral): the hostname changes on every `cloudflared` restart. The launcher
  prints the new one; the log is `%TEMP%\northstar-tunnel.log`.

## Login
- Identifier: **t2** (existing local operator, org *T2 Holdings LLC*, role `operator`)
- Password: set to the operator-directed value through the app's own bootstrap
  (`seed_local_operator.py --email t2 --rotate`, `NS_LOCAL_OPERATOR_PASSWORD` read from the
  process env only). The value is deliberately **not recorded** in this report, any file, or the
  audit metadata; only the bcrypt hash exists in `data/foundation.db`.

## How it was brought up
```
powershell -ExecutionPolicy Bypass -File scripts\launch_alpha.ps1 -Restart -NoComfy -NoAutothink -Email t2
```
- Stopped the bare backend on :8000, restarted it through the launcher so it inherits the full
  environment (signing key from the out-of-repo store, `FOUNDATION_DB_PATH`, `MEDIA_GEN_LIVE`,
  `NORTHSTAR_ROOT_TO_APP`).
- ComfyUI skipped (`-NoComfy`) because it is already live on :8188 with `--cache-none`; AutothinK
  skipped (`-NoAutothink`) because :8100 was not part of the running tier before this session.
- Gate off (`no -Gate`), matching the pre-session posture: `GET /api/v1/models` answered 200
  unauthenticated before the restart, so the private-alpha allowlist was not armed.

## Verified through the public URL
| Check | Result |
|-------|--------|
| `GET /health` | 200 `{"status":"ok",...}` |
| `GET /` | 307 → workspace |
| `GET /ui/` | 200 (1,090 B shell) |
| `GET /ui/sign-in` | 200 |
| `POST /api/v1/foundation/auth/login` `{email:"t2",password:"…"}` | **200** `{"ok":true,"user_id":"1fa6d551-…"}` |
| `GET /api/v1/foundation/me` (session cookie) | 200 — user `1fa6d551-…`, role `operator`, org `42b74646-…`, 1 org, 10 permissions |
| `GET /api/v1/models` (authenticated) | 200 (4,571 B) |
| `GET /api/ops/status` (authenticated) | 200 (1,264 B) |
| `GET /api/v1/provider-suite` | 200 (21,140 B) |
| `GET /api/v1/foundation/auth/session` | 404 — wrong path (the endpoint is `/auth/me` → `/api/v1/foundation/me`); not a defect |
| cloudflared | PID 16824 alive |
| Ollama :11434 / ComfyUI :8188 | up (4 models; ComfyUI 14.6 GB VRAM free) |

## Finding fixed on the way
The 20:00 restart had brought the backend up as a **bare** `python -m uvicorn` process, which does
not inherit the launcher's environment. `NORTHSTAR_JWT_SECRET` therefore resolved to empty and
`POST /api/v1/foundation/auth/login` failed closed with **503 auth_unconfigured** — the hosted login
was dead even though `/health` was green. This is exactly why `launch_alpha.ps1` exists: it loads the
signing key from `%LOCALAPPDATA%\NorthstarOS\jwt-secret.txt` (owner-only ACL, never printed) before
starting uvicorn. Restarting through the launcher restored login; both facts are recorded in
`00_STATE.json` (`bare_uvicorn_restart_drops_launcher_env_20261022`).

## Also committed
`86da261` — `scripts/launch_alpha.ps1` still exported `COMFYUI_URL=http://127.0.0.1:8199` and
started ComfyUI on 8199 without `--cache-none`. That contradicted the resolved 8188 alignment and
re-armed the RAM ceiling that kills the edit lane. Now: `8188`, detected on 8188, started with
`--cache-none`.

## Exposure note
A quick tunnel has **no access control** — the URL is the only secret. That is the documented
"option A, solo test week" posture (`docs/PRIVATE_ALPHA_DEPLOY.md`). For anything beyond a solo
test, run with `-Gate` (in-app allowlist) or use a named tunnel + Cloudflare Access.
