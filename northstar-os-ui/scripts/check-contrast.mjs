#!/usr/bin/env node
/**
 * Contrast guardrail (work order UI-20, item 13).
 *
 * Reads the real token values out of src/styles/tokens.css and asserts WCAG 2.1
 * contrast on the pairs that actually carry text. This is a TEST, not a doc: it
 * exits non-zero and names the pair, the ratio and the required ratio.
 *
 *   node scripts/check-contrast.mjs          # assert
 *   node scripts/check-contrast.mjs --all    # also print advisory pairs
 *
 * Why parse the CSS: a hard-coded copy of the palette drifts the moment someone
 * changes a token. The guardrail has to read the same file the browser does.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const css = readFileSync(resolve(here, '../src/styles/tokens.css'), 'utf8')

/** Pull `--name: value;` out of a selector block. */
function tokensIn(selector) {
  const start = css.indexOf(selector)
  if (start < 0) return {}
  const open = css.indexOf('{', start)
  const close = css.indexOf('}', open)
  const body = css.slice(open + 1, close)
  const out = {}
  for (const m of body.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

const root = tokensIn(':root {')

function hex(v) {
  if (!v) return null
  const s = v.trim()
  if (s.startsWith('#')) {
    let h = s.slice(1)
    if (h.length === 3) h = h.split('').map(c => c + c).join('')
    const n = parseInt(h.slice(0, 6), 16)
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 }
  }
  const m = s.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)/)
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }
  return null
}

/** Composite a possibly-translucent colour over an opaque backdrop. */
function over(fg, bg) {
  const a = fg.a ?? 1
  return {
    r: Math.round(fg.r * a + bg.r * (1 - a)),
    g: Math.round(fg.g * a + bg.g * (1 - a)),
    b: Math.round(fg.b * a + bg.b * (1 - a)),
    a: 1,
  }
}

function lum(c) {
  const ch = v => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b)
}

function ratio(fg, bg) {
  const a = lum(fg) + 0.05
  const b = lum(bg) + 0.05
  return a > b ? a / b : b / a
}

// Every pair here carries real text on a real surface.
//   aa  4.5 - body copy
//   lg  3.0 - large text (>=24px, or >=18.66px bold) and UI glyphs
const PAIRS = [
  ['--ink', '--paper', 'aa', 'body copy on paper'],
  ['--ink-mid', '--paper', 'aa', 'paragraph on paper'],
  ['--ink-soft', '--paper', 'aa', 'low-emphasis label on paper'],
  ['--pine-deep', '--paper', 'lg', 'h1/h2 on paper'],
  ['--pine', '--surface', 'aa', 'link/heading on a card'],
  ['--ink', '--surface', 'aa', 'body copy on a card'],
  ['--ink-mid', '--surface', 'aa', 'paragraph on a card'],
  ['--status-ok', '--paper', 'aa', 'success text'],
  ['--status-warn', '--paper', 'aa', 'warning text'],
  ['--status-error', '--paper', 'aa', 'error text'],
]

// Button label: white on --forest. Checked separately because #fff is literal.
const LITERAL = [['#ffffff', '--forest', 'aa', 'primary button label']]

const ADVISORY = [
  ['--ink-faint', '--paper', 'placeholder text (exempt as non-essential, but reported)'],
]

const failures = []
const report = []

function check(name, fgTok, bgTok, level, note, bucket) {
  const rawFg = fgTok.startsWith('#') ? fgTok : root[fgTok.replace(/^--/, '')]
  const rawBg = root[bgTok.replace(/^--/, '')]
  const fg = hex(rawFg)
  const bg = hex(rawBg)
  if (!fg || !bg) {
    failures.push(`${name}: could not resolve ${fgTok} (${rawFg}) or ${bgTok} (${rawBg})`)
    return
  }
  const solid = fg.a < 1 ? over(fg, bg) : fg
  const r = ratio(solid, bg)
  const need = level === 'aa' ? 4.5 : 3.0
  const line = `${bucket === 'advisory' ? 'ADVISORY' : r >= need ? 'PASS    ' : 'FAIL    '} ` +
    `${String(r.toFixed(2)).padStart(5)}:1  (need ${need})  ${note}`
  report.push(line)
  if (r < need && bucket !== 'advisory') {
    failures.push(`${note}: ${r.toFixed(2)}:1 < ${need}:1 (${fgTok} on ${bgTok})`)
  }
}

for (const [f, b, lvl, note] of PAIRS) check(note, f, b, lvl, note)
for (const [f, b, lvl, note] of LITERAL) check(note, f, b, lvl, note)
for (const [f, b, note] of ADVISORY) check(note, f, b, 'aa', note, 'advisory')

const showAll = process.argv.includes('--all')
const lines = showAll ? report : report.filter(l => !l.startsWith('ADVISORY'))
console.log(lines.join('\n'))

if (failures.length) {
  console.error(`\nCONTRAST GUARDRAIL: ${failures.length} failure(s)`)
  for (const f of failures) console.error('  - ' + f)
  process.exit(1)
}
console.log(`\nCONTRAST GUARDRAIL: ${PAIRS.length + LITERAL.length} pairs pass WCAG AA`)
