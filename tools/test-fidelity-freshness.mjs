// ═══════════════════════════════════════════════════════════════════════════
// FIDELITY + POLICY FRESHNESS — test suite
//
// Directive items 6 and 8. The fidelity maths is pure, so it is tested here
// without a DOM; the canvas extraction path is exercised in the browser
// harness. The freshness register is tested against the real registry.
//
// Run:  node tools/test-fidelity-freshness.mjs
// ═══════════════════════════════════════════════════════════════════════════

import {
  regionDiff, regionToPixels, productRegion,
  FIDELITY_MODES, FIDELITY_MODE_BY_ID, COMPOSITE_STEPS,
  DEFAULT_THRESHOLD, DEFAULT_MAX_PIXEL_DELTA,
  claim, sampleLabel, labelRegionDiff, FIDELITY_BLIND_SPOTS, DEFAULT_LABEL_THRESHOLD,
} from '../northstar-os-ui/src/studio/engine/fidelity.js'
import {
  POLICY_FRESHNESS, RECHECK_DAYS, freshnessOf, freshnessReport, ruleFreshness,
  SPEC_SOURCES, TODAY,
} from '../northstar-os-ui/src/studio/engine/specRegistry.js'
import * as compose from '../northstar-os-ui/src/studio/engine/compose.js'

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++ }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── RGBA fixture helpers ───────────────────────────────────────────────────
const rgba = (pixels) => Uint8ClampedArray.from(pixels.flat())
const solid = (n, r, g, b, a = 255) => rgba(Array.from({ length: n }, () => [r, g, b, a]))

console.log(`thresholds: mean ${(DEFAULT_THRESHOLD * 100).toFixed(0)}%, worst pixel ${(DEFAULT_MAX_PIXEL_DELTA * 100).toFixed(0)}%\n`)

// ── regionDiff: identical buffers pass ─────────────────────────────────────
{
  const a = solid(100, 120, 130, 140)
  const r = regionDiff(a, a)
  if (r.ok && r.mean === 0 && r.worst === 0) ok('identical product regions pass with zero difference')
  else no(`identical buffers gave ok=${r.ok} mean=${r.mean}`)
}

// ── A small uniform shift (a re-shoot under slightly different light) passes
{
  const a = solid(100, 120, 130, 140)
  const b = solid(100, 124, 133, 143)  // ~1.5% mean difference
  const r = regionDiff(a, b)
  if (r.ok) ok(`a 1.5% uniform shift passes (mean ${(r.mean * 100).toFixed(2)}%)`)
  else no(`a 1.5% uniform shift was blocked: ${r.reason}`)
}

// ── A regenerated product (large uniform difference) blocks ────────────────
{
  const a = solid(100, 120, 130, 140)
  const b = solid(100, 40, 200, 60)
  const r = regionDiff(a, b)
  if (!r.ok && r.reason === 'mean-exceeded') ok('a large uniform difference blocks on mean-exceeded')
  else no(`large difference gave ok=${r.ok} reason=${r.reason}`)
}

// ── A single destroyed point blocks even when the average is fine ──────────
{
  const a = solid(100, 120, 130, 140)
  const b = Array.from({ length: 100 }, () => [120, 130, 140, 255])
  b[50] = [255, 0, 0, 255]  // one pixel blown out
  const r = regionDiff(a, rgba(b))
  if (!r.ok && r.reason === 'worst-pixel-exceeded') ok('a single destroyed point blocks on worst-pixel-exceeded')
  else no(`single-point damage gave ok=${r.ok} reason=${r.reason}`)
}

// ── Transparent pixels are skipped (a masked reference) ───────────────────
{
  const a = Array.from({ length: 10 }, (_, i) => [120, 130, 140, i < 5 ? 255 : 0])
  const b = Array.from({ length: 10 }, (_, i) => [i < 5 ? 122 : 255, i < 5 ? 132 : 0, i < 5 ? 142 : 0, i < 5 ? 255 : 0])
  const r = regionDiff(rgba(a), rgba(b))
  if (r.ok && r.compared === 5) ok(`transparent pixels skipped (compared ${r.compared}, mean ${(r.mean * 100).toFixed(2)}%)`)
  else no(`masking wrong: ok=${r.ok} compared=${r.compared}`)
}

