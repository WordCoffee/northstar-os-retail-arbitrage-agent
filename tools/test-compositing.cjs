// ═══════════════════════════════════════════════════════════════════════════
// COMPOSITING SURFACE + FIDELITY CANVAS EXTRACTION — browser harness
//
// Directive item 6 asks for the real compositing surface AND for the fidelity
// canvas extraction to run in a browser. The pixel paths cannot be tested in
// Node (no canvas), so this drives them in a real browser through the opt-in
// ?engine=1 hook, with real generated image data.
//
// It proves, with real pixels:
//   • renderDoc draws layers to a real canvas
//   • a composite that MATCHES the locked reference passes the fidelity diff
//   • a composite that DIFFERS beyond the threshold BLOCKS export
//   • an unverified fidelity blocks export
//   • the export pipeline reports every step's real status
//   • the marker survives the real export path
//
// Run from tools/:  node test-compositing.cjs
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
// Dev builds use the local identity shim, not hosted credentials.
const DEV_IDENT = process.env.NS_DEV_IDENTIFIER || 'T2'
const DEV_PW = process.env.NS_DEV_PASSWORD || '123abc'

// ── Mode flag ──────────────────────────────────────────────────────────────
// 'auto' (default) detects the engine hook and decides for itself.
// 'dev'  REQUIRES the hook (the Vite dev server). Tries the local shim identity
//        first, then the real credential pair.
// 'test' REQUIRES the hook (the dist-test build, served like production with
//        VITE_TEST_HOOKS=1). Signs in with REAL credentials only.
// 'prod' REQUIRES the hook to be ABSENT (the production contract) and runs only
//        the UI-level checks.
const MODE = (process.env.HARNESS_MODE || 'auto').toLowerCase()
if (!['auto', 'dev', 'test', 'prod'].includes(MODE)) {
  console.error(`FATAL unknown HARNESS_MODE "${MODE}" (expected auto|dev|test|prod)`)
  process.exit(2)
}
// Modes that require the engine hook to be present in the served build.
const REQUIRES_HOOK = MODE === 'dev' || MODE === 'test'

// ── Watchdog ───────────────────────────────────────────────────────────────
// A hung page.evaluate used to hang this harness with no output at all. Nothing
// may hang silently: after this many ms the harness reports WHERE it got to and
// exits non-zero.
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)
let lastStep = 'start'
const step = (s) => { lastStep = s; log(`      ... ${s}`) }

// The dev server transforms modules on demand, so its FIRST page load is much
// slower than a built bundle. Every navigation timeout scales with the mode.
const NAV_TIMEOUT = MODE === 'prod' ? 15000 : 60000

