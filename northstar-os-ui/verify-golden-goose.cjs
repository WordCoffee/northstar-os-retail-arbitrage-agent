// P5-T4 focused harness: Golden Goose persisted queue/review/decisions display.
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0, fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

const T = {
  review: '[data-testid="gg-persisted-review"]',
  reviewId: '[data-testid="gg-review-id"]',
  reviewScore: '[data-testid="gg-review-score"]',
  reviewDecision: '[data-testid="gg-review-decision"]',
  reviewNotFound: '[data-testid="gg-review-not-found"]',
  reviewDenied: '[data-testid="gg-review-denied"]',
  queue: '[data-testid="gg-persisted-queue"]',
  basis: '[data-testid="gg-persisted-basis"]',
  queueItems: '[data-testid="gg-persisted-items"]',
  queueEmpty: '[data-testid="gg-persisted-empty"]',
  decisions: '[data-testid="gg-persisted-decisions"]',
  decisionsEmpty: '[data-testid="gg-decisions-empty"]',
}

// Generic, stateful, offline stub. Decisions persist in localStorage so a
// read-after-write round-trip survives reload without any real network.
async function stub(page, cfg) {
  await page.addInitScript((cfg) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({ userId: 'u-gg', orgId: 'org-gg', role: 'operator', env: 'production', previewId: '' }))
    localStorage.removeItem('ns-access-token')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    const FOUND = '/api/v1/foundation'
    const items = cfg.items || {}
    const queue = cfg.queue || { items: [], basis: 'UNKNOWN' }
    const denied = cfg.deniedIds || []
    const DKEY = 'gg-decisions'
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url
      const method = ((init && init.method) || 'GET').toUpperCase()
      if (!url.includes(FOUND)) return Promise.reject(new Error('unexpected fetch ' + url))
      const route = url.split(FOUND)[1].split('?')[0]
      const json = (b, s = 200) => Promise.resolve(new Response(JSON.stringify(b), { status: s, headers: { 'Content-Type': 'application/json' } }))
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: 'u-gg', organizations: [], active_organization_id: 'org-gg', role: 'operator', permissions: [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      if (route === '/golden-goose/queue') return json(queue)
      const dec = route.match(/^\/golden-goose\/([^/]+)\/decision$/)
      if (dec && method === 'POST') {
        const stored = JSON.parse(localStorage.getItem(DKEY) || '{}')
        const d = { decision_state: cfg.postDecisionState || 'review_hold', created_at: '2026-09-30T00:00:00Z', purchase_ready: false }
        stored[dec[1]] = d
        localStorage.setItem(DKEY, JSON.stringify(stored))
        return json({ item_id: dec[1], decision: d, persisted: true, decision_id: 'd-' + dec[1] })
      }
      const one = route.match(/^\/golden-goose\/([^/]+)$/)
      if (one && method === 'GET') {
        const id = one[1]
        if (denied.includes(id)) return json({ detail: { code: 'permission_denied' } }, 403)
        const base = items[id]
        if (!base) return json({ detail: { code: 'not_found' } }, 404)
        const stored = JSON.parse(localStorage.getItem(DKEY) || '{}')
        return json({ ...base, latest_decision: stored[id] || null })
      }
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, cfg)
}

