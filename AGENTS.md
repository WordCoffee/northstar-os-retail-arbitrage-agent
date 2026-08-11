# Northstar OS Retail Arbitrage Agent - Agent Guide

## Pipeline Overview

```
npm run pipeline
    │
    ├─▶ npm run search      → data/snapshots/scan-<timestamp>.json
    │       Scrapes Amazon via Bright Data API for SEARCH_KEYWORDS
    │
    ├─▶ npm run normalize   → data/normalized/normalized-<timestamp>.json
    │       Normalizes records, dedupes by ASIN
    │
    └─▶ npm run score       → data/scored/scored-<timestamp>.json
            + data/scored/top-deals-<timestamp>.csv
            Scores deals against Costco CSV, filters by thresholds
```

## Windows PowerShell-Safe Commands

### Run Pipeline
```powershell
npm run pipeline
# or
./run-agent.bat
```

### Individual Stages
```powershell
npm run search
npm run normalize
npm run score
```

### With Flags
```powershell
npm run normalize -- --dry-run
npm run lint
npm run format
npm run check
```

### Environment Variables (in `.env`)
```env
SEARCH_KEYWORDS=kirkland,kirkland signature
BRIGHTDATA_API_KEY=your_key
BRIGHTDATA_DATASET_ID=gd_lwdb4vjm1ehb499uxs
MIN_PROFIT_MARGIN_PERCENT=25
MIN_ROI_PERCENT=30
MAX_SELLER_RANK=100000
TOP_DEALS_COUNT=20
COSTCO_CSV_PATH=./data/costco-items.csv
```

## Data Directories
```
data/
├── snapshots/      # Raw Bright Data responses
├── normalized/     # Cleaned, deduped records
├── scored/         # Scored deals + top-deals CSV
└── costco-items.csv  # Costco catalog for cost basis
```

## Rules for Small Verified Changes

1. **One change at a time** - Edit one file, verify, then proceed
2. **Test after each edit** - Run the affected stage:
   - Search changes → `npm run search`
   - Normalize changes → `npm run normalize -- --dry-run`
   - Score changes → `npm run score`
3. **Full pipeline verification** - Run `npm run pipeline` after complete changes
4. **Check lint** - `npm run lint` before committing
5. **PowerShell safety**:
   - Use `;` not `&&` for chaining (or use `npm run pipeline`)
   - Quote paths with spaces: `"C:\path with spaces\file.json"`
   - Use `Get-Content` not `cat`/`head`/`tail`
   - Use `Select-Object -First N` for head
6. **No git** - This is not a git repo; changes are manual

## Key Files

| File | Purpose |
|------|---------|
| `src/config.js` | All env-driven config |
| `src/scrapers/amazonSearch.js` | Bright Data search |
| `src/normalizers/amazonSearchNormalizer.js` | Normalize + dedupe |
| `src/analyzers/dealScorer.js` | ROI/profit scoring |
| `src/pipelines/scoreLatestSnapshot.js` | Score + CSV export |
| `src/lib/fsUtils.js` | File helpers |
| `src/lib/paths.js` | Data directory paths |

## Adding New Features

1. Add config to `src/config.js` with `numberEnv()` / `splitCsv()`
2. Update the relevant pipeline stage
3. Test with `--dry-run` where available
4. Run full pipeline
5. Verify output in `data/scored/`