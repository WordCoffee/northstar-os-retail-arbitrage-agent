import { test, expect } from '@playwright/test';
import fs from 'fs';

test('home loads without console errors', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.goto('http://127.0.0.1:8101/ui/');
  await expect(page).toHaveTitle(/NorthstarOS/);

  // Either signed-in (chat-input) or sign-in page (signin-id) should be visible
  const chatInput = page.locator('[data-testid="chat-input"]');
  const signInId = page.locator('#signin-id');
  await expect(chatInput.or(signInId)).toBeVisible();

  // Write errors to file for debugging
  fs.writeFileSync('test-results/console-errors.json', JSON.stringify(consoleErrors, null, 2));

  // Filter out known non-critical errors
  const criticalErrors = consoleErrors.filter(
    (e) => !e.includes('favicon') && !e.includes('manifest') && !e.includes('ERR_CONNECTION_REFUSED') && !e.includes('proxy error') && !e.includes('429') && !e.includes('Too Many Requests')
  );
  if (criticalErrors.length > 0) {
    console.log('Critical console errors:', JSON.stringify(criticalErrors));
  }
  expect(criticalErrors).toHaveLength(0);
});

test('sign-in page loads', async ({ page }) => {
  await page.goto('http://127.0.0.1:8101/ui/sign-in');
  await expect(page.locator('#signin-id')).toBeVisible();
  await expect(page.locator('#signin-pw')).toBeVisible();
  await expect(page.locator('button[type="submit"]')).toBeVisible();
});