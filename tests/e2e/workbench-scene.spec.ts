// U5 — the scene engine. Localhost only (Playwright Test is the sanctioned path
// for tests/e2e against 127.0.0.1).

import { test, expect } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { window.sessionStorage.removeItem('ns-ux-tabs') } catch { /* ignore */ }
  })
})

test('exactly one scene canvas is mounted and it declares a valid tier', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('scene-host')).toBeVisible()

  await expect(page.locator('canvas')).toHaveCount(1)
  const tier = await page.getByTestId('scene-host').getAttribute('data-tier')
  expect(['cinematic', 'reduced', 'still']).toContain(tier)

  // The scene must never be the top element anywhere — it is a backdrop.
  const swallowed = await page.evaluate(() => {
    const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2)
    return !!(el && el.closest('[data-testid="scene-host"]'))
  })
  expect(swallowed).toBe(false)
})

test('the loop runs, pauses when hidden and resumes', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })

  const tier = await page.getByTestId('scene-host').getAttribute('data-tier')
  await page.waitForFunction(() => !!window.__northstarScene, null, { timeout: 30000 })
  const before = await page.evaluate(() => window.__northstarScene.frames)
  await page.waitForTimeout(400)
  const after = await page.evaluate(() => window.__northstarScene.frames)

  if (tier === 'still') {
    // One frame is the whole scene on this tier.
    expect(before).toBe(1)
    expect(after).toBe(1)
  } else {
    expect(after).toBeGreaterThan(before)
  }

  // Simulate a background tab: the browser fires visibilitychange, the scene
  // must stop painting (a hidden tab costs nothing).
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(await page.evaluate(() => window.__northstarScene.paused)).toBe(true)
  const pausedFrames = await page.evaluate(() => window.__northstarScene.frames)
  await page.waitForTimeout(300)
  expect(await page.evaluate(() => window.__northstarScene.frames)).toBe(pausedFrames)

  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(await page.evaluate(() => window.__northstarScene.paused)).toBe(false)
})

test('workspace events re-tone the scene and unmounting stops it', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await page.waitForFunction(() => !!window.__northstarScene, null, { timeout: 30000 })
  const host = page.getByTestId('scene-host')

  await expect(host).toHaveAttribute('data-mode', 'calm')
  await page.evaluate(() => window.__northstarScene.emit('working'))
  await expect(host).toHaveAttribute('data-mode', 'intense')
  await page.evaluate(() => window.__northstarScene.emit('done'))
  await expect(host).toHaveAttribute('data-mode', 'flare')
  await page.evaluate(() => window.__northstarScene.emit('error'))
  await expect(host).toHaveAttribute('data-mode', 'subdued')

  // Leaving the shell unmounts the scene: no canvas, no dev hook, no loop.
  await page.goto('/ui/home')
  await expect(page.getByTestId('workbench-shell')).toHaveCount(0)
  expect(await page.evaluate(() => typeof window.__northstarScene)).toBe('undefined')
})