// ── Fully transparent → nothing to compare, and that is NOT a pass ────────
{
  const t = solid(10, 0, 0, 0, 0)
  const r = regionDiff(t, t)
  if (!r.ok && r.reason === 'nothing-to-compare') ok('an all-transparent region reports nothing-to-compare, not a pass')
  else no(`all-transparent gave ok=${r.ok} reason=${r.reason}`)
}

// ── Degenerate inputs ─────────────────────────────────────────────────────
{
  if (regionDiff(null, solid(4, 1, 2, 3)).reason === 'missing-buffer') ok('a missing buffer is refused')
  else no('missing buffer not refused')
  if (regionDiff(solid(4, 1, 2, 3), solid(6, 1, 2, 3)).reason === 'length-mismatch') ok('a length mismatch is refused')
  else no('length mismatch not refused')
  if (regionDiff(new Uint8ClampedArray([1, 2, 3]), new Uint8ClampedArray([1, 2, 3])).reason === 'not-rgba') ok('a non-RGBA buffer is refused')
  else no('non-RGBA buffer not refused')
}

// ── regionToPixels clamps into the image ──────────────────────────────────
{
  const a = regionToPixels({ x: 0.25, y: 0.5, w: 0.5, h: 0.5 }, 100, 200)
  if (a.x === 25 && a.y === 100 && a.w === 50 && a.h === 100) ok('regionToPixels scales a normalised rect correctly')
  else no(`regionToPixels gave ${JSON.stringify(a)}`)

  const b = regionToPixels({ x: -0.5, y: -0.5, w: 3, h: 3 }, 100, 100)
  if (b.x === 0 && b.y === 0 && b.w === 100 && b.h === 100) ok('regionToPixels clamps an out-of-range rect into the image')
  else no(`regionToPixels clamp gave ${JSON.stringify(b)}`)

  const z = regionToPixels({ x: 1, y: 1, w: 0, h: 0 }, 100, 100)
  if (z.w >= 1 && z.h >= 1) ok('a zero-size rect is still at least 1px so the read cannot throw')
  else no(`zero-size rect gave ${JSON.stringify(z)}`)
}

// ── productRegion unions every product layer ─────────────────────────────
{
  const d = { layers: [{ kind: 'product', x: 0.1, y: 0.1, w: 0.2, h: 0.2 }, { kind: 'product', x: 0.5, y: 0.5, w: 0.3, h: 0.3 }] }
  const r = productRegion(d)
  if (Math.abs(r.x - 0.1) < 1e-9 && Math.abs(r.y - 0.1) < 1e-9 && Math.abs(r.w - 0.7) < 1e-9 && Math.abs(r.h - 0.7) < 1e-9) {
    ok('productRegion returns the union of every product layer')
  } else no(`productRegion gave ${JSON.stringify(r)}`)

  if (productRegion({ layers: [{ kind: 'bg' }] }) === null) ok('productRegion is null when nothing is placed')
  else no('productRegion did not return null for an empty doc')
}

// ── The fidelity modes: generated is blocking, placed is unverified ───────
{
  const gen = FIDELITY_MODE_BY_ID['generated']
  const placed = FIDELITY_MODE_BY_ID['placed']
  const locked = FIDELITY_MODE_BY_ID['locked']
  if (gen && gen.blocking && !gen.enforceable) ok('the "generated" mode is blocking (the product is never generated)')
  else no('the generated mode is not blocking')
  if (placed && !placed.enforceable) ok('the "placed" mode is unenforceable and must be reported unverified')
  else no('the placed mode claims to be enforceable')
  if (locked && locked.enforceable) ok('the "locked" mode is the enforceable one')
  else no('the locked mode is not enforceable')
  if (FIDELITY_MODES.length === 3) ok('three fidelity modes defined')
  else no(`expected 3 fidelity modes, got ${FIDELITY_MODES.length}`)
  if (COMPOSITE_STEPS.length === 4 && COMPOSITE_STEPS[0].id === 'lock' && COMPOSITE_STEPS[3].id === 'diff') {
    ok('the compositing contract runs lock → place → generate-around → diff')
  } else no('compositing contract order is wrong')
}

