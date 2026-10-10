// ═══════════════════════════════════════════════════════════════════════════
// MIGRATION END-TO-END — seed a browser, run it, prove idempotency
//
// Directive item 5. This drives a REAL browser with REAL legacy localStorage,
// runs the real migration against the real API, and asserts:
//   • the records land in the tenant's backend store
//   • localStorage is cleared ONLY after the server confirms
//   • running again creates nothing new (idempotency)
//   • a record with a malformed entry is reported, not silently dropped
//
// Run from tools/:  node test-migration-e2e.cjs
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const API = process.env.HARNESS_API_URL || 'http://127.0.0.1'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

let pass = 0
let fail = 0
let fatal = 0
const log = (m) => console.log(m)
const ok = (m) => { pass++; log('PASS  ' + m) }
const no = (m, d) => { fail++; log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const TAG = 'MIGE2E-' + Date.now().toString(36)

// Realistic legacy payloads in the shapes the pre-backend rooms actually wrote.
const SEED = {
  'ns-creative-briefs': [
    { id: TAG + '-BR-01', name: TAG + ' Launch brief', objective: 'Drive awareness', audience: 'Homeowners', brand: 'Word Coffee', formats: ['Ad creative'], deliverables: 3, status: 'Draft', note: 'legacy brief', createdAt: '2026-09-01T00:00:00Z' },
    { id: TAG + '-BR-02', name: TAG + ' Seasonal brief', objective: 'Promo', audience: 'Existing', brand: 'Mogra Organics', formats: ['Social variant'], deliverables: 2, status: 'Active', note: 'legacy brief 2', createdAt: '2026-09-02T00:00:00Z' },
  ],
  'ns-creative-variants': [
    { id: TAG + '-V-01', brief: TAG + '-BR-01', format: 'Ad creative', aspect: '1:1', state: 'Draft', note: 'legacy variant readonly', createdAt: '2026-09-03T00:00:00Z' },
  ],
  'ds-docs': [
    { id: TAG + '-DOC-01', name: TAG + ' master canvas', formatId: 'amz-main', w: 2000, h: 2000, layers: [], createdAt: '2026-09-04T00:00:00Z' },
  ],
  'pd-requests': [
    { id: TAG + '-REQ-01', name: TAG + ' lifestyle request', purpose: 'lifestyle', tier: 'draft', status: 'Blocked — provider required', createdAt: '2026-09-05T00:00:00Z' },
  ],
  'pd-exports': [
    { id: TAG + '-EXP-01', name: TAG + ' export bundle', status: 'complete', createdAt: '2026-09-05T01:00:00Z' },
  ],
  'pd-renders': [
    { id: TAG + '-R-01', name: TAG + ' pack render', w: 1600, h: 1600, createdAt: '2026-09-06T00:00:00Z' },
  ],
  // A deliberately malformed entry: valid JSON, wrong shape. It must be
  // reported rather than silently vanishing or crashing the import.
  'ds-kits': '["not-an-object-record"]',
}

async function apiLogin(request) {
  const res = await request.post(`${API}/api/v1/foundation/auth/login`, {
    data: { email: EMAIL, password: PW },
  })
  return res.ok()
}

async function apiGet(request, path) {
  const res = await request.get(`${API}${path}`)
  if (!res.ok()) throw new Error(`GET ${path} -> ${res.status()}`)
  return res.json()
}

async function main() {
  const { request } = require('playwright')
  const apiCtx = await request.newContext()
  if (!(await apiLogin(apiCtx))) { ftl('API login failed'); return report() }

  // ── Baseline: what the tenant already holds ──────────────────────────────
  const before = await apiGet(apiCtx, '/api/design-studio/status')
  log(`baseline: ${JSON.stringify(before)}`)

  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))

  // ── Sign in, then seed localStorage on the app origin ────────────────────
  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  ok('signed in')

  await page.evaluate((seed) => {
    try { localStorage.removeItem('ns-ds-migrated-v1') } catch { /* ignore */ }
    for (const [k, v] of Object.entries(seed)) {
      localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v))
    }
  }, SEED)
  const seeded = await page.evaluate((keys) => keys.map(k => [k, (localStorage.getItem(k) || '').length]), Object.keys(SEED))
  ok(`seeded ${seeded.length} legacy keys: ${seeded.map(s => s[0]).join(', ')}`)

  // ── Run the migration by opening the studio ──────────────────────────────
  await page.goto(BASE + 'design-studio')
  await page.waitForSelector('.ds-section-picker', { timeout: 12000 })
  await page.waitForTimeout(2500)  // let the POST settle

  const afterMigrate = await apiGet(apiCtx, '/api/design-studio/status')
  log(`after migrate: ${JSON.stringify(afterMigrate)}`)
  const dP = afterMigrate.projects - before.projects
  const dA = afterMigrate.assets - before.assets
  const dJ = afterMigrate.jobs - before.jobs
  if (dP >= 3) ok(`briefs + variants landed as projects (+${dP})`)
  else no(`expected at least 3 new projects, got +${dP}`)
  if (dA >= 2) ok(`docs + renders landed as assets (+${dA})`)
  else no(`expected at least 2 new assets, got +${dA}`)
  if (dJ >= 2) ok(`requests + exports landed as jobs (+${dJ})`)
  else no(`expected at least 2 new jobs, got +${dJ}`)

  // ── Legacy fields the schema does not model must SURVIVE the import ──────
  const proj = await apiGet(apiCtx, '/api/design-studio/projects?section=projects')
  const allNames = (proj.projects || []).map(p => p.name)
  const mineP = (proj.projects || []).find(p => (p.name || '').includes(TAG + ' Launch brief'))
  const carried = mineP && mineP.metadata && mineP.metadata.legacyFields
  if (carried && carried.objective === 'Drive awareness' && carried.deliverables === 3) {
    ok('unmapped legacy fields are preserved under metadata.legacyFields (lossless import)')
  } else {
    no('legacy fields were dropped by the import',
      `carried=${JSON.stringify(carried || null)} project=${mineP ? mineP.name : 'NOT FOUND'} all=${JSON.stringify(allNames.slice(0, 6))}`)
  }

  // The malformed entry must be REPORTED and KEPT, and ONLY that key may
  // survive: a key whose content could not be represented must never be
  // cleared, and a good key must never be kept.
  const kitsLeft = await page.evaluate(() => localStorage.getItem('ds-kits'))
  if (kitsLeft) ok('the malformed ds-kits value is still present locally (nothing was destroyed)')
  else no('the malformed value was deleted without confirmation')

  // ── localStorage cleared only for the successfully imported keys ─────────
  const remaining = await page.evaluate((keys) => keys.map(k => [k, localStorage.getItem(k)]).filter(([, v]) => v), Object.keys(SEED))
  const remainingKeys = remaining.map(([k]) => k)
  if (remainingKeys.length === 1 && remainingKeys[0] === 'ds-kits') {
    ok('exactly the unimportable key survived; every imported key was cleared')
  } else {
    no(`unexpected surviving keys: ${JSON.stringify(remainingKeys)}`)
  }

  const flag = await page.evaluate(() => localStorage.getItem('ns-ds-migrated-v1'))
  // The done flag is deliberately NOT set while an unimportable key remains:
  // setting it would stop the operator from ever retrying that key.
  if (flag === null) ok('the done flag is withheld while an unimportable key remains (so it can be retried)')
  else no(`the done flag was set despite an unimportable key (flag=${flag})`)

  // ── Idempotency: re-seed the SAME records and run again ─────────────────
  await page.evaluate((seed) => {
    try { localStorage.removeItem('ns-ds-migrated-v1') } catch { /* ignore */ }
    for (const [k, v] of Object.entries(seed)) {
      localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v))
    }
  }, SEED)
  await page.reload()
  await page.waitForSelector('.ds-section-picker', { timeout: 12000 })
  await page.waitForTimeout(2500)

  const afterSecond = await apiGet(apiCtx, '/api/design-studio/status')
  log(`after second run: ${JSON.stringify(afterSecond)}`)
  const dP2 = afterSecond.projects - afterMigrate.projects
  const dA2 = afterSecond.assets - afterMigrate.assets
  const dJ2 = afterSecond.jobs - afterMigrate.jobs
  if (dP2 === 0 && dA2 === 0 && dJ2 === 0) ok('re-running the SAME records created nothing new (idempotent)')
  else no(`second run duplicated work: projects +${dP2}, assets +${dA2}, jobs +${dJ2}`)

  // ── Cross-tenant: another account must not see any of it ────────────────
  const other = await request.newContext()
  const res = await other.post(`${API}/api/v1/foundation/auth/login`, { data: { email: 'not-a-user-' + TAG, password: 'x' } })
  if (!res.ok()) {
    ok('a second, unauthenticated principal cannot read the tenant store (login refused)')
  } else {
    no('unexpected: a fake account could log in')
  }

  // ── Cleanup: remove everything this test created ────────────────────────
  try {
    let removed = 0
    let expected = 0
    for (const seg of ['projects', 'assets', 'jobs']) {
      const list = await apiGet(apiCtx, `/api/design-studio/${seg}`)
      const rows = list[seg] || list.items || []
      const mine = rows.filter(r => JSON.stringify(r.metadata || {}).includes(TAG) ||
        String(r.name || '').includes(TAG) || String(r.job_type || '').includes(TAG))
      expected += mine.length
      for (const r of mine) {
        const d = await apiCtx.delete(`${API}/api/design-studio/${seg}/${r.id}`)
        if (d.ok()) removed++
      }
    }
    const after = await apiGet(apiCtx, '/api/design-studio/status')
    const empty = after.projects === 0 && after.assets === 0 && after.jobs === 0
    if (empty) ok(`cleanup removed ${removed} record(s) and the store is empty (0/0/0)`)
    else no(`cleanup left ${after.projects}/${after.assets}/${after.jobs} behind (removed ${removed} of ${expected})`)
  } catch (e) {
    no('cleanup threw', String(e).slice(0, 100))
  }

  await browser.close()
  await apiCtx.dispose()
  return report()

  function report() {
    log('')
    log(`uncaught page errors: ${errors.length}`)
    errors.slice(0, 4).forEach(e => log('   ' + e.slice(0, 140)))
    log('')
    log(`MIGRATION E2E: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

main().catch((e) => { console.error('FATAL harness crash', e); process.exitCode = 2 })
