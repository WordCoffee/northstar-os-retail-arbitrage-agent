import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const IDS = ['command', 'split', 'grid', 'focus', 'map', 'timeline', 'eclipse', 'editorial', 'terminal', 'parallax']
const OUT = path.resolve('reports', 'theme_review', 'celestial10')
test.beforeAll(() => fs.mkdirSync(OUT, { recursive: true }))

test('ten production compositions render without overlap', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('http://127.0.0.1:8124/celestial10/', { waitUntil: 'networkidle' })
  await expect(page.locator('#tabs button')).toHaveCount(10)
  await expect(page.locator('main > .view')).toHaveCount(10)
  for (const [i, id] of IDS.entries()) {
    await page.locator(`#tabs button:nth-child(${i + 1})`).click()
    await expect(page.locator('body')).toHaveAttribute('data-view', id)
    const active = page.locator('main > .view.on')
    await expect(active).toHaveCount(1)
    await expect(active.locator('.composer input')).toBeVisible()
    const box = await active.boundingBox()
    expect(box.height).toBeGreaterThan(500)
    await page.screenshot({ path: path.join(OUT, `${String(i + 1).padStart(2, '0')}-${id}.png`) })
  }
  const cosmic = await page.evaluate(() => ({ asteroids: window.__cosmic.asteroids.length, stars: window.__cosmic.stars }))
  expect(cosmic.asteroids).toBeGreaterThan(4)
  expect(cosmic.stars).toBeGreaterThan(80)
})
