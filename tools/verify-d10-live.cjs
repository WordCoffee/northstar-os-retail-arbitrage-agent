// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// D10 LIVE NEGATIVES â€” cross-tenant + anonymous on the Design Studio routes
// (Phase 7 item 1). Runs against the served stack; uses the isolated test
// accounts (subscriber + other_tenant) WITHOUT printing any credential.
//
// Proves, over real HTTP with two real organizations:
//   â€¢ anonymous -> 401 on every legacy route (list/read/search/export/mutate);
//   â€¢ tenant B cannot list, search, read, export or delete tenant A's records;
//   â€¢ each tenant sees exactly its own records.
//
// Run:  node tools/verify-d10-live.cjs
// Exit: 0 = isolated, 1 = a leak, 2 = FATAL.
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

const fs = require('fs')
const path = require('path')
const { request } = require('playwright')

const API = process.env.HARNESS_API_URL || 'http://127.0.0.1'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 180000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

function credentialsPath() {
  return process.env.NS_TEST_CREDENTIALS_PATH
    || path.join(process.env.LOCALAPPDATA || '', 'NorthstarOS', 'foundation-test-accounts.json')
}

function loadAccount(key) {
  const file = credentialsPath()
  if (!fs.existsSync(file)) { console.error(`No credentials file at ${file}`); process.exit(2) }
  const j = JSON.parse(fs.readFileSync(file, 'utf8'))
  const a = j.accounts && j.accounts[key]
  if (!a || !a.email || !a.password) { console.error(`Account "${key}" missing from the credentials file`); process.exit(2) }
  return a // never printed
}

async function signIn(key) {
  const acct = loadAccount(key)
  const ctx = await request.newContext()
  const r = await ctx.post(`${API}/api/v1/foundation/auth/login`, { data: { email: acct.email, password: acct.password } })
  if (r.status() !== 200) { ftl(`sign-in failed for "${key}"`, `http ${r.status()}`); return null }
  return ctx
}

