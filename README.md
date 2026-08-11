# Northstar OS Retail Arbitrage Agent

A three-stage Node.js pipeline that searches Amazon via Bright Data, normalizes the results, and scores them against a Costco catalog for retail arbitrage opportunities.

## Quick Start

### 1. Install dependencies

```powershell
npm install
```

### 2. Create your `.env` file

Copy the example and fill in your credentials:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and set:

| Variable | Required | Description |
|---|---|---|
| `BRIGHTDATA_API_KEY` | Yes | Your Bright Data API key |
| `BRIGHTDATA_DATASET_ID` | Yes | Dataset ID (default: `gd_lwdb4vjm1ehb499uxs`) |
| `SEARCH_KEYWORDS` | Yes | Comma-separated keywords, e.g. `kirkland,kirkland signature` |
| `COSTCO_CSV_PATH` | No | Path to Costco CSV (default: `./data/costco-items.csv`) |
| `MIN_PROFIT_MARGIN_PERCENT` | No | Minimum profit margin % to qualify (default: `25`) |
| `MIN_ROI_PERCENT` | No | Minimum ROI % to qualify (default: `30`) |
| `TOP_DEALS_COUNT` | No | Rows in the top-deals CSV (default: `20`) |

### 3. Add your Costco CSV

Place your Costco item list at `data/costco-items.csv`. Required columns:

```
title,price
Kirkland Signature Paper Towels,18.99
Kirkland Signature AA Batteries 48 Count,14.99
```

### 4. Run the full pipeline

```powershell
npm run pipeline
```

Or double-click **`run-agent.bat`** from the project folder.

---

## Pipeline Stages

```
npm run pipeline
    │
    ├─▶ npm run search      → data/snapshots/scan-<timestamp>.json
    │       Scrapes Amazon via Bright Data API
    │
    ├─▶ npm run normalize   → data/normalized/normalized-<timestamp>.json
    │       Normalizes records, deduplicates by ASIN
    │
    └─▶ npm run score       → data/scored/scored-<timestamp>.json
            + data/scored/top-deals-<timestamp>.csv
            Scores deals against Costco CSV, filters by thresholds
```

## Output Files

| File | Description |
|---|---|
| `data/snapshots/scan-*.json` | Raw Bright Data response |
| `data/normalized/normalized-*.json` | Cleaned, deduped records |
| `data/scored/scored-*.json` | All records with ROI/profit scores |
| `data/scored/top-deals-*.csv` | Top N deals, Excel-friendly |

The top-deals CSV lists **qualified deals first** (sorted by ROI), then fills remaining rows with the next-best cost-matched candidates.

## Other Commands

```powershell
npm run normalize -- --dry-run   # Preview normalization without writing
npm run lint                     # Lint source files
npm run format                   # Auto-format source files
npm run check                    # Lint + normalize dry-run
node src/index.js                # Print usage
```

## Design Principles

- Raw snapshots in `data/snapshots/` are never modified.
- Each stage writes a new timestamped artifact; nothing is overwritten.
- Config is centralized in `src/config.js` and driven entirely by `.env`.
- Costco title matching tolerates punctuation, word-order differences, and the common "Krikland" typo.