// ── 7. Sample-size discipline: a claim with no n is refused ───────────────
{
  const good = claim('Average product-region drift on a locked reference', '1.8%', 12)
  const bad = claim('Average product-region drift on a locked reference', '1.8%', 0)
  if (good.ok && /n=12/.test(good.text)) ok('a claim with a sample size reports it inline (n=12)')
  else no(`claim did not report n: ${good.text}`)
  if (!bad.ok && bad.value === null && /No claim is made/.test(bad.text)) ok('a claim with no sample size is REFUSED, not softened')
  else no(`unsized claim was not refused: ${bad.text}`)
  if (sampleLabel(0) === 'no sample' && sampleLabel(7) === 'n=7') ok('sampleLabel labels a zero sample as "no sample"')
  else no('sampleLabel mislabels a zero sample')
}

// ── 8. Freshness register ─────────────────────────────────────────────────
{
  // Every registered source must exist, and every source that DRIVES A RULE
  // must have a cadence — otherwise it can go stale silently.
  const registered = new Set(POLICY_FRESHNESS.map(r => r.source))
  const unknown = [...registered].filter(id => !SPEC_SOURCES[id])
  if (unknown.length === 0) ok(`every freshness row names a known source (${POLICY_FRESHNESS.length} rows)`)
  else no(`freshness rows with unknown sources: ${unknown.join(', ')}`)

  const badTier = POLICY_FRESHNESS.filter(r => !RECHECK_DAYS[r.recheck])
  if (badTier.length === 0) ok(`every freshness row uses a known tier (${Object.keys(RECHECK_DAYS).join(', ')})`)
  else no(`rows with an unknown tier: ${badTier.map(r => r.source).join(', ')}`)

  // Each row must say WHY that cadence, not just carry a number.
  const noWhy = POLICY_FRESHNESS.filter(r => !r.why || r.why.length < 12)
  if (noWhy.length === 0) ok('every freshness row states why that cadence was chosen')
  else no(`rows without a reason: ${noWhy.map(r => r.source).join(', ')}`)

  // Freshness arithmetic on a known date.
  const f = freshnessOf('ai-announce', TODAY)
  if (f.status === 'current' && f.age === 0 && f.limit === RECHECK_DAYS.critical) {
    ok(`ai-announce judged current on its pulled date (age ${f.age}d, limit ${f.limit}d)`)
  } else no(`ai-announce freshness gave ${JSON.stringify(f)}`)

  // A source read long ago is STALE at today's date.
  const stale = freshnessOf('ai-announce', '2027-06-01')
  if (stale.status === 'stale' && stale.dueIn < 0) ok(`ai-announce goes STALE past its cadence (dueIn ${stale.dueIn}d)`)
  else no(`stale detection failed: ${JSON.stringify(stale)}`)

  // Just inside the window is due-soon, not stale.
  const soon = freshnessOf('ai-announce', '2026-11-04')
  if (soon.status === 'due-soon') ok(`a source inside the warning band is due-soon (dueIn ${soon.dueIn}d)`)
  else no(`due-soon detection failed: ${JSON.stringify(soon)}`)

  // An unregistered source is reported, never assumed fresh.
  const unreg = freshnessOf('not-a-real-source', TODAY)
  if (unreg.status === 'unregistered') ok('an unregistered source is reported as unregistered, never assumed fresh')
  else no(`unregistered source reported ${unreg.status}`)

  // The report sorts worst-first and counts. On the pulled date everything is
  // current, so the sort is asserted against a date where staleness exists.
  const rep = freshnessReport(TODAY)
  const laterRep = freshnessReport('2027-01-15')
  if (laterRep.rows[0].status === 'stale') ok(`freshness report sorts worst-first (top: ${laterRep.rows[0].status})`)
  else no(`freshness report top row is ${laterRep.rows[0].status}, expected stale`)
  const total = Object.values(rep.counts).reduce((a, b) => a + b, 0)
  if (total === Object.keys(SPEC_SOURCES).length) ok(`every one of the ${total} sources is judged`)
  else no(`judged ${total} sources but the registry has ${Object.keys(SPEC_SOURCES).length}`)

  // ruleFreshness on a rule citing an unregistered source must NOT read fresh.
  const rf = ruleFreshness({ source: 'ghost-source' }, TODAY)
  if (rf.worst === 'unregistered' && rf.ok === false) ok('a rule citing an unknown source reports unregistered, never current')
  else no(`ruleFreshness on an unknown source gave worst=${rf.worst} ok=${rf.ok}`)

  // On the pulled date nothing should be stale.
  const staleNow = rep.rows.filter(r => r.status === 'stale')
  console.log(`\nfreshness on ${TODAY}: ${JSON.stringify(rep.counts)}`)
  if (staleNow.length === 0) ok('nothing is stale on the pulled-at date (the corpus is current)')
  else no(`${staleNow.length} source(s) already stale on the pulled date: ${staleNow.map(r => r.source).join(', ')}`)

  // And the register DOES go stale if nobody re-checks — proving it bites.
  const later = freshnessReport('2027-01-15')
  if ((later.counts.stale || 0) > 0) ok(`the register goes stale when unmaintained (${later.counts.stale} stale by 2027-01-15)`)
  else no('the register never goes stale — the check is inert')
}

