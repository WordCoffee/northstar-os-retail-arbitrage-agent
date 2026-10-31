#!/usr/bin/env node
/* JSX structural edit for the Galactic deck integration.
 *
 * The Python ast_edit engine refuses non-Python files by design. This is its
 * JSX counterpart: parse with Babel, locate the nodes, insert text at their AST
 * offsets, then re-parse the result. Everything outside the insertion points is
 * byte-identical.
 *
 *   node scripts/ast_edit_js.cjs --check
 *   node scripts/ast_edit_js.cjs --apply
 */
const fs = require('fs')
const path = require('path')
const parser = require('@babel/parser')

const ROOT = path.resolve(__dirname, '..')
const APP = path.join(ROOT, 'src', 'App.jsx')
const NAV = path.join(ROOT, 'src', 'data', 'nav-config.js')

function parse(source, file) {
  return parser.parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator'],
    errorRecovery: false,
    sourceFilename: file,
  })
}

function walk(node, fn, parent = null) {
  if (!node || typeof node.type !== 'string') return
  fn(node, parent)
  for (const key of Object.keys(node)) {
    if (key === 'loc' || key === 'leadingComments' || key === 'trailingComments' || key === 'innerComments') continue
    const value = node[key]
    if (Array.isArray(value)) {
      for (const child of value) walk(child, fn, node)
    } else if (value && typeof value.type === 'string') {
      walk(value, fn, node)
    }
  }
}

function attrValue(opening, name) {
  const attrs = opening.attributes || []
  for (const attr of attrs) {
    if (attr.type !== 'JSXAttribute' || attr.name?.name !== name) continue
    if (attr.value?.type === 'StringLiteral') return attr.value.value
  }
  return null
}

function isRouteTo(node, target) {
  return node.type === 'JSXElement'
    && node.openingElement?.name?.name === 'Route'
    && attrValue(node.openingElement, 'path') === target
}

function objectProp(node, key) {
  if (!node || node.type !== 'ObjectExpression') return null
  for (const prop of node.properties || []) {
    if (prop.type !== 'ObjectProperty') continue
    const name = prop.key?.name || prop.key?.value
    if (name === key) return prop
  }
  return null
}

function insert(list, at, text) {
  list.push({ at, text })
}

function lineStart(source, at) {
  return source.lastIndexOf('\n', Math.max(0, at - 1)) + 1
}

function applyInserts(source, inserts, file) {
  const ordered = [...inserts].sort((a, b) => b.at - a.at)
  let out = source
  for (const item of ordered) {
    out = out.slice(0, item.at) + item.text + out.slice(item.at)
  }
  parse(out, file) // throws on an invalid result
  return out
}

function diff(before, after, label) {
  const a = before.split(/\r?\n/)
  const b = after.split(/\r?\n/)
  const lines = []
  let i = 0
  let j = 0
  while (i < a.length || j < b.length) {
    if (a[i] === b[j]) { i += 1; j += 1; continue }
    lines.push(`- ${a[i] ?? ''}`)
    lines.push(`+ ${b[j] ?? ''}`)
    i += 1
    j += 1
    if (lines.length > 80) break
  }
  console.log(`--- ${label} (${before.length} -> ${after.length} bytes) ---`)
  console.log(lines.join('\n'))
}

function planApp(source) {
  const ast = parse(source, APP)
  const nl = source.includes('\r\n') ? '\r\n' : '\n'
  const inserts = []
  let lastImport = null
  let baroque = null
  let keepArray = null
  walk(ast, (node) => {
    if (node.type === 'ImportDeclaration') lastImport = node
    if (isRouteTo(node, '/baroque')) baroque = node
    if (node.type === 'VariableDeclarator' && node.id?.name === 'SIMPLE_KEEP_ADVANCED'
        && node.init?.type === 'ArrayExpression') keepArray = node.init
  })
  if (source.includes("from './pages/internal/GalacticDeck.jsx'")) {
    return { inserts: [], already: true }
  }
  if (!lastImport) throw new Error('App.jsx: no import declaration found')
  insert(inserts, lastImport.end,
    `${nl}import GalacticDeck from './pages/internal/GalacticDeck.jsx'`)
  if (!baroque) throw new Error('App.jsx: /baroque route not found')
  insert(inserts, lineStart(source, baroque.start),
    `      <Route path="/galactic" element={<GalacticDeck />} />${nl}`)
  if (!keepArray) throw new Error('App.jsx: SIMPLE_KEEP_ADVANCED array not found')
  const keepClose = lineStart(source, keepArray.end - 1)
  const keepPrior = source.slice(0, keepClose).replace(/\s+$/, '')
  insert(inserts, keepClose,
    `${keepPrior.endsWith(',') ? '' : ','}${nl}  new RegExp("^/galactic(/|$)"),${nl}`)
  if (!keepPrior.endsWith(',')) insert(inserts, keepClose - 1, ',')
  return { inserts }
}

function planNav(source) {
  const ast = parse(source, NAV)
  const nl = source.includes('\r\n') ? '\r\n' : '\n'
  if (source.includes("id: 'galactic-deck'")) return { inserts: [], already: true }
  let systems = null
  walk(ast, (node) => {
    if (node.type === 'VariableDeclarator' && node.id?.name === 'RAW_GROUPS'
        && node.init?.type === 'ArrayExpression') {
      for (const group of node.init.elements) {
        const id = objectProp(group, 'id')
        if (id && id.value?.value === 'systems') systems = group
      }
    }
  })
  if (!systems) throw new Error('nav-config.js: systems group not found')
  const sections = objectProp(systems, 'sections')?.value
  if (!sections || sections.type !== 'ArrayExpression') {
    throw new Error('nav-config.js: systems.sections is not an array')
  }
  const entry = [
    `{`,
    `      id: 'galactic-deck',`,
    `      label: 'Galactic Deck',`,
    `      route: '/galactic',`,
    `      roles: ['operator', 'platform_admin'],`,
    `      status: 'Internal',`,
    `    }`,
  ].join(nl)
  const close = lineStart(source, sections.end - 1)
  const prior = source.slice(0, close).replace(/\s+$/, '')
  const inserts = [{ at: close, text: `${prior.endsWith(',') ? '' : ','}${nl}    ${entry}${nl}` }]
  if (!prior.endsWith(',')) inserts.push({ at: close - 1, text: ',' })
  return { inserts }
}

function main() {
  const apply = process.argv.includes('--apply')
  const files = [
    { path: APP, plan: planApp },
    { path: NAV, plan: planNav },
  ]
  let changed = 0
  for (const file of files) {
    const source = fs.readFileSync(file.path, 'utf8')
    const { inserts, already } = file.plan(source)
    if (already || inserts.length === 0) {
      console.log(`${path.basename(file.path)}: already integrated`)
      continue
    }
    const next = applyInserts(source, inserts, file.path)
    diff(source, next, path.basename(file.path))
    if (apply) {
      fs.writeFileSync(file.path, next, 'utf8')
      console.log(`${path.basename(file.path)}: applied ${inserts.length} AST insertion(s)`)
    }
    changed += 1
  }
  if (!apply) console.log('(check only; pass --apply to write)')
  return changed
}

try {
  main()
} catch (error) {
  console.error(`ast_edit_js: ${error.message}`)
  process.exit(1)
}
