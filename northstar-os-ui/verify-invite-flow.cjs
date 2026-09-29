const { chromium } = require('playwright')

// Path routing (P2-T3): BrowserRouter basename /ui.
const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const OUT = 'screenshots'
let pass = 0, fail = 0
const issues = []
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; issues.push(m + (d ? ' :: ' + d : '')); console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
function urlFor(route) { return BASE + route.replace(/^\//, '') }

// Simulates the LOCAL development identity shim: once a dev session exists the
// app calls /me and the backend resolves an (operator) identity.
async function stub(page) {
  await page.addInitScript(() => {
    localStorage.removeItem('ns-access-token')
    const FOUND = '/api/v1/foundation'
    window.__NORTHSTAR_LOCAL_DEV__ = true
    window.__stubCalls = []
    window.fetch = (input) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      window.__stubCalls.push(route)
      const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') {
        // Signed-out (no explicit local-dev session) -> 401, mirroring the real
        // cookie-less backend. With a dev session -> the demo operator.
        let hasDev = false
        try { hasDev = !!JSON.parse(localStorage.getItem('ns-dev-session') || '{}').userId } catch {}
        if (!hasDev) return json({ detail: { code: 'authentication_required', message: 'authentication required' } }, 401)
        return json({ user_id: 'demo-t2', email: '', display_name: '', organizations: [{ id: 'org-t2', name: 'T2 Holdings LLC', role: 'operator' }], active_organization_id: 'org-t2', role: 'operator', environment: 'production', view_context: 'normal', permissions: [] })
      }
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  })
}

async function main() {
  const b = await chromium.launch()
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } })
  const p = await ctx.newPage()
  await stub(p)
  await p.goto(urlFor('/beta'))
  await p.waitForTimeout(700)

  // 1. Accept Invitation -> accept screen (no 404)
  await p.click('button:has-text("Accept Invitation")')
  await p.waitForTimeout(600)
  ;(await p.evaluate(() => location.pathname)) === '/ui/beta/accept' ? ok('Accept Invitation -> /ui/beta/accept (no server 404)') : no('accept route', await p.evaluate(() => location.pathname))

  // 2. Confirm Acceptance -> step 2, then Continue to Sign In carries org context
  await p.click('button:has-text("Confirm Acceptance")')
  await p.waitForTimeout(400)
  await p.screenshot({ path: OUT + '/59-invite-accepted-step2.png', fullPage: true })
  await p.click('button:has-text("Continue to Sign In")')
  await p.waitForTimeout(600)
  const path = await p.evaluate(() => location.pathname + location.search)
  path.startsWith('/ui/sign-in') ? ok('Accept -> /ui/sign-in with org context (' + path + ')') : no('sign-in route', path)
  const banner = await p.evaluate(() => document.body.innerText)
  banner.includes('T2 Holdings LLC') ? ok('sign-in carries invited org context') : no('org context not shown')

  // 3. Fields prefilled with T2 / 123abc
  const idVal = await p.inputValue('#signin-id')
  const pwVal = await p.inputValue('#signin-pw')
  ;(idVal === 'T2' && pwVal === '123abc') ? ok('credentials autopopulated (T2 / 123abc)') : no('prefill', `${idVal}/${pwVal}`)
  await p.screenshot({ path: OUT + '/59b-signin-prefilled.png', fullPage: true })

  // 4. Wrong credentials -> clear error, stays on sign-in
  await p.fill('#signin-pw', 'wrong')
  await p.click('form button[type="submit"]')
  await p.waitForTimeout(400)
  const stillSignin = (await p.evaluate(() => location.pathname)).startsWith('/ui/sign-in')
  const errShown = await p.evaluate(() => /did not match/i.test(document.body.innerText))
  ;(stillSignin && errShown) ? ok('wrong credentials rejected with inline error') : no('wrong-creds handling', `path=${await p.evaluate(() => location.pathname)} err=${errShown}`)

  // 5. Correct credentials -> authenticated workspace + service navigation
  await p.fill('#signin-pw', '123abc')
  await p.click('form button[type="submit"]')
  await p.waitForTimeout(900)
  ;(await p.evaluate(() => location.pathname)) === '/ui/home' ? ok('sign-in -> /ui/home') : no('post-signin route', await p.evaluate(() => location.pathname))
  const rail = await p.evaluate(() => document.querySelector('.suite-rail')?.innerText || '')
  ;(rail.includes('Command Center') && rail.includes('SourceScout')) ? ok('authenticated shell shows service navigation') : no('service nav missing', rail.slice(0, 120))
  rail.includes('Sign in to open your workspace') ? no('signed-out rail still shown after sign-in') : ok('signed-out rail replaced')
  await p.screenshot({ path: OUT + '/59c-signed-in-workspace.png', fullPage: true })

  // 6. Refresh persistence
  await p.reload()
  await p.waitForTimeout(900)
  const rail2 = await p.evaluate(() => document.querySelector('.suite-rail')?.innerText || '')
  ;(rail2.includes('SourceScout')) ? ok('session persists across refresh') : no('refresh persistence lost')

  // 7. Role guards under the demo operator session
  await p.goto(urlFor('/beta-ops')); await p.waitForTimeout(500)
  ;(await p.evaluate(() => location.pathname)) === '/ui/home' ? ok('operator: /beta-ops still guarded') : no('beta-ops guard', await p.evaluate(() => location.pathname))
  await p.goto(urlFor('/admin')); await p.waitForTimeout(500)
  ;(await p.evaluate(() => location.pathname)) === '/ui/home' ? ok('operator: /admin still guarded') : no('admin guard', await p.evaluate(() => location.pathname))

  await b.close()
  console.log(`\nINVITE-FLOW RESULTS: ${pass} passed, ${fail} failed`)
  if (issues.length) { console.log('--- issues ---'); issues.forEach(i => console.log('  ' + i)) }
  process.exit(fail ? 1 : 0)
}
main().catch(e => { console.error('FATAL', e); process.exit(2) })