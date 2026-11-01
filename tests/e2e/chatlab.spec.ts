import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const VIEWS = ['orbital', 'comet', 'observatory', 'nebula', 'eclipse', 'asteroid', 'constellation', 'halo', 'deepfield', 'parallax']
const OUT = path.resolve('reports', 'theme_review', 'chatlab')
test.beforeAll(() => fs.mkdirSync(OUT, { recursive: true }))

test('ten complete chat interfaces, each with a composer', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('http://127.0.0.1:8124/chatlab/', { waitUntil: 'networkidle' })
  await expect(page.locator('#tabs button')).toHaveCount(10)
  for (const [i, id] of VIEWS.entries()) {
    await page.locator(`#tabs button:nth-child(${i + 1})`).click()
    await expect(page.locator('body')).toHaveAttribute('data-view', id)
    await expect(page.locator('main > .view.on')).toHaveCount(1)
    if (i === 2) console.log(await page.locator('main > .view.on').evaluate((e) => ({ name: e.dataset.name, text: e.innerText.slice(0, 200), sections: document.querySelectorAll('main > .view').length })))
    await expect(page.locator('main > .view.on .compose input')).toBeVisible()
    await page.screenshot({ path: path.join(OUT, `${String(i + 1).padStart(2, '0')}-${id}.png`) })
  }
  const cosmic = await page.evaluate(() => ({ asteroids: window.__cosmic.asteroids.length, stars: window.__cosmic.stars, spawns: window.__cosmic.spawns }))
  expect(cosmic.asteroids).toBeGreaterThan(4)
  expect(cosmic.stars).toBeGreaterThan(80)
})

test('meteors spawn from randomized runtime coordinates', async ({ page }) => {
  await page.goto('http://127.0.0.1:8124/chatlab/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(3200)
  const one = await page.evaluate(() => window.__cosmic.lastMeteor)
  expect(one).toBeTruthy()
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(3200)
  const two = await page.evaluate(() => window.__cosmic.lastMeteor)
  expect(two).toBeTruthy()
  expect(`${one.x},${one.y},${one.ang}`).not.toEqual(`${two.x},${two.y},${two.ang}`)
})
