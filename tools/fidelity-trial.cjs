// ═══════════════════════════════════════════════════════════════════════════
// LOCAL FIDELITY TRIAL — composite-only + background-replacement (Phase 8 item 5)
//
// Runs REAL product pixels (the operator's own photos, or a labeled fixture set)
// through the real gates in a browser, via the test build's ?engine=1 hook:
//
//   composite-only            product pixels kept exactly (no generation)
//   background-replacement    the same pixels over a scene background
//   fidelity gate             the rendered product region diffed vs the reference
//   label-region check        the tighter label tripwire on the same region
//   disclosure gates          the same classification rules every section uses
//   export gate               MUST stay blocked pending a human compare sign-off
//   tamper probe              a redrawn product MUST block (failure class recorded)
//
// NO provider is contacted. NO generation runs. NO cloud. NO spend. If a local
// media runtime is running it is reported; if not, the runtime-generation path
// is NOT RUN with the cause. With fewer than 20 images no pass RATE is claimed -
// the sample size is stated instead.
//
// Run:  node tools/fidelity-trial.cjs
// Env:  HARNESS_BASE_URL (default http://127.0.0.1:8200/ui/ - the test build)
//       NS_REFERENCE_PHOTOS (default research/design-studio/reference-photos)
//       NS_LOCAL_MEDIA_ENDPOINT (default http://127.0.0.1:8188)
// Exit: 0 = all executed checks passed, 1 = a failure, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8200/ui/'
const PHOTOS_DIR = process.env.NS_REFERENCE_PHOTOS || path.join(__dirname, '..', 'research', 'design-studio', 'reference-photos')
const MEDIA_ENDPOINT = process.env.NS_LOCAL_MEDIA_ENDPOINT || 'http://127.0.0.1:8188'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 300000)
const REPORT_PATH = path.join(__dirname, '..', 'reports', 'fidelity-trial_20261011.json')

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const IMAGE_EXT = /\.(png|jpe?g|webp)$/i

function findReferencePhotos() {
  try {
    if (!fs.existsSync(PHOTOS_DIR)) return []
    return fs.readdirSync(PHOTOS_DIR)
      .filter(f => IMAGE_EXT.test(f))
      .map(f => path.join(PHOTOS_DIR, f))
  } catch { return [] }
}

async function runtimeReachable() {
  try {
    const res = await fetch(MEDIA_ENDPOINT + '/', { signal: AbortSignal.timeout(2500) })
    return { reachable: true, status: res.status }
  } catch (e) {
    return { reachable: false, reason: String(e && e.message || e).slice(0, 80) }
  }
}

