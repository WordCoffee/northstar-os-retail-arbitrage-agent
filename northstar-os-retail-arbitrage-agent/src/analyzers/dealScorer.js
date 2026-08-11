import { calculateProfit } from './profitCalculator.js';
import { config } from '../config.js';

export function scoreDeals(rawListings) {
  const { minProfitMarginPercent, minRoiPercent } = config.thresholds;

  const scored = rawListings
    .map(listing => {
      const profit = calculateProfit(listing);
      if (!profit) return null;

      return {
        asin: listing.asin,
        title: listing.name || listing.title,
        image: listing.image || listing.urlimage,
        url: listing.url,
        rating: listing.rating,
        numRatings: listing.numratings ?? listing.reviewscount,
        boughtPastMonth: listing.boughtpastmonth ?? listing.salesvolume,
        sponsored: listing.sponsored ?? listing.issponsored ?? false,
        ...profit,
        score: computeScore(profit, listing),
      };
    })
    .filter(Boolean)
    .filter(
      d =>
        d.marginPercent >= minProfitMarginPercent &&
        d.roiPercent >= minRoiPercent
    )
    .sort((a, b) => b.score - a.score);

  return scored;
}

function computeScore(profit, listing) {
  const demandSignal = Number(listing.boughtpastmonth ?? listing.salesvolume ?? 0);
  const ratingSignal = Number(listing.rating ?? 0);
  return (
    profit.roiPercent * 0.5 +
    profit.marginPercent * 0.3 +
    Math.log10(demandSignal + 1) * 10 * 0.15 +
    ratingSignal * 2 * 0.05
  );
}
