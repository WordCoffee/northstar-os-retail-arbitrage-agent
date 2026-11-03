// U9 — the PPC report reader, in the browser.
//
// The operator's file never leaves the machine as a FILE: the page parses it to
// rows and posts the rows. That keeps the upload honest (nothing is stored) and
// keeps the analysis in the Python specialist, where the thresholds and the
// validator already live.
//
// The parser is deliberately small and strict: quoted fields, escaped quotes,
// CRLF, a UTF-8 BOM and blank lines. It does not guess a delimiter and it does
// not repair a broken row — a wrong parse would become a wrong bid.

export const MAX_BYTES = 8 * 1024 * 1024

/** Split one CSV line into fields, honouring double quotes. */
export function splitLine(line) {
  const out = []
  let field = ''
  let quoted = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') { field += '"'; i += 1 } else quoted = false
      } else field += ch
    } else if (ch === '"') quoted = true
    else if (ch === ',') { out.push(field); field = '' }
    else field += ch
  }
  out.push(field)
  return out
}

/** Header cells become the loose keys the specialist matches (lowercase, trimmed). */
export function normaliseHeader(cell) {
  return String(cell || '').replace(/^\uFEFF/, '').trim().toLowerCase()
}

/**
 * Parse a report into rows keyed by header. Returns `{ok, rows, headers}` or
 * `{ok:false, error}` — never a half-parsed table.
 */
export function parseCsv(text) {
  const raw = String(text || '').replace(/^\uFEFF/, '')
  if (!raw.trim()) return { ok: false, error: 'the file is empty' }
  const lines = raw.split(/\r\n|\n|\r/).filter((l) => l.trim() !== '')
  if (lines.length < 2) return { ok: false, error: 'the file has a header but no rows' }

  const headers = splitLine(lines[0]).map(normaliseHeader)
  const seen = new Set()
  for (const h of headers) {
    if (!h) return { ok: false, error: 'the header row has an empty column name' }
    if (seen.has(h)) return { ok: false, error: `the header repeats the column "${h}"` }
    seen.add(h)
  }

  const rows = []
  for (let i = 1; i < lines.length; i += 1) {
    const cells = splitLine(lines[i])
    if (cells.length !== headers.length) {
      return { ok: false, error: `line ${i + 1} has ${cells.length} column(s); the header has ${headers.length}` }
    }
    const row = {}
    headers.forEach((h, idx) => { row[h] = cells[idx] })
    rows.push(row)
  }
  return { ok: true, rows, headers }
}

/** Read a File into rows without ever posting the file itself. */
export async function readReport(file) {
  if (!file) return { ok: false, error: 'no file was chosen' }
  if (file.size > MAX_BYTES) return { ok: false, error: 'that file is larger than 8 MB' }
  const text = await file.text()
  return parseCsv(text)
}
