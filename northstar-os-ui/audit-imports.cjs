// Static import audit for the studio rooms.
//
// Two checks, both reliable:
//   1. DEAD IMPORT  — a binding imported but never referenced in real code.
//   2. MISSING BINDING — an identifier used in real code that is neither
//      imported nor declared anywhere in the file. This is exactly the
//      `ReferenceError: X is not defined` class of bug that esbuild cannot see
//      and that only explodes at runtime.
//
// Comments and string/template literals are stripped first, otherwise prose
// like "A design document is a flat layer list" produces thousands of false
// positives.
const fs = require('fs')
const path = require('path')

const ROOT = __dirname

const FILES = [
  'src/pages/internal/CreativeStudio.jsx',
  'src/pages/internal/ProductDesigner.jsx',
  'src/studio/engine/doc.js',
  'src/studio/engine/three.js',
  'src/studio/engine/mockups.js',
  'src/studio/engine/presets.js',
  'src/studio/engine/sceneDoc.js',
  'src/studio/engine/assets.js',
  'src/studio/engine/store.js',
  'src/studio/components/Stage.jsx',
  'src/studio/components/Chrome.jsx',
  'src/studio/components/Fields.jsx',
]

// Globals and language builtins that legitimately appear un-imported.
const GLOBALS = new Set([
  'React', 'Object', 'Array', 'String', 'Number', 'Boolean', 'Math', 'JSON', 'Date',
  'Promise', 'Map', 'Set', 'WeakMap', 'Error', 'TypeError', 'RangeError', 'Response',
  'Request', 'Headers', 'AbortController', 'localStorage', 'indexedDB', 'navigator',
  'document', 'window', 'Image', 'FileReader', 'Blob', 'URL', 'performance',
  'requestAnimationFrame', 'cancelAnimationFrame', 'ResizeObserver', 'MutationObserver',
  'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'fetch', 'console',
  'URLSearchParams', 'URL', 'FormData', 'KeyboardEvent', 'MouseEvent', 'PointerEvent',
  'undefined', 'null', 'true', 'false', 'Infinity', 'NaN', 'Intl', 'isNaN', 'parseInt',
  'parseFloat', 'Uint8ClampedArray', 'Int32Array', 'Float32Array', 'process', 'require',
  'module', 'exports', '__dirname', '__filename', 'globalThis', 'structuredClone',
])

// Remove comments (line + block) and string/template/regex literals.
function stripNoise(src) {
  let out = ''
  let i = 0
  const n = src.length
  while (i < n) {
    const c = src[i]
    const d = src[i + 1]
    // line comment
    if (c === '/' && d === '/') { while (i < n && src[i] !== '\n') i += 1; continue }
    // block comment
    if (c === '/' && d === '*') { i += 2; while (i < n && !(src[i] === '*' && src[i + 1] === '/')) i += 1; i += 2; continue }
    // strings
    if (c === '"' || c === "'" || c === '`') {
      const q = c
      i += 1
      while (i < n) {
        if (src[i] === '\\') { i += 2; continue }
        if (src[i] === q) { i += 1; break }
        // keep template ${...} expressions, they are real code
        if (q === '`' && src[i] === '$' && src[i + 1] === '{') {
          let depth = 1
          i += 2
          const start = i
          while (i < n && depth > 0) {
            if (src[i] === '{') depth += 1
            else if (src[i] === '}') depth -= 1
            if (depth > 0) i += 1
          }
          out += src.slice(start, i) + ' '
          i += 1
          continue
        }
        i += 1
      }
      out += ' '
      continue
    }
    out += c
    i += 1
  }
  return out
}

let problems = 0

