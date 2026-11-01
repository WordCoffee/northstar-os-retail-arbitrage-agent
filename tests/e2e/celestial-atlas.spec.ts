import { test, expect } from '@playwright/test'

const VIEWS = ['orrery', 'observatory', 'nebula', 'eclipse', 'comet', 'halo', 'zenith', 'parallax', 'singularity', 'starchart']
const NAMES = ['Orrery', 'Observatory', 'Nebula Weave', 'Eclipse Console', 'Comet Trail',
  'Halo Dial', 'Zenith Type', 'Parallax Deck', 'Singularity Terminal', 'Star Chart']

test('the Celestial Atlas exposes ten distinct UI views', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('http://127.0.0.1:8124/atlas/', { waitUntil: 'networkidle' })
  await expect(page.locator('#views button')).toHaveCount(10)
  await expect(page.locator('main > .view')).toHaveCount(10)
  for (const [i, view] of VIEWS.entries()) {
    await page.locator(`#views button:nth-child(${i + 1})`).click()
    await expect(page.locator('#atlas')).toHaveAttribute('data-view', view)
    await expect(page.locator('main .view.on')).toHaveCount(1)
    const activeView = page.locator('main .view.on')
    await expect(activeView).toHaveAttribute('data-name', NAMES[i])
    await expect(activeView).toContainText(view === 'observatory' ? 'See the' : '')
    if (i > 0) await expect(page.locator('main .view').first()).toBeHidden()
    await expect(page.locator(`main .view.on .console`)).toBeVisible()
    await page.screenshot({ path: `reports/theme_review/atlas/${String(i + 1).padStart(2, '0')}-${view}.png` })
  }
})
