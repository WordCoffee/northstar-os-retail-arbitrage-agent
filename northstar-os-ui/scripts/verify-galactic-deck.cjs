#!/usr/bin/env node
/* Static verification for the Galactic deck: every JSX/JS file parses, the
 * route/nav integration is present, the pure state module exports the expected
 * helpers, and the CSS carries the reduced-motion contract. No browser needed.
 */
const fs = require('fs')
const path = require('path')
const parser = require('@babel/parser')

const ROOT = path.resolve(__dirname, '..')
const files = [
  'src/galactic/CommandDeck.jsx',
  'src/galactic/NodeTopology.jsx',
  'src/galactic/KVCacheHeatmap.jsx',
  'src/galactic/EventStream.jsx',
  'src/galactic/HitlQueue.jsx',
  'src/pages/internal/GalacticDeck.jsx',
  'src/lib/galacticState.js',
  'src/App.jsx',
  'src/data/nav-config.js',
]

let failures = 0
function check(ok, label, detail = '') {
  if (ok) {
    console.log(`PASS  ${label}`)
  } else {
    failures += 1
    console.log(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
  }
}

for (const rel of files) {
  const full = path.join(ROOT, rel)
  if (!fs.existsSync(full)) {
    check(false, `${rel} exists`)
    continue
  }
  try {
    parser.parse(fs.readFileSync(full, 'utf8'), {
      sourceType: 'module',
      plugins: ['jsx', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator'],
      sourceFilename: full,
    })
    check(true, `${rel} parses`)
  } catch (error) {
    check(false, `${rel} parses`, error.message)
  }
}

const app = fs.readFileSync(path.join(ROOT, 'src/App.jsx'), 'utf8')
check(app.includes("import GalacticDeck from './pages/internal/GalacticDeck.jsx'"),
  'App.jsx imports the deck')
check(app.includes('path="/galactic"'), 'App.jsx routes /galactic')
check(app.includes('new RegExp("^/galactic(/|$)")'),
  'App.jsx keeps the deck advanced in Simple mode')

const nav = fs.readFileSync(path.join(ROOT, 'src/data/nav-config.js'), 'utf8')
check(nav.includes("id: 'galactic-deck'"), 'nav-config exposes Galactic Deck')
check(nav.includes("route: '/galactic'"), 'nav-config points at /galactic')

const state = fs.readFileSync(path.join(ROOT, 'src/lib/galacticState.js'), 'utf8')
for (const symbol of ['createEventBus', 'layoutTopology', 'heatmapCells', 'pulseFor', 'summarizeEvents']) {
  check(state.includes(`export function ${symbol}`) || state.includes(`export const ${symbol}`),
    `galacticState exports ${symbol}`)
}
check(!state.includes('fetch('), 'galacticState stays pure (no fetch)')

const css = fs.readFileSync(path.join(ROOT, 'src/galactic/galactic.css'), 'utf8')
for (const selector of ['.gx-topology', '.gx-heatmap', '.gx-events', '.gx-node', '.gx-cell', '.gx-hitl']) {
  check(css.includes(selector), `CSS defines ${selector}`)
}
check(css.includes('prefers-reduced-motion: reduce'), 'CSS honours reduced motion')
check(css.includes('grid-template-areas'), 'CSS has the command-deck grid')

const deck = fs.readFileSync(path.join(ROOT, 'src/galactic/CommandDeck.jsx'), 'utf8')
check(deck.includes('/api/v1/galactic/state'), 'deck polls the galactic state endpoint')
check(deck.includes('/api/v1/galactic/events'), 'deck targets the SSE endpoint')
check(deck.includes('new EventSource'), 'deck subscribes to the SSE stream')
check(deck.includes("stream === 'open'"), 'deck falls back to polling when SSE is down')
check(deck.includes('createEventBus()'), 'deck owns a unified event bus')

const hitl = fs.readFileSync(path.join(ROOT, 'src/galactic/HitlQueue.jsx'), 'utf8')
check(hitl.includes('/api/v1/hitl/pending'), 'HITL panel reads the pending queue')
check(hitl.includes("`/api/v1/hitl/${encodeURIComponent(request.id)}/${action}`"),
  'HITL panel posts approve/deny')
check(hitl.includes('hitl.${action}'), 'HITL decisions publish to the event bus')

console.log(failures === 0
  ? 'GALACTIC DECK VERIFIER: all checks pass'
  : `GALACTIC DECK VERIFIER: ${failures} failure(s)`)
process.exit(failures === 0 ? 0 : 1)