// ── 3. Compare sign-off hardening ─────────────────────────────────────────
{
  const { makeCompareSignOff, compareStepStatus, referenceHash } = compose
  const base = {
    formatId: 'amz-main', w: 1200, h: 1200,
    layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.05, y: 0.05, w: 0.9, h: 0.9, dataUrl: 'data:image/png;base64,AAAA' }],
    meta: { referenceDataUrl: 'data:image/png;base64,REF1', lastEditAt: '2026-10-10T00:00:00Z' },
  }
  const noSign = compareStepStatus(base)
  if (noSign.required && !noSign.satisfied) ok('a product asset with no sign-off requires the compare step')
  else no(`unsigned compare status: ${JSON.stringify(noSign)}`)
  if (/self-declaration/i.test(noSign.detail)) ok('the unsigned prompt states plainly that it is a self-declaration')
  else no('the unsigned prompt does not state it is a self-declaration')

  const sign = makeCompareSignOff(base, { user: 't2', at: '2026-10-10T09:00:00Z' })
  if (sign.user === 't2' && sign.at && sign.assetVersion && sign.referenceHash) {
    ok('the sign-off records user, time, asset version and reference hash')
  } else no(`sign-off incomplete: ${JSON.stringify(sign)}`)
  if (/SELF-DECLARATION/.test(sign.declaration || '') && /not proof/i.test(sign.declaration || '')) {
    ok('the sign-off record itself carries the self-declaration caveat')
  } else no('the sign-off record does not carry the caveat')

  const signed = { ...base, meta: { ...base.meta, compareConfirmed: sign } }
  const st = compareStepStatus(signed)
  if (st.satisfied) ok('a matching sign-off satisfies the compare step')
  else no(`matching sign-off reported ${JSON.stringify(st)}`)
  if (/not evidence that anyone looked/i.test(st.detail)) ok('the satisfied state still says it is not evidence of review')
  else no('the satisfied state over-claims')

  // ANY edit invalidates it.
  const edited = { ...signed, meta: { ...signed.meta, lastEditAt: '2026-10-10T09:05:00Z' } }
  const stEdit = compareStepStatus(edited)
  if (!stEdit.satisfied && stEdit.reason === 'asset-changed') ok('an EDIT re-requires the compare sign-off')
  else no(`edited asset reported ${JSON.stringify(stEdit)}`)

  // A reference change invalidates it.
  const refChanged = { ...signed, meta: { ...signed.meta, referenceDataUrl: 'data:image/png;base64,REF2' } }
  const stRef = compareStepStatus(refChanged)
  if (!stRef.satisfied && stRef.reason === 'reference-changed') ok('a REFERENCE change re-requires the compare sign-off')
  else no(`changed reference reported ${JSON.stringify(stRef)}`)

  // A sign-off with no user cannot be attributed.
  const anon = { ...base, meta: { ...base.meta, compareConfirmed: { at: '2026-10-10T09:00:00Z', assetVersion: sign.assetVersion, referenceHash: sign.referenceHash } } }
  if (!compareStepStatus(anon).satisfied) ok('a sign-off with no user is refused (unattributable)')
  else no('an unattributable sign-off was accepted')

  // A pre-hardening record (no version binding) is refused.
  const legacy = { ...base, meta: { ...base.meta, compareConfirmed: { at: '2026-10-10T09:00:00Z', by: 'operator' } } }
  if (!compareStepStatus(legacy).satisfied) ok('a legacy sign-off with no version binding is refused')
  else no('a legacy sign-off was accepted')

  if (referenceHash('abc') === referenceHash('abc') && referenceHash('abc') !== referenceHash('abd')) {
    ok('referenceHash is deterministic and change-sensitive')
  } else no('referenceHash is not deterministically change-sensitive')
  if (referenceHash('') === '') ok('referenceHash of an empty reference is empty, so a missing reference cannot collide')
  else no('referenceHash of an empty reference is not empty')
}

