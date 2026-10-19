// ═══════════════════════════════════════════════════════════════════════════
// VISUAL PROBE — screenshot the real Simple-mode surface + the raw background.
// Scratch tool (underscore = not part of the gate). Signs in with the local
// operator account so the shot is the real product, not a stub.
//
// Run:  NS_TEST_PASSWORD=<pw> node _shot-simple.cjs
// Writes: screenshots/v42-*.png
// ═══════════════════════════════════════════════════════════════════════════
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
// No default: this is a real account password, so the probe fails closed like
// verify-live-signin.cjs rather than carrying a credential in the tree.
const PW = process.env.NS_TEST_PASSWORD
const OUT = __dirname + '/screenshots'

async function main() {
  if (!PW) {
    console.error('NS_TEST_PASSWORD is required (the local operator account password).')
    process.exit(2)
  }
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 })
  const page = await ctx.newPage()
  const problems = []
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', (e) => problems.push('pageerror: ' + String(e).slice(0, 200)))

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 30000 })
  await page.waitForTimeout(3500)                       // fonts + canvas warm-up

  await page.screenshot({ path: OUT + '/v42-home.png' })
  console.log('wrote v42-home.png')

  // Measure BEFORE stripping the chrome (element widths matter).
  const metrics = await page.evaluate(() => {
    const g = (sel) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const s = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return { fs: s.fontSize, lh: s.lineHeight, color: s.color, w: Math.round(r.width) }
    }
    return {
      userBubble: g('.mb-shell .chat-msg.user .chat-bubble'),
      assistantBubble: g('.mb-shell .chat-msg.assistant .chat-bubble'),
      composer: g('.mb-shell .chat-composer-box textarea'),
      chip: g('.mb-focus-chip'),
      stream: g('.mb-shell .chat-stream'),
      head: g('.mb-shell .chat-head h2'),
      toolRow: g('.mb-shell .chat-tool-name'),
      panelBg: getComputedStyle(document.querySelector('.mb-shell .chat-shell')).backgroundColor,
    }
  })
  console.log('metrics:', JSON.stringify(metrics, null, 1))

  // Empty state — what the operator sees before the first message.
  await page.click('[data-testid="chat-new"]').catch(() => {})
  await page.waitForTimeout(900)
  await page.screenshot({ path: OUT + '/v42-empty.png' })
  console.log('wrote v42-empty.png')

  // Raw background: strip the chrome so the shader can be judged on its own.
  await page.evaluate(() => {
    for (const sel of ['.mb-shell .chat-shell', '.mb-header', '.mb-scrim', '.top-nav', '.hw-overlay']) {
      document.querySelectorAll(sel).forEach((el) => { el.style.display = 'none' })
    }
    const c = document.querySelector('.cosmic-canvas')
    if (c) window.__cosmic = { fallback: c.dataset.cosmicFallback || null, w: c.width, h: c.height }
  })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: OUT + '/v42-background.png' })
  const c = await page.evaluate(() => window.__cosmic)
  console.log('wrote v42-background.png ::', JSON.stringify(c))

  if (problems.length) console.log('PROBLEMS:\n  ' + problems.slice(0, 8).join('\n  '))
  else console.log('no console errors')

  await browser.close()
}

main().catch((e) => { console.error('FATAL ' + e.message); process.exit(2) })
