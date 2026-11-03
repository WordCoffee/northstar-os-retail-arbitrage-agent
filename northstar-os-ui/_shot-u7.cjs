// ═══════════════════════════════════════════════════════════════════════════
// VISUAL PROBE — the U7 canvas workspace inside the workbench shell.
// Scratch tool (underscore = not part of the gate). Local loopback only; the
// dev shim signs the session in, so no credential is read or carried here.
//
// Run:  node _shot-u7.cjs
// Writes: ../reports/ty/shots/u7-canvas-{desktop,mobile}.png
// ═══════════════════════════════════════════════════════════════════════════
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const OUT = __dirname + '/../reports/ty/shots'

async function shoot(browser, name, viewport, isMobile) {
  const ctx = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
    isMobile,
    hasTouch: isMobile,
  })
  const page = await ctx.newPage()
  const problems = []
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', (e) => problems.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', (r) => { if (r.status() >= 400) problems.push(`${r.status()} ${r.url().slice(0, 120)}`) })

  await page.goto(BASE + 'workbench', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('[data-testid="canvas-workspace"]', { timeout: 45000 })
  await page.waitForTimeout(1200)

  // Put the surface into a real state: a headline, a subhead, and the layers
  // panel open, so the shot shows the workspace working rather than empty.
  await page.getByTestId('cw-add-text').click()

  // Phones hide the inspector behind the layers button; open it before typing.
  const toggle = page.getByTestId('cw-panel-toggle')
  if (await toggle.isVisible()) {
    if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click()
  }
  await page.getByTestId('cw-panel-properties').click()
  await page.getByTestId('cw-text-input').fill('Lion\u2019s Mane')
  await page.getByTestId('cw-add-subhead').click()

  await page.getByTestId('cw-panel-layers').click()
  // Let the transient toast clear (ToastCenter TTL is 5 s), then frame the
  // canvas: on a phone that is the part worth looking at.
  await page.waitForTimeout(5600)
  await page.getByTestId('cw-canvas-zone').scrollIntoViewIfNeeded()
  await page.waitForTimeout(400)

  await page.screenshot({ path: `${OUT}/u7-canvas-${name}.png`, fullPage: false })
  const facts = await page.evaluate(() => {
    const zone = document.querySelector('[data-testid="cw-canvas-zone"]')
    const layers = document.querySelectorAll('[data-testid="cw-layer"]').length
    const canvases = zone ? zone.querySelectorAll('canvas').length : -1
    return {
      zoneBackground: zone ? getComputedStyle(zone).backgroundColor : null,
      canvasesInZone: canvases,
      layers,
      size: document.querySelector('[data-testid="cw-doc-size"]')?.textContent || null,
    }
  })
  console.log(`${name}:`, JSON.stringify(facts), problems.length ? `PROBLEMS: ${problems.slice(0, 4).join(' | ')}` : 'no console errors')
  await ctx.close()
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  await shoot(browser, 'desktop', { width: 1440, height: 900 }, false)
  await shoot(browser, 'mobile', { width: 390, height: 844 }, true)
  await browser.close()
}

main().catch((e) => { console.error('FATAL ' + e.message); process.exit(2) })
