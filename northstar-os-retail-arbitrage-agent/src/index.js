import { runSearch } from './scrapers/amazonSearch.js';
import { scoreDeals } from './analyzers/dealScorer.js';
import { saveProducts, saveDeals } from './services/storageService.js';
import { alertTopDeals } from './services/alertService.js';

async function main() {
  console.log('Starting Northstar OS scan cycle...');

  const rawListings = await runSearch();
  saveProducts(rawListings);

  const deals = scoreDeals(rawListings);
  saveDeals(deals);

  await alertTopDeals(deals);

  console.log(`Scan complete. ${deals.length} qualifying deal(s) found.`);
}

main().catch(err => {
  console.error('Scan cycle failed:', err.message);
  process.exit(1);
});