let pass = 0
let fail = 0
let fatal = 0
const log = (m) => console.log(m)
const ok = (m) => { pass++; log('PASS  ' + m) }
const no = (m, d) => { fail++; log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  let capturing = false
  page.on('pageerror', (e) => { if (capturing) errors.push(String(e)) })
  page.on('console', (m) => { if (capturing && m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)) })

  step('navigating to sign-in')
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT })
  step('waiting for the sign-in form')
  await page.waitForSelector('#signin-id', { timeout: NAV_TIMEOUT })

  // A dev server serves the module graph on demand, so the form can be in the
  // DOM BEFORE React attaches its submit handler. Settle first so the click
  // always lands on a mounted handler.
  await page.waitForTimeout(MODE === 'dev' ? 2000 : 800)

  // Credential strategy per mode:
  //   dev  -> the shim identity first (works against a local dev-posture
  //           backend), then the real pair (the app itself falls back the same
  //           way when the shim cannot authenticate).
  //   test -> real pair only. A served bundle never carries the shim identity
  //           (asserted by tools/check-prod-bundle.cjs).
  //   prod -> real pair only.
  const credPairs = MODE === 'dev'
    ? [[DEV_IDENT, DEV_PW], [EMAIL, PW]]
    : [[EMAIL, PW]]

  let signedIn = false
  for (const [ident, pw] of credPairs) {
    if (signedIn) break
    await page.fill('#signin-id', ident)
    await page.fill('#signin-pw', pw)
    for (let attempt = 1; attempt <= 2 && !signedIn; attempt++) {
      step(`submitting sign-in as "${ident}" (attempt ${attempt})`)
      await page.click('form button[type="submit"]')
      try {
        await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: Math.round(NAV_TIMEOUT / 3) })
        signedIn = true
      } catch {
        if (attempt < 2) await page.waitForTimeout(1500)
      }
    }
  }
  if (!signedIn) {
    const url = await page.evaluate(() => location.href).catch(() => 'unknown')
    const alert = await page.$eval('[role="alert"]', e => e.textContent).catch(() => 'no alert')
    ftl(`sign-in did not complete in ${MODE} mode (still at ${url}; form says: ${String(alert).slice(0, 140)})`)
    await browser.close()
    return report()
  }
  capturing = true
  ok('signed in')

  // ── The compositing surface mounts ──────────────────────────────────────
  await page.goto(BASE + 'design-studio?section=listing-images&engine=1')
  await page.waitForSelector('[data-testid="listing-images-workspace"]', { timeout: NAV_TIMEOUT })
  step('checking the compositing surface')
  const surface = await page.$('[data-testid="compositing-surface"]')
  if (surface) ok('the compositing surface mounted in Listing Images')
  else { no('no compositing surface'); }
  const canvas = await page.$('[data-testid="compositing-surface"] canvas')
  if (canvas) ok('the surface renders a real <canvas> element')
  else no('no canvas element')
  for (const [sel, name] of [['.ss-leftrail', 'left rail'], ['.ss-inspector', 'inspector'], ['.ss-bottomstrip', 'bottom strip']]) {
    if (await page.$(`${sel}`)) ok(`compositing surface renders ${name}`)
    else no(`compositing surface missing ${name}`)
  }

  // ── Undo / redo --history──
  const undo = await page.$('.ss-leftrail button:has-text("Undo")')
  const redo = await page.$('.ss-leftrail button:has-text("Redo")')
  if (undo && redo) ok('undo and redo controls are present')
  else no('undo/redo missing')

  // ── The engine hook is a DEV-ONLY affordance ───────────────────────────
  // In a production bundle it is dead-code-eliminated (see
  // tools/check-prod-bundle.cjs). Its ABSENCE is the correct production state,
  // so this harness SKIPS the pixel-path tests rather than failing them, and
  // says exactly why. Run it against the Vite dev server to exercise them.
  const hasEngine = await page.evaluate(() => !!window.__northstarStudioEngine)

  // ── Mode enforcement ────────────────────────────────────────────────────
  if (REQUIRES_HOOK && !hasEngine) {
    ftl(`HARNESS_MODE=${MODE} but the engine hook is ABSENT. The pixel paths cannot run.
       dev  -> run the Vite dev server (:8101)
       test -> build and serve the test artifact:
               cd northstar-os-ui
               set VITE_TEST_HOOKS=1 && npm run build -- --outDir dist-test
               npx vite preview --outDir dist-test --port 8200`)
    await browser.close()
    return report()
  }
  if (MODE === 'prod' && hasEngine) {
    ftl('HARNESS_MODE=prod but the engine hook is PRESENT. The production bundle must not carry it.')
    await browser.close()
    return report()
  }
  let skippedPixelPaths = false
  if (!hasEngine) {
    skippedPixelPaths = true
    log('')
    log('SKIP  engine hook absent (CORRECT for a production bundle)')
    log('      The canvas pixel paths (render, fidelity extraction, marker survival)')
    log('      need the ?engine=1 hook. Re-run against a hook-carrying build:')
    log('        the Vite dev server :  HARNESS_MODE=dev HARNESS_BASE_URL=http://127.0.0.1:8101/ui/ node test-compositing.cjs')
    log('        the test build      :  HARNESS_MODE=test HARNESS_BASE_URL=http://127.0.0.1:8200/ui/ node test-compositing.cjs')
    log('      The UI-level checks below still run against this build.')
    log('')
  } else {
    ok(`engine hook present (${MODE === 'test' ? 'test build' : 'dev build'})`)
  }

