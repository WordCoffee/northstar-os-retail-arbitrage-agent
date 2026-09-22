# Private Alpha — Deploy & Access Runbook (Phase H / H4)

**Scope:** put the full suite in front of the operator only, on the live tunnel,
with both AI engines. Payment is deferred (manual invoicing later).

---

## 0. The free, private, full-UX path (start here)

**You do not need to deploy anything to test the complete service UX.** The
Cloudflare **quick tunnel** already serves the entire suite from your machine:

```
you  ->  https://<random>.trycloudflare.com   (Cloudflare Access: your email)
              ->  local backend :8000
                    /northstar-os/   the full suite (every service, real UI)
                    /autothink/      the AutothinK workspace (same-origin)
                    /api/*           real APIs + the Brain model switch
                    Ollama :11434    LOCAL engine (free, private)
                    OpenRouter       CLOUD engine (opt-in, gated)
```

- **Free:** Cloudflare Tunnel + Access free tier; Ollama free; no hosting bill.
- **Private:** Cloudflare Access allow-lists only your email; the in-app alpha
  gate (`NORTHSTAR_PRIVATE_ALPHA=1`) is a second lock. In private-alpha mode
  the tunnel **root redirects into the workspace**, so the URL behaves like the
  real product.
- **Full UX:** nothing is mocked away — it *is* the product shell, talking to
  the real backend.

### Two caveats (both expected)
1. **The URL changes on every `cloudflared` restart** (quick tunnels are
   ephemeral) - re-point the Access application to the new hostname.
2. `cloudflared` must be reachable; the launcher auto-detects common install
   paths, or pass `-CloudflaredPath <path to cloudflared.exe>`.

### Later (when you buy a domain for subscriptions)
Promote to a **named tunnel** on your domain: `app.<yourdomain>` with a stable
hostname (no re-pointing), DNS + Access on your own zone, and the same
everything-else. No code changes - only the tunnel type and the Access app.

---

## 0b. Cloudflare Access needs a domain (the easy blocker)

A self-hosted Access application attaches to a **zone you own**. A quick-tunnel
`*.trycloudflare.com` hostname lives in Cloudflare's zone, so it **cannot** be
added as an Access app. Until you buy a domain, the honest choices are:

| Option | Access control | Free | Setup |
|---|---|---|---|
| **A. URL-only (this week)** | none - unguessable URL only | yes | none (launcher default) |
| **B. In-app gate** | real allowlist (login required) | yes | launch with `-Gate` |
| **C. Tailscale** | real, private, per-device | yes | install Tailscale |
| **D. Domain + named tunnel** | real Cloudflare Access | domain cost | when you buy |

**Option A is acceptable for a solo, same-week test** - the URL is random and
known only to you. It is **not** access control: anyone with the URL gets in.
Do not share it, and do not leave it running long-term.

**Option B (recommended once you want real control without a domain):** launch
with `-Gate`. Registration is then restricted to your allowlist email and every
API call needs a token; authenticate with that email. The tunnel root still
lands in the workspace (`NORTHSTAR_ROOT_TO_APP=1`).

**Option C:** Tailscale gives a private, stable HTTPS address reachable only by
your devices - no domain, no public exposure.

When you buy the domain, move to **D** (named tunnel + Access) and drop A/B.

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

### One command (recommended)

Double-click **`START-NORTHSTAR-ALPHA.bat`** (repo root), or run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_alpha.ps1
```

It sets the private-alpha env, starts Ollama (if down), the backend (:8000),
AutothinK (:8100) and the Cloudflare tunnel, then prints the public URL.

| Mode | Command |
|---|---|
| Check first (no launch) | `... -File scripts\launch_alpha.ps1 -Check` |
| Local only (no tunnel)  | `... -File scripts\launch_alpha.ps1 -NoTunnel` |
| Arm the cloud engine    | `... -File scripts\launch_alpha.ps1 -Cloud` (real spend on run) |
| Stop what it started    | `... -File scripts\launch_alpha.ps1 -Stop` |

> `cloudflared` must be on `PATH` for the tunnel step. If it is installed
> elsewhere, run the launcher with `-NoTunnel` and start the tunnel yourself
> (below); the launcher prints the state of everything else.
> `-Stop` only stops processes the launcher started (it never touches a
> backend that was already running).

### Manual (if you prefer)

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
