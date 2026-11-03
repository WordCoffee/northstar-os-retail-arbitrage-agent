// Workspace tabs — which services are open, which is active, and what Bojo can
// see about it.
//
// Tabs are kept mounted by the shell (hidden, not unmounted) so a half-finished
// design survives a flip to another service. The list itself is persisted in
// sessionStorage, wrapped in try/catch, and a corrupt or empty value degrades to
// a single default tab rather than an empty shell.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { getService } from '../data/serviceRegistry.js'

export const TABS_KEY = 'ns-ux-tabs'
export const DEFAULT_SERVICE = 'design-studio'

function readStored() {
  try {
    const raw = sessionStorage.getItem(TABS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || !Array.isArray(parsed.open)) return null
    const open = parsed.open
      .map((id) => String(id))
      .filter((id, i, all) => getService(id) && all.indexOf(id) === i)
    if (!open.length) return null
    const active = open.includes(parsed.active) ? parsed.active : open[0]
    return { open, active }
  } catch {
    return null
  }
}

function defaultState() {
  return { open: [DEFAULT_SERVICE], active: DEFAULT_SERVICE }
}

const WorkspaceContext = createContext(null)

export function WorkspaceProvider({ children, initialState = null }) {
  const [state, setState] = useState(() => initialState || readStored() || defaultState())
  // U8: what the open workspace tells Bojo, and the single entry point a turn
  // may use to act on it. The workspace owns both; the shell only relays them.
  const [canvas, setCanvas] = useState(null)
  const commandRef = useRef(null)

  useEffect(() => {
    try {
      sessionStorage.setItem(TABS_KEY, JSON.stringify(state))
    } catch { /* storage unavailable */ }
  }, [state])

  const open = useCallback((serviceId, options = {}) => {
    if (!getService(serviceId)) return
    setState((prev) => {
      const already = prev.open.includes(serviceId)
      if (options.replace) {
        return { open: [serviceId], active: serviceId }
      }
      return already
        ? { ...prev, active: serviceId }
        : { open: [...prev.open, serviceId], active: serviceId }
    })
  }, [])

  const activate = useCallback((serviceId) => {
    setState((prev) => (prev.open.includes(serviceId) ? { ...prev, active: serviceId } : prev))
  }, [])

  const close = useCallback((serviceId) => {
    setState((prev) => {
      const open = prev.open.filter((id) => id !== serviceId)
      if (!open.length) return defaultState()   // never leave the shell empty
      const active = prev.active === serviceId
        ? open[Math.max(0, prev.open.indexOf(serviceId) - 1)] || open[0]
        : prev.active
      return { open, active }
    })
  }, [])

  const value = useMemo(() => {
    const activeService = getService(state.active)
    return {
      open: state.open,
      active: state.active,
      activeService,
      // What Bojo is told about the workspace: which service, and a short summary
      // a workspace can extend later (canvas state, filters, selection).
      summary: {
        serviceId: state.active,
        label: activeService?.label || state.active,
        tabCount: state.open.length,
        workspaceType: activeService?.workspaceType || null,
        canvas,
      },
      // U8: the canvas publishes itself here and registers the one function a
      // chat turn may call. `null` when the active workspace has no canvas.
      publishCanvas: (next) => setCanvas(next),
      registerCanvasCommand: (fn) => { commandRef.current = fn },
      runCanvasCommand: (instruction) => {
        const fn = commandRef.current
        if (typeof fn !== 'function') {
          return { ok: false, recognised: false, error: 'The open workspace has no canvas to edit.' }
        }
        try { return fn(instruction) } catch (e) { return { ok: false, recognised: true, error: String(e.message || e) } }
      },
      openService: open,
      activate,
      close,
    }
  }, [state, open, activate, close, canvas])

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return ctx
}

/**
 * The same context, but `null` outside the workbench. The studio also renders on
 * its own route (/design-studio), where no provider exists; a workspace that
 * only wants to PUBLISH must not throw there.
 */
export function useWorkspaceOptional() {
  return useContext(WorkspaceContext)
}
