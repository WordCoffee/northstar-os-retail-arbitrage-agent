# Northstar OS — Retail Arbitrage Agent

Automated pipeline that scrapes Amazon search results via Bright Data,
scores each listing for arbitrage profitability, stores structured
results, and displays them in a local dashboard.

## Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill in your Bright Data key.
3. `npm run scan` — runs one full search + score + store cycle.
4. `npm run server` — launches the dashboard at http://localhost:4000

## Automating on GitHub

Push this folder to a new GitHub repo. The included workflow
(`.github/workflows/scan.yml`) runs the scan every 6 hours using
repository secrets (`BRIGHTDATA_API_KEY`, `BRIGHTDATA_DATASET_ID`)
and commits updated `data/deals.json` back to the repo automatically.

## Data flow

1. `amazonSearch.js` calls Bright Data's dataset scrape endpoint for each keyword.
2. Raw results are archived to `data/snapshots/`.
3. `profitCalculator.js` estimates Amazon referral fee, FBA fee, and net margin.
4. `dealScorer.js` filters by thresholds and ranks.
5. `storageService.js` writes `data/products.json` and `data/deals.json`.
6. `alertService.js` logs top deals and can POST to a webhook.
7. `ui/server.js` exposes `/api/deals` and serves the dashboard reading that JSON.
