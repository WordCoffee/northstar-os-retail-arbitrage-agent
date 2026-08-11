import path from 'path';
import { pathToFileURL } from 'url';
import { scrapeDataset } from './brightDataClient.js';
import { config, requireEnv } from '../config.js';
import { ensureDir, timestampForFile, writeJson } from '../lib/fsUtils.js';
import { paths } from '../lib/paths.js';

async function runSearch() {
  requireEnv(['BRIGHTDATA_API_KEY', 'SEARCH_KEYWORDS']);

  const { keywords, marketplace, pagesToSearch } = config.search;

  console.log(`Searching ${keywords.length} keyword(s) on ${marketplace} ...`);

  const inputs = keywords.map(keyword => ({
    keyword,
    url: marketplace,
    pages_to_search: pagesToSearch,
  }));

  console.log('Bright Data inputs:', JSON.stringify(inputs, null, 2));

  const results = await scrapeDataset(inputs);
  console.log('Bright Data results received:', results.length);

  ensureDir(paths.snapshots);
  const outPath = path.join(paths.snapshots, `scan-${timestampForFile()}.json`);
  writeJson(outPath, results);

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
