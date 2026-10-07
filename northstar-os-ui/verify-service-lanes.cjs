const { chromium } = require('playwright')

// Functional check of the local creative service lanes: loads each room's
// "Local Lane" tab and runs its primary action against the REAL local API
// (/api/listing-forge/*, /api/ad-pilot/*, /api/social/*). Foundation reads are
// stubbed for the session shim only; creative API calls pass through untouched.
//
//   HARNESS_BASE_URL=http://127.0.0.1:8000/ui/ node verify-service-lanes.cjs

const UI = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0
let fail = 0
const ok = (c) => { pass++; console.log('PASS  ' + c) }
const no = (c, d) => { fail++; console.log('FAIL  ' + c + (d ? ' :: ' + d : '')) }

async function stub(page) {
  await page.addInitScript(() => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId: 'u-lane', orgId: 'org-lane', role: 'operator', env: 'production', previewId: '',
    }))
    window.__NORTHSTAR_LOCAL_DEV__ = true
    const FOUND = '/api/v1/foundation'
    const real = window.fetch.bind(window)
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return real(input, init)
      const route = url.split(FOUND)[1].split('?')[0]
      const json = (b, s = 200) => Promise.resolve(new Response(JSON.stringify(b), {
        status: s, headers: { 'Content-Type': 'application/json' },
      }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: 'u-lane', organizations: [], active_organization_id: null, role: 'operator', permissions: [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  })
}

async function lane(page, path, clickText, waitFor, label) {
  try {
    await page.goto(UI + path)
    await page.waitForSelector(`button:has-text("${clickText}")`, { timeout: 12000 })
    await page.click(`button:has-text("${clickText}")`)
    await page.waitForFunction(
      (t) => document.body.innerText.includes(t), waitFor, { timeout: 30000 })
    ok(`${label}: primary action produced a real result`)
  } catch (e) {
    no(`${label}: primary action produced a real result`,
      await page.evaluate(() => location.pathname + location.search).catch(() => String(e)))
  }
}

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } })
  await stub(page)

  await lane(page, 'listingforge?view=lane', 'Generate Local Draft', 'review required', 'ListingForge lane')
  await lane(page, 'adpilot?view=lane', 'Recommend Bid', 'Reasoning', 'AdPilot lane')
  await lane(page, 'socialpulse?view=lane', 'Generate Caption', 'Call to action', 'SocialPulse lane')

  await browser.close()
  console.log(`\nSERVICE-LANES RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

main().catch((e) => { console.error('FATAL', e); process.exit(2) })
