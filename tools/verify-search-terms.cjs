// ═══════════════════════════════════════════════════════════════════════════
// SEARCH-TERMS / BRIEFS / VARIANTS / INDEXING — end-to-end harness
// (Phase 6 items 4-7 + the legacy-redirect regression)
//
// Runs against a SERVED build (the container SPA at :80 by default) with the
// real credential login, because the imported-evidence endpoints are strictly
// tenant-scoped and refuse anonymous callers.
//
// Run:  node tools/verify-search-terms.cjs
//       HARNESS_BASE_URL=http://127.0.0.1:8200/ui/ node tools/verify-search-terms.cjs
// Exit: 0 = all green, 1 = a failure, 2 = FATAL / watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)
const NAV_TIMEOUT = 30000

let pass = 0
let fail = 0
let fatal = 0
let lastStep = 'start'
const log = (m) => console.log(m)
const step = (s) => { lastStep = s; log(`      ... ${s}`) }
const ok = (m) => { pass++; log('PASS  ' + m) }
const no = (m, d) => { fail++; log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; log('FATAL ' + m + (d ? ' :: ' + d : '')) }

// Synthetic fixtures only. The files exercise the honesty rules (missing
// columns, a real 0, dated rows) without carrying any third-party text.
const SP_CSV = [
  'Customer Search Term,Campaign Name,Match Type,Date,Clicks,Spend,7 Day Total Orders (#)',
  'tumbler steel 20oz,Launch,broad,2026-09-20,18,12.40,3',
  'cold brew filter,Launch,exact,2026-09-21,0,0,0',
  'yoga mat grip,Summer,phrase,2026-09-21,4,3.10,1',
].join('\n')
const BA_CSV = [
  'Search Query,Search Frequency Rank,Search Query Score',
  'insulated tumbler,41,88.2',
  'travel coffee kit,120,71.5',
].join('\n')
const METRICS_CSV = [
  'variant,impressions,clicks,orders,spend',
  'Harness hero 1:1,1000,12,3,4.20',
  'ghost variant,5,1,0,0.10',
].join('\n')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })

  // ── Sign in (strict session required by the imported-evidence routes) ────
  step('signing in')
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  await page.waitForSelector('#signin-id', { timeout: NAV_TIMEOUT })
  await page.waitForTimeout(800)
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in with a real credential session')
  } catch {
    ftl('sign-in failed', await page.evaluate(() => location.pathname))
    await browser.close()
    return report()
  }

  // ── Deterministic start: remove THIS harness's own fixtures from earlier
  // runs (a tenant store persists between runs; deleting only records whose
  // source label / name carries the "harness" prefix keeps re-runs honest).
  step('cleaning up this harness\'s fixtures from earlier runs')
  await page.goto(BASE + 'home', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  const cleaned = await page.evaluate(async () => {
    const j = await (await fetch('/api/design-studio/imports', { credentials: 'include' })).json()
    const mine = (j.imports || []).filter(i => String(i.source_label || '').startsWith('harness '))
    for (const i of mine) {
      await fetch('/api/design-studio/imports/' + encodeURIComponent(i.id), { method: 'DELETE', credentials: 'include' })
    }
    const vj = await (await fetch('/api/design-studio/variants', { credentials: 'include' })).json()
    const vmine = (vj.variants || []).filter(v => String(v.name || '').startsWith('Harness '))
    for (const v of vmine) {
      await fetch('/api/design-studio/variants/' + encodeURIComponent(v.id), { method: 'DELETE', credentials: 'include' })
    }
    return { imports: mine.length, variants: vmine.length }
  })
  ok(`fixture cleanup: ${cleaned.imports} import(s) and ${cleaned.variants} variant(s) removed (the store persists between runs)`)

  // ── Seed the local listing stores (item 5 reads them; no marketplace call) ─
  step('seeding the local ListingForge record + brand profile')
  await page.evaluate(() => {
    localStorage.setItem('ns-studio-lf-listings', JSON.stringify([{
      asin: 'B00HARNESS1',
      title: 'Harness tumbler listing',
      updated: '2026-10-05T00:00:00Z',
      copy: {
        title: 'Stainless steel tumbler — 20oz, cold brew ready',
        bullets: ['Keeps drinks cold for hours', 'Fits most cup holders'],
        description: 'A tumbler built for cold brew.',
        keywords: 'tumbler, cold brew, steel cup',
      },
    }]))
    localStorage.setItem('ns-studio-ds-brand-profile', JSON.stringify({
      id: 'brand-harness', name: 'Harness Brand', promise: 'Brew better mornings',
      voice: 'Warm, plain-spoken', audience: 'home brewers', updatedAt: '2026-10-01T00:00:00Z',
    }))
  })
  ok('local listing record + brand profile seeded (browser stores only)')

  // ── Proof the strict dependency actually refuses anonymous callers ───────
  step('proving the imported-evidence routes refuse an anonymous caller')
  const { request } = require('playwright')
  const anonCtx = await request.newContext() // NO cookies: a different principal
  const anon = await anonCtx.get(BASE.replace(/\/ui\/?$/, '') + '/api/design-studio/imports')
  if (anon.status() === 401) ok('anonymous call to /imports -> 401 (tenant-scoped surface)')
  else no(`anonymous call returned ${anon.status()} (expected 401)`)
  await anonCtx.dispose()

  // ── The surface mounts; Brand Analytics starts UNAVAILABLE; notes show ───
  step('opening Ads › Search terms')
  await page.goto(BASE + 'design-studio?section=ads&view=search-terms', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  await page.waitForSelector('[data-testid="search-terms-workspace"]', { timeout: NAV_TIMEOUT })
  ok('the Search terms sub-view mounted inside Ads')
  const notesText = await page.$eval('[data-testid="import-notes"]', e => e.textContent).catch(() => '')
  for (const needle of ['65-day', '31 days', 'Click-only']) {
    if (notesText.includes(needle)) ok(`the pre-import notes state "${needle}"`)
    else no(`the pre-import notes are missing "${needle}"`)
  }
  const baBefore = await page.$eval('[data-testid="ba-status"]', e => e.textContent).catch(() => '')
  if (/UNAVAILABLE/.test(baBefore)) ok('Brand Analytics reads UNAVAILABLE before any file is imported')
  else no('Brand Analytics did not start UNAVAILABLE')

  // ── Import the SP file ────────────────────────────────────────────────────
  step('importing the Sponsored Products fixture')
  await page.selectOption('select.field', 'sp_search_terms').catch(() => no('kind select not found'))
  await page.fill('input.field[placeholder*="SP console"]', 'harness SP export, US')
  await page.setInputFiles('[data-testid="import-file"]', { name: 'sp-terms.csv', mimeType: 'text/csv', buffer: Buffer.from(SP_CSV) })
  await page.click('[data-testid="import-run"]')
  await page.waitForSelector('[data-testid="import-banner"]', { timeout: 20000 })
  const banner = await page.$eval('[data-testid="import-banner"]', e => e.textContent)
  if (/^imported file, observed .+, not live$/.test(banner.trim())) ok(`the banner states the truth: "${banner.trim()}"`)
  else no('the banner does not read "imported file, observed <date>, not live"', banner.slice(0, 120))
  const result = await page.$eval('[data-testid="import-result"]', e => e.textContent).catch(() => '')
  if (/Columns absent from the file/i.test(result) && /impressions/i.test(result)) ok('the result names the absent columns (their values are UNKNOWN)')
  else no('the result does not name the absent columns', result.slice(0, 160))

  step('re-importing the identical file')
  const rowsBefore = await page.$$eval('table.table tbody tr', rs => rs.length)
  await page.setInputFiles('[data-testid="import-file"]', { name: 'sp-terms.csv', mimeType: 'text/csv', buffer: Buffer.from(SP_CSV) })
  await page.click('[data-testid="import-run"]')
  await page.waitForTimeout(1200)
  const dup = await page.$eval('[data-testid="import-result"]', e => e.textContent).catch(() => '')
  if (/nothing was duplicated/i.test(dup)) ok('re-importing the identical file reports duplicate, nothing duplicated')
  else no('duplicate import was not recognized', dup.slice(0, 160))

  // ── Import the BA file; the panel flips to IMPORTED ─────────────────────
  step('importing the Brand Analytics fixture')
  await page.selectOption('select.field', 'brand_analytics_sqp').catch(() => {})
  await page.fill('input.field[placeholder*="SP console"]', 'harness BA SQP export')
  await page.setInputFiles('[data-testid="import-file"]', { name: 'sqp.csv', mimeType: 'text/csv', buffer: Buffer.from(BA_CSV) })
  await page.click('[data-testid="import-run"]')
  await page.waitForTimeout(1500)
  const baAfter = await page.$eval('[data-testid="ba-status"]', e => e.textContent).catch(() => '')
  if (/IMPORTED/.test(baAfter) && !/UNAVAILABLE/.test(baAfter)) ok('Brand Analytics flips to IMPORTED only after the file arrives')
  else no('Brand Analytics did not flip to IMPORTED', baAfter.slice(0, 160))

  // ── Import the brand voice + a keyword list (Phase 7 item 6) ────────────
  step('importing the brand voice and keyword fixtures')
  await page.selectOption('select.field', 'brand_voice').catch(() => {})
  await page.fill('input.field[placeholder*="SP console"]', 'harness brand voice')
  await page.setInputFiles('[data-testid="import-file"]', {
    name: 'voice.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ name: 'Harness Brand', promise: 'Brew better mornings', voice: 'Warm, plain-spoken', audience: 'home brewers' })),
  })
  await page.click('[data-testid="import-run"]')
  await page.waitForTimeout(1200)
  let result2 = await page.$eval('[data-testid="import-result"]', e => e.textContent).catch(() => '')
  if (/harness brand voice/.test(result2) || /row\(s\) archived/.test(result2)) ok('the brand-voice file imported and archived with its label')
  else no('brand-voice import failed', result2.slice(0, 140))

  await page.selectOption('select.field', 'keywords').catch(() => {})
  await page.fill('input.field[placeholder*="SP console"]', 'harness keywords')
  await page.setInputFiles('[data-testid="import-file"]', {
    name: 'keywords.csv', mimeType: 'text/csv',
    buffer: Buffer.from('keyword,volume\ncold brew filter,900\ninsulated cup,\n'),
  })
  await page.click('[data-testid="import-run"]')
  await page.waitForTimeout(1200)
  result2 = await page.$eval('[data-testid="import-result"]', e => e.textContent).catch(() => '')
  if (/row\(s\) archived/.test(result2)) ok('the keyword list imported and archived')
  else no('keyword import failed', result2.slice(0, 140))
  const archiveText = await page.$$eval('table.table', ts => ts.map(t => t.textContent).join(' ')).catch(() => '')
  if (/Keyword list/.test(archiveText) && /Brand voice/.test(archiveText)) ok('the archive lists both new kinds with their dates and labels')
  else no('archive does not list the new kinds', archiveText.slice(0, 160))

  // ── Terms table honesty: UNKNOWN for absent columns, a real 0 stays 0 ───
  step('checking the terms table honesty rules')
  await page.click('button:has-text("Apply")')
  await page.waitForTimeout(1000)
  const row = async (term) => page.$$eval('[data-testid="terms-table"] tbody tr', (rs, t) => {
    const r = rs.find(x => x.textContent.includes(t))
    return r ? Array.from(r.querySelectorAll('td')).map(td => td.textContent.trim()) : null
  }, term)
  const tumbler = await row('tumbler steel 20oz')
  const zeroRow = await row('cold brew filter')
  if (tumbler && tumbler[3] === 'UNKNOWN' && tumbler[4] === '18') {
    ok('a term without an impressions column shows UNKNOWN; a real click count stays a number')
  } else no('terms-row honesty failed (tumbler)', JSON.stringify(tumbler))
  if (zeroRow && zeroRow[4] === '0' && zeroRow[6] === '0') {
    ok('a literal 0 click/spend value in the file stays 0 (only absence becomes UNKNOWN)')
  } else no('a literal 0 was not preserved', JSON.stringify(zeroRow))
  const baRow = await row('insulated tumbler')
  if (baRow && baRow[4] === 'UNKNOWN' && baRow[9] === 'BA SQP') ok('a BA row shows clicks UNKNOWN and is labelled BA SQP')
  else no('BA row rendering wrong', JSON.stringify(baRow))

  // ── Export CSV: tenant-scoped download, NULL written as empty ───────────
  step('checking the export CSV')
  const exportRes = await ctx.request.get(BASE.replace(/\/ui\/?$/, '') + '/api/design-studio/terms/export')
  if (exportRes.status() === 200) ok('the export endpoint answers a signed-in session (200)')
  else no(`export returned ${exportRes.status()}`)
  const csv = await exportRes.text()
  const header = csv.split('\n')[0]
  if (header.startsWith('term,campaign,ad_group,match_type,impressions,clicks,orders,spend,sales')) ok('the export carries the documented column order')
  else no('export header wrong', header.slice(0, 120))
  const expLine = csv.split('\n').find(l => l.startsWith('tumbler steel 20oz'))
  if (expLine && expLine.split(',')[4] === '' ) ok('a NULL metric exports as an EMPTY cell, not 0')
  else no('export did not keep NULL empty', JSON.stringify(expLine))

  // ── Brief composition ────────────────────────────────────────────────────
  step('composing a brief from the shown terms')
  await page.click('[data-testid="brief-run"]')
  await page.waitForSelector('[data-testid="brief-panel"]', { timeout: 20000 })
  const briefText = await page.$eval('[data-testid="brief-panel"]', e => e.textContent).catch(() => '')
  if (/composed — nothing generated/i.test(briefText)) ok('the brief panel states nothing was generated')
  else no('the brief panel does not state the no-generation boundary')
  if (/Click-only bias/i.test(briefText)) ok('every ranking that reads clicks carries the click-only caveat')
  else no('the click-only caveat is missing from the brief')
  if (/UNKNOWN/.test(briefText) && /very small|small|moderate|large/i.test(briefText)) ok('sample-size labels appear; UNKNOWN survives for missing data')
  else no('no sample-size labelling found in the brief')
  if (/No image or video is generated by this brief/i.test(briefText)) ok('the brief notes state the no-generation rule')
  else no('the brief notes miss the no-generation rule')

  // ── Voice provenance (item 6): the imported file wins and is named ──────
  const prov = await page.$eval('[data-testid="brief-voice-provenance"]', e => e.textContent).catch(() => '')
  if (/imported brand-voice file/.test(prov) && /harness brand voice/.test(prov)) {
    ok(`the brief names the imported voice file as its provenance ("${prov.slice(0, 90)}…")`)
  } else no('voice provenance does not name the imported file', prov.slice(0, 160))

  // ── Listing context (item 5): local fields with provenance + mismatches ─
  const ctxText = await page.$eval('[data-testid="listing-context"]', e => e.textContent).catch(() => '')
  if (/Stainless steel tumbler/.test(ctxText) && /ListingForge local record/.test(ctxText)) {
    ok('the listing context shows the local title with its source named')
  } else no('listing context missing the title or its source', ctxText.slice(0, 160))
  if (/2026-10-05/.test(ctxText) && /current/.test(ctxText)) ok('the observed date and freshness are shown for the record')
  else no('observed date / freshness missing', ctxText.slice(0, 160))
  if (/UNKNOWN/.test(ctxText)) ok('a field no local store provides reads UNKNOWN (not blank, not invented)')
  else no('no UNKNOWN field rendered - suspicious')
  const mismatch = await page.$eval('[data-testid="listing-mismatch"]', e => e.textContent).catch(() => '')
  if (/NEEDS HUMAN REVIEW/.test(mismatch) && /does not carry/.test(mismatch)) {
    ok(`a creative term absent from the listing copy is flagged for human review ("${mismatch.slice(0, 90)}…")`)
  } else no('no mismatch flag rendered', mismatch.slice(0, 160))

  // ── Variants: create, metric, compare warnings, file import matching ────
  step('working the variant comparison')
  await page.fill('input.field[placeholder*="Hero v2"]', 'Harness hero 1:1')
  await page.click('button:has-text("Add variant")')
  await page.waitForTimeout(1200)
  const createdRow = await page.$$eval('[data-testid="variants-panel"] tbody tr', rs => rs.map(r => r.textContent))
  if (createdRow.some(t => t.includes('Harness hero 1:1'))) ok('variant created and listed')
  else no('variant did not appear')
  await page.click('[data-testid="variants-panel"] tbody tr button:has-text("Add")')
  await page.fill('input[placeholder="clicks"]', '5')
  await page.click('[data-testid="variants-panel"] button:has-text("Store")')
  await page.waitForTimeout(1200)
  await page.click('[data-testid="compare-run"]')
  await page.waitForSelector('[data-testid="variant-compare"]', { timeout: 15000 })
  const cmp = await page.$eval('[data-testid="variant-compare"]', e => e.textContent).catch(() => '')
  if (/Small sample: 5 clicks/i.test(cmp)) ok('a 5-click comparison warns about the small sample')
  else no('the sample-size warning is missing', cmp.slice(0, 140))
  if (/small/i.test(cmp) && /Under 25 clicks/i.test(cmp)) ok('the comparison carries the shared confidence band and note')
  else no('confidence band missing from the comparison', cmp.slice(0, 160))
  if (/makes NO causation claim/i.test(cmp) && /no creative identifier/i.test(cmp)) ok('the comparison carries the no-causation and attribution-gap statements')
  else no('the no-causation statement is missing')

  // ── Results CSV (item 7): real download, NULL as empty, caveat present ──
  const csvRes = await ctx.request.get(BASE.replace(/\/ui\/?$/, '') + '/api/design-studio/variants/export')
  if (csvRes.status() === 200) ok('the variant results CSV answers a signed-in session (200)')
  else no(`variants export returned ${csvRes.status()}`)
  const vcsv = await csvRes.text()
  if (/NO CAUSATION CLAIM/.test(vcsv) && /sample,confidence_note/.test(vcsv.split('\n')[0])) {
    ok('the results CSV carries the header and the no-causation caveat')
  } else no('results CSV header/caveat wrong', vcsv.split('\n')[0].slice(0, 140))
  const vLine = vcsv.split('\n').find(l => l.startsWith('Harness hero 1:1'))
  if (vLine && vLine.split(',')[5] === '') ok('a NULL metric exports as an EMPTY cell in the results CSV')
  else no('results CSV did not keep NULL empty', JSON.stringify(vLine && vLine.slice(0, 120)))

  step('importing a metrics file with an unmatched row')
  await page.setInputFiles('[data-testid="variant-metrics-file"]', { name: 'metrics.csv', mimeType: 'text/csv', buffer: Buffer.from(METRICS_CSV) })
  await page.waitForSelector('[data-testid="metrics-import-result"]', { timeout: 15000 })
  const metricsMsg = await page.$eval('[data-testid="metrics-import-result"]', e => e.textContent).catch(() => '')
  if (/1 row\(s\) attached; 1 unmatched/.test(metricsMsg)) ok('metrics file attached 1 row and reported the unmatched row')
  else no('metrics file result wrong', metricsMsg.slice(0, 160))
  const names = await page.$$eval('[data-testid="variants-panel"] tbody tr', rs => rs.map(r => r.textContent))
  if (!names.some(t => t.includes('ghost variant'))) ok('an unmatched metrics row is never turned into a variant')
  else no('the unmatched row created a variant')

  // ── Indexing register (item 7) ───────────────────────────────────────────
  step('opening the indexing register')
  await page.goto(BASE + 'design-studio?section=aplus&view=indexing', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  await page.waitForSelector('[data-testid="indexing-register"]', { timeout: NAV_TIMEOUT })
  ok('the Indexing claims register mounted inside A+')
  const regText = await page.$eval('[data-testid="indexing-register"]', e => e.textContent).catch(() => '')
  if (/no recorded Amazon source/i.test(regText)) ok('the register states imagery has no recorded ranking source')
  else no('the register does not state the imagery limit')
  if (/UNSOURCED/.test(regText) && /unofficial/i.test(regText)) ok('the folklore claims render as UNSOURCED/unofficial')
  else no('folklore claims are not marked UNSOURCED/unofficial')
  // The phrase may appear ONLY with a negation in the same window (the register
  // explains the myth in order to refuse it).
  let positiveAlt = false
  {
    const mention = /alt[- ]?text/gi
    let m
    while ((m = mention.exec(regText)) !== null) {
      const w = regText.slice(Math.max(0, m.index - 160), Math.min(regText.length, m.index + 200))
      if (/improv\w*[^.]{0,40}ranking|ranking[^.]{0,40}improv/i.test(w) && !/not\b|never\b|no recorded|no amazon|will not|does not|doesn't/i.test(w)) {
        positiveAlt = true
      }
    }
  }
  if (!positiveAlt) ok('the register never tells the seller alt text improves ranking')
  else no('the register contains a positive alt-text ranking claim')

  // ── The legacy redirect keeps the sub-view (merge regression) ───────────
  step('checking the legacy redirect carries the sub-view')
  await page.goto(BASE + 'creative-studio?view=briefs', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  await page.waitForTimeout(1500)
  const redirected = await page.evaluate(() => ({ path: location.pathname, search: location.search }))
  const params = new URLSearchParams(redirected.search)
  if (redirected.path === '/ui/design-studio' && params.get('section') === 'projects' && params.get('view') === 'briefs') {
    ok('creative-studio?view=briefs -> design-studio?section=projects&view=briefs')
  } else no('legacy redirect dropped the view param', JSON.stringify(redirected))

  // ── Error budget ─────────────────────────────────────────────────────────
  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors beyond the pre-auth 401 noise (${errors.length} filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 3).join(' | '))

  await browser.close()
  return report()

  function report() {
    log('')
    log(`SEARCH TERMS / BRIEFS / VARIANTS / INDEXING: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) =>
  setTimeout(() => rej(new Error(`WATCHDOG: no completion after ${WATCHDOG_MS}ms. Last step reached: "${lastStep}"`)), WATCHDOG_MS))

Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => {
    console.error('')
    console.error(`FATAL ${e.message}`)
    console.error(`       last step reached: "${lastStep}"`)
    process.exit(2)
  },
)
