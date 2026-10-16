# NorthstarOS runbook (2026-10-16)

One page. Everything below is local-first; nothing contacts Amazon.

## Start / stop / restart

```
# Normal start (reads the JWT secret from %LOCALAPPDATA%\NorthstarOS, never printed)
powershell -File tools/start-local.ps1

# Stop everything
docker compose down

# Restart one service after a code change (ALWAYS rebuild — a stale image
# previously shipped missing endpoints)
docker compose up -d --build api caddy
```

URLs: **http://localhost/ui/** (the app) · **http://127.0.0.1:8101/ui/** (dev
server with hot reload, when `npm run dev` is running) · API health:
http://127.0.0.1:8000/health

The sidebar footer shows the **build commit** — if it does not match your
latest commit, the image is stale; rebuild.

## The media stack (local generation)

- ComfyUI runs on this machine (start it with the operator's usual launcher);
  the studio reads it at `COMFYUI_URL` when `MEDIA_GEN_LIVE=1`.
- Keep ComfyUI off during LLM-heavy sessions (measured ~2× LLM slowdown when
  co-resident).
- Ollama runs natively on Windows (port 11434) and serves the brain.

## Backups

```
# In deploy/: set PGPASSFILE, BACKUP_ENC_KEY_FILE, and (to complete the
# off-machine leg) RCLONE_REMOTE=<remote>:<bucket>.
bash deploy/backup.sh          # dump → encrypt → hash → upload (rclone)
bash deploy/restore.sh         # restore drill into a DISPOSABLE db only
```

Without `RCLONE_REMOTE` the script says "LOCAL ONLY" — a backup that never left
the machine is never reported as done.

## Monitoring (optional)

```
docker compose -f docker-compose.monitoring.yml up -d
```

- Uptime Kuma → http://127.0.0.1:3001 (add HTTP checks for /ui/ and /health)
- Dozzle → http://127.0.0.1:8080 (live container logs)

## Partner access

- Local: create an invite for the partner's email (Beta Operations → invites),
  then the partner signs up at `/ui/sign-in`.
- Remote: expose the local UI through the operator's Cloudflare tunnel; keep
  the tunnel URL private and share the invite link, not credentials.

## When something looks wrong

| Symptom | First move |
| --- | --- |
| A feature 404s | Rebuild: `docker compose up -d --build api caddy` (stale image) |
| "Too many requests" | Check the rate-limit budget (`Northstar_backend/rate_limiter.py`); never set the harness opt-out in a hosted env |
| Generation fails | Is ComfyUI running? Is `MEDIA_GEN_LIVE=1`? Check Dozzle logs for the ComfyUI error |
| Sign-in 503 | The JWT secret is missing — start via `tools/start-local.ps1` |
| Backup says LOCAL ONLY | Set `RCLONE_REMOTE`; run a restore drill |
| Database issues | `docker compose ps` → postgres healthy? Then `docker compose logs postgres --tail 100` |

## Rules that never change

- No credentials are ever printed, logged or committed; `.env` values are
  never read aloud by tooling.
- Nothing in this product signs in to Amazon or calls Amazon APIs — the
  file-only architecture is enforced by `tools/test_no_amazon_linkage.py`.
- Generation stays unarmed unless `MEDIA_GEN_LIVE=1` is set deliberately.
- Reports live in `reports/`; the plan lives in
  `reports/PRODUCTION_READINESS_PLAN_20261016.md`.
