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

  const internalShots = [
    ['#/socialpulse', '41-socialpulse-calendar.png'],
    ['#/socialpulse?view=campaigns', '41b-socialpulse-campaigns.png'],
    ['#/socialpulse?view=performance', '41c-socialpulse-performance.png'],
    ['#/creative-studio', '42-creative-library.png'],
    ['#/creative-studio?view=templates', '42b-creative-templates.png'],
    ['#/creative-studio?view=health', '42c-creative-health.png'],
    ['#/listings', '43-guardian-alerts.png'],
    ['#/listings?view=tracked', '43b-guardian-tracked.png'],
    ['#/listings?view=rules', '43c-guardian-rules.png'],
    ['#/keyword-tracker', '44-keyword-rankings.png'],
    ['#/keyword-tracker?view=terms', '44b-keyword-terms.png'],
    ['#/keyword-tracker?view=reports', '44c-keyword-reports.png'],
    ['#/monitoring', '45-monitoring-alerts.png'],
    ['#/monitoring?view=health', '45b-monitoring-health.png'],
    ['#/monitoring?view=sync', '45c-monitoring-sync.png'],
  ]
  const p1 = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  for (const [hash, file] of internalShots) {
    await p1.goto(BASE + hash)
    await p1.waitForTimeout(900)
    await p1.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  const adminShots = [
    ['#/beta-ops', '46-betaops-overview.png'],
    ['#/beta-ops/orgs', '46b-betaops-orgs.png'],
    ['#/beta-ops/cohorts', '46c-betaops-cohorts.png'],
    ['#/beta-ops/invites', '46d-betaops-invites.png'],
    ['#/beta-ops/support', '46e-betaops-support.png'],
    ['#/beta-ops/audit', '46f-betaops-audit.png'],
    ['#/admin', '47-admin-internal.png'],
  ]
  const p2 = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await stubAdmin(p2)
  await p2.goto(BASE + '#/beta-ops')
  await p2.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  for (const [hash, file] of adminShots) {
    await p2.evaluate(h => { location.hash = h }, hash)
    await p2.waitForTimeout(900)
    await p2.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
