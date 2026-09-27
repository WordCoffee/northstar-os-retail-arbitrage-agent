const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const shotsDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(shotsDir)) fs.mkdirSync(shotsDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') console.log(`[ERROR] ${msg.text()}`);
  });
  page.on('pageerror', err => console.log(`[PAGEERROR] ${err.message}`));

  const screenshots = [
    { name: '1-command-center', url: 'http://127.0.0.1:8104/ui/#/home', desc: 'Command Center desktop with suite rail' },
    { name: '2-sourcescout', url: 'http://127.0.0.1:8104/ui/#/product-finder', desc: 'SourceScout workbench desktop' },
    { name: '4-golden-goose', url: 'http://127.0.0.1:8104/ui/#/golden-goose', desc: 'Golden Goose Finder review desk' },
    { name: '5-listingforge', url: 'http://127.0.0.1:8104/ui/#/listingforge', desc: 'ListingForge workspace' },
    { name: '6-adpilot', url: 'http://127.0.0.1:8104/ui/#/adpilot', desc: 'AdPilot workspace' },
    { name: '7-profitability', url: 'http://127.0.0.1:8104/ui/#/profitability', desc: 'Profitability Dashboard' },
    { name: '7b-profitability-scenario', url: 'http://127.0.0.1:8104/ui/#/profitability?view=scenario', desc: 'Profitability Scenario Calculator subview' },
    { name: '8-commerce-ops', url: 'http://127.0.0.1:8104/ui/#/commerce-ops', desc: 'Commerce Ops workflow room' },
    { name: '8b-commerce-ops-workflow', url: 'http://127.0.0.1:8104/ui/#/commerce-ops/CO-01', desc: 'Commerce Ops workflow detail (:id)' },
    { name: '9-autothink', url: 'http://127.0.0.1:8104/ui/#/autothink', desc: 'AutothinK workspace' },
    { name: '9b-autothink-composer', url: 'http://127.0.0.1:8104/ui/#/autothink?view=composer', desc: 'AutothinK Composer subview' },
    { name: '10-customer-workspace', url: 'http://127.0.0.1:8104/ui/#/customer-workspace', desc: 'Customer Workspace home' },
    { name: '10b-customer-workspace-services', url: 'http://127.0.0.1:8104/ui/#/customer-workspace?view=services', desc: 'Customer Workspace entitled services' },
    { name: '11-beta-ops', url: 'http://127.0.0.1:8104/ui/#/beta-ops', desc: 'Beta Operations overview' },
    { name: '13-listing-guardian', url: 'http://127.0.0.1:8104/ui/#/listings', desc: 'Listing Guardian alert room' },
    { name: '14-keyword-tracker', url: 'http://127.0.0.1:8104/ui/#/keyword-tracker', desc: 'Keyword Tracker rankings room' },
    { name: '15-competitor-monitor', url: 'http://127.0.0.1:8104/ui/#/competitor-monitor', desc: 'Competitor Monitor landscape room' },
    { name: '16-socialpulse', url: 'http://127.0.0.1:8104/ui/#/socialpulse', desc: 'SocialPulse calendar room' },
    { name: '17-creative-studio', url: 'http://127.0.0.1:8104/ui/#/creative-studio', desc: 'Creative Studio library room' },
    { name: '18-memory-bank', url: 'http://127.0.0.1:8104/ui/#/memory-bank', desc: 'Memory Bank topics room' },
    { name: '19-shared-data-layer', url: 'http://127.0.0.1:8104/ui/#/shared-data', desc: 'Shared Data Layer sources room' },
    { name: '20-provider-adapters', url: 'http://127.0.0.1:8104/ui/#/provider-adapters', desc: 'Provider Adapters status room' },
    { name: '21-master-brain', url: 'http://127.0.0.1:8104/ui/#/master-brain', desc: 'Master Brain sessions room' },
    { name: '22-monitoring', url: 'http://127.0.0.1:8104/ui/#/monitoring', desc: 'Monitoring alerts room' },
  ];

  for (const s of screenshots) {
    await page.goto(s.url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(6000);
    await page.screenshot({ path: path.join(shotsDir, s.name + '.png'), fullPage: false });
    console.log(`Screenshot: ${s.name} — ${s.desc}`);
  }

  // SourceScout mobile
  const mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const mobilePage = await mobileCtx.newPage();
  await mobilePage.goto('http://127.0.0.1:8104/ui/#/product-finder', { waitUntil: 'networkidle' });
  await mobilePage.waitForTimeout(6000);
  await mobilePage.screenshot({ path: path.join(shotsDir, '3-sourcescout-mobile.png'), fullPage: false });
  console.log('Screenshot: 3-sourcescout-mobile — SourceScout workbench mobile');

  // Mobile Tools sheet
  await mobilePage.goto('http://127.0.0.1:8104/ui/#/home', { waitUntil: 'networkidle' });
  await mobilePage.waitForTimeout(3000);
  // Click the Tools button in mobile bottom nav (5th item)
  await mobilePage.click('.mobile-bottom-nav-item:nth-child(5)');
  await mobilePage.waitForTimeout(2000);
  await mobilePage.screenshot({ path: path.join(shotsDir, '12-mobile-tools-sheet.png'), fullPage: false });
  console.log('Screenshot: 12-mobile-tools-sheet — Mobile Tools sheet');

  await browser.close();
})();
