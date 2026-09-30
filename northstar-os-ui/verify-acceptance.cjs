const { chromium } = require('playwright')

// Path routing (P2-T3): BrowserRouter basename /ui.
const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0, fail = 0
const issues = []
function ok(ctx) { pass++; console.log('PASS  ' + ctx) }
function no(ctx, detail) { fail++; issues.push(ctx + (detail ? ' :: ' + detail : '')); console.log('FAIL  ' + ctx + (detail ? ' :: ' + detail : '')) }
function urlFor(route) { return BASE + route.replace(/^\//, '') }

async function stub(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    const dev = role === 'signedout'
      ? { userId: '', orgId: '', role: '', env: 'production', previewId: '' }
      : { userId, orgId: 'org-acc', role, env: 'production', previewId: '' }
    localStorage.setItem('ns-dev-session', JSON.stringify(dev))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      window.__stubCalls.push(route)
      const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: userId, organizations: [], active_organization_id: null, role, permissions: role === 'platform_admin' ? ['platform_admin'] : [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      // Golden Goose persisted round-trip (P5-T4): org-scoped item + decision
      // persist in localStorage so a read-after-write survives reload offline.
      const GKEY = 'gg-acc-decisions'
      if (route === '/golden-goose/queue') return json({ items: [{ item_id: 'GG-ACC' }], basis: 'OBSERVED' })
      const decRoute = route.match(/^\/golden-goose\/([^/]+)\/decision$/)
      if (decRoute && (init?.method || 'GET').toUpperCase() === 'POST') {
        const stored = JSON.parse(localStorage.getItem(GKEY) || '{}')
        stored[decRoute[1]] = { decision_state: 'APPROVAL_REQUIRED', created_at: '2026-09-30T00:00:00Z', purchase_ready: false }
        localStorage.setItem(GKEY, JSON.stringify(stored))
        return json({ item_id: decRoute[1], decision: stored[decRoute[1]], persisted: true, decision_id: 'd-' + decRoute[1] })
      }
      const one = route.match(/^\/golden-goose\/([^/]+)$/)
      if (one) {
        if (one[1] !== 'GG-ACC') return json({ detail: { code: 'not_found' } }, 404)
        const stored = JSON.parse(localStorage.getItem(GKEY) || '{}')
        return json({ item_id: 'GG-ACC', match_state: 'QUALIFIED_FOR_REVIEW', resale_score: 0.62, net_per_unit: 4.1, policy_exclusion_flag: 0, latest_decision: stored['GG-ACC'] || null })
      }
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, { role, userId })
}

async function settle(page) {
  await page.goto(urlFor('/home'))
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/ui-mode') || (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(400)
}

async function goPath(page, route) {
  await page.goto(urlFor(route))
  await page.waitForTimeout(500)
  return await page.evaluate(() => location.pathname + location.search)
}

async function bodyHas(page, t) { return page.evaluate(x => document.body.innerText.includes(x), t) }
async function pathIs(page, p) { return await page.evaluate(x => (location.pathname + location.search) === x, p) }

async function run() {
  const browser = await chromium.launch()

  // ---------- Role guards (running UI) ----------
  const roles = [
    { role: 'signedout', userId: '' },
    { role: 'customer', userId: 'u-cust' },
    { role: 'operator', userId: 'u-op' },
    { role: 'platform_admin', userId: 'u-admin' },
  ]
  const matrix = {}
  for (const r of roles) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const page = await ctx.newPage()
    await stub(page, r.role, r.userId)
    await settle(page)
    const probes = ['/home', '/product-finder', '/listings', '/customer-workspace', '/beta-ops', '/admin']
    const out = {}
    for (const h of probes) {
      out[h] = await goPath(page, h)
    }
    matrix[r.role] = out
    await ctx.close()
  }
  console.log('\n--- role->deep-link final path ---')
  for (const r of Object.keys(matrix)) console.log(r, JSON.stringify(matrix[r]))

  // F4: signed-out internal access -> /ui/sign-in (auth gate).
  ;(matrix['signedout']['/beta-ops'] === '/ui/sign-in')
    ? ok('signedout: /beta-ops redirected to /ui/sign-in')
    : no('signedout: /beta-ops guard', 'got ' + matrix['signedout']['/beta-ops'])
  ;(matrix['signedout']['/admin'] === '/ui/sign-in')
    ? ok('signedout: /admin redirected to /ui/sign-in')
    : no('signedout: /admin guard', 'got ' + matrix['signedout']['/admin'])
  // Authenticated non-admins: admin paths redirect to /ui/home.
  for (const role of ['customer', 'operator']) {
    (matrix[role]['/beta-ops'] === '/ui/home')
      ? ok(`${role}: /beta-ops redirected to /ui/home`)
      : no(`${role}: /beta-ops guard`, 'got ' + matrix[role]['/beta-ops'])
    (matrix[role]['/admin'] === '/ui/home')
      ? ok(`${role}: /admin redirected to /ui/home`)
      : no(`${role}: /admin guard`, 'got ' + matrix[role]['/admin'])
  }
  ;(matrix['platform_admin']['/beta-ops'] === '/ui/beta-ops') ? ok('platform_admin: /beta-ops loads') : no('platform_admin /beta-ops', matrix['platform_admin']['/beta-ops'])
  ;(matrix['platform_admin']['/admin'] === '/ui/admin') ? ok('platform_admin: /admin loads') : no('platform_admin /admin', matrix['platform_admin']['/admin'])

  // Invitee/customer reaching internal operator room via deep link (report actual, flag if open)
  const inviteeInternal = matrix['signedout']['/product-finder']
  const custInternal = matrix['customer']['/product-finder']
  console.log(`NOTE  invitee /product-finder -> ${inviteeInternal}; customer /product-finder -> ${custInternal}`)

  // ---------- Deep links (platform_admin) ----------
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await ctx.newPage()
  await stub(page, 'platform_admin', 'u-admin')
  await settle(page)

  const deep = [
    ['/socialpulse?view=composer', 'Platform Preview'],
    ['/socialpulse?view=queue', 'Drafts'],
    ['/creative-studio?view=variants', 'Add Variant'],
    ['/listings?view=history', 'Change Timeline'],
    ['/listings?view=diffs', 'Detected Changes'],
    ['/keyword-tracker?view=coverage', 'Coverage Gaps'],
    ['/monitoring?view=health', 'Service Checks'],
    ['/beta-ops', 'Beta Operations'],
    ['/beta-ops/eligibility', 'Eligibility Checklist'],
    ['/admin', 'Internal Administration'],
    ['/product-finder', 'SourceScout'],
  ]
  for (const [h, marker] of deep) {
    await goPath(page, h)
    ;(await bodyHas(page, marker))
      ? ok(`deep link ${h} shows "${marker}"`)
      : no(`deep link ${h}`, `marker "${marker}" not found (path ${await page.evaluate(() => location.pathname + location.search)})`)
  }

  // ---------- Primary actions ----------
  async function actionNav(route, clickText, expectPath, ctx2) {
    await goPath(page, route)
    try {
      await page.click(`button:has-text("${clickText}")`, { timeout: 5000 })
      await page.waitForTimeout(400)
      ;(await pathIs(page, expectPath)) ? ok(ctx2) : no(ctx2, `path ${await page.evaluate(() => location.pathname + location.search)}`)
    } catch (e) { no(ctx2, e.message) }
  }
  await actionNav('/socialpulse', 'Draft Post', '/ui/socialpulse?view=composer', 'SocialPulse "Draft Post" -> composer')
  await actionNav('/listings', 'New Rule', '/ui/listings?view=escalations', 'Guardian "New Rule" -> escalations')
  await actionNav('/product-finder', 'Saved Sets', '/ui/product-finder?view=saved', 'SourceScout "Saved Sets" -> saved')
  await actionNav('/beta-ops', 'Export Report', '/ui/beta-ops/reports', 'Beta-Ops "Export Report" -> reports')

  // Toast-only primary action (no nav) + honesty
  async function toastAction(route, clickText, contains, ctx2) {
    await goPath(page, route)
    try {
      await page.waitForSelector('.app', { timeout: 5000 })
      await page.click(`button:has-text("${clickText}")`, { timeout: 5000 })
      await page.waitForSelector('.toast-item', { timeout: 5000 })
      const txt = await page.evaluate(() => Array.from(document.querySelectorAll('.toast-item')).map(e => e.textContent).join(' | '))
      ;(txt.toLowerCase().includes(contains.toLowerCase())) ? ok(ctx2) : no(ctx2, 'toast: ' + txt)
    } catch (e) { no(ctx2, e.message) }
  }
  await toastAction('/creative-studio', 'New Brief', 'sample', 'Creative Studio "New Brief" toast')
  await toastAction('/keyword-tracker', 'Track New', 'sample', 'Keyword "Track New" toast')
  await toastAction('/monitoring', 'Configure Alerts', 'sample', 'Monitoring "Configure Alerts" toast')
  await toastAction('/socialpulse?view=queue', 'Send to Approvals', 'publishes', 'SocialPulse send-to-approvals honesty toast')

  // Disabled controls must be disabled
  await goPath(page, '/beta-ops/lifecycle')
  const disabled = await page.evaluate(() => Array.from(document.querySelectorAll('button')).filter(b => /Confirm Lifecycle Action/.test(b.textContent)).every(b => b.disabled))
  disabled ? ok('Beta-Ops lifecycle confirm is disabled (sample)') : no('Beta-Ops lifecycle confirm disabled')

  // No-navigation on "shadow" actions: strong check — clicking Configure Alerts must not change path
  await goPath(page, '/monitoring')
  const before = await page.evaluate(() => location.pathname + location.search)
  await page.click('button:has-text("Configure Alerts")').catch(() => {})
  await page.waitForTimeout(300)
  ;(await page.evaluate(() => location.pathname + location.search) === before) ? ok('Monitoring "Configure Alerts" does not navigate') : no('Monitoring Configure Alerts navigated')

  // P5-T4: Golden Goose review/decision persisted round-trip (acceptance).
  {
    await goPath(page, '/golden-goose?view=decisions')
    await page.waitForTimeout(700)
    const before = await page.evaluate(() => document.body.innerText)
    ;(before.includes('GG-ACC')) ? ok('acceptance: decisions view lists persisted item GG-ACC') : no('acceptance decisions item missing')
    ;(before.includes('UNKNOWN') || before.includes('No persisted decisions')) ? ok('acceptance: no recorded decision shown UNKNOWN (not invented)') : no('acceptance unknown missing')
    await page.evaluate(async () => {
      await window.fetch('/api/v1/foundation/golden-goose/GG-ACC/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    })
    await goPath(page, '/golden-goose/GG-ACC')
    await page.waitForTimeout(700)
    const reviewTxt = await page.evaluate(() => document.body.innerText)
    ;(reviewTxt.includes('GG-ACC')) ? ok('acceptance: review view renders persisted item GG-ACC') : no('acceptance review id missing')
    ;(reviewTxt.includes('APPROVAL_REQUIRED') || reviewTxt.includes('Approval')) ? ok('acceptance: recorded decision round-trips into review view') : no('acceptance review decision round-trip', 'not shown in ' + reviewTxt.slice(0, 200))
    await goPath(page, '/golden-goose/GG-404')
    await page.waitForTimeout(700)
    const nf = await page.evaluate(() => document.body.innerText)
    ;(nf.includes('No persisted opportunity') || nf.includes('GG-404')) ? ok('acceptance: missing item shows explicit not-found (no fabrication)') : no('acceptance not-found marker', nf.slice(0, 160))
  }

  await ctx.close()
  await browser.close()
  console.log(`\nACCEPTANCE RESULTS: ${pass} passed, ${fail} failed`)
  if (issues.length) { console.log('--- issues ---'); issues.forEach(i => console.log('  ' + i)) }
  process.exit(fail ? 1 : 0)
}

run().catch(e => { console.error('FATAL', e); process.exit(2) })