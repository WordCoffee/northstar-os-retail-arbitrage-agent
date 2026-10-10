// Verification for the dev sign-in fix. Run: node tools/_repro-signin.cjs
const { chromium } = require('playwright')

const BASE = process.env.REPRO_BASE || 'http://127.0.0.1:8101/ui/'

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
  const page = await ctx.newPage()
  const rejections = []
  const pageerrors = []
  page.on('pageerror', (e) => pageerrors.push(String(e).slice(0, 200)))
  await page.addInitScript(() => {
    window.__rejections = []
    window.addEventListener('unhandledrejection', (e) => window.__rejections.push(String(e.reason)))
  })

  console.log('=== TEST A: demo shim creds against a containerized backend (must fail VISIBLY) ===')
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 45000 })
  await page.waitForTimeout(2500)
  await page.click('form button[type="submit"]')
  await page.waitForTimeout(3000)
  const a = await page.evaluate(() => ({
    path: location.pathname,
    alert: document.querySelector('[role="alert"]')?.textContent || null,
    devSession: localStorage.getItem('ns-dev-session'),
  }))
  console.log('   path:', a.path)
  console.log('   alert:', a.alert ? a.alert.slice(0, 180) : 'NONE (defect: silent failure)')
  console.log(a.path === '/ui/sign-in' && a.alert ? '   PASS: failure is explicit, not silent' : '   FAIL: silent or unexpected state')

  console.log('=== TEST B: real local account (t2/T2holdings) ===')
  await page.fill('#signin-id', 't2')
  await page.fill('#signin-pw', 'T2holdings')
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    console.log('   PASS: navigated to /ui/home')
  } catch {
    console.log('   FAIL: still at', await page.evaluate(() => location.pathname), await page.evaluate(() => document.querySelector('[role="alert"]')?.textContent || 'no alert'))
  }
  await page.waitForTimeout(2500)
  console.log('   settled path (must still be /ui/home):', await page.evaluate(() => location.pathname))

  console.log('   reload persistence:')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3500)
  console.log('   after reload path:', await page.evaluate(() => location.pathname))

  console.log('pageerrors:', pageerrors.length ? pageerrors : 'none')
  console.log('rejections:', await page.evaluate(() => window.__rejections).catch(() => 'n/a'))
  await browser.close()
}

main().catch((e) => { console.error('REPRO FATAL', e); process.exit(2) })
