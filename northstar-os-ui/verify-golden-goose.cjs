// P5-T4 focused harness: Golden Goose persisted queue display.
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0, fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

async function stub(page, queueBody) {
  await page.addInitScript((qb) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({ userId: 'u-gg', orgId: 'org-gg', role: 'operator', env: 'production', previewId: '' }))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    const FOUND = '/api/v1/foundation'
    window.fetch = (input) => {
      const url = typeof input === 'string' ? input : input.url
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      const json = (b, s = 200) => Promise.resolve(new Response(JSON.stringify(b), { status: s, headers: { 'Content-Type': 'application/json' } }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: 'u-gg', organizations: [], active_organization_id: 'org-gg', role: 'operator', permissions: [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      if (route === '/golden-goose/queue') return json(qb)
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, queueBody)
}

async function main() {
  const browser = await chromium.launch()

  // Context A: persisted item present -> OBSERVED, visible, and survives reload.
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const a = await ctxA.newPage()
  await stub(a, { items: [{ item_id: 'GG-9', resale_score: 0.72, match_state: 'QUALIFIED_FOR_REVIEW' }], basis: 'OBSERVED' })
  await a.goto(BASE + 'golden-goose')
  await a.waitForSelector('[data-testid="gg-persisted-queue"]', { timeout: 8000 })
  const basisA = await a.textContent('[data-testid="gg-persisted-basis"]')
  basisA.trim().toUpperCase() === 'OBSERVED' ? ok('persisted queue basis OBSERVED') : no('basis', basisA)
  ;(await a.textContent('[data-testid="gg-persisted-items"]')).includes('GG-9') ? ok('persisted item GG-9 displayed') : no('item missing')
  await a.reload()
  await a.waitForSelector('[data-testid="gg-persisted-queue"]', { timeout: 8000 })
  ;(await a.textContent('[data-testid="gg-persisted-items"]')).includes('GG-9') ? ok('persisted item round-trip after reload') : no('reload lost item')
  await ctxA.close()

  // Context B: empty queue -> UNKNOWN, not fabricated.
  const ctxB = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const b = await ctxB.newPage()
  await stub(b, { items: [], basis: 'UNKNOWN' })
  await b.goto(BASE + 'golden-goose')
  await b.waitForSelector('[data-testid="gg-persisted-queue"]', { timeout: 8000 })
  const basisB = await b.textContent('[data-testid="gg-persisted-basis"]')
  basisB.trim().toUpperCase() === 'UNKNOWN' ? ok('empty queue basis UNKNOWN') : no('empty basis', basisB)
  ;(await b.textContent('[data-testid="gg-persisted-empty"]')).includes('UNKNOWN') ? ok('empty queue shows UNKNOWN message (not fabricated)') : no('empty message missing')
  await ctxB.close()

  await browser.close()
  console.log(`\nGOLDEN-GOOSE RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })