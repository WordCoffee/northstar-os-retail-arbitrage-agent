import 'dotenv/config';

export const config = {
  brightData: {
    apiKey: process.env.BRIGHTDATA_API_KEY,
    datasetId: process.env.BRIGHTDATA_DATASET_ID,
  },
  search: {
    marketplace: process.env.DEFAULT_MARKETPLACE || 'https://www.amazon.com',
    pagesToSearch: Number(process.env.PAGES_TO_SEARCH || 2),
    keywords: (process.env.SEARCH_KEYWORDS || '')
      .split(',')
      .map(k => k.trim())
      .filter(Boolean),
  },
  thresholds: {
    minProfitMarginPercent: Number(process.env.MIN_PROFIT_MARGIN_PERCENT || 25),
    minRoiPercent: Number(process.env.MIN_ROI_PERCENT || 30),
    maxSellerRank: Number(process.env.MAX_SELLER_RANK || 100000),
  },
  server: {
    port: Number(process.env.PORT || 4000),
  },
};
