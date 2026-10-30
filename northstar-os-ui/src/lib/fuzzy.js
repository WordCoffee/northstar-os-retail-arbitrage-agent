/**
 * Fuzzy scoring for the command palette (work order UI-20, item 17).
 *
 * Pure and dependency-free so it can be unit-tested with `node --test` and
 * reused by any surface.
 *
 * A match must be a subsequence. Beyond that the score is:
 *
 *   base        10
 *   boundary    +8   match starts a word (start, space, -, _, /, .)
 *   consecutive +5   directly follows the previous match
 *   exact case  +2   a typed capital is a real signal
 *   gap         -1   per skipped character, capped at -6
 *   length      -0.02 per character the target is longer than the query
 *
 * and then multiplied by DENSITY (query length / span). Density is what makes
 * "Billing" beat "Bedrock illustration lane" for `bill`: both are subsequences
 * with boundary hits, but one covers 4 of 4 characters and the other 4 of 11.
 * Without it, a boundary bonus alone promotes scattered junk.
 *
 * A query that is not a subsequence scores null, never 0 - callers must be able
 * to tell "no match" from "weak match".
 */

const BOUNDARY = /[\s\-_/.]/

export function score(query, text) {
  if (typeof query !== 'string' || typeof text !== 'string') return null
  const q = query.trim()
  if (!q) return 0
  const lowerQ = q.toLowerCase()
  const lower = text.toLowerCase()

  let qi = 0
  let lastIndex = -1
  let boundaries = 0
  let consecutive = 0
  let caseHits = 0
  let gaps = 0
  let firstIndex = -1

  for (let i = 0; i < text.length && qi < lowerQ.length; i += 1) {
    if (lower[i] !== lowerQ[qi]) continue
    if (i === 0 || BOUNDARY.test(text[i - 1])) boundaries += 1
    if (lastIndex === i - 1) consecutive += 1
    if (text[i] === q[qi]) caseHits += 1
    if (lastIndex >= 0) gaps += i - lastIndex - 1
    if (firstIndex < 0) firstIndex = i
    lastIndex = i
    qi += 1
  }

  if (qi < lowerQ.length) return null

  const span = lastIndex - firstIndex + 1
  const density = q.length / span
  const base = 10 + boundaries * 8 + consecutive * 5 + caseHits * 2 - Math.min(gaps, 6)
  const lengthPenalty = Math.max(0, text.length - q.length) * 0.02
  return Math.max(0.01, base * density - lengthPenalty)
}

/**
 * Rank a list. `key` may be a string field name or a function.
 * Ties break on the original order, so the list never reshuffles between keys.
 */
export function rank(query, items, key = 'label') {
  const get = typeof key === 'function' ? key : (item) => String(item?.[key] ?? '')
  const scored = []
  items.forEach((item, i) => {
    const s = score(query, get(item))
    if (s !== null) scored.push({ item, score: s, i })
  })
  scored.sort((a, b) => (b.score - a.score) || (a.i - b.i))
  return scored.map((entry) => entry.item)
}

export default { score, rank }
