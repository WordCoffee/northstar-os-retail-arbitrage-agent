/**
 * Markdown subset (work order UI-20, item 16).
 *
 * Deliberately NOT a general Markdown implementation and deliberately not a
 * dependency: the editor needs a safe subset it fully controls. Raw HTML is
 * never passed through - `<script>` is text, not a tag - and only http(s),
 * mailto and relative links survive, so `javascript:` cannot be smuggled in.
 *
 * Two pure functions, both tested:
 *   parseBlocks(src)  -> block list
 *   parseInline(text) -> inline token list
 */

const SAFE_HREF = /^(https?:\/\/|mailto:|\/|\.\/|#)/i

export function parseInline(text) {
  const src = String(text ?? '')
  const tokens = []
  let buffer = ''

  const flush = () => {
    if (buffer) { tokens.push({ type: 'text', value: buffer }); buffer = '' }
  }

  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i]

    if (ch === '`') {
      const end = src.indexOf('`', i + 1)
      if (end > i) { flush(); tokens.push({ type: 'code', value: src.slice(i + 1, end) }); i = end; continue }
    }

    if (ch === '*' && src[i + 1] === '*') {
      const end = src.indexOf('**', i + 2)
      if (end > i + 1) { flush(); tokens.push({ type: 'strong', value: src.slice(i + 2, end) }); i = end + 1; continue }
    }

    if (ch === '*' || ch === '_') {
      const marker = ch
      const end = src.indexOf(marker, i + 1)
      if (end > i + 1) { flush(); tokens.push({ type: 'em', value: src.slice(i + 1, end) }); i = end; continue }
    }

    if (ch === '[') {
      const close = src.indexOf(']', i + 1)
      const open = close >= 0 ? src.indexOf('(', close) : -1
      const end = open === close + 1 ? src.indexOf(')', open) : -1
      if (close > i && end > open) {
        const label = src.slice(i + 1, close)
        const href = src.slice(open + 1, end).trim()
        flush()
        if (SAFE_HREF.test(href)) tokens.push({ type: 'link', value: label, href })
        else tokens.push({ type: 'text', value: label })   // unsafe scheme: keep the words, drop the link
        i = end
        continue
      }
    }

    buffer += ch
  }

  flush()
  return tokens
}

export function parseBlocks(source) {
  const lines = String(source ?? '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let paragraph = []
  let fence = null

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: 'p', text: paragraph.join(' ').trim() })
      paragraph = []
    }
  }

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')

    if (fence) {
      if (/^```/.test(line)) { blocks.push({ type: 'code', lang: fence.lang, text: fence.lines.join('\n') }); fence = null }
      else fence.lines.push(raw)
      continue
    }

    if (/^```/.test(line)) { flushParagraph(); fence = { lang: line.slice(3).trim(), lines: [] }; continue }

    if (!line.trim()) { flushParagraph(); continue }

    if (/^(---|\*\*\*|___)\s*$/.test(line)) { flushParagraph(); blocks.push({ type: 'hr' }); continue }

    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) { flushParagraph(); blocks.push({ type: 'h', level: heading[1].length, text: heading[2].trim() }); continue }

    const quote = line.match(/^>\s?(.*)$/)
    if (quote) { flushParagraph(); blocks.push({ type: 'quote', text: quote[1] }); continue }

    const bullet = line.match(/^\s*[-*+]\s+(.*)$/)
    const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (bullet || ordered) {
      flushParagraph()
      const isOrdered = Boolean(ordered)
      const text = (bullet || ordered)[1]
      const last = blocks[blocks.length - 1]
      if (last && last.type === 'list' && last.ordered === isOrdered) last.items.push(text)
      else blocks.push({ type: 'list', ordered: isOrdered, items: [text] })
      continue
    }

    paragraph.push(line.trim())
  }

  if (fence) blocks.push({ type: 'code', lang: fence.lang, text: fence.lines.join('\n') })
  flushParagraph()
  return blocks
}

export default { parseBlocks, parseInline }
