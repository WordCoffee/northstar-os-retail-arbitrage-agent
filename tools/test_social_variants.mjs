// S5 contract test — the variant matrix (node, no bundler).
//   node tools/test_social_variants.mjs
// Exits non-zero on any failure so tools/rea_regress.py can gate it.

import { buildVariantMatrix, cropFor, keepInIntersection } from '../northstar-os-ui/src/studio/engine/variants.js'

let failures = 0
const check = (name, cond, detail = '') => {
  if (cond) { console.log(`  ok   ${name}`) }
  else { failures += 1; console.log(`  FAIL ${name} ${detail}`) }
}
const near = (a, b, tol = 0.01) => Math.abs(a - b) <= tol

const master = { w: 1440, h: 1800 }   // the IG portrait master
const targets = [
  { id: 'ig-post', w: 1440, h: 1800 },
  { id: 'pin', w: 1000, h: 1500 },
  { id: 'x-post', w: 1200, h: 628 },
  { id: 'tiktok', w: 1080, h: 1920 },
]

console.log('S5 — variant matrix')

const m = buildVariantMatrix({ master, targets })
check('ok on a compatible target set', m.ok === true, m.reason || '')
check('one variant per target', m.variants.length === targets.length)
check('keepIn is non-empty', m.keepIn && !m.keepIn.empty, JSON.stringify(m.keepIn))
check('keepIn area reported as a percentage', typeof m.keepIn.areaPct === 'number')

// every crop must sit inside the master
let inside = true
for (const v of m.variants) {
  if (v.cropPx.x < 0 || v.cropPx.y < 0) inside = false
  if (v.cropPx.x + v.cropPx.w > master.w + 1) inside = false
  if (v.cropPx.y + v.cropPx.h > master.h + 1) inside = false
}
check('every crop box lies inside the master', inside)

// the 16:9 target keeps only 41.9% of the master height, full width
const x = m.variants.find(v => v.id === 'x-post')
check('16:9 keeps full width and ~41.9% height',
  near(x.cropNorm.w, 1.0) && near(x.cropNorm.h, 0.4189, 0.02),
  JSON.stringify(x.cropNorm))

// the shared region is the height of the widest crop (16:9), so ~41.9%
check('keepIn height matches the tightest crop', near(m.keepIn.h, 0.4189, 0.02), JSON.stringify(m.keepIn))

// upscaling is disclosed, not hidden: a 4K target from a 1440 master
const big = buildVariantMatrix({ master, targets: [{ id: 'yt-thumb', w: 3840, h: 2160 }] })
check('upscale is flagged', big.variants[0].upscale === true && big.warnings.length > 0)

// gravity moves the window
const left = cropFor(master, targets[2], { x: 0.0, y: 0.5 })
const right = cropFor(master, targets[2], { x: 1.0, y: 0.5 })
check('gravity 0 pins to the left edge', left.cropPx.x === 0)
check('gravity 1 pins to the right edge',
  right.cropPx.x + right.cropPx.w === master.w, JSON.stringify(right.cropPx))

// contradictory gravity across targets => no shared region, and the matrix says so.
// A crop must be narrower than half the master before left/right gravity can
// actually make two windows disjoint (2:5 = 0.5 of the master width).
const conflicting = buildVariantMatrix({
  master,
  targets: [
    { id: 'a', w: 720, h: 1800, focal: { x: 0.0, y: 0.5 } },
    { id: 'b', w: 720, h: 1800, focal: { x: 1.0, y: 0.5 } },
  ],
})
check('conflicting anchors are refused', conflicting.ok === false, conflicting.reason || '')
check('the refusal is explained', /cannot share one anchor/.test(conflicting.reason || ''))

// a degenerate intersection helper
check('empty intersection detected',
  keepInIntersection([
    { cropNorm: { x: 0, y: 0, w: 0.3, h: 1 } },
    { cropNorm: { x: 0.8, y: 0, w: 0.2, h: 1 } },
  ]).empty === true)

// no targets is a stated outage, not a silent pass
const none = buildVariantMatrix({ master, targets: [] })
check('empty target list is refused', none.ok === false && /no target/.test(none.reason))

console.log(failures === 0 ? '\nPASS: variant matrix' : `\nFAIL: ${failures} check(s)`)
process.exit(failures === 0 ? 0 : 1)