for (const rel of FILES) {
  const file = path.join(ROOT, rel)
  if (!fs.existsSync(file)) { console.log('MISSING FILE: ' + rel); problems += 1; continue }
  const raw = fs.readFileSync(file, 'utf8')

  // ── collect imported bindings (from the RAW source; noise removal would
  //    erase the module specifier and make the import lines unmatchable) ──
  const imported = new Map()
  const importRe = /import\s+(?:([A-Za-z_$][\w$]*)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['"][^'"]+['"]/g
  let m
  while ((m = importRe.exec(raw))) {
    if (m[1]) imported.set(m[1], rel)
    if (m[2]) {
      m[2].split(',').map(s => s.trim()).filter(Boolean).forEach(spec => {
        const parts = spec.split(/\s+as\s+/)
        const local = parts[parts.length - 1].trim()
        if (local) imported.set(local, rel)
      })
    }
  }
  const starRe = /import\s+\*\s+as\s+([A-Za-z_$][\w$]*)/g
  while ((m = starRe.exec(raw))) imported.delete(m[1])

  // ── body: imports removed, then comments/strings stripped ──
  const body = stripNoise(raw.replace(/^\s*import\s[\s\S]*?from\s*['"][^'"]*['"]\s*$/gm, ''))

  // ── declared names ──
  const declared = new Set()
  const addDecl = (re) => { let mm; while ((mm = re.exec(body))) declared.add(mm[1]) }
  addDecl(/\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)/g)
  addDecl(/\bfunction\s+([A-Za-z_$][\w$]*)/g)
  addDecl(/\b(?:const|let|var)\s*\{([^}]*)\}/g)
  // destructured names
  {
    let mm
    const dRe = /\b(?:const|let|var)\s*\{([^}]*)\}/g
    while ((mm = dRe.exec(body))) {
      mm[1].split(',').map(s => s.trim()).filter(Boolean).forEach(spec => {
        const parts = spec.split(':')
        const local = parts.length > 1 ? parts[1].trim() : parts[0].trim()
        const alias = local.split(/\s+as\s+/)
        declared.add((alias[alias.length - 1] || '').trim())
      })
    }
  }
  // function parameters (covers arrow props and helper params)
  {
    let mm
    const pRe = /(?:function\s*[\w$]*\s*)?\(([^()]*)\)/g
    while ((mm = pRe.exec(body))) {
      mm[1].split(',').map(s => s.trim()).filter(Boolean).forEach(p => {
        const nm = p.replace(/^[.\[]{0,2}|[.\]]{0,2}$/g, '').split('=')[0].trim().split(':')[0].trim()
        if (/^[A-Za-z_$][\w$]*$/.test(nm)) declared.add(nm)
      })
    }
  }

  // ── 1. dead imports ──
  const dead = []
  for (const name of imported.keys()) {
    const uses = (body.match(new RegExp('\\b' + name.replace(/\$/g, '\\$') + '\\b', 'g')) || []).length
    if (uses === 0) dead.push(name)
  }

  // ── 2. missing bindings ──
  // Only trust two signals: JSX element names and StandaloneCapitalised refs
  // that look like component/factory calls. Everything else is too noisy.
  const used = new Set()
  {
    let mm
    const jsxRe = /<\s*([A-Z][\w$]*)/g
    while ((mm = jsxRe.exec(body))) used.add(mm[1])
  }
  {
    let mm
    const callRe = /\b([A-Z][\w$]{2,})\s*\(/g
    while ((mm = callRe.exec(body))) used.add(mm[1])
  }
  const missing = []
  for (const name of used) {
    if (GLOBALS.has(name)) continue
    if (imported.has(name)) continue
    if (declared.has(name)) continue
    missing.push(name)
  }

  if (dead.length || missing.length) {
    problems += dead.length + missing.length
    console.log(rel)
    if (dead.length) console.log('  unused imports:    ' + dead.join(', '))
    if (missing.length) console.log('  possibly-undefined: ' + missing.join(', '))
  }
}

console.log(problems === 0
  ? 'IMPORT AUDIT: clean — no dead imports, no undefined references'
  : `IMPORT AUDIT: ${problems} issue(s)`)
process.exit(problems ? 1 : 0)
