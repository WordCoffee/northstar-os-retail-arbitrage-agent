// ═══════════════════════════════════════════════════════════════════════════
// NO-THIRD-PARTY GUARD — the served UI must make ZERO external requests.
//
// Scans the REAL built output (northstar-os-ui/dist):
//   • index.html: no http(s) URL at all (every resource reference is local);
//   • CSS: no external url(...) and no @import;
//   • JS: no request-shaped external reference (fetch/import/new URL with a
//     literal https URL, font-CDN hosts, src/href assignments to https).
//
// Amazon help-page URLs that live in the studio's DATA (source citations in
// specRegistry/disclosure) are strings, not requests: the scan deliberately
// checks request shapes, not every URL string. tools/verify-amazon-files.cjs
// additionally proves at RUNTIME that zero external requests occur.
//
// Run:  node tools/check-no-third-party.cjs
// Exit: 0 = clean, 1 = a third-party reference, 2 = no dist to scan.
// ═══════════════════════════════════════════════════════════════════════════

const fs = require('fs')
const path = require('path')

const UI = path.join(__dirname, '..', 'northstar-os-ui')
const DIST = path.join(UI, 'dist')
const ASSETS = path.join(DIST, 'assets')

let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

if (!fs.existsSync(DIST)) {
  console.log('FAIL  dist not found - run `npm run build` first')
  process.exit(2)
}

// XML namespace identifiers are inert strings (inside data: URIs / xmlns
// attributes), never requests. Strip them before matching.
const NAMESPACE_ALLOW = /https?:\/\/(?:www\.w3\.org\/2000\/svg|schemas\.openxmlformats\.org|purl\.org|schemas\.microsoft\.com)[^\s"'<>)]*/gi
const stripNamespaces = (s) => s.replace(NAMESPACE_ALLOW, '')

// 1. index.html: zero http(s) URLs.
const indexHtml = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8')
const htmlUrls = stripNamespaces(indexHtml).match(/https?:\/\/[^\s"'<>]+/g) || []
if (htmlUrls.length === 0) ok('dist/index.html contains no http(s) URL (all references are local; XML namespaces excluded)')
else no('dist/index.html references external URLs', htmlUrls.slice(0, 3).join(' | '))

// 2. CSS: no external url() or @import.
const cssFiles = fs.existsSync(ASSETS) ? fs.readdirSync(ASSETS).filter(f => f.endsWith('.css')) : []
let cssBad = []
for (const f of cssFiles) {
  const src = fs.readFileSync(path.join(ASSETS, f), 'utf8')
  for (const m of src.matchAll(/url\(\s*['"]?https?:\/\/[^)]+\)/gi)) cssBad.push(`${f}: ${m[0].slice(0, 80)}`)
  for (const m of src.matchAll(/@import\s+(?:url\()?['"]https?:\/\//gi)) cssBad.push(`${f}: @import external`)
}
if (cssBad.length === 0) ok(`dist CSS (${cssFiles.length} file(s)) has no external url() or @import`)
else no('dist CSS references a third-party resource', cssBad.slice(0, 3).join(' | '))

// 3. JS: request-shaped external references only.
const jsFiles = fs.existsSync(ASSETS) ? fs.readdirSync(ASSETS).filter(f => f.endsWith('.js')) : []
const REQUEST_SHAPES = [
  /fetch\(\s*["'`]https?:\/\//,
  /import\(\s*["'`]https?:\/\//,
  /new\s+URL\(\s*["'`]https?:\/\//,
  /fonts\.googleapis\.com|fonts\.gstatic\.com/,
  /\.src\s*=\s*["'`]https?:\/\//,
]
let jsBad = []
for (const f of jsFiles) {
  const src = fs.readFileSync(path.join(ASSETS, f), 'utf8')
  for (const re of REQUEST_SHAPES) {
    const m = src.match(re)
    if (m) jsBad.push(`${f}: ${m[0].slice(0, 60)}`)
  }
}
if (jsBad.length === 0) ok(`dist JS (${jsFiles.length} file(s)) has no request-shaped external reference`)
else no('dist JS contains a request-shaped external reference', jsBad.slice(0, 3).join(' | '))

// 4. The vendored fonts are present and local-only.
const fontsCss = path.join(DIST, 'fonts', 'fonts.css')
if (fs.existsSync(fontsCss)) {
  const src = fs.readFileSync(fontsCss, 'utf8')
  const external = src.match(/url\(https?:\/\//g) || []
  const local = src.match(/url\(\/ui\/fonts\//g) || []
  if (external.length === 0 && local.length > 0) ok(`dist/fonts/fonts.css: ${local.length} local font reference(s), zero external`)
  else no('dist/fonts/fonts.css still references an external font', `${external.length} external`)
} else {
  no('dist/fonts/fonts.css is missing - the self-hosted fonts were not copied')
}

// 5. Source CSS files must not import third-party resources either.
const srcCss = []
const walk = (dir) => {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory()) walk(p)
    else if (name.endsWith('.css')) srcCss.push(p)
  }
}
walk(path.join(UI, 'src'))
let srcBad = []
for (const p of srcCss) {
  const src = stripNamespaces(fs.readFileSync(p, 'utf8'))
  if (/url\(\s*['"]?https?:\/\//i.test(src) || /@import\s+(?:url\()?['"]https?:\/\//i.test(src)) {
    srcBad.push(path.relative(UI, p))
  }
}
if (srcBad.length === 0) ok(`source CSS (${srcCss.length} file(s)) is local-only`)
else no('source CSS imports a third-party resource', srcBad.join(', '))

console.log(`\nNO-THIRD-PARTY GUARD: ${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
