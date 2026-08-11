import path from 'path';
import { normalizeAmazonRecord, dedupeAmazonRecords } from '../normalizers/amazonSearchNormalizer.js';
import { latestFileInDir, timestampForFile, readJson, writeJson } from '../lib/fsUtils.js';
import { paths } from '../lib/paths.js';
import { hasFlag } from '../lib/cli.js';

async function main() {
  const latestSnapshot = latestFileInDir(paths.snapshots, filePath => filePath.endsWith('.json'));

  if (!latestSnapshot) {
    throw new Error('No snapshot files found in data/snapshots. Run npm run search first.');
  }

  const raw = readJson(latestSnapshot);
  const normalized = raw.map(normalizeAmazonRecord);
  const deduped = dedupeAmazonRecords(normalized);

  const output = {
    meta: {
      sourceFile: latestSnapshot,
      rawCount: raw.length,
      normalizedCount: normalized.length,
      dedupedCount: deduped.length,
      createdAt: new Date().toISOString(),
    },
    rows: deduped,
  };

  if (hasFlag('--dry-run')) {
    console.log(JSON.stringify(output.meta, null, 2));
    return;
  }

  const outPath = path.join(paths.normalized, `normalized-${timestampForFile()}.json`);
  writeJson(outPath, output);
  console.log(`Saved normalized snapshot -> ${outPath}`);
}

main().catch(error => {
  console.error('Normalize failed:', error.message);
  process.exit(1);
});
