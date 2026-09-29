const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0
let fail = 0

async function stubSession(page, role, userId) {
  await page.addInitScript(({ role, userId }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId, orgId: 'org-verify', role, env: 'production', previewId: '',
    }))
    localStorage.removeItem('ns-access-token')
    window.__stubCalls = []
    const FOUND = '/api/v1/foundation'
    window.fetch = (input, init) => {
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
        permissions: role === 'platform_admin' ? ['platform_admin'] : [],
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

async function waitHash(page, hash, ms = 6000) {
  try {
    await page.waitForFunction(h => location.hash === h, hash, { timeout: ms })
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
  await page.goto(BASE + '#/beta-ops')
  const a1 = await waitHash(page, '#/sign-in')
  a1 && !(await bodyHas(page, 'Beta Operations'))
    ? ok('signed-out direct #/beta-ops -> redirects #/sign-in, admin content absent')
    : no('signed-out direct #/beta-ops', 'hash=' + await page.evaluate(() => location.hash))

  await page.goto(BASE + '#/admin')
  const a2 = await waitHash(page, '#/sign-in')
  a2 && !(await bodyHas(page, 'Internal Administration'))
    ? ok('signed-out direct #/admin -> redirects #/sign-in, admin content absent')
    : no('signed-out direct #/admin', 'hash=' + await page.evaluate(() => location.hash))

  await page.goto(BASE + '#/golden-goose')
  const a3 = await waitHash(page, '#/sign-in')
  a3 ? ok('signed-out direct internal #/golden-goose -> redirects #/sign-in')
     : no('signed-out direct #/golden-goose', 'hash=' + await page.evaluate(() => location.hash))

  await page.goto(BASE + '#/monitoring')
  const a4 = await waitHash(page, '#/sign-in')
  a4 ? ok('signed-out direct internal #/monitoring -> redirects #/sign-in')
     : no('signed-out direct #/monitoring', 'hash=' + await page.evaluate(() => location.hash))

  await page.goto(BASE + '#/beta')
  const a5 = await waitHash(page, '#/beta')
  a5 ? ok('signed-out public #/beta stays reachable (not redirected)')
     : no('signed-out public #/beta', 'hash=' + await page.evaluate(() => location.hash))

  // --- Case B: authenticated customer -------------------------------------
  // full page load required so the fetch stub + dev session apply on a fresh document
  await stubSession(page, 'customer', 'u-cust-1')
  await page.goto(BASE)
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.evaluate(() => { location.hash = '#/beta-ops' })
  const b1 = await waitHash(page, '#/home')
  b1 && !(await bodyHas(page, 'Beta Operations'))
    ? ok('customer direct #/beta-ops -> redirects #/home, admin content absent')
    : no('customer direct #/beta-ops', 'hash=' + await page.evaluate(() => location.hash))

  await page.evaluate(() => { location.hash = '#/admin' })
  const b2 = await waitHash(page, '#/home')
  b2 && !(await bodyHas(page, 'Internal Administration'))
    ? ok('customer direct #/admin -> redirects #/home, admin content absent')
    : no('customer direct #/admin', 'hash=' + await page.evaluate(() => location.hash))

  // --- Case B2: customer mobile tools sheet --------------------------------
  await page.setViewportSize({ width: 375, height: 667 })
  await page.evaluate(() => { location.hash = '#/home' })
  await waitHash(page, '#/home')
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
  await stubSession(page, 'platform_admin', 'u-admin-1')
  await page.goto(BASE)
  await page.waitForFunction(() => (window.__stubCalls || []).includes('/me'), null, { timeout: 8000 })
  await page.evaluate(() => { location.hash = '#/beta-ops' })
  await waitHash(page, '#/beta-ops')
  await page.waitForFunction(() => document.body.innerText.includes('Beta Operations'), null, { timeout: 6000 })
  ok('platform_admin #/beta-ops loads (control)')

  await page.evaluate(() => { location.hash = '#/admin' })
  await waitHash(page, '#/admin')
  await page.waitForFunction(() => document.body.innerText.includes('Internal Administration'), null, { timeout: 6000 })
  ok('platform_admin #/admin loads (control)')

  // --- Case C2: platform_admin mobile tools sheet ---------------------------
  await page.setViewportSize({ width: 375, height: 667 })
  await page.evaluate(() => { location.hash = '#/home' })
  await waitHash(page, '#/home')
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