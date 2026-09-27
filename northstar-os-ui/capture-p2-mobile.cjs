const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function stub(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({ userId, orgId: 'org-p2', role, env: 'production', previewId: '' }))
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

async function main() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } })
  const page = await ctx.newPage()
  await stub(page, 'operator', 'u-op')
  await page.goto(BASE)
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.waitForTimeout(500)

  const shots = [
    ['#/creative-studio', '57-creative-briefs-375.png'],
    ['#/creative-studio?view=variants', '57b-creative-variants-375.png'],
    ['#/creative-studio?view=assets', '57c-creative-assets-375.png'],
    ['#/creative-studio?view=exports', '57d-creative-exports-375.png'],
    ['#/creative-studio?view=library', '57e-creative-library-375.png'],
    ['#/listings?view=diffs', '57f-guardian-diffs-375.png'],
    ['#/listings?view=history', '57g-guardian-history-375.png'],
    ['#/provider-adapters', '57h-provider-adapters-375.png'],
  ]
  for (const [hash, file] of shots) {
    await page.evaluate(h => { location.hash = h }, hash)
    await page.waitForTimeout(800)
    await page.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