async function main() {
  const photos = findReferencePhotos()
  const liveTrial = photos.length >= 1
  const runtime = await runtimeReachable()

  console.log(`reference photos: ${photos.length} found in ${PHOTOS_DIR}`)
  console.log(`local media runtime (${MEDIA_ENDPOINT}): ${runtime.reachable ? 'REACHABLE' : 'NOT RUNNING (' + runtime.reason + ')'}`)
  if (!liveTrial) {
    console.log('LIVE TRIAL: NOT RUN - no reference photos supplied in the folder (drop >=5 real photos in to run it).')
  }
  if (!runtime.reachable) {
    console.log('RUNTIME-GENERATION PATH: NOT RUN - no local media runtime is running; the trial uses composite-only paths (real product pixels preserved).')
  }

  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
  const page = await ctx.newPage()
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 45000 })
  await page.fill('#signin-id', process.env.NS_TEST_EMAIL || 't2')
  await page.fill('#signin-pw', process.env.NS_TEST_PASSWORD || 'T2holdings')
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 20000 }).catch(() => {})
  await page.goto(BASE + 'design-studio?section=listing-images&engine=1', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('[data-testid="listing-images-workspace"]', { timeout: 45000 })
  await page.waitForTimeout(1500)
  const hasEngine = await page.evaluate(() => !!window.__northstarStudioEngine)
  if (!hasEngine) {
    ftl('the engine hook is absent - this trial needs the TEST build (dist-test served on :8200)')
    await browser.close()
    return report([])
  }

  // Fixture set: 5 labeled synthetic "photos" when no real photos are supplied.
  const sources = liveTrial
    ? photos.map(p => ({ kind: 'photo', name: path.basename(p), dataUrl: 'data:image/' + (p.toLowerCase().endsWith('.png') ? 'png' : 'jpeg') + ';base64,' + fs.readFileSync(p).toString('base64') }))
    : null

  const results = await page.evaluate(async (payload) => {
    const { compose, fidelity, disclosure } = window.__northstarStudioEngine
    const out = []
    const load = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('img load failed')); i.src = src })
    const mkFixture = (seed) => {
      const c = document.createElement('canvas'); c.width = 1200; c.height = 1200
      const x = c.getContext('2d')
      x.fillStyle = ['#f2e3c9', '#dfe9f2', '#efe0f2', '#e2f2e0', '#f2ece0'][seed % 5]
      x.fillRect(0, 0, 1200, 1200)
      x.fillStyle = ['#c94f2a', '#2a6fc9', '#7a3fc9', '#2f8f4e', '#b8860b'][seed % 5]
      x.fillRect(150, 150, 900, 900)
      x.fillStyle = '#111111'; x.font = '72px sans-serif'
      x.fillText('LABEL ' + seed, 380, 640)
      return c.toDataURL('image/png')
    }
    const items = payload.sources || Array.from({ length: 5 }, (_, i) => ({ kind: 'fixture', name: `fixture-${i + 1}`, dataUrl: mkFixture(i) }))

    for (const item of items) {
      const t0 = performance.now()
      // Full-canvas product placement: the composite's contain-fit geometry is
      // IDENTICAL to the reference's, so the diff compares like-for-like. The
      // trial never regenerates the product; only the background differs.
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [
          { kind: 'bg', fill: '#ffffff' },
          { kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: item.dataUrl, fit: 'contain' },
        ],
        meta: {
          fidelityMode: 'locked', referenceDataUrl: item.dataUrl,
          peopleClass: 'no-people',
        },
      }
      const canvas = await compose.renderDoc(doc, () => null)
      const fid = await compose.fidelityVerdict(doc, canvas, () => null)

      // Label-region check on the same product region (extracted both sides).
      const region = { x: 0, y: 0, w: 1, h: 1 }
      let label = { ok: false, reason: 'not-run' }
      try {
        const refBytes = await fidelity.extractRegion(item.dataUrl, region, 400, 400)
        const outBytes = await fidelity.extractRegion(canvas.toDataURL('image/png'), region, 400, 400)
        label = fidelity.labelRegionDiff(refBytes, outBytes, {})
      } catch (e) { label = { ok: false, reason: 'label-extract-failed: ' + String(e.message || e) } }

      // Background-replacement composite (same pixels, scene background).
      const sceneDoc = { ...doc, layers: [
        { kind: 'bg', gradient: ['#f5f0e8', '#cfe3d4'] },
        { kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: item.dataUrl, fit: 'contain' },
      ] }
      const sceneCanvas = await compose.renderDoc(sceneDoc, () => null)
      const sceneFid = await compose.fidelityVerdict(sceneDoc, sceneCanvas, () => null)

      // Disclosure gates (same rules as every section).
      const cls = disclosure.classifyDisclosure(doc)
      const discOk = cls.status === 'decided' && !cls.tagRequired

      // Export gate: MUST stay blocked pending a human compare sign-off.
      const exportBlocked = await compose.exportComposite(doc, {})
      const blockedOnCompare = !exportBlocked.ok && exportBlocked.steps.compare && exportBlocked.steps.compare.status === 'block' && exportBlocked.bytes === null

      // Tamper probe: a redrawn product region (a red block over the product)
      // MUST block the fidelity gate.
      const tamperDoc = { ...doc, layers: [
        { kind: 'bg', fill: '#ffffff' },
        { kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: item.dataUrl, fit: 'contain' },
        { kind: 'shape', shape: 'rect', x: 0.3, y: 0.35, w: 0.4, h: 0.2, fill: '#ff0000' },
      ] }
      const tamperCanvas = await compose.renderDoc(tamperDoc, () => null)
      const tamperFid = await compose.fidelityVerdict(tamperDoc, tamperCanvas, () => null)

      out.push({
        name: item.name, kind: item.kind,
        fidelity: fid.status, fidelity_ok: fid.ok,
        label: label.ok ? 'pass' : (label.reason || 'fail'), label_ok: !!label.ok,
        background_replacement: sceneFid.status, background_ok: !!sceneFid.ok,
        disclosure: discOk ? 'pass' : (cls.status || 'fail'), disclosure_ok: discOk,
        export_gate: blockedOnCompare ? 'blocked-pending-signoff' : 'UNEXPECTEDLY-OPEN', export_gate_ok: blockedOnCompare,
        tamper: tamperFid.status, tamper_ok: !tamperFid.ok && tamperFid.status === 'block',
        ms: Math.round(performance.now() - t0),
      })
    }
    return out
  }, { sources })

  let failures = 0
  for (const r of results) {
    const bad = []
    if (!r.fidelity_ok) bad.push('fidelity:' + r.fidelity)
    if (!r.label_ok) bad.push('label:' + r.label)
    if (!r.background_ok) bad.push('background:' + r.background_replacement)
    if (!r.disclosure_ok) bad.push('disclosure:' + r.disclosure)
    if (!r.export_gate_ok) bad.push('export-gate:' + r.export_gate)
    if (!r.tamper_ok) bad.push('tamper:' + r.tamper)
    if (bad.length === 0) ok(`${r.name}: fidelity pass, label pass, background pass, disclosure pass, export blocked pending sign-off, tamper blocked (${r.ms} ms)`)
    else { failures++; no(`${r.name}: ${bad.join('; ')}`) }
  }

  const n = results.length
  console.log('')
  console.log(`sample size: ${n} image(s)`)
  if (n < 20) console.log(`NO PASS RATE CLAIMED: ${n} < 20 samples. Per-image results above are the evidence.`)
  else console.log(`pass rate: ${((n - failures) / n * 100).toFixed(0)}% (${n - failures}/${n})`)
  console.log(`live trial: ${liveTrial ? `RAN on ${photos.length} operator photo(s)` : 'NOT RUN (no reference photos supplied)'}`)
  console.log(`runtime generation path: ${runtime.reachable ? 'runtime reachable - generation still NOT exercised by this harness' : 'NOT RUN (no local media runtime running)'}`)

  const reportData = {
    at: new Date().toISOString(),
    live_trial: liveTrial ? 'RAN' : 'NOT RUN',
    live_trial_cause: liveTrial ? null : `no reference photos in ${PHOTOS_DIR}`,
    runtime_generation: runtime.reachable ? 'runtime reachable; generation not exercised' : 'NOT RUN - no local media runtime running',
    runtime_endpoint: MEDIA_ENDPOINT,
    sample_size: n,
    pass_rate_claimed: n >= 20,
    results,
  }
  try { fs.writeFileSync(REPORT_PATH, JSON.stringify(reportData, null, 2)) } catch { /* report write is best effort */ }
  console.log(`report: ${REPORT_PATH}`)

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`FIDELITY TRIAL: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
