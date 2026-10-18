// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL SHELL MODE — Simple | Advanced (S0, V3 rework 2026-10-18)
//
// V3: Simple is the PRODUCT DEFAULT (main view); Advanced is the dev-level
// room shell offered on certain subscription tiers (or to platform admins).
// The gate is resolved by the backend (`/api/shell/context` →
// `capabilities.advanced_view`) and enforced here for presentation/routing.
// ui_gates are UI-surface only — they never arm a live action.
//
// Resolution order for the initial mode:
//   1. `?shell=simple|advanced` (deep link; used by support/tests/operators)
//   2. localStorage 'ns-shell-mode'
//   3. DEFAULT_MODE
// An 'advanced' request without the capability degrades to 'simple'.
// ═══════════════════════════════════════════════════════════════════════════

import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export const MODE_KEY = 'ns-shell-mode'
export const SHELL_MODES = ['simple', 'advanced']
export const DEFAULT_MODE = 'simple'
export const SHELL_PARAM = 'shell'

function readMode(advancedAllowed) {
  // advancedAllowed === null means "capability not resolved yet" (the shell
  // context is still loading): honor the stored/preferred mode and let the
  // resolving effect enforce the gate, so an entitled operator is not demoted
  // to Simple on first paint.
  const allowed = (m) => (m === 'advanced' ? advancedAllowed !== false : SHELL_MODES.includes(m))
  try {
    const q = new URLSearchParams(window.location.search).get(SHELL_PARAM)
    if (SHELL_MODES.includes(q) && allowed(q)) return q
  } catch { /* no URL */ }
  try {
    const v = localStorage.getItem(MODE_KEY)
    if (SHELL_MODES.includes(v) && allowed(v)) return v
  } catch { /* storage unavailable */ }
  return DEFAULT_MODE
}

const ModeContext = createContext({
  mode: DEFAULT_MODE,
  advancedAllowed: null,
  setMode: () => {},
  toggleMode: () => {},
})

export function ModeProvider({ advancedAllowed = null, children }) {
  const [mode, setModeState] = useState(() => readMode(advancedAllowed))

  // The entitlement resolves asynchronously; when it lands as "denied", any
  // open advanced mode falls back to simple (never before it is known).
  useEffect(() => {
    if (advancedAllowed === false && mode === 'advanced') setModeState('simple')
  }, [advancedAllowed, mode])

  useEffect(() => {
    try { localStorage.setItem(MODE_KEY, mode) } catch { /* storage unavailable */ }
    try { document.documentElement.dataset.shellMode = mode } catch { /* no DOM */ }
    // Keep a deep-linked ?shell=… honest once the operator switches.
    try {
      const url = new URL(window.location.href)
      if (url.searchParams.has(SHELL_PARAM)) {
        url.searchParams.set(SHELL_PARAM, mode)
        window.history.replaceState({}, '', url.toString())
      }
    } catch { /* no URL context */ }
  }, [mode])

  const value = useMemo(() => ({
    mode,
    advancedAllowed: advancedAllowed !== false,
    setMode: (m) => {
      if (!SHELL_MODES.includes(m)) m = DEFAULT_MODE
      if (m === 'advanced' && advancedAllowed === false) m = 'simple'
      setModeState(m)
    },
    toggleMode: () => setModeState((prev) => {
      if (prev === 'simple') return advancedAllowed === false ? 'simple' : 'advanced'
      return 'simple'
    }),
  }), [mode, advancedAllowed])

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}

export function useMode() {
  return useContext(ModeContext)
}
