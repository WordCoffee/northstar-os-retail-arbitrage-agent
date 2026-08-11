# Northstar OS — Cloudflare Pages Deployment

This guide covers deploying the dashboard UI to **Cloudflare Pages** and protecting it with **Cloudflare Access** (Zero Trust).

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

> The `.gitignore` excludes `.env`, `node_modules`, and local data files.

---

## 2. Create Cloudflare Pages Project

1. Go to **Cloudflare Dashboard → Pages → Create a project**
2. Connect to Git → Select your private repo
3. Configure build settings:
   - **Framework preset**: None (static)
   - **Build command**: `npm run build` (or leave empty if no build step)
   - **Build output directory**: `public`
   - **Root directory**: `/` (or where `public/` lives)
4. Click **Save and Deploy**

> Cloudflare Pages will auto-detect the `functions/` directory and deploy API routes as Pages Functions.

---

## 3. Add Custom Domain

1. In your Pages project → **Custom domains** → **Set up a custom domain**
2. Enter your domain (e.g., `northstar.yourdomain.com`)
3. Cloudflare will add the DNS records automatically (if domain is on Cloudflare)

---

## 4. Enable Cloudflare Access (Password Protection)

**Cloudflare Access** (part of Zero Trust) adds authentication in front of your Pages deployment — no code changes needed.

### Option A: GitHub/Google/OIDC Login (Recommended)

1. Go to **Zero Trust → Access → Applications → Add an application**
2. Select **Self-hosted** → **Next**
3. **Application domain**: `northstar.yourdomain.com` (your Pages domain)
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
- After login → dashboard loads with latest deals
- API: `https://northstar.yourdomain.com/api/latest-deals` → returns JSON

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
  index.html          # Dashboard UI
functions/
  api/
    latest-deals.js   # GET /api/latest-deals → JSON
    files.js          # GET /api/files → list of scored JSON files
    data/[filename].js# GET /api/data/:filename → raw scored JSON
src/lib/dealsApi.js   # Shared logic for reading data files
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 404 on `/api/latest-deals` | Ensure `functions/api/latest-deals.js` exists and Pages Functions are enabled |
| CORS errors | Pages Functions auto-handle CORS for same-origin; add headers if calling from elsewhere |
| Access denies you | Check Zero Trust policy includes your email/domain; verify login method works |
| Stale data | Pipeline must run and commit new `data/scored/` files; GitHub Action above automates this |

---

## Costs

All free tier:
- **Cloudflare Pages**: Unlimited sites, 500 builds/mo, unlimited bandwidth
- **Cloudflare Access**: Free for ≤50 users
- **Cloudflare DNS/Registrar**: Wholesale pricing (no markup)

Total: **$0/month** for typical usage.