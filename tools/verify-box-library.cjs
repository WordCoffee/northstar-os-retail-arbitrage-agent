// BOX LIBRARY — Boxes.py external generator harness (2026-10-16)
//
// Proves the box library end-to-end: the library catalog, a real generation
// through the API, refusals (unknown generator, out-of-range params,
// anonymous), and the UI card generating + previewing a structure.
//
// Run:  node tools/verify-box-library.cjs   (stack on :80; dev server for UI)
// Exit: 0 = all green, 1 = a failure, 2 = FATAL/watchdog.

const { chromium, request } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const API = BASE.replace(/\/ui\/?$/, '')
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
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
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)) })

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 20000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  // API calls ride the context's request client (same cookies as the page,
  // but OUTSIDE the page: intentional refusals do not pollute the console).
  const api = ctx.request
  const call = async (method, url, body) => {
    const res = await api.fetch(API + url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      data: body ? JSON.stringify(body) : undefined,
    })
    let json = null
    try { json = await res.json() } catch { /* non-JSON */ }
    return { status: res.status(), json }
  }

  // ── Library catalog ────────────────────────────────────────────────────
  let r = await call('GET', '/api/design-studio/print/box-library')
  const lib = r.json || {}
  if (r.status === 200 && Array.isArray(lib.generators) && lib.generators.length >= 10) {
    ok(`box library lists ${lib.generators.length} curated structures`)
  } else no('box library catalog wrong', `http ${r.status} ${JSON.stringify(lib).slice(0, 140)}`)
  if (/GPL-3\.0/.test(lib.license_note || '')) ok('license note states the external GPL-3.0 tool')
  else no('license note missing', JSON.stringify(lib.license_note).slice(0, 120))
  if (lib.available === true) ok('Boxes.py is available on this machine')
  else no('Boxes.py not available (install or rebuild the API image)', JSON.stringify(lib.available))

  // ── Real generation ────────────────────────────────────────────────────
  r = await call('POST', '/api/design-studio/print/box-generate', {
    generator: 'ClosedBox', x: 120, y: 90, h: 70, thickness: 3,
  })
  const gen = r.json || {}
  if (r.status === 200 && typeof gen.svg === 'string' && gen.svg.includes('<svg') && gen.size_bytes > 1000) {
    ok(`generated ClosedBox locally (${gen.size_bytes} bytes of SVG)`)
  } else no('box generation failed', `http ${r.status} ${JSON.stringify(gen).slice(0, 160)}`)
  if (gen.params && gen.params.x === 120 && gen.params.thickness === 3) ok('generation echoes the exact parameters')
  else no('parameters not echoed', JSON.stringify(gen.params))

  // ── Refusals ───────────────────────────────────────────────────────────
  r = await call('POST', '/api/design-studio/print/box-generate', { generator: 'NotARealThing' })
  if (r.status === 422 && r.json.detail.code === 'box_generation_refused') ok('unknown generator is refused (422, stated reason)')
  else no('unknown generator not refused', `http ${r.status}`)
  r = await call('POST', '/api/design-studio/print/box-generate', { generator: 'ClosedBox', x: 99999 })
  if (r.status === 422) ok('out-of-range parameter is refused (422)')
  else no('out-of-range not refused', `http ${r.status}`)

  // ── Anonymous refusal ──────────────────────────────────────────────────
  const anonCtx = await request.newContext()
  const anonRes = await anonCtx.get(API + '/api/design-studio/print/box-library')
  await anonCtx.dispose()
  if (anonRes.status() === 401) ok('anonymous -> 401 on the box library')
  else no(`anonymous got ${anonRes.status()}`)

  // ── UI card ────────────────────────────────────────────────────────────
  await page.goto(BASE + 'design-studio?section=dielines', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="box-library"]', { timeout: 20000 })
  ok('box library card renders in Dielines & Print')
  await page.click('[data-testid="box-generate"]')
  await page.waitForSelector('[data-testid="box-preview"]', { timeout: 30000 })
  ok('UI generated a structure and shows the preview')
  const previewImg = await page.$('[data-testid="box-preview"] img')
  if (previewImg) ok('preview renders the SVG as an image (no script execution)')
  else no('preview image missing')

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`BOX LIBRARY: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