async function main() {
  const A = await signIn('tenant_a')
  const B = await signIn('tenant_b')
  const anon = await request.newContext()
  if (!A || !B) { await anon.dispose(); return report() }
  ok('signed in two distinct organizations (subscriber / other_tenant)')

  const stamp = Date.now().toString(36)
  const probeName = `D10 probe ${stamp}`

  // Tenant A writes a project and a recheck through the REAL routes.
  const mk = await A.post(`${API}/api/design-studio/projects`, { data: { name: probeName, section: 'listing-images', asin: 'B00D10TEST' } })
  if (mk.status() !== 200) { ftl('tenant A could not create a project', `http ${mk.status()}`); return report() }
  const pid = (await mk.json()).id
  const rc = await A.post(`${API}/api/design-studio/rechecks`, { data: { asset_id: `asset-${stamp}`, verdict: 'marker-present', passed: true, surface: 'd10-live' } })
  if (rc.status() !== 200) ftl('tenant A could not create a recheck', `http ${rc.status()}`)
  else ok('tenant A created its own records through the strict routes')

  // A sees its own data.
  const aList = await (await A.get(`${API}/api/design-studio/projects`)).json()
  const aSearch = await (await A.get(`${API}/api/design-studio/search?q=${encodeURIComponent(stamp)}`)).json()
  if ((aList.projects || []).some(p => p.id === pid) && (aSearch.projects || []).some(p => p.id === pid)) {
    ok('tenant A lists and searches its own record')
  } else no('tenant A cannot see its own record', JSON.stringify({ list: aList.projects && aList.projects.length, search: aSearch.projects && aSearch.projects.length }))

  // B must not see it anywhere.
  const bList = await (await B.get(`${API}/api/design-studio/projects`)).json()
  const bSearch = await (await B.get(`${API}/api/design-studio/search?q=${encodeURIComponent(stamp)}`)).json()
  if (!(bList.projects || []).some(p => p.id === pid)) ok('tenant B LIST does not contain tenant A\'s project')
  else no('LEAK: tenant B listed tenant A\'s project')
  if ((bSearch.projects || []).length === 0 && (bSearch.rechecks || []).length === 0) ok('tenant B SEARCH returns nothing for A\'s probe')
  else no('LEAK: tenant B search crossed tenants', JSON.stringify(bSearch.counts))

  // B cannot read / export / delete by id.
  const bRead = await B.get(`${API}/api/design-studio/projects/${pid}`)
  const bExport = await B.get(`${API}/api/design-studio/projects/${pid}/export-manifest`)
  const bDelete = await B.delete(`${API}/api/design-studio/projects/${pid}`)
  if (bRead.status() === 404) ok('tenant B READ by id -> 404 (indistinguishable from missing)')
  else no(`tenant B read returned ${bRead.status()} (expected 404)`)
  if (bExport.status() === 404) ok('tenant B EXPORT manifest -> 404')
  else no(`tenant B export returned ${bExport.status()} (expected 404)`)
  if (bDelete.status() === 404) ok('tenant B DELETE -> 404')
  else no(`tenant B delete returned ${bDelete.status()} (expected 404)`)
  const aStill = await A.get(`${API}/api/design-studio/projects/${pid}`)
  if (aStill.status() === 200) ok('tenant A\'s record survives B\'s attempted delete')
  else no('tenant A\'s record disappeared after B\'s attempt', `http ${aStill.status()}`)

  // B's rechecks list must not contain A's entry.
  const bRechecks = await (await B.get(`${API}/api/design-studio/rechecks`)).json()
  if (!(bRechecks.rechecks || []).some(r => r.asset_id === `asset-${stamp}`)) ok('tenant B re-check LIST excludes A\'s entry')
  else no('LEAK: tenant B saw A\'s re-check entry')

  // ── Listing records (Phase 8 item 3): tenant store + idempotent migration ─
  const lrPayload = { records: [{
    asin: `B00LR${stamp.slice(0, 5).toUpperCase()}`, title: 'Tenant A listing record',
    bullets: ['bullet one'], backend_terms: 'terms a', description: 'desc a',
    observed_at: '2026-10-05T00:00:00Z', legacy_key: `lr:${stamp}`,
  }] }
  const lrMig = await A.post(`${API}/api/design-studio/listing-records/migrate`, { data: lrPayload })
  const lrMigBody = await lrMig.json().catch(() => ({}))
  if (lrMig.status() === 200 && lrMigBody.created === 1) ok('tenant A migrated a listing record into the tenant store')
  else no('listing-record migrate failed', `http ${lrMig.status()} ${JSON.stringify(lrMigBody).slice(0, 120)}`)
  const lrDup = await A.post(`${API}/api/design-studio/listing-records/migrate`, { data: lrPayload })
  const lrDupBody = await lrDup.json().catch(() => ({}))
  if (lrDupBody.created === 0 && lrDupBody.skipped === 1) ok('re-running the migration reports skipped, never a duplicate')
  else no('listing-record migration is not idempotent', JSON.stringify(lrDupBody).slice(0, 120))
  const aLr = await (await A.get(`${API}/api/design-studio/listing-records`)).json()
  const aRec = (aLr.records || []).find(r => r.legacy_key === `lr:${stamp}`)
  if (aRec) ok('tenant A lists its own listing record')
  else no('tenant A cannot see its migrated record')
  const bLr = await (await B.get(`${API}/api/design-studio/listing-records`)).json()
  if (!(bLr.records || []).some(r => r.legacy_key === `lr:${stamp}`)) ok('tenant B LIST does not contain A\'s listing record')
  else no('LEAK: tenant B listed A\'s listing record')
  if (aRec) {
    const bRead = await B.get(`${API}/api/design-studio/listing-records/${aRec.id}`)
    const bDel = await B.delete(`${API}/api/design-studio/listing-records/${aRec.id}`)
    if (bRead.status() === 404) ok('tenant B READ by id -> 404')
    else no(`tenant B listing-record read returned ${bRead.status()}`)
    if (bDel.status() === 404) ok('tenant B DELETE -> 404')
    else no(`tenant B listing-record delete returned ${bDel.status()}`)
  }

  // Anonymous: every legacy route refuses with 401.
  const anonRoutes = [
    ['GET', '/api/design-studio/projects'],
    ['GET', '/api/design-studio/assets'],
    ['GET', '/api/design-studio/jobs'],
    ['GET', '/api/design-studio/rechecks'],
    ['GET', '/api/design-studio/search?q=x'],
    ['GET', `/api/design-studio/projects/${pid}/export-manifest`],
    ['POST', '/api/design-studio/projects'],
    ['GET', '/api/design-studio/status'],
    ['GET', '/api/design-studio/imports'],
    ['GET', '/api/design-studio/terms'],
    ['GET', '/api/design-studio/variants'],
  ]
  let anonFailures = []
  for (const [method, url] of anonRoutes) {
    const r = method === 'GET' ? await anon.get(API + url) : await anon.post(API + url, { data: { name: 'anon', section: 'ads' } })
    if (r.status() !== 401) anonFailures.push(`${method} ${url} -> ${r.status()}`)
  }
  if (anonFailures.length === 0) ok(`anonymous -> 401 on all ${anonRoutes.length} design-studio routes`)
  else no('anonymous reached a design-studio route', anonFailures.join(' | '))

  // Cleanup: each tenant removes its own probes.
  await A.delete(`${API}/api/design-studio/projects/${pid}`)
  const aRechecks = await (await A.get(`${API}/api/design-studio/rechecks`)).json()
  for (const r of (aRechecks.rechecks || []).filter(x => x.asset_id === `asset-${stamp}`)) {
    await A.delete(`${API}/api/design-studio/rechecks/${r.id}`)
  }
  const aLrClean = await (await A.get(`${API}/api/design-studio/listing-records`)).json()
  for (const r of (aLrClean.records || []).filter(x => x.legacy_key === `lr:${stamp}`)) {
    await A.delete(`${API}/api/design-studio/listing-records/${r.id}`)
  }
  ok('probe records cleaned up by their owner')

  await A.dispose(); await B.dispose(); await anon.dispose()
  return report()

  function report() {
    console.log('')
    console.log(`D10 LIVE NEGATIVES: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
