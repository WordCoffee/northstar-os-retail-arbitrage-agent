// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — LOCAL ROOM STORE
//
// Each room owns an isolated localStorage slice (`ns-studio-*`). Records the
// operator creates here are real local records — they are not provider output
// and are never presented as such. Keys are namespaced so two rooms can never
// read one another's state.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useState } from 'react'

const PREFIX = 'ns-studio-'

export function readRoom(key, seed) {
  try {
    const raw = localStorage.getItem(PREFIX + key)
    if (!raw) return seed
    const parsed = JSON.parse(raw)
    return parsed === null || parsed === undefined ? seed : parsed
  } catch {
    return seed
  }
}

export function writeRoom(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export function useRoom(key, seed) {
  const [value, setValue] = useState(() => readRoom(key, seed))
  useEffect(() => { writeRoom(key, value) }, [key, value])
  return [value, setValue]
}

let n = 0
export function uid(prefix = 'ID') {
  n += 1
  return `${prefix}-${Math.random().toString(36).slice(2, 6).toUpperCase()}${n.toString(36).toUpperCase()}`
}

export const nowIso = () => new Date().toISOString()

export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function fmtBytes(b) {
  if (!b && b !== 0) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

/** Stable hash for a doc — used for "unsaved changes" detection. */
export function hashDoc(doc) {
  const s = JSON.stringify(doc)
  let h = 5381
  for (let i = 0; i < s.length; i += 1) h = ((h << 5) + h + s.charCodeAt(i)) | 0
  return (h >>> 0).toString(36)
}

export function useToggle(initial = false) {
  const [on, setOn] = useState(initial)
  const toggle = useCallback(() => setOn(v => !v), [])
  return [on, toggle, setOn]
}

export function useStickyCallback(fn) {
  const ref = useCallback(fn, [fn])
  return ref
}
