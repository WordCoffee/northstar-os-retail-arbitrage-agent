const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function stubAdmin(page) {
  await page.addInitScript(() => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId: 'u-admin-cap', orgId: 'org-cap', role: 'platform_admin', env: 'production', previewId: '',
    }))
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
      if (route === '/me') return json({ user_id: 'u-admin-cap', organizations: [], active_organization_id: null, role: 'platform_admin', permissions: ['platform_admin'] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  })
}

async function main() {
  const browser = await chromium.launch()

  const shots = [
    ['#/admin', '53-admin-internal.png'],
    ['#/beta-ops', '54-betaops-overview.png'],
    ['#/beta-ops/orgs', '54b-betaops-orgs.png'],
    ['#/beta-ops/orgs/0001', '54c-betaops-org-detail.png'],
    ['#/beta-ops/invites', '54d-betaops-invites.png'],
    ['#/beta-ops/invites/INV-2026-09-25-0192', '54e-betaops-invite-detail.png'],
    ['#/beta-ops/cohorts', '54f-betaops-cohorts.png'],
    ['#/beta-ops/support', '54g-betaops-support.png'],
    ['#/beta-ops/lifecycle', '54h-betaops-lifecycle.png'],
    ['#/beta-ops/eligibility', '54i-betaops-eligibility.png'],
    ['#/beta-ops/audit', '54j-betaops-audit.png'],
    ['#/beta-ops/reports', '54k-betaops-reports.png'],
  ]

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await stubAdmin(page)
  await page.goto(BASE + '#/beta-ops')
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  for (const [hash, file] of shots) {
    await page.evaluate(h => { location.hash = h }, hash)
    await page.waitForTimeout(900)
    await page.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
