const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function stub(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    const dev = role === 'signedout'
      ? { userId: '', orgId: '', role: '', env: 'production', previewId: '' }
      : { userId, orgId: 'org-acc', role, env: 'production', previewId: '' }
    localStorage.setItem('ns-dev-session', JSON.stringify(dev))
    localStorage.removeItem('ns-access-token')
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    window.fetch = (input) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      window.__stubCalls.push(route)
      const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: userId, organizations: [], active_organization_id: null, role, permissions: role === 'platform_admin' ? ['platform_admin'] : [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, { role, userId })
}

async function settle(page) {
  await page.goto(BASE)
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(500)
}

async function run() {
  const browser = await chromium.launch()

  const shots = [
    { role: 'platform_admin', user: 'u-admin', vp: { width: 1440, height: 900 }, hash: '#/product-finder', file: '55-sourcescout-desktop.png' },
    { role: 'operator', user: 'u-op', vp: { width: 1440, height: 900 }, hash: '#/socialpulse?view=queue', file: '55b-socialpulse-desktop.png' },
    { role: 'operator', user: 'u-op', vp: { width: 1440, height: 900 }, hash: '#/creative-studio?view=assets', file: '55c-creative-desktop.png' },
    { role: 'operator', user: 'u-op', vp: { width: 1440, height: 900 }, hash: '#/listings?view=history', file: '55d-guardian-desktop.png' },
    { role: 'operator', user: 'u-op', vp: { width: 1440, height: 900 }, hash: '#/keyword-tracker?view=coverage', file: '55e-keyword-desktop.png' },
    { role: 'operator', user: 'u-op', vp: { width: 1440, height: 900 }, hash: '#/monitoring?view=health', file: '55f-monitoring-desktop.png' },
    { role: 'platform_admin', user: 'u-admin', vp: { width: 1440, height: 900 }, hash: '#/admin', file: '55g-admin-desktop.png' },
    { role: 'platform_admin', user: 'u-admin', vp: { width: 1440, height: 900 }, hash: '#/beta-ops', file: '55h-betaops-desktop.png' },
    { role: 'customer', user: 'u-cust', vp: { width: 1440, height: 900 }, hash: '#/customer-workspace?view=services', file: '55i-customer-desktop.png' },

    { role: 'operator', user: 'u-op', vp: { width: 390, height: 844 }, hash: '#/product-finder', file: '56-sourcescout-mobile.png' },
    { role: 'operator', user: 'u-op', vp: { width: 390, height: 844 }, hash: '#/socialpulse?view=queue', file: '56b-socialpulse-mobile.png' },
    { role: 'operator', user: 'u-op', vp: { width: 390, height: 844 }, hash: '#/monitoring?view=health', file: '56c-monitoring-mobile.png' },
    { role: 'platform_admin', user: 'u-admin', vp: { width: 390, height: 844 }, hash: '#/beta-ops', file: '56d-betaops-mobile.png' },
    { role: 'customer', user: 'u-cust', vp: { width: 390, height: 844 }, hash: '#/customer-workspace?view=services', file: '56e-customer-mobile.png' },
  ]

  for (const s of shots) {
    const ctx = await browser.newContext({ viewport: s.vp })
    const page = await ctx.newPage()
    await stub(page, s.role, s.user)
    await settle(page)
    await page.evaluate(h => { location.hash = h }, s.hash)
    await page.waitForTimeout(800)
    await page.screenshot({ path: OUT + '/' + s.file, fullPage: true })
    await ctx.close()
  }

  // mobile operator tools sheet
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const page = await ctx.newPage()
  await stub(page, 'operator', 'u-op')
  await settle(page)
  await page.evaluate(() => { location.hash = '#/home' })
  await page.waitForTimeout(600)
  await page.click('.mobile-bottom-nav-item:has-text("Tools")').catch(() => {})
  await page.waitForSelector('.tools-sheet', { timeout: 4000 }).catch(() => {})
  await page.screenshot({ path: OUT + '/56f-operator-tools-mobile.png', fullPage: false })
  await ctx.close()

  await browser.close()
  console.log('CAPTURE DONE')
}

run().catch(e => { console.error(e); process.exit(1) })