const fixtures = await page.evaluate(() => {
    const mk = (fill, stripe) => {
      const c = document.createElement('canvas')
      c.width = 1200; c.height = 1200
      const x = c.getContext('2d')
      x.fillStyle = fill
      x.fillRect(0, 0, 1200, 1200)
      if (stripe) {
        x.fillStyle = stripe
        x.fillRect(120, 120, 960, 960)
        x.fillStyle = '#111111'
        x.font = '84px sans-serif'
        x.fillText('LABEL', 450, 630)
      }
      return c.toDataURL('image/png')
    }
    return {
      // The product: a striped box with a label. Identical in both fixtures.
      product: mk('#c94f2a', '#f2e3c9'),
      // A composite that reproduces the product exactly.
      sameComposite: mk('#c94f2a', '#f2e3c9'),
      // A composite where the product has been redrawn in a different colour.
      differentComposite: mk('#2a6fc9', '#c9dcf2'),
      // A neutral background.
      bg: mk('#ffffff', null),
    }
  })
  ok('page generated 4 real PNG fixtures via canvas')

  if (hasEngine) {
    // ── Draw two real reference images IN THE PAGE ──────────────────────────
  
    // ── Fidelity: matching composite PASSES ─────────────────────────────────
    // Uses compose.fidelityVerdict -- the path that actually ships, which diffs
    // the RENDERED CANVAS against the locked reference. (fidelity.verifyFidelity
    // is the data-URL variant, which requires a supplied composite image and is
    // not what the export pipeline calls.)
    const matchResult = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const canvas = document.createElement('canvas')
      canvas.width = 1200; canvas.height = 1200
      const ctx = canvas.getContext('2d')
      const load = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('image failed to load: ' + String(src).slice(0, 32))); i.src = src })
      const img = await load(fx.sameComposite)
      ctx.drawImage(img, 0, 0, 1200, 1200)

      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [{ kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: fx.sameComposite }],
        meta: { fidelityMode: 'locked', referenceDataUrl: fx.product, fidelityRegion: { x: 0, y: 0, w: 1, h: 1 } },
      }
      const r = await compose.fidelityVerdict(doc, canvas, () => null)
      return { status: r.status, ok: r.ok, detail: r.detail, mean: r.diff && r.diff.mean }
    }, fixtures)
    if (matchResult.ok && matchResult.status === 'pass') ok(`matching composite PASSES the fidelity diff (mean ${(matchResult.mean * 100).toFixed(2)}%)`)
    else no(`matching composite gave ${matchResult.status}`, String(matchResult.detail).slice(0, 100))

    // ── Fidelity: differing composite BLOCKS ────────────────────────────────
    const diffResult = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const canvas = document.createElement('canvas')
      canvas.width = 1200; canvas.height = 1200
      const ctx = canvas.getContext('2d')
      const load = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('image failed to load: ' + String(src).slice(0, 32))); i.src = src })
      const img = await load(fx.differentComposite)
      ctx.drawImage(img, 0, 0, 1200, 1200)
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [{ kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: fx.differentComposite }],
        meta: { fidelityMode: 'locked', referenceDataUrl: fx.product, fidelityRegion: { x: 0, y: 0, w: 1, h: 1 } },
      }
      const r = await compose.fidelityVerdict(doc, canvas, () => null)
      return { status: r.status, ok: r.ok, detail: r.detail, mean: r.diff && r.diff.mean }
    }, fixtures)
    if (!diffResult.ok && diffResult.status === 'block') ok(`a redrawn product BLOCKS (mean ${(diffResult.mean * 100).toFixed(1)}% vs a ${(0.06 * 100).toFixed(0)}% limit)`)
    else no(`differing composite gave ${diffResult.status}`, String(diffResult.detail).slice(0, 100))

    // ── Fidelity: a locked reference with no image -> UNVERIFIED ────────────
    const unverified = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const canvas = document.createElement('canvas')
      canvas.width = 1200; canvas.height = 1200
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [{ kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: fx.product }],
        meta: { fidelityMode: 'locked' },
      }
      const r = await compose.fidelityVerdict(doc, canvas, () => null)
      return { status: r.status, ok: r.ok }
    }, fixtures)
    if (!unverified.ok && unverified.status === 'unverified') ok('locked fidelity with no reference is UNVERIFIED (and therefore blocks)')
    else no(`no-reference case gave ${unverified.status}`)

    // ── Fidelity: a generated product region BLOCKS ─────────────────────────
    const generated = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const canvas = document.createElement('canvas')
      canvas.width = 1200; canvas.height = 1200
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [{ kind: 'product', x: 0, y: 0, w: 1, h: 1 }],
        meta: { fidelityMode: 'generated', referenceDataUrl: fx.product },
      }
      const r = await compose.fidelityVerdict(doc, canvas, () => null)
      return { status: r.status, ok: r.ok, detail: r.detail }
    }, fixtures)
    if (!generated.ok && generated.status === 'block') ok('a GENERATED product region blocks export')
    else no(`generated mode gave ${generated.status}`)

    // ── renderDoc actually draws ────────────────────────────────────────────
    const renderCheck = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const doc = {
        formatId: 'amz-main', w: 200, h: 200,
        layers: [
          { kind: 'bg', fill: '#ffffff' },
          { kind: 'shape', shape: 'rect', x: 0, y: 0, w: 0.5, h: 1, fill: '#e8e2d8' },
          { kind: 'text', text: 'HI', x: 0.6, y: 0.4, w: 0.3, h: 0.2, size: 0.1, color: '#000000' },
        ],
      }
      const canvas = await compose.renderDoc(doc, () => null)
      const px = canvas.getContext('2d').getImageData(10, 10, 1, 1).data
      const px2 = canvas.getContext('2d').getImageData(150, 10, 1, 1).data
      return { w: canvas.width, h: canvas.height, bg: [px[0], px[1], px[2]], shape: [px2[0], px2[1], px2[2]] }
    }, fixtures)
    if (renderCheck.w === 200 && renderCheck.bg[0] === 232 && renderCheck.bg[1] === 226) ok('renderDoc painted the shape layer over the background at its box (x 0-50%)')
    else no('renderDoc shape wrong at x=10', JSON.stringify(renderCheck.bg))
    if (renderCheck.shape[0] === 255 && renderCheck.shape[1] === 255) ok('renderDoc left the background visible outside the shape box (x 75%)')
    else no('renderDoc background wrong at x=150', JSON.stringify(renderCheck.shape))

    // ── The export pipeline reports every step, and blocks on compare ───────
    step('running the export pipeline')
  const pipeline = await page.evaluate(async (fx) => {
      const { compose, disclosure } = window.__northstarStudioEngine
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200, channel: 'Amazon listing',
        layers: [
          { kind: 'bg', fill: '#ffffff' },
          { kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: fx.sameComposite },
        ],
        meta: {
          fidelityMode: 'locked', referenceDataUrl: fx.product,
          peopleClass: 'ai-photoreal', syntheticPerformerTag: true,
          filename: 'B01ABCDEFG.main.png', dpi: 300, colorSpace: 'sRGB',
        },
      }
      // No compare sign-off yet -> must block.
      const blocked = await compose.exportComposite(doc, {})
      // A stale sign-off shape (no user, no asset version, no reference hash -
      // exactly the record that shipped before the Phase 5 hardening) must ALSO
      // be refused, not treated as a satisfied comparison.
      const stale = { ...doc, meta: { ...doc.meta, compareConfirmed: { at: new Date().toISOString(), by: 'harness' } } }
      const staleRun = await compose.exportComposite(stale, {})
      // The engine's own maker binds the record to the asset version and the
      // reference hash -> must proceed and verify the marker.
      const signed = { ...doc, meta: { ...doc.meta, compareConfirmed: compose.makeCompareSignOff(doc, { user: 'harness' }) } }
      const passed = await compose.exportComposite(signed, {})
      const markerOk = passed.bytes ? await (async () => {
        const v = disclosure.verifyDisclosureMarker(passed.bytes, passed.mime, disclosure.DISCLOSURE_KEYWORD)
        return v.ok
      })() : false
      return {
        blockedOk: blocked.ok,
        blockedCompare: blocked.steps.compare && blocked.steps.compare.status,
        blockedBytes: blocked.bytes === null,
        staleOk: staleRun.ok,
        staleCompare: staleRun.steps.compare && staleRun.steps.compare.status,
        staleBytes: staleRun.bytes === null,
        passedOk: passed.ok,
        passedSteps: Object.fromEntries(Object.entries(passed.steps).map(([k, v]) => [k, v.status])),
        passedBytes: passed.bytes ? passed.bytes.length : 0,
        markerOk,
        summary: compose.summariseExport(passed),
        // Why the pre-flight blocked, if it did. Without this the failure is a
        // bare "block" and the cause is invisible.
        blockedRules: (passed.steps.compliance && passed.steps.compliance.report)
          ? passed.steps.compliance.report.blocked.map(r => `${r.id}: ${r.detail}`)
          : [],
      }
    }, fixtures)
    if (!pipeline.blockedOk && pipeline.blockedCompare === 'block' && pipeline.blockedBytes) {
      ok('the export pipeline BLOCKS on the missing compare sign-off and writes no bytes')
    } else no(`compare gate did not block: ${JSON.stringify(pipeline).slice(0, 140)}`)
    if (!pipeline.staleOk && pipeline.staleCompare === 'block' && pipeline.staleBytes) {
      ok('a sign-off that is NOT bound to the asset version/reference is refused (Phase 5 hardening holds)')
    } else no(`an unbound sign-off was accepted: ${pipeline.staleCompare}`)
    if (pipeline.passedOk && pipeline.markerOk) ok(`the full pipeline passes with the sign-off; the marker survives the real export (${pipeline.passedBytes} bytes)`)
    else no(`pipeline did not pass: blocked=${JSON.stringify(pipeline.blockedRules)}`, pipeline.summary)
    if (pipeline.passedSteps && pipeline.passedSteps['marker-verify'] === 'pass') ok(`marker-verify reported pass (${pipeline.summary})`)
    else no('marker-verify did not report pass', pipeline.summary)

    // ── A no-product asset does not require the compare step ────────────────
    const noProduct = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const doc = { formatId: 'amz-main', w: 1200, h: 1200, layers: [{ kind: 'bg', fill: '#ffffff' }], meta: {} }
      const r = await compose.exportComposite(doc, {})
      return { compare: r.steps.compare.status, fidelity: r.steps.fidelity.status }
    }, fixtures)
    if (noProduct.compare === 'not-required') ok('an asset with no product does not require the compare step')
    else no(`no-product compare status was ${noProduct.compare}`)

    // ── Step statuses are never invented ───────────────────────────────────
    const stepDiscipline = await page.evaluate(async (fx) => {
      const { compose } = window.__northstarStudioEngine
      const doc = {
        formatId: 'amz-main', w: 1200, h: 1200,
        layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl: fx.product }],
        meta: { fidelityMode: 'placed', peopleClass: 'no-people' },
      }
      const r = await compose.exportComposite(doc, {})
      return { steps: Object.fromEntries(Object.entries(r.steps).map(([k, v]) => [k, v.status])), ok: r.ok }
    }, fixtures)
    const st = stepDiscipline.steps
    if (st['marker-embed'] === 'not-required' && st['marker-verify'] === 'not-required') {
      ok('an asset that needs no marker reports not-required, never a false pass')
    } else no(`marker steps reported ${st['marker-embed']}/${st['marker-verify']}`)

  }

  // ── ITEM 3: the upload check, driven for real ───────────────────────────
  // Produce a TAGGED png and an UNTAGGED png in the page, then feed both
  // through the real file input.
  step('generating upload fixtures')
  const uploadFixtures = await page.evaluate(async (fx) => {
    const disclosure = window.__northstarStudioEngine ? window.__northstarStudioEngine.disclosure : null
    const canvas = document.createElement('canvas')
    canvas.width = 1200; canvas.height = 1200
    const ctx = canvas.getContext('2d')
    const load = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('image failed to load: ' + String(src).slice(0, 32))); i.src = src })
    ctx.drawImage(await load(fx.product), 0, 0, 1200, 1200)
    const untagged = await new Promise(r => canvas.toBlob(b => r(b), 'image/png'))
    const rawBytes = new Uint8Array(await untagged.arrayBuffer())
    const b64 = (u8) => btoa(String.fromCharCode.apply(null, u8))
    if (!disclosure) return { tagged: null, untagged: b64(rawBytes) }
    const taggedBytes = disclosure.embedDisclosure(rawBytes, 'image/png', [disclosure.DISCLOSURE_KEYWORD])
    return { tagged: b64(taggedBytes), untagged: b64(rawBytes) }
  }, fixtures)

  const libTab = await page.$('.ss-leftrail-tab:has-text("Library")')
  if (libTab) ok('the Library tab is present in the compositing surface')
  else no('no Library tab')

  // Declare the classification FIRST: the requirement is derived from the
  // asset's own disclosure state, so an unanswered asset legitimately reports
  // not-required. This is the real workflow order.
  const classSel = await page.$('[data-testid="surface-people-class"]')
  if (classSel) {
    await classSel.selectOption('ai-photoreal')
    await page.waitForTimeout(400)
    ok('the surface collects the people classification (asset-level, where the asset is made)')
  } else no('the surface has no people-classification control')

  // The identifiability gate must be reachable from the surface too, and must
  // actually BLOCK with its explanation rather than silently toggling.
  const idCtl = await page.$('[data-testid="surface-identifiable"]')
  if (idCtl) {
    await idCtl.check()
    await page.waitForTimeout(400)
    const status = await page.$eval('[data-testid="disclosure-status"]', e => e.textContent).catch(() => '')
    if (/BLOCKED/i.test(status) && /right-of-publicity|consent/i.test(status)) {
      ok('ticking identifiability shows the block and explains it is a consent matter')
    } else no('identifiability did not surface its block explanation', status.slice(0, 120))
    await idCtl.uncheck()
    await page.waitForTimeout(300)
  } else no('the surface has no identifiability control')

  if (libTab) {
    await libTab.click()
    await page.waitForTimeout(400)
    if (await page.$('[data-testid="recheck-library"]')) ok('the re-check library panel renders')
    else no('no re-check library panel')

    // Tagged -> marker-present. Needs the engine to WRITE the tag; skipped
    // without it, with the reason stated.
    if (!uploadFixtures.tagged) {
      log('SKIP  tagged-upload check needs the engine to write the marker (production build)')
    } else {
      await page.setInputFiles('[data-testid="upload-check-input"]', {
        name: 'live-listing.png', mimeType: 'image/png', buffer: Buffer.from(uploadFixtures.tagged, 'base64'),
      })
      await page.waitForTimeout(700)
      const taggedRes = await page.$eval('[data-testid="upload-check-result"]', e => e.textContent).catch(() => '')
      if (/marker-present/.test(taggedRes)) ok('upload check reads a tagged live image as marker-present')
      else no('tagged live image did not report marker-present', taggedRes.slice(0, 120))
    }

    // Untagged -> marker-missing with the warning
    await page.setInputFiles('[data-testid="upload-check-input"]', {
      name: 'live-listing-lost.png', mimeType: 'image/png', buffer: Buffer.from(uploadFixtures.untagged, 'base64'),
    })
    await page.waitForTimeout(700)
    const missRes = await page.$eval('[data-testid="upload-check-result"]', e => e.textContent).catch(() => '')
    if (/marker-missing/.test(missRes)) ok('upload check WARNS on a live image that lost the marker')
    else no('untagged live image did not warn', missRes.slice(0, 120))
    if (/re-upload/i.test(missRes)) ok('the warning tells the operator what to do')
    else no('the warning does not state the fix')

    // ── ITEM 4: the log records each check with its date ──────────────────
    // The log moved to the TENANT-SCOPED BACKEND in Phase 5, so it is no longer
    // in localStorage. Assert on the real store through the page's own session.
    const readBackendLog = () => page.evaluate(async () => {
      const r = await fetch('/api/design-studio/rechecks', { credentials: 'include' })
      if (!r.ok) return { state: 'error', status: r.status, entries: [] }
      const j = await r.json()
      return { state: 'ready', entries: j.rechecks || [], counts: j.counts || null }
    })
    const logged = await readBackendLog()
    if (logged.state === 'ready') ok(`the backend re-check log is readable (${logged.entries.length} entry/entries)`)
    else no(`could not read the backend log (http ${logged.status})`)

    if (logged.entries.length >= 1) ok('the upload check wrote to the tenant-scoped log')
    else no('the upload check did not reach the backend log')
    const hasDate = logged.entries.every(e => !!e.checked_at)
    if (hasDate && logged.entries.length) ok('every backend entry carries the date of the check')
    else no('a backend entry is missing its date')
    if (logged.entries.some(e => e.surface)) ok('the backend entry records which surface ran the check')
    else no('the backend entry does not record the surface')

    // A failed check must be recorded as a failure, not smoothed to a pass.
    const failedEntry = logged.entries.find(e => e.verdict === 'marker-missing')
    if (failedEntry && failedEntry.passed === false) ok('a failed check is stored as a failure in the backend')
    else no('a failed check was not stored as a failure')

    // ── The log survives a reload ─────────────────────────────────────────
    await page.reload()
    await page.waitForSelector('[data-testid="listing-images-workspace"]', { timeout: NAV_TIMEOUT })
    await page.waitForTimeout(1200)
    const after = await readBackendLog()
    if (after.state === 'ready' && after.entries.length >= logged.entries.length) {
      ok(`the log persisted across a reload (${after.entries.length} entries, backend-backed)`)
    } else no(`log did not persist: ${JSON.stringify(after).slice(0, 90)}`)

    // ── The cure window ───────────────────────────────────────────────────
    const libTab2 = await page.$('.ss-leftrail-tab:has-text("Library")')
    if (libTab2) {
      await libTab2.click()
      await page.waitForTimeout(400)
      await page.fill('[data-testid="notice-date"]', '2026-10-08')
      await page.waitForTimeout(400)
      const cure = await page.$('[data-testid="cure-window"]')
      const cureText = cure ? await cure.textContent() : ''
      if (cure && /day/i.test(cureText)) ok(`the notice-and-cure window renders (${cureText.trim().slice(0, 60)})`)
      else no('no cure window rendered', cureText.slice(0, 80))
      const recheckBtn = await page.$('[data-testid^="recheck-"]')
      if (recheckBtn) ok('a per-entry "re-check exported ad" action is present')
      else no('no per-entry re-check action')
    }
  }

  // ── The page errors check ──────────────────────────────────────────────
  if (errors.length === 0) ok('no console or page errors during the whole run')
  else no(`${errors.length} console/page error(s)`, errors.slice(0, 3).join(' | ').slice(0, 200))

  await browser.close()
  if (skippedPixelPaths) {
    log('')
    log(`NOTE  ${skippedPixelPaths ? 'pixel paths were SKIPPED (production mode)' : ''}`)
  }
  return report()

  function report() {
    log('')
    log(`MODE: ${MODE}`)
    log(`COMPOSITING + FIDELITY (browser): ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

// Run under a watchdog: a hang must produce a report naming the last step, never
// silence.
const guard = new Promise((_, rej) =>
  setTimeout(() => rej(new Error(`WATCHDOG: no completion after ${WATCHDOG_MS}ms. Last step reached: "${lastStep}"`)), WATCHDOG_MS))

Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => {
    console.error('')
    console.error(`FATAL ${e.message}`)
    console.error(`       last step reached: "${lastStep}"`)
    console.error('       This is an isolated cause, not a pass. Nothing was skipped silently.')
    process.exit(2)
  },
)
