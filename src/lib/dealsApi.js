import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const SCORED_DIR = path.join(PROJECT_ROOT, 'data/scored');

export function findLatestTopDealsCsv() {
  if (!fs.existsSync(SCORED_DIR)) return null;
  const files = fs.readdirSync(SCORED_DIR)
    .filter(f => f.startsWith('top-deals-') && f.endsWith('.csv'))
    .map(f => ({ name: f, mtime: fs.statSync(path.join(SCORED_DIR, f)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  return files[0] ? path.join(SCORED_DIR, files[0].name) : null;
}

export function findLatestScoredJson() {
  if (!fs.existsSync(SCORED_DIR)) return null;
  const files = fs.readdirSync(SCORED_DIR)
    .filter(f => f.startsWith('scored-') && f.endsWith('.json'))
    .map(f => ({ name: f, mtime: fs.statSync(path.join(SCORED_DIR, f)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  return files[0] ? path.join(SCORED_DIR, files[0].name) : null;
}

export function countScoredRuns() {
  if (!fs.existsSync(SCORED_DIR)) return 0;
  return fs.readdirSync(SCORED_DIR).filter(f => f.startsWith('scored-') && f.endsWith('.json')).length;
}

export function loadLatestDeals() {
  const csvPath = findLatestTopDealsCsv();
  const jsonPath = findLatestScoredJson();

  if (!csvPath || !jsonPath) {
    return { rows: [], meta: { createdAt: null, costMatchedCount: 0, runCount: 0 } };
  }

  const csvText = fs.readFileSync(csvPath, 'utf8');
  const jsonData = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

  const rows = parse(csvText, { columns: true, skip_empty_lines: true }).map(r => ({
    asin: r.asin,
    title: r.title,
    brand: r.brand,
    price: r.price ? Number(r.price) : null,
    costBasis: r.costBasis ? Number(r.costBasis) : null,
    estimatedProfit: r.estimatedProfit ? Number(r.estimatedProfit) : null,
    roiPercent: r.roiPercent ? Number(r.roiPercent) : null,
    profitMarginPercent: r.profitMarginPercent ? Number(r.profitMarginPercent) : null,
    qualifies: r.qualifies === 'true' || r.qualifies === '1' || r.qualifies === true,
    rating: r.rating ? Number(r.rating) : null,
    reviewCount: r.reviewCount ? Number(r.reviewCount) : null,
    monthlySold: r.monthlySold ? Number(r.monthlySold) : null,
    isPrime: r.isPrime === 'true' || r.isPrime === '1' || r.isPrime === true,
    url: r.url,
    reasons: r.reasons,
  }));

  const meta = {
    createdAt: jsonData.meta?.createdAt,
    costMatchedCount: jsonData.meta?.costMatchedCount ?? rows.filter(r => r.costBasis).length,
    runCount: countScoredRuns(),
  };

  return { rows, meta };
}