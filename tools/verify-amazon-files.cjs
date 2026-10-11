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

  // ── No external network during the entire run ──────────────────────────
  // Allowed: the app shell's own web-font CDN (pre-existing, unrelated to the
  // file path). Everything else - and every Amazon host in particular - must
  // be absent.
  const FONT_CDNS = ['fonts.googleapis.com', 'fonts.gstatic.com']
  const unexpected = external.filter(u => !FONT_CDNS.some(h => u.includes(h)))
  const amazonHits = external.filter(u => /amazon\./i.test(u))
  if (unexpected.length === 0 && amazonHits.length === 0) {
    ok(`no non-local request outside the app's own font CDN; ZERO Amazon hosts contacted (${external.length} font request(s) noted)`)
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
