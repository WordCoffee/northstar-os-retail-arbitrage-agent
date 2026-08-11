import { parse } from "csv-parse/sync";

export async function loadLatestDeals(env) {
  const csvList = await env.DEALS_KV.list({ prefix: "csv:top-deals-" });
  const jsonList = await env.DEALS_KV.list({ prefix: "scored:scored-" });

  if (!csvList.keys.length || !jsonList.keys.length) {
    return { rows: [], meta: { createdAt: null, costMatchedCount: 0, runCount: 0 } };
  }

  const latestCsvKey = csvList.keys[csvList.keys.length - 1].name;
  const latestJsonKey = jsonList.keys[jsonList.keys.length - 1].name;

  const csvText = await env.DEALS_KV.get(latestCsvKey);
  const jsonData = JSON.parse(await env.DEALS_KV.get(latestJsonKey));

  const rows = parse(csvText, { columns: true, skip_empty_lines: true }).map(r => ({
    asin: r.asin,
    title: r.title,
    brand: r.brand,
    price: r.price ? Number(r.price) : null,
    costBasis: r.costBasis ? Number(r.costBasis) : null,
    estimatedProfit: r.estimatedProfit ? Number(r.estimatedProfit) : null,
    roiPercent: r.roiPercent ? Number(r.roiPercent) : null,
    profitMarginPercent: r.profitMarginPercent ? Number(r.profitMarginPercent) : null,
    qualifies: r.qualifies === "true" || r.qualifies === "1" || r.qualifies === true,
    rating: r.rating ? Number(r.rating) : null,
    reviewCount: r.reviewCount ? Number(r.reviewCount) : null,
    monthlySold: r.monthlySold ? Number(r.monthlySold) : null,
    isPrime: r.isPrime === "true" || r.isPrime === "1" || r.isPrime === true,
    url: r.url,
    reasons: r.reasons,
  }));

  const meta = {
    createdAt: jsonData.meta?.createdAt,
    costMatchedCount: jsonData.meta?.costMatchedCount ?? rows.filter(r => r.costBasis).length,
    runCount: jsonList.keys.length,
  };

  return { rows, meta };
}