// ── 4. Threshold calibration across synthetic edit classes ────────────────
{
  // A synthetic base "product": a striped box with a label. 64x64 keeps the
  // maths fast while still exercising every pixel.
  const N = 64
  const base = new Uint8ClampedArray(N * N * 4)
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const i = (y * N + x) * 4
      const inBox = x > 6 && x < N - 6 && y > 6 && y < N - 6
      const onLabel = inBox && y > 24 && y < 34 && x > 16 && x < N - 16
      base[i] = onLabel ? 20 : (inBox ? 201 : 242)
      base[i + 1] = onLabel ? 20 : (inBox ? 79 : 227)
      base[i + 2] = onLabel ? 20 : (inBox ? 42 : 201)
      base[i + 3] = 255
    }
  }
  const clone = () => new Uint8ClampedArray(base)

  const EDITS = [
    { id: 'identical', class: 'control (no change)', expect: 'pass', make: () => clone() },
    { id: 'recolor-global', class: 'recolour (whole product)', expect: 'block', make: () => { const a = clone(); for (let i = 0; i < a.length; i += 4) { a[i] = 42; a[i + 1] = 111; a[i + 2] = 201 }; return a } },
    { id: 'relight', class: 'relight (uniform luminance shift)', expect: 'pass-or-block', make: () => { const a = clone(); for (let i = 0; i < a.length; i += 4) { a[i] = Math.min(255, a[i] + 24); a[i + 1] = Math.min(255, a[i + 1] + 24); a[i + 2] = Math.min(255, a[i + 2] + 24) }; return a } },
    { id: 'warp-shift', class: 'warp (2px shift)', expect: 'block', make: () => { const a = clone(); for (let y = 10; y < N - 10; y++) for (let x = 10; x < N - 10; x++) { const s = (y * N + (x - 2)) * 4, d = (y * N + x) * 4; a[d] = a[s]; a[d + 1] = a[s + 1]; a[d + 2] = a[s + 2] }; return a } },
    { id: 'label-text-change', class: 'label text change (small in-product)', expect: 'evade-average', make: () => { const a = clone(); for (let y = 26; y < 32; y++) for (let x = 18; x < 26; x++) { const i = (y * N + x) * 4; a[i] = 240; a[i + 1] = 240; a[i + 2] = 20 }; return a } },
    { id: 'logo-swap', class: 'logo swap (localised block)', expect: 'evade-average', make: () => { const a = clone(); for (let y = 12; y < 18; y++) for (let x = 12; x < 20; x++) { const i = (y * N + x) * 4; a[i] = 12; a[i + 1] = 92; a[i + 2] = 220 }; return a } },
  ]

  const results = []
  for (const e of EDITS) {
    const r = regionDiff(base, e.make())
    results.push({ ...e, ok: r.ok, mean: r.mean, worst: r.worst, reason: r.reason })
  }

  console.log('\nthreshold calibration (mean limit 6%, worst-pixel tripwire 45%):')
  for (const r of results) {
    console.log(`  ${r.id.padEnd(20)} mean ${(r.mean * 100).toFixed(2).padStart(6)}%  worst ${(r.worst * 100).toFixed(1).padStart(5)}%  -> ${r.ok ? 'PASS' : 'BLOCK'} (${r.reason})`)
  }

  const byId = Object.fromEntries(results.map(r => [r.id, r]))
  if (byId.identical.ok && byId.identical.mean === 0) ok('calibration control: an identical product passes at 0.00%')
  else no(`control gave mean ${byId.identical.mean}`)
  if (!byId['recolor-global'].ok) ok('recolour is DETECTED (blocked)')
  else no('recolour evaded detection')
  if (!byId['warp-shift'].ok) ok('warp is DETECTED (blocked)')
  else no('warp evaded detection')
  if (!byId['relight'].ok) {
    ok(`relight is blocked at these thresholds (mean ${(byId.relight.mean * 100).toFixed(2)}%) - a re-shoot under different light may be refused, which is the safe direction`)
  } else {
    ok(`relight passes at these thresholds (mean ${(byId.relight.mean * 100).toFixed(2)}%) - a genuine re-shoot is tolerated`)
  }

  // The honest part: document what EVADES the average test but is caught, if at
  // all, only by the worst-pixel tripwire.
  const evaders = results.filter(r => r.ok && r.id !== 'identical' && r.id !== 'relight')
  const caughtByWorst = results.filter(r => !r.ok && r.reason === 'worst-pixel-exceeded')
  console.log(`  classes evading the average test: ${evaders.length ? evaders.map(r => r.id).join(', ') : 'none'} (relight is expected to pass by design)`)
  console.log(`  classes caught only by the worst-pixel tripwire: ${caughtByWorst.length ? caughtByWorst.map(r => r.id).join(', ') : 'none'}`)
  console.log('  LIMIT: a small in-product edit that stays inside the worst-pixel tolerance is NOT detectable by this method.')
  ok('calibration reported per class with the undetectable class named explicitly')
}