async function main() {
  const browser = await chromium.launch()
  const txt = (page, sel) => page.textContent(sel)

  // A: persisted queue present -> OBSERVED, visible, survives reload.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [{ item_id: 'GG-9', resale_score: 0.72, match_state: 'QUALIFIED_FOR_REVIEW' }], basis: 'OBSERVED' }, items: { 'GG-9': { item_id: 'GG-9', resale_score: 0.72, match_state: 'QUALIFIED_FOR_REVIEW', policy_exclusion_flag: 0 } } })
    await p.goto(BASE + 'golden-goose')
    await p.waitForSelector(T.queue, { timeout: 8000 })
    ;(await txt(p, T.basis)).trim().toUpperCase() === 'OBSERVED' ? ok('persisted queue basis OBSERVED') : no('basis', await txt(p, T.basis))
    ;(await txt(p, T.queueItems)).includes('GG-9') ? ok('persisted item GG-9 displayed') : no('item missing')
    await p.reload()
    await p.waitForSelector(T.queue, { timeout: 8000 })
    ;(await txt(p, T.queueItems)).includes('GG-9') ? ok('persisted item round-trip after reload') : no('reload lost item')
    await ctx.close()
  }

  // B: empty queue -> UNKNOWN, not fabricated.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [], basis: 'UNKNOWN' }, items: {} })
    await p.goto(BASE + 'golden-goose')
    await p.waitForSelector(T.queue, { timeout: 8000 })
    ;(await txt(p, T.basis)).trim().toUpperCase() === 'UNKNOWN' ? ok('empty queue basis UNKNOWN') : no('empty basis', await txt(p, T.basis))
    ;(await txt(p, T.queueEmpty)).includes('UNKNOWN') ? ok('empty queue shows UNKNOWN message (not fabricated)') : no('empty message missing')
    await ctx.close()
  }

  // C: persisted item review uses org-scoped route and renders the stored item.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [], basis: 'UNKNOWN' }, items: { 'GG-9': { item_id: 'GG-9', match_state: 'QUALIFIED_FOR_REVIEW', resale_score: 0.72, net_per_unit: 4.1, policy_exclusion_flag: 0 } } })
    await p.goto(BASE + 'golden-goose/GG-9')
    await p.waitForSelector(T.review, { timeout: 8000 })
    ok('persisted item opens persisted review state')
    ;(await txt(p, T.reviewId)).includes('GG-9') ? ok('review rendered from organization-scoped data (GG-9)') : no('review id', await txt(p, T.reviewId))
    ;(await txt(p, T.reviewScore)).includes('0.72') ? ok('review shows stored resale score') : no('review score', await txt(p, T.reviewScore))
    ;(await txt(p, T.reviewDecision)).includes('UNKNOWN') ? ok('review keeps empty decision UNKNOWN (not invented)') : no('review decision', await txt(p, T.reviewDecision))
    await ctx.close()
  }

  // D: unknown/missing persisted item -> explicit not-found, never fabricated.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [], basis: 'UNKNOWN' }, items: {} })
    await p.goto(BASE + 'golden-goose/GG-404')
    await p.waitForSelector(T.reviewNotFound, { timeout: 8000 })
    ok('missing persisted item shows explicit not-found (no fabrication)')
    await ctx.close()
  }

  // E: cross-tenant / denied persisted item -> explicit denied state.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [], basis: 'UNKNOWN' }, items: {}, deniedIds: ['GG-X'] })
    await p.goto(BASE + 'golden-goose/GG-X')
    await p.waitForSelector(T.reviewDenied, { timeout: 8000 })
    ok('denied persisted item shows explicit denied state')
    await ctx.close()
  }

  // F: persisted latest decision renders and round-trips across reload.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [{ item_id: 'GG-9' }], basis: 'OBSERVED' }, items: { 'GG-9': { item_id: 'GG-9', match_state: 'QUALIFIED_FOR_REVIEW', resale_score: 0.72, policy_exclusion_flag: 0 } } })
    await p.goto(BASE + 'golden-goose?view=decisions')
    await p.waitForSelector(T.decisions, { timeout: 8000 })
    ;(await txt(p, T.decisions)).includes('GG-9') ? ok('decisions view lists persisted item') : no('decisions item missing')
    ;(await txt(p, T.decisions)).includes('UNKNOWN') ? ok('no recorded decision shown UNKNOWN (not invented)') : no('decisions unknown missing')
    await p.evaluate(async () => { await window.fetch('/api/v1/foundation/golden-goose/GG-9/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }) })
    await p.reload()
    await p.waitForSelector(T.decisions, { timeout: 8000 })
    ;(await txt(p, T.decisions)).includes('review_hold') ? ok('persisted latest decision survives reload (round-trip)') : no('round-trip lost decision', await txt(p, T.decisions))
    await ctx.close()
  }

  // G: cross-tenant denied item in decisions view -> denied, never a decision.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [{ item_id: 'GG-Z' }], basis: 'OBSERVED' }, items: {}, deniedIds: ['GG-Z'] })
    await p.goto(BASE + 'golden-goose?view=decisions')
    await p.waitForSelector(T.decisions, { timeout: 8000 })
    const t = await txt(p, T.decisions)
    ;(t.includes('DENIED') || t.includes('denied')) ? ok('cross-tenant item shown denied (never a fabricated decision)') : no('denied not shown', t)
    await ctx.close()
  }

  // H: demo/deep-link fallback for static fixture remains intact.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const p = await ctx.newPage()
    await stub(p, { queue: { items: [], basis: 'UNKNOWN' }, items: {} })
    await p.goto(BASE + 'golden-goose/GG-001')
    await p.waitForSelector(T.review, { timeout: 8000 }).catch(() => {})
    const body = await p.textContent('body')
    body.includes('Water Filter Pro') ? ok('demo deep-link /golden-goose/GG-001 still renders Water Filter Pro (fallback intact)') : no('demo fallback broken')
    await ctx.close()
  }

  await browser.close()
  console.log(`\nGOLDEN-GOOSE RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
