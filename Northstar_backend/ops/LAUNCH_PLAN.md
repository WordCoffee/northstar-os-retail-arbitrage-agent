# Phase 2 → Launch — Complete Ops Plan (Northstar OS)

**Status as of commit a5c3881:** SPA Phase 2 UI redesign complete + ALL GREEN
(71-shell contract, zero network). `schema.sql` + `views.sql` committed.

---

## 1 · What's left before a real first launch (in build order)

| # | Block | What it produces | Effort |
|---|-------|------------------|--------|
| 1 | **Auth + gates CLI** | `NS.gates` fail-closed UI is done; backend needs real JWT login + per-account plan rows so the `data-live-gate="off"` → "Authorization required" path is wired to actual entitlements | 1-2 days |
| 2 | **Golden Goose DB loader** | `ops/schema.sql` is ready; add the PA-API + enrichment writer so `products.tier / products.goose / products.roi_pct` get filled from real scans instead of demo fixtures | 3-5 days |
| 3 | **SourceScout live pull** | wired to Amazon Product Advertising API (PA-API 5.0, free) — BSR, price history, buy-box ownership, fee tables | 2-3 days |
| 4 | **ListingForge SP-API** | listing create/update + A+ templates via Selling Partner API | 2-3 days |
| 5 | **AdPilot Ads API** | campaign read + bid/budget edits via Amazon Ads API | 2-3 days |
| 6 | **SocialPulse publish** | Meta Graph + X API post pipeline, scheduled queue | 2-3 days |
| 7 | **AutothinK local LLM** | Ollama/vLLM on your GPU (see §3) — replaces the demo iframe with a live inference endpoint | 3-5 days |
| 8 | **Deploy** | Oracle Always Free (see §4) + Nginx + PM2 + TLS | 1-2 days |

**Total:** ~3-4 focused weeks to a real, but honest, private launch.
Nothing in the shell pretends to be live — every gate stays OFF until its API key
is configured and that gate is individually approved. That USB-stick-LAN honesty
is the launch contract.

---

## 2 · Cheap data stack (the "massive database" for ~20-50 power users)

Your Golden Goose goes from "Costco demo fixtures" to **every qualifying Amazon
ASIN** — that's hundreds of thousands of rows. Cost model at scale:

| Layer | Cheapest real option | Cost |
|-------|---------------------|------|
| Product DB | SQLite (dev) → **Postgres** on Oracle Free (2026) | **$0** |
| Product data | **Amazon PA-API 5.0** (free with Associates) + your own scanner | **$0** |
| Wholesale/BSR enrichment | **DataForSEO / MerchantWords** paid only if you want velocity beyond free | **$0-60/mo** |
| Listings API | Amazon SP-API (free, credentials only) | **$0** |
| Ads API | Amazon Ads API (free) | **$0** |
| Social posting | Meta Graph + X — free tiers to start | **$0** |
| Local LLM | GGUF into your own GPU (see §3) | **$0 ongoing** |
| Hosting | Oracle Always Free (see §4) | **$0** |
| **Total** | — | **$0-60/mo** |

The heavy lifting (live Amazon pull, 1P/vendor exclusion, ROI ≥ 10% + $10 net
filter, tiering A/B/C) all runs in YOUR layer — so the only unavoidable spend is
wholesale velocity data if you outgrow free quotas.

---

## 3 · GPU / VRAM — cheapest real upgrade path

Rule of thumb: for a local model that is dramatically more capable than the
demo iframe, you want **≥ 24GB VRAM** (runs a 13B-30B model fully in GPU, and
12B+ with serious headroom for 20-50 users).

Cheapest, honest, real options (eBay used prices, 2026):

| GPU | VRAM | Used 2026 | Notes |
|-----|------|-----------|-------|
| **Tesla P40** | 24GB | $150-200 | Passive datacenter card — best $/VRAM. No display out; run inference-only (llama.cpp/Ollama would work great on Linux). |
| Tesla P100 16GB | 16GB | $180-250 | Faster memory/bandwidth than P40 per GB, lower VRAM. |
| RTX 3090 24GB | 24GB | $550-700 | Best all-round (display out, NVLink SLI pair option, most software support). |
| RTX 4090 24GB | 24GB | $1,300-1,600 | Fastest consumer 24GB; only if the budget opens up. |
| **Dual P40** | 48GB | ~$350 | Two cards → 48GB VRAM, runs a 65-70B quantized model; needs a big PSU + case airflow. |

**My pick for you:** start with **one Tesla P40 (24GB, ~$150-200)**. It runs
Mixtral-8x7B / Llama-3-8B / Mistral-7B at full speed with 20-50 users' headroom,
and if you later want a much larger model, add a second P40 (~$150) for 48GB —
that 48GB runs 70B-class quantized models well. Pair with a used X99/E5 v3 board
or your existing PC's x16 slot.

> P40 needs: 6-pin + 8-pin power, ~250W TDP, an open x16 slot, and since it's
> passive, decent case airflow. No Windows display output — totally fine since
> AutothinK talks to it over localhost HTTP only.

---

## 4 · Oracle Always Free — everything the app needs, $0

| Resource | Free-tier gift | Northstar OS use |
|----------|---------------|------------------|
| **Ampere A1** (ARM) | 4 OCPU / 24GB RAM total (split across 1-4 VMs) | Runs your Node/Python API + static shell + Nginx |
| **Block volume** | 200GB | Northstar DB (Postgres via docker) + uploads |
| **Autonomous DB** | 1 free instance, ~20GB | Managed Postgres — skip Docker DB entirely |
| **Object storage** | 20GB | Backups, exports, media |

**Deploy recipe (2-3h):**
1. Create **Ampere A1 VM**, Ubuntu 22.04 ARM, 4 OCPU / 24GB RAM, add 100GB block.
2. `docker` API container + `nginx:alpine` reverse-proxy + Let's Encrypt (free) + PM2.
3. Point `northstar-os/static` at Nginx; keep the SPA **exactly** as tested (drawer, gates, demo badges — nothing changes).
4. Move the DB to Oracle Autonomous Postgres; run `ops/schema.sql` + `views.sql`.

**That is the entire app stack — permanently $0/month**, which is why the
20-50 power-user plan stays viable without revenue pressure.

---

## 5 · What the "Golden Goose to every product" means concretely

Golden Goose today = Costco Kirkland demo fixtures. The upgrade path:

```
EVERY Amazon product meeting scout criteria
  ├─ exclude: 1P / vendor / brand-gated / restricted (fail-closed gates)
  ├─ compute: net = amazon_price − cogs − fba_fee − referral − inbound
  ├─ require: net ≥ $10 AND roi_pct ≥ 30 (the $10 min-profit toggle)
  ├─ tier: A (golden) / B / C / discard
  └─ write: products table → hub KPIs → analyst's desk (Phase 2 UI ships this)
```

The Phase 2 UI already renders this decision system honestly. Phase 3 only
swaps demo fixtures for PA-API + enrichment output against the committed
`ops/schema.sql`.

---

## Bottom line

- **UI (the redesign):** DONE and ALL GREEN — commit a5c3881.
- **Data layer:** schema committed; loader is the next 3-5 days of work.
- **Cost to run everything:** $0-60/mo on Oracle Free, $0 for all Amazon/API
  data, $0 for local AI after the one-time ~$150-200 Tesla P40 buy.
- **Recommended order:** Golden Goose DB loader → SourceScout live → SP-API
  listing → Ads → Social → AutothinK GPU → deploy. ~3-4 weeks to private launch.
