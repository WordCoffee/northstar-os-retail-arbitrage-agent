import { useCallback, useEffect, useRef, useState } from 'react'
import { parse, serialize, withDefaults, WORKSPACE_TTL_MS } from '../lib/workspaceState.js'

/**
 * Survive a reload (item 20).
 *
 * Restores an allowlisted slice of UI state, then checkpoints it on a debounce.
 * Writes are skipped while the tab is hidden (mobile browsers throttle them and
 * a write during unload is unreliable), and one final write happens on
 * visibilitychange -> hidden and on pagehide, which is what actually fires.
 */
export function useWorkspaceState(storageKey, defaults, { debounceMs = 250, ttlMs = WORKSPACE_TTL_MS } = {}) {
  const keys = Object.keys(defaults)
  const [state, setState] = useState(() => {
    try {
      return withDefaults(defaults, parse(localStorage.getItem(storageKey), { keys, ttlMs }))
    } catch {
      return { ...defaults }
    }
  })

  const timer = useRef(null)
  const latest = useRef(state)
  latest.current = state

  const write = useCallback(() => {
    try {
      localStorage.setItem(storageKey, serialize(latest.current, { keys }))
    } catch { /* quota or private mode: the UI keeps working, it just will not restore */ }
  }, [storageKey, keys.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(write, debounceMs)
    return () => clearTimeout(timer.current)
  }, [state, write, debounceMs])

  useEffect(() => {
    const onHide = () => { if (document.visibilityState === 'hidden') write() }
    window.addEventListener('pagehide', write)
    document.addEventListener('visibilitychange', onHide)
    return () => {
      window.removeEventListener('pagehide', write)
      document.removeEventListener('visibilitychange', onHide)
    }
  }, [write])

  const patch = useCallback((next) => {
    setState((prev) => (typeof next === 'function' ? next(prev) : { ...prev, ...next }))
  }, [])

  const reset = useCallback(() => setState({ ...defaults }), []) // eslint-disable-line react-hooks/exhaustive-deps

  return [state, patch, reset]
}

export default useWorkspaceState
