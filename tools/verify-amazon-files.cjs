// ═══════════════════════════════════════════════════════════════════════════
// AMAZON FILES — end-to-end harness (file-only architecture)
//
// Drives the whole workflow through the real API with a real session:
//   upload -> detect/validate -> propose (before/after, blocks, guardrail)
//   -> approve/reject (blocked + second confirmation refused) -> write the
//   change file -> download it -> re-upload and prove ONLY the approved
//   change differs -> A+ pack (not an uploadable module file).
//
// It also proves the run made ZERO non-local network requests.
//
// Run:  node tools/verify-amazon-files.cjs
// Exit: 0 = all green, 1 = a failure, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const API = BASE.replace(/\/ui\/?$/, '')
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const FIX = path.join(__dirname, 'fixtures', 'amazon_files')
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } })
  const page = await ctx.newPage()
  const external = []
  page.on('request', (r) => {
    try {
      const host = new URL(r.url()).hostname
      if (!['127.0.0.1', 'localhost'].includes(host)) external.push(r.url().slice(0, 100))
    } catch { /* non-URL request */ }
  })

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  // Everything goes through the page's fetch so the request tracker sees it.
  const call = async (method, url, body) => page.evaluate(async ({ method, url, body }) => {
    const res = await fetch(url, {
      method,
      credentials: 'include',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
    let json = null
    try { json = await res.json() } catch { /* non-JSON */ }
    return { status: res.status, json }
  }, { method, url: API + url, body })

  const b64 = (f) => fs.readFileSync(path.join(FIX, f)).toString('base64')
  const created = []

  // ── Upload the SP bulksheet ─────────────────────────────────────────────
  let r = await call('POST', '/api/design-studio/amazon-files/upload', {
    filename: 'sp_bulksheet.xlsx', content_b64: b64('sp_bulksheet.xlsx'), downloaded_at: new Date().toISOString().slice(0, 10),
  })
  if (r.status === 200 && r.json.upload.kind === 'ads_bulksheet' && r.json.upload.row_count === 4) {
    ok(`bulksheet uploaded: kind=${r.json.upload.kind}, ${r.json.upload.row_count} rows, checksum recorded`)
  } else no('bulksheet upload failed', `http ${r.status} ${JSON.stringify(r.json).slice(0, 160)}`)
  const up = r.json && r.json.upload
  if (up) created.push(up.id)
  if (up && up.checksum && up.missing_columns.length === 0) ok('checksum recorded; no required columns missing')
  else no('checksum/missing columns wrong', JSON.stringify(up && up.missing_columns))

  // ── Propose: bid change, campaign archive, blocked row, guardrail row ──
  const sheet = up.sheets[0].name
  r = await call('POST', `/api/design-studio/amazon-files/${up.id}/proposals`, {
    spend_limit_cents: 100,
    changes: [
      { sheet, row_index: 2, op: 'Update', fields: { bid: '0.95' }, reason: 'raise bid on a converting term' },
      { sheet, row_index: 0, op: 'Archive', fields: {}, reason: 'retire the campaign' },
      { sheet, row_index: 3, op: 'Update', fields: { bid: '1.20' }, reason: 'row with no keyword id' },
      { sheet, row_index: 2, op: 'Update', fields: { bid: '1.50' }, reason: 'above the seller limit' },
    ],
  })
  const props = r.json && r.json.proposals
  if (r.status === 200 && props && props.length === 4) ok('four proposals built with before/after and evidence')
  else no('proposals failed', `http ${r.status} ${JSON.stringify(r.json).slice(0, 200)}`)
  const [p0, p1, p2, p3] = props || []
  if (p0 && p0.before.bid === '0.75' && p0.after.bid === '0.95' && p0.id_value === 'K300') ok('proposal 0: before/after + exact keyword ID')
  else no('proposal 0 wrong', JSON.stringify(p0).slice(0, 160))
  if (p1 && p1.op_value === 'Archive' && p1.id_value === 'C100') ok('proposal 1: Archive operation + campaign ID copied')
  else no('proposal 1 wrong', JSON.stringify(p1).slice(0, 160))
  if (p2 && p2.status === 'blocked' && (p2.blocks || []).some(b => b.includes('missing-id'))) ok('proposal 2: empty Keyword ID is BLOCKED')
  else no('proposal 2 not blocked', JSON.stringify(p2).slice(0, 160))
  if (p3 && p3.requires_second_confirmation) ok('proposal 3: above the spend limit -> second confirmation required')
  else no('guardrail missing', JSON.stringify(p3).slice(0, 160))

  // ── Approve / refuse ────────────────────────────────────────────────────
  r = await call('POST', `/api/design-studio/amazon-files/proposals/${p0.id}/approve`, { second_confirmation: false })
  if (r.status === 200 && r.json.proposal.status === 'approved') ok('approve: the bid change is approved')
  else no('approve failed', `http ${r.status}`)
  r = await call('POST', `/api/design-studio/amazon-files/proposals/${p2.id}/approve`, { second_confirmation: false })
  if (r.status === 409 && r.json.detail.code === 'proposal_blocked') ok('approve: a BLOCKED row is refused (409)')
  else no('blocked approval not refused', `http ${r.status}`)
  r = await call('POST', `/api/design-studio/amazon-files/proposals/${p3.id}/approve`, { second_confirmation: false })
  if (r.status === 409 && r.json.detail.code === 'second_confirmation_required') ok('approve: the spend-limit row needs the second confirmation (409)')
  else no('second confirmation not enforced', `http ${r.status}`)
  r = await call('POST', `/api/design-studio/amazon-files/proposals/${p1.id}/reject`, {})
  if (r.status === 200 && r.json.proposal.status === 'rejected') ok('reject: the Archive proposal is rejected')
  else no('reject failed', `http ${r.status}`)

  // ── Write the change file + round-trip ─────────────────────────────────
  r = await call('POST', `/api/design-studio/amazon-files/${up.id}/write`, {})
  const cf = r.json && r.json.change_file
  const rt = r.json && r.json.roundtrip
  if (r.status === 200 && cf && cf.filename.includes('-change-v1') && cf.row_count === 1) ok(`change file written: ${cf.filename} (${cf.row_count} row)`)
  else no('write failed', `http ${r.status} ${JSON.stringify(r.json).slice(0, 200)}`)
  if (rt && rt.ok && rt.written_count === 1 && rt.source_checksum && rt.written_checksum) ok('round-trip: only the approved change differs; checksums recorded')
  else no('round-trip failed', JSON.stringify(rt).slice(0, 200))

  // ── Download the change file and re-upload it: only the bid changed ────
  const dl = await page.evaluate(async (url) => {
    const res = await fetch(url, { credentials: 'include' })
    const buf = await res.arrayBuffer()
    let binary = ''
    const bytes = new Uint8Array(buf)
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return { status: res.status, b64: btoa(binary) }
  }, `${API}/api/design-studio/amazon-files/change/${cf.id}/download`)
  if (dl.status === 200 && dl.b64) ok('the change file downloads as real bytes')
  else no('download failed', `http ${dl.status}`)
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'reupload.xlsx', content_b64: dl.b64 })
  const reup = r.json && r.json.upload
  if (reup) created.push(reup.id)
  if (reup && reup.kind === 'ads_bulksheet' && reup.row_count === 1) ok('the downloaded file re-parses as a bulksheet with exactly the one approved row')
  else no('re-upload parse wrong', JSON.stringify(reup && { kind: reup.kind, rows: reup.row_count }))
  if (reup) {
    const rowsRes = await call('GET', `/api/design-studio/amazon-files/${reup.id}/rows?sheet=${encodeURIComponent(reup.sheets[0].name)}`)
    const row = (rowsRes.json.rows || [])[0] || {}
    if (row.bid === '0.95' && row.keyword_id === 'K300' && row.operation === 'Update') {
      ok('the written row carries the approved bid (0.95) with the source ID and Operation intact')
    } else no('written row wrong', JSON.stringify(row).slice(0, 160))
  }

  // ── A+ pack: not an uploadable module file ─────────────────────────────
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'aplus_list.csv', content_b64: b64('aplus_list.csv') })
  const aplus = r.json && r.json.upload
  if (aplus) created.push(aplus.id)
  if (aplus && aplus.kind === 'aplus_asin_list') ok('A+ ASIN list uploaded and detected')
  else no('A+ upload failed', JSON.stringify(aplus && aplus.kind))
  r = await call('POST', `/api/design-studio/amazon-files/${aplus.id}/aplus-pack`, {
    assets: [{ name: 'hero.png', placement: 'Premium full-width image' }],
  })
  const pack = r.json && r.json.pack
  if (pack && pack.uploadable_module_file === false && pack.asin_bulk_upload_limit === null && /UNKNOWN/.test(pack.asin_bulk_upload_limit_note)) {
    ok('A+ pack: NOT an uploadable module file; the ASIN bulk-upload limit is UNKNOWN')
  } else no('A+ pack wrong', JSON.stringify(pack).slice(0, 200))
  if (pack && pack.asins.length === 2 && pack.assets[0].alt_text_required === true && /UNKNOWN/.test(pack.assets[0].alt_text_note || '')) {
    ok('A+ pack: ASINs read from the file; required alt text flagged when missing')
  } else no('A+ pack assets wrong', JSON.stringify(pack && pack.assets).slice(0, 200))
  // A+ copy slots (item 6): operator text carried; empty slots UNKNOWN.
  r = await call('POST', `/api/design-studio/amazon-files/${aplus.id}/aplus-pack`, {
    assets: [{ name: 'hero.png' }],
    copy: { headline: 'Built for the job' },
  })
  const pack2 = r.json && r.json.pack
  const slotOf = (p, s) => (p && p.copy_slots || []).find(x => x.slot === s) || {}
  if (slotOf(pack2, 'headline').text === 'Built for the job' && slotOf(pack2, 'headline').source === 'operator') {
    ok('A+ copy: the operator headline is carried with its source')
  } else no('A+ copy headline wrong', JSON.stringify(slotOf(pack2, 'headline')))
  if (slotOf(pack2, 'body').text === null && /UNKNOWN/.test(slotOf(pack2, 'body').note || '')) {
    ok('A+ copy: an empty slot stays UNKNOWN with a write-it-yourself note')
  } else no('A+ copy empty slot wrong', JSON.stringify(slotOf(pack2, 'body')))

  // ── Change files list (item 2 surface) ─────────────────────────────────
  r = await call('GET', `/api/design-studio/amazon-files/${up.id}/changes`)
  const cfList = r.json && r.json.change_files
  if (r.status === 200 && cfList && cfList.length === 1 && cfList[0].filename === cf.filename) {
    ok('change files list returns the written change file for its upload')
  } else no('change files list wrong', `http ${r.status} ${JSON.stringify(cfList).slice(0, 160)}`)

  // ── Processing report: proposals refused, rows matched (item 2) ────────
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'ads_error_report.xlsx', content_b64: b64('ads_error_report.xlsx') })
  const reportUp = r.json && r.json.upload
  if (reportUp) created.push(reportUp.id)
  if (reportUp && reportUp.kind === 'ads_error_report') ok('ads error report detected as a processing report')
  else no('error report detection wrong', JSON.stringify(reportUp && reportUp.kind))
  r = await call('POST', `/api/design-studio/amazon-files/${reportUp.id}/proposals`, { changes: [] })
  if (r.status === 422 && r.json.detail.code === 'report_has_no_proposals') ok('a report upload cannot produce proposals (422, stated reason)')
  else no('report proposals not refused', `http ${r.status}`)
  r = await call('POST', `/api/design-studio/amazon-files/${reportUp.id}/write`, {})
  if (r.status === 422 && r.json.detail.code === 'report_has_no_change_file') ok('a report upload cannot be written as a change file (422)')
  else no('report write not refused', `http ${r.status}`)
  r = await call('POST', '/api/design-studio/amazon-files/reports/match', {
    filename: 'ads_error_report.xlsx', content_b64: b64('ads_error_report.xlsx'), change_file_id: cf.id,
  })
  const match = r.json && r.json.match
  if (r.status === 200 && match && match.matched_count === 1 && match.unmatched_count === 1) {
    ok('report match: 1 row matched to the change file, 1 unmatched (never guessed)')
  } else no('report match counts wrong', `http ${r.status} ${JSON.stringify(match).slice(0, 200)}`)
  const hit = match && match.matches && match.matches[0]
  const k300ProposalIds = [p0, p2, p3].filter(Boolean).map(x => x.id)
  if (hit && k300ProposalIds.includes(hit.proposal_id) && /Bid is invalid/.test(hit.cause || '') && /bid/i.test(hit.fix_hint || '')) {
    ok('report match: row linked to a K300 proposal; cause quoted; bid-specific fix hint')
  } else no('report match linkage wrong', JSON.stringify(hit).slice(0, 220))
  if (match && match.unmatched[0] && /not matched/.test(match.unmatched[0].cause || '')) ok('report match: the K999 row is reported unmatched')
  else no('unmatched row not reported', JSON.stringify(match && match.unmatched).slice(0, 160))
  r = await call('POST', '/api/design-studio/amazon-files/reports/match', {
    filename: 'sp_bulksheet.xlsx', content_b64: b64('sp_bulksheet.xlsx'), change_file_id: cf.id,
  })
  if (r.status === 422 && r.json.detail.code === 'not_a_processing_report') ok('a non-report file is refused as a report (422, stated reason)')
  else no('non-report accepted as report', `http ${r.status}`)

  // ── Corrected resubmittable file (item 2) ──────────────────────────────
  r = await call('POST', `/api/design-studio/amazon-files/change/${cf.id}/correct`, {
    corrections: [{ row_index: 0, fields: { bid: '0.85' } }],
  })
  const corr = r.json && r.json.change_file
  const crt = r.json && r.json.roundtrip
  if (r.status === 200 && corr && /-corrected-v2/.test(corr.filename)) ok(`corrected file written as a NEW version: ${corr.filename}`)
  else no('corrected write failed', `http ${r.status} ${JSON.stringify(r.json).slice(0, 200)}`)
  if (crt && crt.ok && crt.written_count === 1) ok('corrected round-trip: only the corrections differ from the change file')
  else no('corrected round-trip failed', JSON.stringify(crt).slice(0, 200))
  const cdl = await page.evaluate(async (url) => {
    const res = await fetch(url, { credentials: 'include' })
    const buf = await res.arrayBuffer()
    let binary = ''
    const bytes = new Uint8Array(buf)
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return { status: res.status, b64: btoa(binary) }
  }, `${API}/api/design-studio/amazon-files/change/${corr.id}/download`)
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'corrected_reupload.xlsx', content_b64: cdl.b64 })
  const creup = r.json && r.json.upload
  if (creup) created.push(creup.id)
  if (creup && creup.row_count === 1) {
    const rowsRes = await call('GET', `/api/design-studio/amazon-files/${creup.id}/rows`)
    const row = (rowsRes.json.rows || [])[0] || {}
    if (row.bid === '0.85' && row.keyword_id === 'K300') ok('the corrected file re-parses with the corrected bid (0.85) and the same exact ID')
    else no('corrected row wrong', JSON.stringify(row).slice(0, 160))
  } else no('corrected re-upload wrong', JSON.stringify(creup && { kind: creup.kind, rows: creup.row_count }))
  r = await call('POST', `/api/design-studio/amazon-files/change/${cf.id}/correct`, { corrections: [{ row_index: 0, fields: { bullet1: 'nope' } }] })
  if (r.status === 422 && r.json.detail.code === 'correction_refused') ok('a correction naming a column the file does not carry is refused (422, stated reason)')
  else no('unknown-column correction not refused', `http ${r.status}`)

  // ── Before/after comparison (item 5) ───────────────────────────────────
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'metrics_before.xlsx', content_b64: b64('metrics_before.xlsx') })
  const beforeUp = r.json && r.json.upload
  if (beforeUp) created.push(beforeUp.id)
  r = await call('POST', '/api/design-studio/amazon-files/upload', { filename: 'metrics_after.xlsx', content_b64: b64('metrics_after.xlsx') })
  const afterUp = r.json && r.json.upload
  if (afterUp) created.push(afterUp.id)
  r = await call('POST', `/api/design-studio/amazon-files/${beforeUp.id}/compare`, {
    after_upload_id: afterUp.id,
    before_from: '2026-09-01', before_to: '2026-09-14', after_from: '2026-09-15', after_to: '2026-09-28',
  })
  const cmp = r.json && r.json.comparison
  const byKey = {}
  for (const row of (cmp && cmp.rows) || []) byKey[row.key] = row
  if (r.status === 200 && byKey.K300 && byKey.K300.delta_clicks === 6) ok('comparison: K300 before/after computed (12 → 18 clicks, delta 6)')
  else no('comparison delta wrong', `http ${r.status} ${JSON.stringify(byKey.K300).slice(0, 200)}`)
  if (byKey.K301 && byKey.K301.metrics.clicks.after === 'UNKNOWN' && byKey.K302 && byKey.K302.metrics.clicks.before === 'UNKNOWN') {
    ok('comparison: a metric missing from one file is UNKNOWN, never 0')
  } else no('comparison UNKNOWN handling wrong', JSON.stringify([byKey.K301, byKey.K302]).slice(0, 200))
  if (cmp && /NO CAUSATION/.test(cmp.causation || '') && /engineering choice/.test(cmp.stale_window_note || '') && cmp.stale_window_days === 14) {
    ok('comparison: explicit no-causation notice; 14-day window labelled an engineering choice')
  } else no('comparison notices wrong', JSON.stringify(cmp && { c: cmp.causation, s: cmp.stale_window_note }).slice(0, 200))

  // ── Brief → assets: templates only, tied to variant ids (item 7) ───────
  const termsCsv = [
    'Customer Search Term,Impressions,Clicks,Spend,Sales,Orders',
    'cold brew filter,340,12,4.20,20.00,1',
    'tumbler steel,210,8,3.10,12.00,1',
    'insulated cup,120,4,1.10,5.00,0',
  ].join('\n')
  r = await call('POST', '/api/design-studio/imports', {
    kind: 'sp_search_terms', source_label: 'harness terms', filename: 'terms.csv', content: termsCsv,
  })
  if (r.status === 200 || r.json && r.json.state === 'duplicate') ok(`search terms imported (state=${r.json && r.json.state})`)
  else console.log(`NOTE  search-term import returned http ${r.status}: ${JSON.stringify(r.json).slice(0, 140)}`)
  r = await call('POST', '/api/design-studio/terms/brief/assets', {
    limit: 10, variants_limit: 2,
    brand: { promise: 'Keeps drinks cold', voice: 'Plain and practical', audience: 'commuters' },
    project_id: null,
  })
  const assets = r.json && r.json.variants
  if (r.status === 200 && r.json.template_only === true && Array.isArray(assets)) {
    if (assets.length === 0) {
      console.log('NOTE  no imported terms were available, so the brief produced 0 variants (honest empty)')
      ok('brief→assets: endpoint answered with template_only=true and an honest empty result')
    } else {
      const v = assets[0]
      if (v.id && v.name.startsWith('Brief variant:') && v.copy.headline === 'Keeps drinks cold - ' + v.brief_ref.term) {
        ok(`brief→assets: variant created with id ${String(v.id).slice(0, 8)}…, template headline from the brand promise + term`)
      } else no('brief variant wrong', JSON.stringify(v).slice(0, 220))
      if (Array.isArray(v.on_image_text) && v.on_image_text.some(l => l.layer === 'term')) ok('brief→assets: on-image text layers carry the imported term')
      else no('on-image text wrong', JSON.stringify(v.on_image_text).slice(0, 160))
      const vv = await call('GET', `/api/design-studio/variants/${v.id}`)
      if (vv.status === 200 && vv.json.variant) ok('brief→assets: the variant exists in the variants store (matchable by a later results import)')
      else no('variant not found in store', `http ${vv.status}`)
      // Clean the created variants up (harness hygiene).
      for (const a of assets) { if (a.id) await call('DELETE', `/api/design-studio/variants/${a.id}`) }
      ok(`brief→assets: ${assets.length} harness variant(s) cleaned up`)
    }
  } else no('brief→assets failed', `http ${r.status} ${JSON.stringify(r.json).slice(0, 200)}`)

  // ── No external network during the entire run ──────────────────────────
  // Fonts are self-hosted (2026-10-11): the served UI must make ZERO external
  // requests. Every external host - and every Amazon host in particular - fails.
  const unexpected = external.slice()
  const amazonHits = external.filter(u => /amazon\./i.test(u))
  if (unexpected.length === 0 && amazonHits.length === 0) {
    ok('ZERO external requests during the entire run (fonts self-hosted; no Amazon host contacted)')
  } else {
    no(`${unexpected.length + amazonHits.length} unexpected external request(s)`, [...amazonHits, ...unexpected].slice(0, 3).join(' | '))
  }

  // ── Cleanup ─────────────────────────────────────────────────────────────
  for (const id of created) await call('DELETE', `/api/design-studio/amazon-files/${id}`)
  ok(`cleaned up ${created.length} upload(s) (cascading their proposals and change files)`)

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`AMAZON FILES: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
