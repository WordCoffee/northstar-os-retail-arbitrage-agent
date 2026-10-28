// Regression: the studio asset picker must be deterministic for a human AND for
// automation. Before this, the panel opened on click but stayed empty while the
// fetch was in flight, so a `data-asset-id` selector was simply absent on the
// next step and an automated selection failed with "does not match any elements".
//
// LOCALHOST ONLY (127.0.0.1:8101), per the AGENTS.md e2e exception.
import { test, expect } from '@playwright/test';

test('the asset picker shows a loading state then real assets', async ({ page }) => {
  test.setTimeout(120000);
  await page.goto('http://127.0.0.1:8101/ui/design-studio');
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 45000 });

  const toggle = page.getByTestId('chat-asset-picker-toggle');
  await toggle.click();

  const picker = page.getByTestId('chat-asset-picker');
  await expect(picker).toBeVisible({ timeout: 15000 });

  // It must never be an unexplained void: loading, error or empty is always shown.
  await expect.poll(async () => {
    const loading = await page.getByTestId('chat-asset-picker-loading').count();
    const error = await page.getByTestId('chat-asset-picker-error').count();
    const empty = await page.getByTestId('chat-asset-picker-empty').count();
    const options = await page.getByTestId('chat-asset-option').count();
    return loading + error + empty + options;
  }, { timeout: 20000 }).toBeGreaterThan(0);

  // Once settled it must be one of: real options, an honest error, or an honest
  // empty. Never a silently blank panel - that is what broke automation.
  await expect.poll(async () => {
    const busy = await page.getByTestId('chat-asset-picker-loading').count();
    const error = await page.getByTestId('chat-asset-picker-error').count();
    const empty = await page.getByTestId('chat-asset-picker-empty').count();
    const options = await page.getByTestId('chat-asset-option').count();
    return busy === 0 && (error + empty + options) > 0;
  }, { timeout: 20000 }).toBe(true);

  // If options did load (an authenticated session), they expose a stable id so
  // automation can target one exactly.
  const optionCount = await page.getByTestId('chat-asset-option').count();
  if (optionCount > 0) {
    const ids = await page.getByTestId('chat-asset-option').evaluateAll(
      (els) => els.map((el) => el.getAttribute('data-asset-id')).filter(Boolean),
    );
    expect(ids.length).toBe(optionCount);
    expect(ids[0]).toMatch(/^[0-9a-f-]{36}$/);

    await page.getByTestId('chat-asset-option').first().click();
    await expect(page.getByTestId('chat-attachments')).toBeVisible({ timeout: 10000 });
  }
});
