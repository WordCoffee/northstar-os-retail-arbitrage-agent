# Northstar OS — Live Mode Migration Report

**Date:** 2026-09-23
**Status:** ✅ Demo mode removed — all generators and tools are live
**URL:** http://127.0.0.1:8101/ (SPA on :8101, backend proxied to :8000)

---

## 1. Constitution change (operator directive)

The blanket "never execute live outbound calls" hard-stop was the blocker keeping
the app demo-gated. Per operator instruction, it was replaced with guardrails
that make sense without blocking the product:

- `AGENTS.md` — "Hard stop" section → "Guardrails" (credential hygiene, real-money
  approval, git safety, protected data, circuit breaker). The product's own live
  operations are now normal function.
- `docs/OPERATING_CONSTITUTION.md` — §3 "HARD STOP ZONE" → "GUARDRAIL ZONE";
  §2A key-distinction, §6, §10 reconciled. Only real-money/purchase/listing/
  transaction actions remain named-approval.

## 2. What is now LIVE (verified with real clicks in browser)

| Service | Real data source | Verified live result |
|---------|------------------|----------------------|
| Prospector | `/api/kirkland/scanner` (45 products, real fee stack) | 42 rows rendered; Minoxidil $53.99 / COGS $19.79 / ROI 87.5% / score 87 |
| Golden Goose | scanner products, weighted score | 21 deals ranked; #1 net $17.32 / ROI 87.5% |
| OfferChisel | `/api/autothink/run` → local Ollama `northstar-qwen3:rev1` | Generated title + 4 bullets + keywords for Kirkland coffee (10.7s) |
| The Town Crier | `/api/autothink/run` (brand-voice enforced) | Caption + hashtags: "Fuel your day with purpose… #MindfulMoments" |
| AutothinK | `/api/v1/models` + `/api/autothink/run` | 4 installed models listed; real decision run returned strategy; appears in Recent Runs |
| The Auctioneer | live fee calculator (referral + FBA + fuel) | Break-even ACoS 16.6% / target 11.6% at $24.99 |
| The Ledger | `/api/v1/credits/me` | balance 5,000 / foundation plan |
| The Watch | scanner products | live ROI signals + buy-box seller |
| RankLedger | scanner products | ranked by opportunity score |
| The Rival Board | scanner products | posture classes (high-margin / saturated) |
| Account | `/api/v1/credits/me` + `/api/v1/models` | plan, credits, cloud key posture |

All 12 routes navigated with real clicks; 0 console errors across every page.

## 3. Wiring

- `northstar-os-ui/vite.config.js` — proxy `/api`, `/health`, `/autothink`, `/legal`
  → `http://127.0.0.1:8000` (dev and preview).
- `src/services/api.js` — typed client for every backend endpoint used.
- Production build passes: 55 modules, 213 kB JS (66 kB gzip), 0 errors.

## 4. What stays GATED (by guardrail, not demo-mode)

- Amazon listing / pricing / purchase / transaction (real-money) — requires named
  operator approval; buttons show gate state.
- Live Costco refresh (scanner `refresh` route is 403 until `SCANNER_LIVE_ALLOWED`).
- Social publish — caption generation is live, publishing is gated.

## 5. Screenshots

- `reports/signal-live-prospector.png` — live economics table
- `reports/signal-live-offerchisel.png` — real generated listing
- `reports/signal-live-auctioneer.png` — live ACoS calculator

## 6. Run

```
cd northstar-os-ui && npm run dev   # :8101 (already running, proxies :8000)
```
Backend FastAPI must be up on :8000 (it is — PID 39468).