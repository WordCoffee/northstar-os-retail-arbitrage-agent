// verify-gilded-void.cjs — Playwright check of the Baroque "Gilded Void" stage.
// Localhost-only (dev server on 127.0.0.1:8101), per the Playwright-Test
// localhost exception. Verifies the 5 manifest components render and the
// modal curtain interaction works.
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8101/ui/baroque'
const SHOTS = 'C:/Users/T2Hol/AppData/Local/Temp/opencode'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

  await page.goto(BASE, { waitUntil: 'networkidle' })

  // 1. Backdrop + filter bank
  const backdrop = await page.locator('.ambient-backdrop').count()
  const shaft = await page.locator('.baroque-shaft').count()
  const filters = await page.locator('filter#micro-surface-noise').count()

  // 2. Control frame + banner + CTA
  const frame = await page.locator('.control-frame').count()
  const banner = await page.locator('.status-banner').count()
  const cta = await page.locator('.cta-trigger').count()
  const title = await page.locator('.baroque-title').textContent()

  // 3. Open the modal (curtain draw)
  await page.locator('.cta-trigger', { hasText: 'Raise the curtain' }).click()
  await page.waitForSelector('.notification-modal', { timeout: 5000 })
  const curtain = await page.locator('.baroque-curtain').count()
  const modalTitle = await page.locator('.baroque-modal-title').textContent()
  const dimmed = await page.locator('.ambient-backdrop.is-dimmed').count()
  await page.waitForTimeout(1000) // let curtain-draw finish
  await page.screenshot({ path: `${SHOTS}/gilded-void-modal.png` })

  // 4. Close the modal (curtain close)
  await page.locator('.notification-modal .cta-trigger', { hasText: 'Close the curtain' }).click()
  await page.waitForTimeout(1100) // let curtain-close finish
  const modalAfter = await page.locator('.notification-modal').count()
  const dimmedAfter = await page.locator('.ambient-backdrop.is-dimmed').count()
  await page.screenshot({ path: `${SHOTS}/gilded-void-stage.png` })

  // 5. Light-source tracking: move the mouse over the stage, read the readout
  await page.mouse.move(700, 450)
  await page.waitForTimeout(300)
  const readout = await page.locator('.baroque-readout').textContent()

  const results = {
    backdrop, shaft, filters, frame, banner, cta,
    title, curtain, modalTitle, dimmed, modalAfter, dimmedAfter,
    readout, errors,
  }
  console.log(JSON.stringify(results, null, 2))

  const pass =
    backdrop === 1 && shaft === 1 && filters === 1 &&
    frame === 1 && banner === 1 && cta >= 2 &&
    curtain === 1 && dimmed === 1 &&
    modalAfter === 0 && dimmedAfter === 0 &&
    errors.length === 0

  console.log(pass ? 'PASS' : 'FAIL')
  await browser.close()
  process.exit(pass ? 0 : 1)
}

main().catch((e) => {
  console.error('HARNESS ERROR:', e.message)
  process.exit(2)
})
