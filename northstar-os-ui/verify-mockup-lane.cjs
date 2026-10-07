const { chromium } = require('playwright')

// Verifies the exact-text mockup lane renders BOTH as the standalone local page
// (/mogra-mockup) and inside the React Creative Studio room, against the REAL
// local /api/creative/* backend. Foundation reads are stubbed (session shim) so
// only the creative room chrome resolves; /api/creative passes through untouched.
//
// Run with the Northstar backend serving the UI:
//   HARNESS_BASE_URL=http://127.0.0.1:8000/ui/ node verify-mockup-lane.cjs

const UI = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const ROOT = UI.replace(/\/ui\/?$/, '/')
let pass = 0
let fail = 0
const ok = (c) => { pass++; console.log('PASS  ' + c) }
const no = (c, d) => { fail++; console.log('FAIL  ' + c + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })

  // ---- 1) standalone local page (no auth) against the real creative API ----
  await page.goto(ROOT + 'mogra-mockup')
  try {
    await page.waitForFunction(() => document.body.innerText.includes('Generate Final Mockup'), null, { timeout: 8000 })
    ok('standalone /mogra-mockup renders the Generate button')
  } catch { no('standalone /mogra-mockup renders the Generate button', await page.url()) }
  try {
    const n = await page.evaluate(() => document.querySelectorAll('#container option').length)
    n >= 4 ? ok(`standalone presets loaded from /api/creative (${n} container options)`)
           : no('standalone presets loaded from /api/creative', 'options=' + n)
  } catch (e) { no('standalone presets loaded from /api/creative', String(e)) }

  // ---- 2) React Creative Studio lane (foundation stubbed, /api/creative real) ----
  await page.addInitScript(() => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId: 'u-mock', orgId: 'org-mock', role: 'operator', env: 'production', previewId: '',
    }))
    window.__NORTHSTAR_LOCAL_DEV__ = true
    const FOUND = '/api/v1/foundation'
    const real = window.fetch.bind(window)
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return real(input, init) // let /api/creative through
      const route = url.split(FOUND)[1].split('?')[0]
      const json = (b, s = 200) => Promise.resolve(new Response(JSON.stringify(b), {
        status: s, headers: { 'Content-Type': 'application/json' },
      }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({
        user_id: 'u-mock', organizations: [], active_organization_id: null,
        role: 'operator', permissions: [],
      })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  })
  await page.goto(UI + 'creative-studio?view=mockups')
  try {
    await page.waitForSelector('text=Generate Final Mockup', { timeout: 12000 })
    ok('React Creative Studio: exact-text mockups lane renders the Generate button')
  } catch {
    no('React Creative Studio: exact-text mockups lane renders the Generate button',
      await page.evaluate(() => location.pathname + location.search))
  }
  try {
    const tabs = await page.evaluate(() => document.querySelector('.room-tabs')?.innerText || '')
    tabs.includes('Exact-Text Mockups')
      ? ok('Creative Studio tabs include "Exact-Text Mockups"')
      : no('Creative Studio tabs include "Exact-Text Mockups"', tabs.replace(/\n/g, ' | '))
  } catch (e) { no('Creative Studio tabs include "Exact-Text Mockups"', String(e)) }
  try {
    const body = await page.evaluate(() => document.body.innerText)
    ;/qwen t2i/.test(body) ? ok('lane health pills render (qwen t2i)')
                           : no('lane health pills render (qwen t2i)')
  } catch (e) { no('lane health pills render (qwen t2i)', String(e)) }
  try {
    const opts = await page.evaluate(() => {
      const sel = document.getElementById('ms-container')
      return sel ? sel.querySelectorAll('option').length : 0
    })
    opts >= 4 ? ok(`Creative Studio lane loaded presets from /api/creative (${opts} container options)`)
              : no('Creative Studio lane loaded presets from /api/creative', 'options=' + opts)
  } catch (e) { no('Creative Studio lane loaded presets from /api/creative', String(e)) }

  await browser.close()
  console.log(`\nMOCKUP-LANE RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

main().catch((e) => { console.error('FATAL', e); process.exit(2) })
