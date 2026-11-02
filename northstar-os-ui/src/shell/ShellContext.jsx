// ═══════════════════════════════════════════════════════════════════════════
// SHELL CONTEXT (V3) — plan capabilities, focus modes, hardware telemetry.
//
// One provider for the Northstar shell:
//   • fetches /api/shell/context (capabilities + server-owned focus catalogue)
//   • owns the ACTIVE FOCUS state (persisted; switching re-points the chat)
//   • polls /api/shell/hardware (real local readings; honest ok:false)
//
// Honesty: an unreachable shell context degrades to a labelled offline
// fallback (capabilities denied, catalogue mirrored locally). It never
// pretends the server said yes.
// ═══════════════════════════════════════════════════════════════════════════

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { shellApi } from './api.js'

export const FOCUS_KEY = 'ns-focus'

// Offline mirror of the server catalogue (ids only need to match; the server
// re-validates every focus it is sent and owns the tool subsets).
const FALLBACK_FOCUSES = [
  { id: 'auto', label: 'Auto', blurb: 'The Master Brain routes by intent.', suggestions: [] },
  { id: 'create', label: 'Create', blurb: 'Packaging, photos, listing images, ad creative.', suggestions: [] },
  { id: 'grow', label: 'Grow', blurb: 'Listings, keywords, ads and search visibility.', suggestions: [] },
  { id: 'research', label: 'Research', blurb: 'Sourcing, competitors, market reads.', suggestions: [] },
  { id: 'operate', label: 'Operate', blurb: 'Inventory, profitability, monitoring.', suggestions: [] },
  { id: 'autothink', label: 'AutothinK', blurb: 'Premium build-anything workspace.', suggestions: [], locked: true },
]

const ShellContext = createContext(null)

function readFocus() {
  try {
    const v = localStorage.getItem(FOCUS_KEY)
    return v || 'auto'
  } catch { return 'auto' }
}

export function ShellProvider({ children }) {
  const [ctx, setCtx] = useState({
    ready: false,
    offline: false,
    plan: null,
    planName: '',
    capabilities: { advanced_view: false, autothink_workspace: false },
    focuses: FALLBACK_FOCUSES,
    identity: { role: '', source: 'pending' },
  })
  const [focusId, setFocusIdState] = useState(readFocus)
  const [hardware, setHardware] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await shellApi.context()
        if (cancelled) return
        setCtx({
          ready: true, offline: false,
          plan: r.identity?.plan || null,
          planName: r.identity?.plan_name || '',
          capabilities: r.capabilities || { advanced_view: false, autothink_workspace: false },
          focuses: Array.isArray(r.focuses) && r.focuses.length ? r.focuses : FALLBACK_FOCUSES,
          identity: r.identity || { role: '', source: 'session' },
        })
      } catch (e) {
        if (cancelled) return
        setCtx((c) => ({ ...c, ready: true, offline: true, offlineReason: e.message }))
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Hardware chip: poll while the tab is visible; stop when hidden.
  useEffect(() => {
    let cancelled = false
    let timer = null
    const tick = async () => {
      if (cancelled) return
      try {
        const h = await shellApi.hardware()
        if (!cancelled) setHardware(h)
      } catch { /* chip shows UNKNOWN */ }
      timer = setTimeout(tick, 20000)
    }
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') tick()
    const onVis = () => {
      if (document.visibilityState === 'visible') { if (!timer) tick() }
      else if (timer) { clearTimeout(timer); timer = null }
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])

  const setFocus = useCallback((id) => {
    setFocusIdState((prev) => {
      const next = id || 'auto'
      try { localStorage.setItem(FOCUS_KEY, next) } catch { /* storage unavailable */ }
      return next
    })
  }, [])

  const value = useMemo(() => {
    const focuses = ctx.focuses || FALLBACK_FOCUSES
    const active = focuses.find((f) => f.id === focusId) || focuses[0]
    return {
      ...ctx,
      focuses,
      focusId: active ? active.id : 'auto',
      focus: active,
      setFocus,
      hardware,
      advancedAllowed: !!ctx.capabilities?.advanced_view,
      autothinkAllowed: !!ctx.capabilities?.autothink_workspace,
    }
  }, [ctx, focusId, setFocus, hardware])

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
}

export function useShell() {
  const v = useContext(ShellContext)
  if (!v) throw new Error('useShell must be used within <ShellProvider>')
  return v
}
