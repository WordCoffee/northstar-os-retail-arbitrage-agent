/**
 * Estimates Amazon FBA economics for a scraped listing.
 * Simplified fee assumptions — tune as needed.
 */
const REFERRAL_RATE = 0.15;
const FBA_FEE_FLAT = 5.5;
const ESTIMATED_SOURCE_DISCOUNT = 0.35;

export function calculateProfit(listing) {
  const price = Number(listing.finalprice ?? listing.price ?? 0);
  if (!price) return null;

  const estimatedCost = price * (1 - ESTIMATED_SOURCE_DISCOUNT);
  const referralFee = price * REFERRAL_RATE;
  const totalFees = referralFee + FBA_FEE_FLAT;
  const netProfit = price - estimatedCost - totalFees;
  const marginPercent = (netProfit / price) * 100;
  const roiPercent = (netProfit / estimatedCost) * 100;

  return {
    price,
    estimatedCost: round2(estimatedCost),
    referralFee: round2(referralFee),
    fbaFee: FBA_FEE_FLAT,
    netProfit: round2(netProfit),
    marginPercent: round2(marginPercent),
    roiPercent: round2(roiPercent),
  };
}

function round2(n) {
  return Math.round(n * 100) / 100;
}
