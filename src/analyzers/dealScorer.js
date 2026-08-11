import { config } from '../config.js';

function round(value) {
  return Math.round(value * 100) / 100;
}

export function scoreDeal(row, costBasis = null) {
  const amazonPrice = row.price;
  const cost = costBasis;

  if (!amazonPrice || !cost) {
    return {
      ...row,
      costBasis: cost,
      estimatedProfit: null,
      roiPercent: null,
      profitMarginPercent: null,
      qualifies: false,
      reasons: ['Missing amazon price or cost basis'],
    };
  }

  const estimatedProfit = amazonPrice - cost;
  const roiPercent = cost ? (estimatedProfit / cost) * 100 : null;
  const profitMarginPercent = amazonPrice ? (estimatedProfit / amazonPrice) * 100 : null;

  const reasons = [];
  if (profitMarginPercent < config.thresholds.minProfitMarginPercent) {
    reasons.push('Profit margin below threshold');
  }
  if (roiPercent < config.thresholds.minRoiPercent) {
    reasons.push('ROI below threshold');
  }
  if (!row.asin) {
    reasons.push('Missing ASIN');
  }
  if (row.isSponsored) {
    reasons.push('Sponsored result');
  }
  if (row.rankOnPage && row.rankOnPage > config.thresholds.maxSellerRank) {
    reasons.push('Seller rank above threshold');
  }

  return {
    ...row,
    costBasis: round(cost),
    estimatedProfit: round(estimatedProfit),
    roiPercent: round(roiPercent),
    profitMarginPercent: round(profitMarginPercent),
    qualifies: reasons.length === 0,
    reasons,
  };
}
