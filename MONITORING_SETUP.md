# MONITORING & ALERTING SETUP — Phase E1

**Date:** 2026-09-20 · **Baseline:** `0a5126b` · **Cost:** $0 (Cloudflare
free-tier only; no paid monitoring tool). Closes D5 checklist item **#4**.

## 1. What is wired (in-repo)

| Hook | Endpoint / file | Behavior |
|---|---|---|
| **Public uptime probe** | `GET /api/health` (`functions/api/health.js`) | bff/v1 envelope; `status:"ok"`, `data.status:"ok"`, `data.kv_bound` (KV binding presence), `data.time`. No secrets/providers/paths (no-leak verified by the functions contract suite). Unauthenticated by design. |
| **Backend liveness** | `GET /health`, `GET /health/detailed` (FastAPI) | Existing detailed health for the local backend (DB/connectivity detail). |
| **Error contract** | `functions/api/_envelope.js` | All Functions errors return a generic `internal_error` (no stack/exception leak); structured codes enable alerting on error rate. |
| **Static build/analytics** | `public/`, Cloudflare Pages | Pages build + request analytics are captured by Cloudflare automatically. |

## 2. Cloudflare free-tier views (where to look)

Enable/view in the Cloudflare dashboard (free):

1. **Pages → project → Analytics** — requests, bandwidth, status-code mix,
   build history. (Free.)
2. **Web Analytics** (Account → Web Analytics → Add site) — free RUM beacon
   (page views, Core Web Vitals). Optional snippet; no cost.
3. **Pages → Functions → Real-time logs** — per-request Function logs
   (development/preview and short-window live tail). Free-tier live view.
4. **Account → Notifications** — free email notifications for account/Pages
   events (build failures, etc.).

## 3. Uptime / error alerting (recommended, free, operator-enabled)

Cloudflare's own Health Checks are a **paid** add-on — do **not** enable without
approval. Use a **free** external probe instead:

- **UptimeRobot (free tier)** or **Better Stack (free tier)**: create an HTTP(s)
  monitor for `https://<staging-or-prod-domain>/api/health`, keyword/JSON check
  `"status":"ok"`, 5-min interval; alert to operator email/webhook.
- If the site is behind **Cloudflare Access**, either exclude `/api/health` from
  the Access policy (recommended for probes) or attach an Access **service
  token** to the monitor. Documented in `CLOUDFLARE_DEPLOY.md`.

This is an operator-side, **$0** action (account setup only; I do not handle
Cloudflare credentials).

## 4. What this resolves (and what remains)

- **D5 #4 Monitoring/alerting hooks → RESOLVED (E1):** an uptime-assertable
  health endpoint + documented free analytics/log/alert paths; no paid tier.
- **Remaining operator step (no cost):** actually create the external monitor
  and (optionally) enable Web Analytics in the dashboard — credential-gated,
  flagged, not spend.

**Verification:** `node Northstar_backend/test_functions_contract.cjs` →
`/api/health` envelope + `kv_bound` honesty + no-leak assertions pass (suite now
31 PASS / 0 FAIL).