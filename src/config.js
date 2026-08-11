import dotenv from 'dotenv';

dotenv.config();

function splitCsv(value) {
  return String(value || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
}

function numberEnv(name, fallback) {
  const value = process.env[name];
  if (value === undefined || value === '') return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * Call at the start of any stage that needs a specific set of env vars.
 * Prints a clear error listing every missing variable and exits.
 *
 * @param {string[]} names - env var names required by the calling stage
 */
export function requireEnv(names) {
  const missing = names.filter(name => !process.env[name]);
  if (missing.length > 0) {
    console.error('Missing required environment variables:');
    for (const name of missing) {
      console.error(`  ${name}`);
    }
    console.error('Create or update your .env file. See .env.example for reference.');
    process.exit(1);
  }
}

export const config = {
  brightData: {
    apiKey: process.env.BRIGHTDATA_API_KEY || '',
    datasetId: process.env.BRIGHTDATA_DATASET_ID || 'gd_lwdb4vjm1ehb499uxs',
  },
  search: {
    keywords: splitCsv(process.env.SEARCH_KEYWORDS),
    marketplace: process.env.DEFAULT_MARKETPLACE || 'https://www.amazon.com',
    pagesToSearch: numberEnv('PAGES_TO_SEARCH', 2),
  },
  thresholds: {
    minProfitMarginPercent: numberEnv('MIN_PROFIT_MARGIN_PERCENT', 25),
    minRoiPercent: numberEnv('MIN_ROI_PERCENT', 30),
    maxSellerRank: numberEnv('MAX_SELLER_RANK', 100000),
  },
  sources: {
    costcoCsvPath: process.env.COSTCO_CSV_PATH || './data/costco-items.csv',
  },
  export: {
    topDealsCount: numberEnv('TOP_DEALS_COUNT', 20),
  },
};
