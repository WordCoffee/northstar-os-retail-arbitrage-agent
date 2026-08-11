function toBool(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return value.toLowerCase() === 'true';
  return Boolean(value);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

// Like numberOrNull but treats 0 as null (for prices that should be positive)
function positiveNumberOrNull(value) {
  const n = numberOrNull(value);
  return n !== null && n > 0 ? n : null;
}

export function normalizeAmazonRecord(record) {
  const asin = record.asin || null;
  const title = record.name || record.title || null;
  const price = numberOrNull(record.final_price ?? record.finalprice ?? record.price);
  const listPrice = positiveNumberOrNull(record.initial_price ?? record.initialprice ?? record.highestprice);
  const rating = numberOrNull(record.rating);
  const reviewCount = numberOrNull(record.num_ratings ?? record.numratings ?? record.reviewscount);
  const monthlySold = numberOrNull(record.bought_past_month ?? record.boughtpastmonth ?? record.sold);
  const rankOnPage = numberOrNull(record.rank_on_page ?? record.rankonpage ?? record.organicposition);
  const pageNumber = numberOrNull(record.page_number ?? record.pagenumber);

  return {
    asin,
    title,
    brand: record.brand || null,
    url: record.url || null,
    image: record.image || record.urlimage || null,
    keyword: record.keyword || record.input?.keyword || null,
    marketplace: record.domain || record.input?.url || null,
    price,
    listPrice,
    rating,
    reviewCount,
    monthlySold,
    pageNumber,
    rankOnPage,
    isSponsored: toBool(record.sponsored ?? record.issponsored),
    isPrime: toBool(record.is_prime ?? record.isprime),
    badge: record.badge || null,
    delivery: record.delivery || record.shippinginformation || null,
    raw: record,
  };
}

export function dedupeAmazonRecords(records) {
  const byAsin = new Map();

  for (const record of records) {
    if (!record.asin) continue;
    const existing = byAsin.get(record.asin);

    if (!existing) {
      byAsin.set(record.asin, record);
      continue;
    }

    const existingScore = (existing.isSponsored ? 0 : 2) + (existing.rankOnPage ? 1 : 0) + (existing.reviewCount || 0);
    const candidateScore = (record.isSponsored ? 0 : 2) + (record.rankOnPage ? 1 : 0) + (record.reviewCount || 0);

    if (candidateScore > existingScore) {
      byAsin.set(record.asin, record);
    }
  }

  return [...byAsin.values()];
}
