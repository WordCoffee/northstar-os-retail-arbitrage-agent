// ═══════════════════════════════════════════════════════════════════════════
// LAYOUT PROBE — measures the U7 canvas workspace inside the workbench shell.
// Scratch tool (underscore = not part of the gate). Local loopback only.
// It exists because the first U7 screenshot showed a 26px-wide canvas: a class
// collision had turned every workspace into a fixed 372px box, and only a
// measurement made that obvious.
//
// Run:  node _probe-u7.cjs
// ═══════════════════════════════════════════════════════════════════════════
const { chromium } = require('playwright')
const BASE = 'http://127.0.0.1:8101/ui/'
async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await page.goto(BASE + 'workbench', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="canvas-workspace"]', { timeout: 45000 })
  await page.waitForTimeout(1200)
  const out = await page.evaluate(() => {
    const box = (sel) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const r = el.getBoundingClientRect()
      const s = getComputedStyle(el)
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), display: s.display, grid: s.gridTemplateColumns }
    }
    const outlet = document.querySelector('[data-testid="wb-outlet"]')
    return {
      outlet: { ...box('[data-testid="wb-outlet"]'), scrollW: outlet.scrollWidth, clientW: outlet.clientWidth, scrollLeft: outlet.scrollLeft },
      panel: box('[data-testid="wb-panel-design-studio"]'),
      pageHeader: box('[data-testid="wb-panel-design-studio"] .page-header'),
      root: box('[data-testid="canvas-workspace"]'),
      body: box('.cw-body'),
      side: box('[data-testid="cw-side"]'),
      zone: box('[data-testid="cw-canvas-zone"]'),
      insp: box('[data-testid="cw-panel"]'),
      stage: box('.cw-zone .stage'),
      canvas: box('[data-testid="stage-canvas"]'),
    }
  })
  console.log(JSON.stringify(out, null, 1))
  await browser.close()
}
main().catch((e) => { console.error(e); process.exit(2) })
