// U9 — the PPC report reader. A wrong parse becomes a wrong bid, so the parser
// refuses a table it cannot read exactly instead of repairing it.

import test from 'node:test'
import assert from 'node:assert/strict'

import { splitLine, parseCsv, normaliseHeader, MAX_BYTES } from './ppcCsv.js'

const HEADER = 'Campaign,Ad Group,Customer Search Term,Impressions,Clicks,Spend,Sales,Orders'
const ROW = 'Lions Mane,Broad,lions mane powder,1200,24,12.00,60.00,2'

test('quoted fields, escaped quotes and commas inside a field survive', () => {
  assert.deepEqual(splitLine('a,b,c'), ['a', 'b', 'c'])
  assert.deepEqual(splitLine('"a,b",c'), ['a,b', 'c'])
  assert.deepEqual(splitLine('"he said ""hi""",x'), ['he said "hi"', 'x'])
  assert.deepEqual(splitLine(''), [''])
})

test('headers are normalised the way the specialist matches them', () => {
  assert.equal(normaliseHeader('\uFEFFCampaign'), 'campaign')
  assert.equal(normaliseHeader('  Customer Search Term '), 'customer search term')
})

test('a real report parses to rows keyed by header', () => {
  const out = parseCsv(`${HEADER}\r\n${ROW}\r\n`)
  assert.equal(out.ok, true)
  assert.deepEqual(out.headers, [
    'campaign', 'ad group', 'customer search term', 'impressions', 'clicks', 'spend', 'sales', 'orders',
  ])
  assert.equal(out.rows.length, 1)
  assert.equal(out.rows[0]['customer search term'], 'lions mane powder')
  assert.equal(out.rows[0].orders, '2')
})

test('a UTF-8 BOM and blank lines do not shift the table', () => {
  const out = parseCsv(`\uFEFF${HEADER}\n\n${ROW}\n\n`)
  assert.equal(out.ok, true)
  assert.equal(out.rows.length, 1)
  assert.equal(out.headers[0], 'campaign')
})

test('an unreadable file is refused with the reason, never half-parsed', () => {
  assert.equal(parseCsv('').ok, false)
  assert.equal(parseCsv(`${HEADER}\n`).ok, false, 'a header with no rows')
  assert.match(parseCsv(`${HEADER}\nLions Mane,Broad`).error, /has 2 column/)

  const repeated = parseCsv('Campaign,Campaign\nx,y')
  assert.equal(repeated.ok, false)
  assert.match(repeated.error, /repeats the column/)

  const emptyHeader = parseCsv('Campaign,,Clicks\nx,y,z')
  assert.equal(emptyHeader.ok, false)
  assert.match(emptyHeader.error, /empty column/)
})

test('the size ceiling is a real number the caller can state', () => {
  assert.equal(MAX_BYTES, 8 * 1024 * 1024)
})
