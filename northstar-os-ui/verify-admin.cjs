// verify-admin.cjs — Item 4 admin workflow acceptance (local, offline).
//
// Verifies the /beta-ops/* admin surface against the Vite dev server:
//   1. platform_admin can reach every /beta-ops sub-page and its title renders.
//   2. Every destructive/action surface is sample-mode DISABLED (no invite,
//      no lifecycle action, no eligibility apply, no download/export run).
//   3. Internal DataNotices are present (sample/internal, not entitlements).
//   4. Non-platform_admin roles (operator/customer) are bounced away from /beta-ops.
//
// Admin pages are intentionally sample-mode stubs; no backend write is performed.
// Real invitations, exports, lifecycle changes are NOT executed (local-only).
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
let pass = 0
let fail = 0

function urlFor(route) { return BASE + route.replace(/^\//, '') }

function ok(cond, msg) {
  if (cond) { pass++; console.log('  PASS ' + msg) }
  else { fail++; console.log('  FAIL ' + msg) }
}

async function stubSession(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId, orgId: 'org-verify', role, env: 'production', previewId: '',
    }))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    window.fetch = (input, init) => {
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
        user_id: userId, organizations: [], active_organization_id: null,
        role, permissions: role === 'platform_admin' ? ['platform_admin'] : [],
      })
      if (route === '/environment') return json({
        environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false,
      })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed', message: 'not stubbed' } }, 404)
    }
  }, { role, userId })
}

async function load(page, route) {
  await page.goto(urlFor(route), { waitUntil: 'load' })
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.waitForTimeout(150)
}

async function checkNavigation(page) {
  const labels = await page.$$eval('.room-tab-label', els => els.map(e => e.textContent.trim()))
  for (const expected of ['Overview', 'Organizations', 'Invites', 'Cohorts', 'Support', 'Lifecycle', 'Audit', 'Reports']) {
    ok(labels.includes(expected), `beta-ops nav includes "${expected}"`)
  }
}

async function checkDisabledByTitle(page, titles) {
  for (const t of titles) {
    const btn = await page.$(`button[title="${t}"]`)
    ok(!!btn, `surface button "${t}" present`)
    if (btn) {
      const dis = await btn.getAttribute('disabled')
      ok(dis !== null, `surface button "${t}" is DISABLED (sample mode)`)
    }
  }
}

async function checkNoticeInnerText(page, ctx) {
  const joined = await page.evaluate(() => {
    const els = document.querySelectorAll('[class*="alert-title"], [class*="alert-text"], .alert-title, .alert-text')
    let s = ''
    els.forEach(e => { s += (e.textContent || '') + ' ' })
    return s
  })
  ok(/internal/i.test(joined) && /sample|internal|authorization|entitlement/i.test(joined),
     `internal/sample DataNotice present on ${ctx}`)
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()

  console.log('--- platform_admin reaches all /beta-ops pages ---')
  await stubSession(page, 'platform_admin', 'u-admin-1')
  const adminPages = [
    ['/beta-ops', 'Beta Operations'],
    ['/beta-ops/orgs', 'Organizations'],
    ['/beta-ops/invites', 'Create Invitation'],
    ['/beta-ops/cohorts', 'Cohorts'],
    ['/beta-ops/support', 'Support Operations'],
    ['/beta-ops/reports', 'Reports & Exports'],
    ['/beta-ops/audit', 'Audit & Notes'],
    ['/beta-ops/lifecycle', 'Lifecycle Action'],
    ['/beta-ops/eligibility', 'Eligibility Checklist'],
  ]
  for (const [route, title] of adminPages) {
    await load(page, route)
    const has = await page.evaluate(t => document.body.innerText.includes(t), title)
    ok(has, `[platform_admin] ${route} renders "${title}"`)
  }

  console.log('--- beta-ops navigation labels ---')
  await load(page, '/beta-ops/orgs')
  await checkNavigation(page)

  console.log('--- destructive/action surfaces are DISABLED (sample mode) ---')
  await load(page, '/beta-ops/invites')
  await checkDisabledByTitle(page, ['Sample surface — no invite is sent'])
  await load(page, '/beta-ops/invites/INV-2026-09-25-0192')
  await checkDisabledByTitle(page, [
    'Sample surface — no invite is reissued',
    'Sample surface — no invite is revoked',
  ])
  await load(page, '/beta-ops/lifecycle')
  await checkDisabledByTitle(page, ['Sample surface — no lifecycle action is applied'])
  await load(page, '/beta-ops/eligibility')
  await checkDisabledByTitle(page, ['Sample surface — eligibility is not applied'])
  await load(page, '/beta-ops/reports')
  await checkDisabledByTitle(page, ['Export disabled in sample mode'])

  console.log('--- internal DataNotices ---')
  await load(page, '/beta-ops/reports')
  await checkNoticeInnerText(page, 'Reports & Exports')
  await load(page, '/beta-ops/audit')
  await checkNoticeInnerText(page, 'Audit & Notes')
  await load(page, '/beta-ops/cohorts')
  await checkNoticeInnerText(page, 'Cohorts')

  console.log('--- role isolation: operator bounced away from /beta-ops ---')
  await stubSession(page, 'operator', 'u-op-1')
  await load(page, '/beta-ops')
  const opPath = await page.evaluate(() => location.pathname)
  ok(opPath.endsWith('/home'), `[operator] /beta-ops bounces to /home (got ${opPath})`)

  await context.close()
  const anonCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const aPage = await anonCtx.newPage()
  console.log('--- unauthenticated bounced to sign-in ---')
  await stubSession(aPage, '', '')
  await aPage.addInitScript(() => { localStorage.removeItem('ns-dev-session') })
  await aPage.goto(urlFor('/beta-ops'), { waitUntil: 'load' })
  await aPage.waitForTimeout(500)
  const anonPath = await aPage.evaluate(() => location.pathname)
  ok(anonPath.endsWith('/sign-in'), `[anonymous] /beta-ops bounces to /sign-in (got ${anonPath})`)
  await anonCtx.close()

  await browser.close()
  console.log(`\nADMIN HARNESS: ${pass} passed, ${fail} failed`)
  process.exit(fail === 0 ? 0 : 1)
})().catch((e) => { console.error('HARNESS ERROR:', e); process.exit(1) })
