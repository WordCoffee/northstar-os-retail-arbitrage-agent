# Northstar OS — Cloudflare Pages Deployment

This guide covers the **actual** deploy path of this repository: a static
dashboard UI on **Cloudflare Pages** with **Pages Functions** for `/api/*`,
protected by **Cloudflare Access** (Zero Trust).

> **Honest scope (B5 alignment):** this project deploys as **Pages + Pages
> Functions only**. There is **no Workers compute layer**, no backend-on-
> Workers staging, and no second deploy target. The FastAPI backend
> (`Northstar_backend/main.py`) and AutothinK (`autothink/`) run locally and
> are **not** part of this Pages deployment. Any claim that this Pages site
> serves the full backend would be false — it does not.

---

## Current architecture

```
public/                      # static dashboard (Cloudflare Pages build dir)
functions/
  api/
    _envelope.js             # bff/v1 envelope helper (NOT a route; _ = util)
    files.js                 # GET /api/files          -> bff/v1 envelope
    latest-deals.js          # GET /api/latest-deals   -> bff/v1 envelope
    data/[filename].js       # GET /api/data/:name     -> bff/v1 envelope
    transcribe.js            # GET/POST -> 501 not_implemented (intentional through Phase E — see E3 note below)
src/lib/dealsApi.js          # Shared KV read logic for latest-deals
wrangler.toml                # Pages project config (pages_build_output_dir=public)
_routes.json                 # /* static, /api/* -> Pages Functions
```

**API contract:** every Functions response conforms to
[`docs/contracts/BFF_CONTRACT_v1.md`](docs/contracts/BFF_CONTRACT_v1.md):
uniform envelope (`contract`, `request_id`, `status`, `data`, `error`, `meta`),
honest error taxonomy (including `not_implemented` = 501 for `transcribe.js`),
and a no-leak rule (generic messages only — never raw provider/exception text).

**KV:** `DEALS_KV` (bound in `wrangler.toml`) backs `/api/files` and
`/api/latest-deals` with the `scored:*` and `csv:*` keys written by the local
pipeline.

---

## Prerequisites

- Cloudflare account (free)
- Domain in Cloudflare (or subdomain)
- Private GitHub repo with this code

---

## 1. Push to GitHub (Private Repo)

```bash
git init
git add .
git commit -m "Northstar OS dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/northstar-os-dashboard.git
git push -u origin main
```

> `.gitignore` excludes `.env`, `node_modules`, and local data files.

---

## 2. Create Cloudflare Pages Project

1. Go to **Cloudflare Dashboard → Pages → Create a project**
2. Connect to Git → Select your private repo
3. Configure build settings:
   - **Framework preset**: None (static)
   - **Build command**: empty (no build step required for `public/`)
   - **Build output directory**: `public`
   - **Root directory**: `/` (or where `public/` lives)
4. Click **Save and Deploy**

> Cloudflare Pages auto-detects the `functions/` directory and serves `/api/*`
> routes through Pages Functions. The functions expect a KV namespace bound as
> `DEALS_KV` (set it in **Settings → Bindings → KV namespace**).

---

## 3. Add Custom Domain

1. In your Pages project → **Custom domains** → **Set up a custom domain**
2. Enter your domain (e.g., `northstar.yourdomain.com`)
3. Cloudflare adds DNS records automatically (if domain is on Cloudflare)

---

## 4. Enable Cloudflare Access (Password Protection)

**Cloudflare Access** (part of Zero Trust) adds authentication in front of your
Pages deployment — no code changes needed.

### Option A: GitHub/Google/OIDC Login (Recommended)

1. Go to **Zero Trust → Access → Applications → Add an application**
2. Select **Self-hosted** → **Next**
3. **Application domain**: `northstar.yourdomain.com`
4. **Policy name**: "Northstar OS Access"
5. **Action**: Allow
6. **Include**: Emails ending in `@yourdomain.com` (or specific emails)
7. **Login methods**: Add GitHub, Google, or OIDC (e.g., Okta, Auth0)
8. **Save**

Now anyone accessing `northstar.yourdomain.com` must authenticate via GitHub/Google first.

### Option B: Simple Email PIN (No SSO)

1. Same as above, but in **Login methods** → **One-time PIN**
2. Users enter email → get a code → access granted

### Option C: Service Token (For API Access)

If you need programmatic access to `/api/*`:

1. **Zero Trust → Access → Service Tokens → Generate**
2. Use the `CF-Access-Client-Id` and `CF-Access-Client-Secret` headers in API calls

---

## 5. Verify Deployment

- Visit `https://northstar.yourdomain.com` → should redirect to login
- After login → dashboard loads
- API: `https://northstar.yourdomain.com/api/latest-deals` → a **bff/v1 JSON
  envelope** with `status:"ok"` (or `status:"empty"` when no KV rows yet)
- `/api/transcribe` → `status:"error"`, `error.code:"not_implemented"` (501) —
  this is the honest stub state; not a hidden feature

---

## 6. Auto-Deploy on Pipeline Runs (Optional)

Add a GitHub Action to push scored data to the repo after each pipeline run:

```yaml
# .github/workflows/deploy-data.yml
name: Deploy Scored Data
on:
  workflow_dispatch:
  schedule:
    - cron: '0 */6 * * *'  # every 6 hours
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run pipeline
      - name: Commit & push data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/scored/
          git diff --staged --quiet || git commit -m "chore: update scored data $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push
```

> This keeps the dashboard data fresh without manual intervention.

---

## File Structure

```
public/
  index.html          # Dashboard UI (static)
functions/
  api/
    _envelope.js      # bff/v1 envelope helper (not a route)
    latest-deals.js   # GET /api/latest-deals      -> bff/v1 envelope
    files.js          # GET /api/files             -> bff/v1 envelope
    data/[filename].js# GET /api/data/:name        -> bff/v1 envelope
    transcribe.js     # GET/POST -> 501 not_implemented (honest stub)
src/lib/dealsApi.js   # Shared logic for reading KV data
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 404 on `/api/latest-deals` | Ensure `functions/api/latest-deals.js` exists and Pages Functions are enabled |
| `internal_error` from `/api/latest-deals` | KV binding `DEALS_KV` missing or not bound to the Pages project |
| CORS errors | Pages Functions auto-handle CORS for same-origin; add headers if calling from elsewhere |
| Access denies you | Check Zero Trust policy includes your email/domain; verify login method works |
| `/api/transcribe` returns 501 | **Intentional through Phase E (E3 deferral)** — transcription is not implemented in this deployment; the stub is honest (no fake result). See the E3 decision note below. |
| Stale data | Pipeline must run and commit new `data/scored/` files; GitHub Action above automates this |

---

## Costs

All free tier:
- **Cloudflare Pages**: unlimited sites, 500 builds/mo, unlimited bandwidth
- **Cloudflare Access**: free for ≤50 users
- **Cloudflare DNS/Registrar**: wholesale pricing (no markup)

Total: **$0/month** for typical usage.

> Updated 2026-09-19 (B5): documents the real Pages + Functions path, the
> bff/v1 envelope, and the honest `not_implemented` transcribe stub. No
> Workers compute layer or second deploy target is claimed.

> **E3 decision (2026-09-20):** `/api/transcribe` **remains the 501
> `not_implemented` stub intentionally through Phase E** (and until a later
> phase explicitly scopes STT). No live provider is wired; any paid STT call is
> a §3 Hard-Stop action (named approval + per-call cost). Target phase:
> post-alpha (Phase F / hosted release) with provider + cost approval.