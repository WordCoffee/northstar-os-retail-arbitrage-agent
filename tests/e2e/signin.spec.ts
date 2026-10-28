import { test, expect } from '@playwright/test';

test('dev: /ui/sign-in redirects to /home in dev build', async ({ page }) => {
  await page.goto('/ui/sign-in');
  // Dev builds auto-navigate past sign-in; lands on /home after submit.
  await page.waitForURL('**/ui/home', { timeout: 15000 });
});

test('dev: no-click /ui/home shows mb-shell and DEV banner', async ({ page }) => {
  // Fresh context, no sign-in, no clicks — opens /ui/home directly.
  await page.goto('/ui/home');
  await expect(page.locator('[data-testid="mb-shell"]')).toBeVisible({ timeout: 30000 });
  await expect(page.locator('[data-testid="dev-banner"]')).toBeVisible({ timeout: 30000 });
  await expect(page.locator('[data-testid="dev-banner"]')).toContainText('DEV: AUTH DISABLED');
});
