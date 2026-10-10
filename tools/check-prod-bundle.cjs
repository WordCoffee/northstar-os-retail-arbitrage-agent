// ═══════════════════════════════════════════════════════════════════════════
// PRODUCTION BUNDLE GUARD
//
// Item 5: the ?engine=1 test hook must not be able to run in a production
// build. It is gated on `import.meta.env.DEV`, which Vite replaces with a
// literal, so rollup eliminates the dynamic imports entirely. This asserts that
// against the REAL built output rather than trusting the config.
//
// Run:  node tools/check-prod-bundle.cjs
// Exit: 0 = clean, 1 = the hook (or another dev-only surface) is in the bundle.
// ═══════════════════════════════════════════════════════════════════════════

const fs = require('fs')
const path = require('path')

const DIST = path.join(__dirname, '..', 'northstar-os-ui', 'dist')
const ASSETS = path.join(DIST, 'assets')

let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

// Strings that must NOT survive into a production bundle.
const FORBIDDEN = [
  { needle: '__northstarStudioEngine', why: 'the ?engine=1 test hook global' },
]

// Dev-only markers that would indicate the hook body was not eliminated.
const DEV_ONLY = [
  { needle: 'engine', param: true, why: 'the engine query parameter read' },
]

if (!fs.existsSync(ASSETS)) {
  console.log('FAIL  dist/assets not found - run `npm run build` first')
  process.exit(1)
}

const files = fs.readdirSync(ASSETS).filter(f => f.endsWith('.js'))
if (!files.length) { console.log('FAIL  no .js files in dist/assets'); process.exit(1) }
console.log(`scanning ${files.length} bundle file(s) in dist/assets\n`)

let totalBytes = 0
const contents = []
for (const f of files) {
  const p = path.join(ASSETS, f)
  const src = fs.readFileSync(p, 'utf8')
  totalBytes += src.length
  contents.push({ f, src })
}

for (const { needle, why } of FORBIDDEN) {
  const hits = contents.filter(c => c.src.includes(needle))
  if (hits.length === 0) ok(`"${needle}" is ABSENT from the production bundle (${why})`)
  else no(`"${needle}" is PRESENT in the production bundle (${why})`, hits.map(h => h.f).join(', '))
}

// The query-parameter read only exists inside the hook. Match it by pattern so
// the needle cannot be confused with its own quoting.
const ENGINE_READ = /get\(\s*.engine.\s*\)\s*!==\s*.1./
const engineRead = contents.filter(c => ENGINE_READ.test(c.src))
if (engineRead.length === 0) ok('the hook query-parameter read is ABSENT (its body was eliminated)')
else no('the hook body survived into the bundle', engineRead.map(h => h.f).join(', '))

// A positive control: something that MUST be present, so an empty or broken
// scan cannot pass vacuously.
const control = contents.some(c => /createElement|react/i.test(c.src))
if (control) ok('positive control: react/createElement present, so the scan is not vacuous')
else no('positive control failed: the bundles look empty or unreadable')

console.log(`\nscanned ${(totalBytes / 1024).toFixed(0)} KB across ${files.length} file(s)`)
console.log(`\nPROD BUNDLE GUARD: ${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
