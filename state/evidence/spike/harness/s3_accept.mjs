#!/usr/bin/env node
/**
 * S3 gate: every text-bearing colour the /ui/documents page renders must clear
 * WCAG 2.1 AA against the background it actually sits on.
 *
 * Run from the worktree root:  node .spike_acceptance/s3_accept.mjs
 *
 * Independent of the repository's own check-contrast.mjs (a candidate can edit
 * that script; it cannot edit this one). It reads the same two stylesheets the
 * browser loads, in import order (tokens.css then app.css), resolves var(--x)
 * and the cascade for each selector, composites translucent backgrounds over
 * their parent surface, and exits non-zero naming each pair that fails.
 *
 * Why these pairs: they are exactly the classes Documents.jsx renders -
 * PageLayout's .page-title/.page-subtitle, .card-title, the 13px body <p>, the
 * .text-low label, and the pill variants its states can show.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const files = [
  resolve('northstar-os-ui/src/styles/tokens.css'),
  resolve('northstar-os-ui/src/styles/app.css'),
]

const sheets = files.map((f) => ({ file: f, css: readFileSync(f, 'utf8') }))

/** Every `selector { body }` block, in load order. */
function blocks() {
  const out = []
  for (const { file, css } of sheets) {
    const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
    for (const m of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selectors = m[1].split(',').map((s) => s.trim()).filter(Boolean)
      out.push({ selectors, body: m[2], file })
    }
  }
  return out
}

const ALL = blocks()

/** Declarations that apply to an exact simple selector, last one wins. */
function declsFor(selector) {
  const merged = {}
  for (const block of ALL) {
    if (!block.selectors.includes(selector)) continue
    for (const m of block.body.matchAll(/([a-z-]+)\s*:\s*([^;]+);/g)) {
      merged[m[1]] = m[2].trim()
    }
  }
  return merged
}

/** Resolve var(--x) against :root, repeatedly (tokens may reference tokens). */
function resolveValue(value, depth = 0) {
  if (!value || depth > 8) return value
  const m = String(value).match(/var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)/)
  if (!m) return value
  const token = declsFor(':root')[m[1]] ?? m[2]
  return resolveValue(String(value).replace(m[0], token ?? ''), depth + 1)
}

function parseColour(value) {
  const v = resolveValue(value)
  if (!v) return null
  const s = v.trim()
  if (s.startsWith('#')) {
    let h = s.slice(1)
    if (h.length === 3) h = h.split('').map((c) => c + c).join('')
    const n = parseInt(h.slice(0, 6), 16)
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 }
  }
  const m = s.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)/)
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }
  return null
}

const over = (fg, bg) => {
  const a = fg.a ?? 1
  return {
    r: Math.round(fg.r * a + bg.r * (1 - a)),
    g: Math.round(fg.g * a + bg.g * (1 - a)),
    b: Math.round(fg.b * a + bg.b * (1 - a)),
    a: 1,
  }
}

const lum = (c) => {
  const ch = (v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b)
}

const ratio = (a, b) => {
  const x = lum(a) + 0.05
  const y = lum(b) + 0.05
  return x > y ? x / y : y / x
}

// selector, text selector (defaults to selector), parent surface token,
// minimum ratio, description
const PAIRS = [
  ['.page-title', '.page-title', '--paper', 3.0, 'documents h1 on paper'],
  ['.page-subtitle', '.page-subtitle', '--paper', 4.5, 'documents subtitle on paper'],
  ['.card-title', '.card-title', '--surface', 4.5, 'card heading on a card'],
  ['p', 'p', '--surface', 4.5, 'documents body copy on a card'],
  ['.text-low', '.text-low', '--surface', 4.5, 'low-emphasis label on a card'],
  ['.pill-forest', '.pill-forest', '--surface', 4.5, 'pill text (live) on a card'],
  ['.pill-ok', '.pill-ok', '--surface', 4.5, 'pill text (accepted) on a card'],
  ['.pill-ochre', '.pill-ochre', '--surface', 4.5, 'pill text (action required) on a card'],
  ['.pill-muted', '.pill-muted', '--surface', 4.5, 'pill text (muted) on a card'],
  ['.pill-unknown', '.pill-unknown', '--surface', 4.5, 'pill text (unknown) on a card'],
  ['.pill-warn', '.pill-warn', '--surface', 4.5, 'pill text (warn) on a card'],
]

const rows = []
const failures = []
for (const [selector, textSelector, parentToken, need, label] of PAIRS) {
  const decl = declsFor(selector)
  const fg = parseColour(decl.color)
  const parent = parseColour(declsFor(':root')[parentToken])
  const ownBg = decl.background || decl['background-color']
  let bg = parent
  if (ownBg) {
    const parsed = parseColour(ownBg)
    if (parsed && parent) bg = over(parsed, parent)
    else if (parsed) bg = parsed
  }
  const row = { label, selector: textSelector, need, color: decl.color ?? null,
                background: ownBg ?? parentToken }
  if (!fg || !bg) {
    row.contrast = null
    row.verdict = 'UNMEASURABLE'
    failures.push(`${label}: colour unreadable (${decl.color} / ${ownBg ?? parentToken})`)
  } else {
    const r = ratio(fg, bg)
    row.contrast = Math.round(r * 100) / 100
    row.verdict = r >= need ? 'PASS' : 'FAIL'
    if (r < need) failures.push(`${label}: ${r.toFixed(2)}:1, need ${need}:1`)
  }
  rows.push(row)
}

for (const row of rows) {
  const pad = row.verdict === 'PASS' ? '  ' : '!!'
  console.log(`${pad}${row.verdict.padEnd(6)} ${String(row.contrast ?? '-').padStart(6)} ` +
              `(need ${row.need})  ${row.label}`)
}

const payload = { gate: 'S3', pairs: PAIRS.length,
                  passed: rows.filter((r) => r.verdict === 'PASS').length,
                  failed: failures.length, ok: failures.length === 0,
                  failures, rows }
console.log(JSON.stringify(payload, null, 2))
process.exit(payload.ok ? 0 : 1)
