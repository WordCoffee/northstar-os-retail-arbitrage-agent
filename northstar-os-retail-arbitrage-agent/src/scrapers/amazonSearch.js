import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { scrapeDataset } from './brightDataClient.js';
import { config } from '../config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SNAPSHOT_DIR = path.join(__dirname, '../../data/snapshots');

async function runSearch() {
  const { keywords, marketplace, pagesToSearch } = config.search;

  if (keywords.length === 0) {
    console.error('No SEARCH_KEYWORDS configured in .env');
    process.exit(1);
  }

  console.log(`Searching ${keywords.length} keyword(s) on ${marketplace} ...`);

  const inputs = keywords.map(keyword => ({
    keyword,
    url: marketplace,
    pages_to_search: pagesToSearch,
  }));

  console.log('Bright Data inputs:', JSON.stringify(inputs, null, 2));

  const results = await scrapeDataset(inputs);
  console.log('Bright Data results received:', results.length);

  if (!fs.existsSync(SNAPSHOT_DIR)) {
    fs.mkdirSync(SNAPSHOT_DIR, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const outPath = path.join(SNAPSHOT_DIR, `scan-${timestamp}.json`);

  fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(`Saved ${results.length} raw record(s) -> ${outPath}`);

  return results;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  runSearch().catch(err => {
    console.error('Search failed:', err.message);
    process.exit(1);
  });
}

export { runSearch };