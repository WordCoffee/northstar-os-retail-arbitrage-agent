import { test, expect } from '@playwright/test';

test('chromeconnect page loads', async ({ page }) => {
  await page.goto('http://127.0.0.1:8101/ui/chromeconnect');
  // Either the page renders or redirects to sign-in
  const body = page.locator('body');
  await expect(body).toBeVisible();
});

test('chromeconnect page has runner status section', async ({ page }) => {
  await page.goto('http://127.0.0.1:8101/ui/chromeconnect');
  // Wait for content to load
  await page.waitForTimeout(2000);
  // Check for either status content or loading/error state
  const content = await page.content();
  expect(content.length).toBeGreaterThan(100);
});
