# Private Alpha — Deploy & Access Runbook (Phase H / H4)

**Scope:** put the full suite in front of the operator only, on the live tunnel,
with both AI engines. Payment is deferred (manual invoicing later).

---

## 1. Topology (what actually serves what)

```
Operator browser
      │  CF Access: allowlist = northstarosllc@gmail.com
      ▼
Cloudflare Tunnel  (loops-subsequently-california-invest.trycloudflare.com)
      ▼
Local FastAPI backend  (127.0.0.1:8000)
      ├── /northstar-os/          the services suite shell  ← THE WEBSITE
      ├── /autothink/             the AutothinK workspace (same-origin iframe)
      ├── /api/...                services + /api/v1/models (Brain catalog)
      └── Ollama 127.0.0.1:11434  LOCAL engine
                  └── cloud calls → OpenRouter DeepSeek lane (CLOUD engine)
```

> The Cloudflare **Pages** site (`public/`) is a separate public deals page.
> It does **not** serve the suite. The suite is served by the local backend via
> the tunnel. Do not confuse the two.

## 2. Bring-up (each session)

```powershell
# 1. Local engines
ollama serve                                   # local engine (leave running)

# 2. Backend (serves the suite + APIs)
cd Northstar_backend
$env:NORTHSTAR_DISABLE_RATE_LIMIT="0"          # real limiter in the live test
$env:NORTHSTAR_PRIVATE_ALPHA="1"               # lock to the allowlist
$env:NORTHSTAR_ALPHA_ALLOWLIST="northstarosllc@gmail.com"
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 3. AutothinK (optional separate process on :8100)
cd ../autothink
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8100

# 4. Tunnel
cloudflared tunnel --url http://127.0.0.1:8000
#   → prints a NEW https://<random>.trycloudflare.com URL each restart
```

## 3. Cloud engine arm (only when executing the approved run)

```powershell
# Presence-only check (never print the value)
if ($env:OPENROUTER_API_KEY) { "present" } else { "missing" }
$env:CLOUD_MODEL_LIVE="1"        # arms cloud EXECUTION; remove to disarm
```
Cloud stays **disarmed** by default: with the flag unset the Brain reports
`not armed` and returns an honest fallback instead of calling out.

## 4. Cloudflare Access (the edge lock)

1. Zero Trust → Access → Applications → Add application → **Self-hosted**.
2. Hostname = the current tunnel URL (update it after every restart).
3. Policy: Allow → Emails → `northstarosllc@gmail.com`.
4. (Optional) add a **service token** and exclude `/api/health` for probes.

**Ephemeral hostname:** `*.trycloudflare.com` changes on every `cloudflared`
restart → re-point the Access application to the new hostname. For a durable
URL, promote to a **named tunnel** with a stable hostname (survives restarts,
no re-pointing).

## 5. Verify

| Check | Expected |
|---|---|
| `GET /health` | 200 `{status: ok}` (public, never gated) |
| `GET /api/v1/models` (no token) | **403 `private_alpha_locked`** (in-app lock) |
| `GET /northstar-os/` | the suite shell loads |
| Brain selector in ribbon | `local · T2 · northstar-qwen3:rev1` |
| AutothinK view | iframe mounts (same-origin) |
| `GET /api/v1/plans` | Whetstone/Mainstay/Keystone/AutothinK at 39/79/129/179 |

## 6. Rollback

Code rollback = `scripts/rollback_drill.ps1` (see `ROLLBACK_DRILL.md`).
Deploy rollback = stop `cloudflared`, re-point Access, restart the backend.
Nothing here touches Amazon or spends money.
