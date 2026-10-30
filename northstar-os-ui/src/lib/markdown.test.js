import test from 'node:test'
import assert from 'node:assert/strict'
import { parseBlocks, parseInline } from './markdown.js'

test('headings carry their level', () => {
  const b = parseBlocks('# One\n### Three')
  assert.equal(b[0].type, 'h')
  assert.equal(b[0].level, 1)
  assert.equal(b[1].level, 3)
})

test('paragraphs join soft-wrapped lines and split on a blank line', () => {
  const b = parseBlocks('first line\nsecond line\n\nnext para')
  assert.deepEqual(b[0], { type: 'p', text: 'first line second line' })
  assert.deepEqual(b[1], { type: 'p', text: 'next para' })
})

test('fenced code keeps its body verbatim and its language', () => {
  const b = parseBlocks('```ts\nconst a = 1\n  const b = 2\n```')
  assert.equal(b.length, 1)
  assert.equal(b[0].type, 'code')
  assert.equal(b[0].lang, 'ts')
  assert.equal(b[0].text, 'const a = 1\n  const b = 2')
})

test('an unterminated fence still renders as code', () => {
  const b = parseBlocks('```\nlet x = 1')
  assert.equal(b[0].type, 'code')
  assert.equal(b[0].text, 'let x = 1')
})

test('consecutive bullets group, ordered and unordered do not mix', () => {
  const b = parseBlocks('- a\n- b\n1. one\n2. two')
  assert.equal(b.length, 2)
  assert.deepEqual(b[0], { type: 'list', ordered: false, items: ['a', 'b'] })
  assert.deepEqual(b[1], { type: 'list', ordered: true, items: ['one', 'two'] })
})

test('quotes, rules and mixed blocks', () => {
  const b = parseBlocks('> quoted\n---\nafter')
  assert.equal(b[0].type, 'quote')
  assert.equal(b[1].type, 'hr')
  assert.equal(b[2].type, 'p')
})

test('inline: code, bold, italic', () => {
  const t = parseInline('a `x` b **c** d *e*')
  assert.deepEqual(t.map((x) => x.type), ['text', 'code', 'text', 'strong', 'text', 'em'])
  assert.equal(t[1].value, 'x')
  assert.equal(t[3].value, 'c')
  assert.equal(t[5].value, 'e')
})

test('inline: safe links become links, unsafe schemes keep only the label', () => {
  const safe = parseInline('[docs](https://example.com/x)')
  assert.equal(safe[0].type, 'link')
  assert.equal(safe[0].href, 'https://example.com/x')

  const js = parseInline('[click](javascript:alert(1))')
  assert.equal(js[0].type, 'text')
  assert.equal(js[0].value, 'click')
})

test('raw html is text, never a tag', () => {
  const t = parseInline('<script>alert(1)</script>')
  assert.equal(t.every((x) => x.type === 'text'), true)
  const blocks = parseBlocks('<img src=x onerror=alert(1)>')
  assert.equal(blocks[0].type, 'p')
  assert.match(blocks[0].text, /<img/)
})

test('empty input produces no blocks', () => {
  assert.deepEqual(parseBlocks(''), [])
  assert.deepEqual(parseBlocks(null), [])
})