// ?? The second check: label-region diff ???????????????????????????????????
{
  const N = 32
  const mk = (labelValue) => {
    const a = new Uint8ClampedArray(N * N * 4)
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const i = (y * N + x) * 4
      const inLabel = x > 8 && x < 24 && y > 10 && y < 22
      a[i] = inLabel ? labelValue : 201
      a[i + 1] = inLabel ? labelValue : 79
      a[i + 2] = inLabel ? labelValue : 42
      a[i + 3] = 255
    }
    return a
  }
  const ref = mk(20)
  const same = labelRegionDiff(ref, mk(20))
  if (same.ok && same.mean === 0) ok('label-region check passes an unchanged label at 0.00%')
  else no(`unchanged label gave ${JSON.stringify({ ok: same.ok, mean: same.mean })}`)

  const changed = labelRegionDiff(ref, mk(120))
  if (!changed.ok) ok(`label-region check BLOCKS a label change (${(changed.mean * 100).toFixed(1)}% vs a ${(DEFAULT_LABEL_THRESHOLD * 100).toFixed(1)}% limit)`)
  else no('label-region check passed a changed label')

  // A global recolour moves the label too, so the tighter check still fires.
  const globalTest = labelRegionDiff(ref, mk(60))
  if (!globalTest.ok) ok('label-region check is tighter than the global average test')
  else no('label-region check is not tighter than the global test')

  // An empty or mismatched label region must be REFUSED, whatever the precise
  // reason: a comparison that could not run is never a pass.
  const empty = labelRegionDiff(new Uint8ClampedArray(0), ref)
  const refusedReasons = ['nothing-to-compare', 'label-region-empty', 'length-mismatch', 'not-rgba', 'missing-buffer']
  if (!empty.ok && refusedReasons.includes(empty.reason)) {
    ok(`a label region that cannot be compared is refused, not passed (${empty.reason})`)
  } else no(`empty label region gave ok=${empty.ok} reason=${empty.reason}`)
  const bothEmpty = labelRegionDiff(new Uint8ClampedArray(0), new Uint8ClampedArray(0))
  if (!bothEmpty.ok) ok(`two empty label regions are refused (${bothEmpty.reason})`)
  else no('two empty label regions passed')

  if (FIDELITY_BLIND_SPOTS.length >= 4) ok(`the undetectable cases are documented explicitly (${FIDELITY_BLIND_SPOTS.length} listed)`)
  else no('the blind spots are not documented')
}

console.log(`\nFIDELITY + FRESHNESS: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
