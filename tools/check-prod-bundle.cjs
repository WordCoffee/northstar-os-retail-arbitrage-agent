// ═══════════════════════════════════════════════════════════════════════════
// BUNDLE GUARD — production dist + the separate test build (dist-test)
//
// Item 5 (Phase 5): the ?engine=1 test hook must not be able to run in a
// production build. It is gated on a compile-time constant, so rollup
// eliminates its body (dynamic imports included).
//
// Item 2 (Phase 6) extends the contract:
//   • PRODUCTION dist must carry NEITHER the engine hook NOR the dev shim
//     (identity, demo credentials, X-User-Id header emitter, runtime switch).
//   • the TEST build (dist-test, built with VITE_TEST_HOOKS=1) is served the
//     same way as production but DOES carry the engine hook; it must still NOT
//     carry the dev shim - a served bundle signs in through real credentials.
//
// Run:  node tools/check-prod-bundle.cjs
// Exit: 0 = clean, 1 = contract violated, 2 = no production dist to scan.
// ═══════════════════════════════════════════════════════════════════════════

const fs = require('fs')
const path = require('path')

const UI = path.join(__dirname, '..', 'northstar-os-ui')
const DIST = path.join(UI, 'dist')
const TEST_DIST = path.join(UI, 'dist-test')

let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

// Strings that must NOT survive into ANY served bundle (production AND test).
// The dev-shim identity, its credentials and the header emitter are
// compile-time-eliminated (foundation/dev.js: LOCAL_DEV = import.meta.env.DEV).
const SHIM_FORBIDDEN = [
  { needle: '123abc', why: 'the local dev-shim demo password' },
  { needle: 'demo-t2', why: 'the local dev-shim demo identity' },
  { needle: 'X-User-Id', why: 'the dev-shim header emitter' },
  { needle: '__NORTHSTAR_LOCAL_DEV__', why: 'the removed runtime shim switch' },
]

// The hook query read only exists inside the hook body. Match it by pattern so
// the needle cannot be confused with its own quoting.
const ENGINE_READ = /get\(\s*.engine.\s*\)\s*!==\s*.1./

function loadAssets(dir) {
  const assets = path.join(dir, 'assets')
  if (!fs.existsSync(assets)) return null
  const files = fs.readdirSync(assets).filter(f => f.endsWith('.js'))
  if (!files.length) return null
  let total = 0
  const contents = files.map((f) => {
    const src = fs.readFileSync(path.join(assets, f), 'utf8')
    total += src.length
    return { f, src }
  })
  return { files, contents, total }
}

function hasNeedle(contents, needle) {
  return contents.filter(c => c.src.includes(needle))
}
function hasPattern(contents, re) {
  return contents.filter(c => re.test(c.src))
}

// ── 1. PRODUCTION dist ─────────────────────────────────────────────────────
const prod = loadAssets(DIST)
if (!prod) {
  console.log('FAIL  production dist/assets not found - run `npm run build` first')
  process.exit(2)
}
console.log(`scanning PRODUCTION: ${prod.files.length} bundle file(s) in dist/assets\n`)

for (const { needle, why } of [{ needle: '__northstarStudioEngine', why: 'the ?engine=1 test hook global' }, ...SHIM_FORBIDDEN]) {
  const hits = hasNeedle(prod.contents, needle)
  if (hits.length === 0) ok(`prod: "${needle}" is ABSENT (${why})`)
  else no(`prod: "${needle}" is PRESENT (${why})`, hits.map(h => h.f).join(', '))
}
if (hasPattern(prod.contents, ENGINE_READ).length === 0) ok('prod: the hook query-parameter read is ABSENT (its body was eliminated)')
else no('prod: the hook body survived into the bundle', hasPattern(prod.contents, ENGINE_READ).map(h => h.f).join(', '))
if (prod.contents.some(c => /createElement|react/i.test(c.src))) ok('prod: positive control present (react/createElement), the scan is not vacuous')
else no('prod: positive control failed - the bundles look empty or unreadable')

// ── 2. TEST build (dist-test) ──────────────────────────────────────────────
console.log('')
const test = loadAssets(TEST_DIST)
if (!test) {
  console.log('NOT RUN  dist-test not built - the test-artifact contract was NOT checked.')
  console.log('         Build it with:  cd northstar-os-ui && set VITE_TEST_HOOKS=1 && npm run build -- --outDir dist-test')
} else {
  console.log(`scanning TEST BUILD: ${test.files.length} bundle file(s) in dist-test/assets\n`)
  const hookHits = hasNeedle(test.contents, '__northstarStudioEngine')
  if (hookHits.length) ok(`test: the engine hook global is PRESENT (${hookHits.map(h => h.f).join(', ')}) - the pixel-path harness can run`)
  else no('test: the engine hook global is ABSENT from the test build - the pixel paths cannot run against it')
  if (hasPattern(test.contents, ENGINE_READ).length) ok('test: the hook query-parameter read is PRESENT')
  else no('test: the hook query-parameter read is missing - the hook cannot be activated')
  for (const { needle, why } of SHIM_FORBIDDEN) {
    const hits = hasNeedle(test.contents, needle)
    if (hits.length === 0) ok(`test: "${needle}" is ABSENT (served bundles sign in with real credentials)`)
    else no(`test: "${needle}" is PRESENT (${why})`, hits.map(h => h.f).join(', '))
  }
  if (test.contents.some(c => /createElement|react/i.test(c.src))) ok('test: positive control present, the scan is not vacuous')
  else no('test: positive control failed - the bundles look empty or unreadable')
}

console.log(`\nscanned ${(prod.total / 1024).toFixed(0)} KB (prod)${test ? ` + ${(test.total / 1024).toFixed(0)} KB (test)` : ''} across ${prod.files.length + (test ? test.files.length : 0)} file(s)`)
console.log(`\nBUNDLE GUARD: ${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
