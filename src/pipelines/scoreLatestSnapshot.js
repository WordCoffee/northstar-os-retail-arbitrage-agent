import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import { scoreDeal } from '../analyzers/dealScorer.js';
import { config } from '../config.js';
import { latestFileInDir, readJson, timestampForFile, writeJson } from '../lib/fsUtils.js';
import { paths } from '../lib/paths.js';

function loadCostcoRows() {
  const csvPath = config.sources.costcoCsvPath;

  if (!fs.existsSync(csvPath)) {
    console.warn(`WARNING: Costco CSV not found at "${csvPath}". No cost basis will be available.`);
    console.warn('  Create the file or set COSTCO_CSV_PATH in .env. See data/costco-items.csv for the expected format.');
    return [];
  }

  const text = fs.readFileSync(csvPath, 'utf8').trim();
  if (!text) {
    console.warn(`WARNING: Costco CSV at "${csvPath}" is empty. No cost basis will be available.`);
    return [];
  }

  let rows;
  try {
    rows = parse(text, { columns: true, skip_empty_lines: true });
  } catch (err) {
    console.warn(`WARNING: Could not parse Costco CSV: ${err.message}. No cost basis will be available.`);
    return [];
  }

  if (rows.length === 0) {
    console.warn(`WARNING: Costco CSV has no data rows. No cost basis will be available.`);
  }

  return rows;
}

/**
 * Normalise a string for fuzzy matching: lowercase, strip punctuation,
 * collapse whitespace, and correct the common "Krikland" typo.
 */
function normaliseForMatch(str) {
  return String(str || '')
    .toLowerCase()
    .replace(/krikland/g, 'kirkland') // correct known CSV typo
    .replace(/[^a-z0-9\s]/g, ' ')    // strip punctuation
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Tokenise a normalised string into a Set of words.
 */
function tokenSet(str) {
  return new Set(normaliseForMatch(str).split(' ').filter(Boolean));
}

/**
 * Score how well catalogTitle matches amazonTitle using token overlap.
 * Returns a value in [0, 1]; higher is better.
 */
function titleMatchScore(amazonTitle, catalogTitle) {
  const amazonTokens = tokenSet(amazonTitle);
  const catalogTokens = tokenSet(catalogTitle);

  if (amazonTokens.size === 0 || catalogTokens.size === 0) return 0;

  let matches = 0;
  for (const t of catalogTokens) {
    if (amazonTokens.has(t)) matches++;
  }

  // Jaccard-like: intersection / union of the smaller set to the larger
  return matches / Math.max(amazonTokens.size, catalogTokens.size);
}

const MATCH_SCORE_THRESHOLD = 0.35; // require at least 35% token overlap

function inferCostBasis(row, catalogRows) {
  if (catalogRows.length === 0) return null;

  const amazonTitle = row.title || '';
  let bestScore = 0;
  let bestMatch = null;

  for (const item of catalogRows) {
    const catalogTitle = item.item_name || item.title || item.name || '';
    const score = titleMatchScore(amazonTitle, catalogTitle);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = item;
    }
  }

  if (bestScore < MATCH_SCORE_THRESHOLD || !bestMatch) return null;

  const price = Number(bestMatch.costco_cost || bestMatch.price || bestMatch.cost || bestMatch.unit_price);
  return Number.isFinite(price) && price > 0 ? price : null;
}

function toCsvRow(r) {
  return {
    asin: r.asin,
    title: r.title,
    brand: r.brand,
    price: r.price,
    costBasis: r.costBasis,
    estimatedProfit: r.estimatedProfit,
    roiPercent: r.roiPercent,
    profitMarginPercent: r.profitMarginPercent,
    qualifies: r.qualifies,
    rating: r.rating,
    reviewCount: r.reviewCount,
    monthlySold: r.monthlySold,
    isPrime: r.isPrime,
    url: r.url,
    reasons: r.reasons?.join('; ') || '',
  };
}

async function main() {
  const latestNormalized = latestFileInDir(paths.normalized, filePath => filePath.endsWith('.json'));

  if (!latestNormalized) {
    throw new Error('No normalized file found. Run npm run normalize first.');
  }

  const normalized = readJson(latestNormalized);
  const catalogRows = loadCostcoRows();
  const scoredRows = normalized.rows.map(row => scoreDeal(row, inferCostBasis(row, catalogRows)));

  const qualifiedRows = scoredRows.filter(r => r.qualifies);
  const matchedRows = scoredRows.filter(r => r.costBasis !== null);

  // Sort: qualified first (by ROI desc), then unqualified-but-costed (by ROI desc)
  const sortedRows = [
    ...qualifiedRows.sort((a, b) => (b.roiPercent || -Infinity) - (a.roiPercent || -Infinity)),
    ...scoredRows
      .filter(r => !r.qualifies)
      .sort((a, b) => (b.roiPercent || -Infinity) - (a.roiPercent || -Infinity)),
  ];

  const output = {
    meta: {
      sourceFile: latestNormalized,
      createdAt: new Date().toISOString(),
      rowCount: scoredRows.length,
      costMatchedCount: matchedRows.length,
      qualifiedCount: qualifiedRows.length,
    },
    rows: sortedRows,
  };

  const outPath = path.join(paths.scored, `scored-${timestampForFile()}.json`);
  writeJson(outPath, output);
  console.log(`Saved scored snapshot -> ${outPath}`);

  // Top-deals CSV: qualified first, then fill remaining slots with best-ROI unqualified (costed only)
  const topCount = config.export.topDealsCount;
  const topDeals = qualifiedRows
    .sort((a, b) => (b.roiPercent || -Infinity) - (a.roiPercent || -Infinity))
    .slice(0, topCount);

  if (topDeals.length < topCount) {
    const remaining = topCount - topDeals.length;
    const fillers = matchedRows
      .filter(r => !r.qualifies)
      .sort((a, b) => (b.roiPercent || -Infinity) - (a.roiPercent || -Infinity))
      .slice(0, remaining);
    topDeals.push(...fillers);
  }

  const csvPath = path.join(paths.scored, `top-deals-${timestampForFile()}.csv`);
  fs.writeFileSync(csvPath, stringify(topDeals.map(toCsvRow), { header: true }));

  // Console summary
  console.log('');
  console.log('--- Score Summary ---');
  console.log(`  Total rows:         ${scoredRows.length}`);
  console.log(`  Cost-matched rows:  ${matchedRows.length} (out of ${scoredRows.length})`);
  console.log(`  Qualified deals:    ${qualifiedRows.length}`);
  console.log(`  Top-deals CSV rows: ${topDeals.length}`);
  console.log(`Saved top-deals CSV  -> ${csvPath}`);
}

main().catch(error => {
  console.error('Scoring failed:', error.message);
  process.exit(1);
});
