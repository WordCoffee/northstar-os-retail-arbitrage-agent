// Temporary verification: the locally-served built UI must not show sign-in.
// Owner directive 2026-10-29: remove sign-in until production is ready.
const { chromium } = require('playwright')

const BASE = process.argv[2] || 'http://127.0.0.1:8000/ui/'

;(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const apiCalls = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('requestfailed', (r) => errors.push(`REQFAIL ${r.url()} ${r.failure()?.errorText || ''}`))
  page.on('response', async (r) => {
    const u = r.url()
    if (u.includes('/api/')) apiCalls.push(`${r.status()} ${u}`)
  })

  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 60000 }).catch((e) => errors.push('GOTO ' + e.message))
  await page.waitForTimeout(2500)

  const finalUrl = page.url()
  const hasSigninForm = await page.locator('#signin-id').count()
  const hasSigninTitle = await page.locator('h2', { hasText: 'Sign In' }).count()
  const devBanner = await page.locator('[data-testid="dev-banner"]').count()
  const bodyText = ((await page.locator('body').innerText().catch(() => '')) || '').slice(0, 700)

  const out = {
    finalUrl,
    hasSigninForm,
    hasSigninTitle,
    devBanner,
    apiCalls: apiCalls.slice(0, 20),
    errors: errors.slice(0, 12),
    bodyText,
  }
  console.log(JSON.stringify(out, null, 2))

  const pass = !/\/sign-in/.test(finalUrl) && hasSigninForm === 0 && hasSigninTitle === 0
  console.log(pass ? 'PASS' : 'FAIL')
  await browser.close()
  process.exit(pass ? 0 : 1)
})().catch((e) => { console.error(e); process.exit(1) })
