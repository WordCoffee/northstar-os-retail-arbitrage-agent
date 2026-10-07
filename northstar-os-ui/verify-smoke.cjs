const { chromium } = require('playwright')

// Path routing (P2-T3): BrowserRouter basename /ui. BASE always ends in /ui/.
const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0
let fail = 0

function ok(ctx) { pass++; console.log('PASS  ' + ctx) }
function no(ctx, detail) { fail++; console.log('FAIL  ' + ctx + (detail ? ' :: ' + detail : '')) }

// F4: internal rooms require an authenticated session. Stub the local
// development identity shim (operator) so the rooms under test render.
async function stubSession(page, role = 'operator', userId = 'u-smoke-1') {
  await page.addInitScript(({ role, userId }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId, orgId: 'org-smoke', role, env: 'production', previewId: '',
    }))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    window.fetch = (input) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      window.__stubCalls.push(route)
      const json = (body, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(body), {
          status, headers: { 'Content-Type': 'application/json' },
        }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({
        user_id: userId, organizations: [], active_organization_id: null, role,
        permissions: role === 'platform_admin' ? ['platform_admin'] : [],
      })
      if (route === '/environment') return json({
        environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false,
      })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, { role, userId })
}

function urlFor(route) { return BASE + route.replace(/^\//, '') }

async function expectMarker(page, marker, ctx) {
  try {
    await page.waitForFunction(m => document.body.innerText.includes(m), marker, { timeout: 7000 })
    ok(ctx + ' [marker: "' + marker + '"]')
  } catch {
    no(ctx, 'marker "' + marker + '" not found, url=' + page.url() + ' path=' + await page.evaluate(() => location.pathname + location.search))
  }
}

async function expectPath(page, expected, ctx) {
  try {
    await page.waitForFunction(p => (location.pathname + location.search) === p, expected, { timeout: 5000 })
    ok(ctx + ' [path: ' + expected + ']')
  } catch {
    no(ctx, 'expected ' + expected + ' got ' + await page.evaluate(() => location.pathname + location.search))
  }
}

async function expectToast(page, text, ctx) {
  try {
    await page.waitForSelector('.toast-item', { timeout: 5000 })
    await page.waitForFunction(t => Array.from(document.querySelectorAll('.toast-item')).some(e => e.textContent.includes(t)), text, { timeout: 4000 })
    ok(ctx + ' [toast]')
  } catch {
    no(ctx, 'toast not found')
  }
}

async function run() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
  await stubSession(page, 'operator', 'u-smoke-1')

  // ---- deep links (path routing) ----
  const deepLinks = [
    ['/home?view=exceptions', 'for routing', 'deep /home?view=exceptions'],
    ['/socialpulse?view=composer', 'Platform Preview', 'deep /socialpulse?view=composer'],
    ['/socialpulse?view=presets', 'Brand Voice', 'deep /socialpulse?view=presets'],
    ['/socialpulse?view=queue', 'Drafts', 'deep /socialpulse?view=queue'],
    ['/creative-studio?view=variants', 'Add Variant', 'deep /creative-studio?view=variants'],
    ['/creative-studio?view=exports', 'Bundle Builder', 'deep /creative-studio?view=exports'],
    ['/creative-studio?view=mockups', 'Exact-Text Mockups', 'deep /creative-studio?view=mockups'],
    ['/creative-studio?view=registry', 'Create export bundle', 'deep /creative-studio?view=registry'],
    ['/listingforge?view=lane', 'Generate Local Draft', 'deep /listingforge?view=lane'],
    ['/adpilot?view=lane', 'Recommend Bid', 'deep /adpilot?view=lane'],
    ['/socialpulse?view=lane', 'Generate Caption', 'deep /socialpulse?view=lane'],
    ['/golden-goose?view=review', 'What Remains Unknown', 'deep /golden-goose?view=review'],
    ['/golden-goose?view=decisions', 'internal review history', 'deep /golden-goose?view=decisions'],
    ['/golden-goose?view=history', 'Historical log', 'deep /golden-goose?view=history'],
    ['/home?view=activity', 'Assigned-Owner Visibility', 'deep /home?view=activity'],
    ['/home?view=exposure', 'not authorizations', 'deep /home?view=exposure'],
    ['/home?view=handoffs', 'Handoff Queue', 'deep /home?view=handoffs'],
    ['/profitability?view=scenarios', 'Scenario Calculator', 'deep /profitability?view=scenarios'],
    ['/profitability?view=fee', 'Set-Level Fee Basis', 'deep /profitability?view=fee'],
    ['/commerce-ops?view=approvals', 'Approval Checkpoints', 'deep /commerce-ops?view=approvals'],
    ['/commerce-ops?view=blockers', 'Blocking Conditions', 'deep /commerce-ops?view=blockers'],
    ['/autothink?view=composer', 'Research Run Composer', 'deep /autothink?view=composer'],
    ['/customer-workspace?view=services', 'Entitled Services', 'deep /customer-workspace?view=services'],
    ['/keyword-tracker?view=trends', 'Rank Trend Summary', 'deep /keyword-tracker?view=trends'],
    ['/keyword-tracker?view=coverage', 'Coverage Gaps', 'deep /keyword-tracker?view=coverage'],
    ['/keyword-tracker?view=alerts', 'Flagged Movement Alerts', 'deep /keyword-tracker?view=alerts'],
    ['/listings?view=diffs', 'Detected Changes', 'deep /listings?view=diffs'],
    ['/listings?view=history', 'Change Timeline', 'deep /listings?view=history'],
    ['/listings?view=escalations', 'Escalation Queue', 'deep /listings?view=escalations'],
    ['/monitoring?view=health', 'Service Checks', 'deep /monitoring?view=health'],
    ['/monitoring?view=sync', 'Staleness Summary', 'deep /monitoring?view=sync'],
    ['/commerce-ops/CO-01', 'Sourcing Validation', 'deep /commerce-ops/CO-01'],
    ['/product-finder/B08L5VJQ7T', 'Product Set — B08L5VJQ7T', 'deep /product-finder/B08L5VJQ7T'],
    ['/golden-goose/GG-001', 'Water Filter Pro', 'deep /golden-goose/GG-001'],
  ]
  for (const [route, marker, ctx] of deepLinks) {
    await page.goto(urlFor(route))
    await expectMarker(page, marker, ctx)
  }

  // ---- P2-T3 accept: direct load of /ui/golden-goose ----
  await page.goto(urlFor('/golden-goose'))
  await expectMarker(page, 'Golden Goose Finder', 'direct load /ui/golden-goose (SPA fallback)')
  const ggPath = await page.evaluate(() => location.pathname)
  ggPath === '/ui/golden-goose' ? ok('direct load keeps pathname /ui/golden-goose') : no('golden-goose pathname', ggPath)

  // ---- wired action: navigation ----
  async function navAction(route, clickTarget, expectedPath, ctx) {
    await page.goto(urlFor(route))
    await page.waitForSelector('.app', { timeout: 8000 })
    await page.click(clickTarget, { timeout: 6000 })
    await expectPath(page, expectedPath, ctx)
  }

  await navAction('/listings', 'button:has-text("New Rule")', '/ui/listings?view=escalations', 'ListingGuardian New Rule')
  await navAction('/listingforge', 'button:has-text("Create Listing")', '/ui/listingforge?view=editor', 'ListingForge Create Listing')
  await navAction('/adpilot', 'button:has-text("Create Campaign")', '/ui/adpilot?view=planner', 'AdPilot Create Campaign')
  await navAction('/autothink', 'button:has-text("New Research Run")', '/ui/autothink?view=composer', 'AutothinK New Research Run')
  await navAction('/product-finder', 'button:has-text("Saved Sets")', '/ui/product-finder?view=saved', 'ProductFinder Saved Sets')
  await navAction('/golden-goose', 'table button:has-text("Open") >> nth=0', '/ui/golden-goose/GG-001', 'GoldenGoose row Open')
  await navAction('/golden-goose/GG-001', 'button:has-text("Open SourceScout")', '/ui/product-finder/B08L5VJQ7T', 'GoldenGoose Open SourceScout')
  await navAction('/commerce-ops', 'table button:has-text("Open") >> nth=0', '/ui/commerce-ops/CO-01', 'CommerceOps row Open')

  // ---- wired action: toast ----
  await navAction('/commerce-ops', 'button:has-text("New Workflow")', '/ui/commerce-ops', 'CommerceOps New Workflow (no nav)')
  await expectToast(page, 'New workflow requires a product set and operator owner', 'CommerceOps New Workflow toast')

  await page.goto(urlFor('/profitability'))
  await page.waitForSelector('.app', { timeout: 8000 })
  await page.click('button:has-text("Export Report")', { timeout: 6000 })
  await expectToast(page, 'Export prepared from observed data', 'Profitability Export Report toast')

  await browser.close()
  console.log(`\nSMOKE RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

run().catch(e => { console.error('FATAL', e); process.exit(2) })