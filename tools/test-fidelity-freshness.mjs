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
  claim, sampleLabel,
} from '../northstar-os-ui/src/studio/engine/fidelity.js'
import {
  POLICY_FRESHNESS, RECHECK_DAYS, freshnessOf, freshnessReport, ruleFreshness,
  SPEC_SOURCES, TODAY,
} from '../northstar-os-ui/src/studio/engine/specRegistry.js'

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

console.log(`\nFIDELITY + FRESHNESS: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
