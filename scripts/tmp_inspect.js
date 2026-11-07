const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.goto('http://127.0.0.1:8101/ui/home', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  const url = page.url();
  const html = await page.content();
  const banner = await page.locator('[data-testid="dev-banner"]').count();
  const shell = await page.locator('[data-testid="mb-shell"]').count();
  console.log('URL:', url);
  console.log('BANNER COUNT:', banner);
  console.log('MB-SHELL COUNT:', shell);
  console.log('ERRORS:', JSON.stringify(errors, null, 2));
  console.log('BODY SNIPPET:', html.substring(0, 2000));
  await browser.close();
})();
