const { chromium } = require('playwright')

// Path routing (P2-T3): BrowserRouter basename /ui.
const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0
let fail = 0

function urlFor(route) { return BASE + route.replace(/^\//, '') }

async function stubSession(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId, orgId: 'org-verify', role, env: 'production', previewId: '',
    }))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    localStorage.setItem('ns-shell-mode', 'advanced')
    window.fetch = (input, init) => {
      if (String(typeof input === 'string' ? input : input.url).includes('/api/shell/')) {
        return Promise.resolve(new Response(JSON.stringify({
          contract: 'shell/v1',
          capabilities: { advanced_view: true, autothink_workspace: true },
          focuses: [],
          identity: { role: 'operator', plan: 'autothink', plan_name: 'AutothinK', source: 'stub' },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) {
        return Promise.reject(new Error('unexpected fetch ' + url))
      }
      const route = url.split(FOUND)[1].split('?')[0]
      window.__stubCalls.push(route)
      const json = (body, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(body), {
          status, headers: { 'Content-Type': 'application/json' },
        }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({
        user_id: userId,
        organizations: [],
        active_organization_id: null,
        role,
        permissions: role === 'internal_platform_admin' ? ['platform_admin'] : [],
      })
      if (route === '/environment') return json({
        environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false,
      })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed', message: 'not stubbed' } }, 404)
    }
  }, { role, userId })
}

function ok(ctx) { pass++; console.log('PASS  ' + ctx) }
function no(ctx, detail) { fail++; console.log('FAIL  ' + ctx + (detail ? ' :: ' + detail : '')) }

async function waitPath(page, path, ms = 6000) {
  try {
    await page.waitForFunction(p => location.pathname === p, path, { timeout: ms })
    return true
  } catch { return false }
}

async function bodyHas(page, text) {
  return page.evaluate(t => document.body.innerText.includes(t), text)
}

async function run() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await ctx.newPage()

  // --- Case A: signed-out (invitee) direct URL access ---------------------
  // F4: internal paths require authentication -> signed-out sends them to sign-in.
  await page.goto(urlFor('/beta-ops'))
  const a1 = await waitPath(page, '/ui/sign-in')
  a1 && !(await bodyHas(page, 'Beta Operations'))
    ? ok('signed-out direct /beta-ops -> redirects /ui/sign-in, admin content absent')
    : no('signed-out direct /beta-ops', 'path=' + await page.evaluate(() => location.pathname))

  await page.goto(urlFor('/admin'))
  const a2 = await waitPath(page, '/ui/sign-in')
  a2 && !(await bodyHas(page, 'Internal Administration'))
    ? ok('signed-out direct /admin -> redirects /ui/sign-in, admin content absent')
    : no('signed-out direct /admin', 'path=' + await page.evaluate(() => location.pathname))

  await page.goto(urlFor('/golden-goose'))
  const a3 = await waitPath(page, '/ui/sign-in')
  a3 ? ok('signed-out direct internal /golden-goose -> redirects /ui/sign-in')
     : no('signed-out direct /golden-goose', 'path=' + await page.evaluate(() => location.pathname))

  await page.goto(urlFor('/monitoring'))
  const a4 = await waitPath(page, '/ui/sign-in')
  a4 ? ok('signed-out direct internal /monitoring -> redirects /ui/sign-in')
     : no('signed-out direct /monitoring', 'path=' + await page.evaluate(() => location.pathname))

  await page.goto(urlFor('/beta'))
  const a5 = await waitPath(page, '/ui/beta')
  a5 ? ok('signed-out public /beta stays reachable (not redirected)')
     : no('signed-out public /beta', 'path=' + await page.evaluate(() => location.pathname))

  // --- Case B: authenticated customer -------------------------------------
  // full page load required so the fetch stub + dev session apply on a fresh document
  await stubSession(page, 'organization_owner', 'u-cust-1')
  await page.goto(urlFor('/home'))
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.goto(urlFor('/beta-ops'))
  const b1 = await waitPath(page, '/ui/home')
  b1 && !(await bodyHas(page, 'Beta Operations'))
    ? ok('customer direct /beta-ops -> redirects /ui/home, admin content absent')
    : no('customer direct /beta-ops', 'path=' + await page.evaluate(() => location.pathname))

  await page.goto(urlFor('/admin'))
  const b2 = await waitPath(page, '/ui/home')
  b2 && !(await bodyHas(page, 'Internal Administration'))
    ? ok('customer direct /admin -> redirects /ui/home, admin content absent')
    : no('customer direct /admin', 'path=' + await page.evaluate(() => location.pathname))

  // --- Case B2: customer mobile tools sheet --------------------------------
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto(urlFor('/home'))
  await waitPath(page, '/ui/home')
  await page.click('.mobile-bottom-nav-item:has-text("Tools")')
  await page.waitForSelector('.tools-sheet', { timeout: 4000 })
  const custTools = await page.$$eval('.tools-sheet-item', els => els.map(e => e.textContent.trim()))
  const sheetOk = custTools.includes('Customer Workspace') &&
    !custTools.some(t => t.includes('Beta Operations')) &&
    !custTools.some(t => t.includes('Administration')) &&
    !custTools.some(t => t.includes('SourceScout'))
  sheetOk
    ? ok('customer mobile Tools sheet shows ONLY Customer Workspace [' + custTools.join(' | ') + ']')
    : no('customer mobile Tools sheet', custTools.join(' | '))

  // --- Case C: platform_admin (control group) ------------------------------
  await page.setViewportSize({ width: 1280, height: 800 })
  await stubSession(page, 'internal_platform_admin', 'u-admin-1')
  await page.goto(urlFor('/home'))
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.goto(urlFor('/beta-ops'))
  await waitPath(page, '/ui/beta-ops')
  await page.waitForFunction(() => document.body.innerText.includes('Beta Operations'), null, { timeout: 6000 })
  ok('platform_admin /beta-ops loads (control)')

  await page.goto(urlFor('/admin'))
  await waitPath(page, '/ui/admin')
  await page.waitForFunction(() => document.body.innerText.includes('Internal Administration'), null, { timeout: 6000 })
  ok('platform_admin /admin loads (control)')

  // --- Case C2: platform_admin mobile tools sheet ---------------------------
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto(urlFor('/home'))
  await waitPath(page, '/ui/home')
  await page.click('.mobile-bottom-nav-item:has-text("Tools")')
  await page.waitForSelector('.tools-sheet', { timeout: 4000 })
  const adminTools = await page.$$eval('.tools-sheet-item', els => els.map(e => e.textContent.trim()))
  adminTools.some(t => t.includes('Beta Operations')) && adminTools.some(t => t.includes('Administration'))
    ? ok('platform_admin mobile Tools sheet includes Beta Operations + Administration')
    : no('platform_admin mobile Tools sheet', adminTools.join(' | '))

  await browser.close()
  console.log(`\nGUARD RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

run().catch(e => { console.error('FATAL', e); process.exit(2) })