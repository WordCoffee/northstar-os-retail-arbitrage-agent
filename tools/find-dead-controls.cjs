// Find buttons that do nothing.
//
// "Dead" = a <button> that is clickable (not disabled, no aria-disabled, not
// inside an intentionally-non-activating AuthorizationNote) but has no onClick
// handler at all. React attaches handlers through its synthetic event system,
// so the reliable signal is the absence of any onClick prop AND the absence of
// a wrapping form submit context.
//
// Also reports buttons whose only handler is a toast, which the audit calls
// "toast-only" — the control looks functional and does nothing.

const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'northstar-os-ui', 'src')

let dead = []
let toastOnly = []
let scanned = 0

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) { walk(full); continue }
    if (!/\.(jsx|tsx)$/.test(entry.name)) continue
    scanned++

    const rel = path.relative(SRC, full).replace(/\\/g, '/')
    const src = fs.readFileSync(full, 'utf8')
    const lines = src.split('\n')

    // Find every <button ...> opening tag (single-line and multi-line).
    const openTag = /<button\b([\s\S]*?)>/g
    let m
    while ((m = openTag.exec(src)) !== null) {
      const attrs = m[1]
      // Skip buttons that are deliberately inert.
      if (/\bdisabled\b/.test(attrs)) continue
      if (/aria-disabled=\{(?:true|'true'|"true")\}/.test(attrs)) continue
      // Skip buttons rendered inside an AuthorizationNote (documented as
      // non-activating by design).
      const before = src.slice(0, m.index)
      if (/AuthorizationNote[\s\S]{0,4000}$/.test(before.slice(-4000)) &&
          /status=/.test(before.slice(-1200))) {
        // heuristic only; still record below if clearly inert
      }
      const hasOnClick = /\bonClick=/.test(attrs)
      if (hasOnClick) {
        // Is the handler just a toast? Handles `() => t(...)`,
        // `() => toast(...)`, and `(e) => t(...)`.
        const handler = /\bonClick=\{([\s\S]*?)\}\s*$/m.exec(attrs + '\n')
        const body = handler ? handler[1].trim() : ''
        const toastPattern = /^\(?(?:\w+)?\)?\s*=>\s*(?:t|toast)\(\s*['"`]/
        if (body && toastPattern.test(body)) {
          const lineNo = src.slice(0, m.index).split('\n').length
          const tagEnd = src.indexOf('>', m.index)
          const label = src.slice(tagEnd + 1).split('<')[0].trim().replace(/\s+/g, ' ')
          toastOnly.push({ file: rel, line: lineNo, label: label.slice(0, 60) || '(icon only)' })
        }
        continue
      }
      // No onClick. Report it unless it is type="submit" inside a form.
      if (/\btype="submit"/.test(attrs)) continue
      const lineNo = src.slice(0, m.index).split('\n').length
      const tagEnd = src.indexOf('>', m.index)
      const label = src.slice(tagEnd + 1).split('<')[0].trim().replace(/\s+/g, ' ')
      const inForm = /<form[\s\S]{0,2000}$/.test(src.slice(0, m.index).slice(-2000))
      dead.push({ file: rel, line: lineNo, label: label.slice(0, 60) || '(icon only)', inForm })
    }
  }
}

walk(SRC)

console.log(`scanned ${scanned} source files`)
console.log(`\nDEAD (no handler at all): ${dead.length}`)
for (const d of dead) {
  console.log(`  ${d.file}:${d.line}  "${d.label}"${d.inForm ? '  (inside a form)' : ''}`)
}
console.log(`\nTOAST-ONLY (looks functional, does nothing): ${toastOnly.length}`)
for (const t of toastOnly) {
  console.log(`  ${t.file}:${t.line}  "${t.label}"`)
}
process.exit(dead.length + toastOnly.length ? 1 : 0)
