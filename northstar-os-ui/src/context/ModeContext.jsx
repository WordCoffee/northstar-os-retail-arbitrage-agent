// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL SHELL MODE — Simple | Advanced (S0)
//
// One app-wide mode state. Simple mode is the chat-first Master Brain shell;
// Advanced mode is today's room layouts. Persisted per browser; later synced
// to the backend uiMode. Nothing consumes the mode yet except the toggle and
// the Creative Studio simple branch — rooms migrate one at a time (S4/S6).
//
// Default: 'advanced' — the existing experience stays the default until the
// simple shell has been rolled through every room; flipping DEFAULT_MODE to
// 'simple' is the single-line launch switch.
// ═══════════════════════════════════════════════════════════════════════════

import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export const MODE_KEY = 'ns-shell-mode'
export const SHELL_MODES = ['simple', 'advanced']
export const DEFAULT_MODE = 'advanced'

function readMode() {
  try {
    const v = localStorage.getItem(MODE_KEY)
    return SHELL_MODES.includes(v) ? v : DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

const ModeContext = createContext({
  mode: DEFAULT_MODE,
  setMode: () => {},
  toggleMode: () => {},
})

export function ModeProvider({ children }) {
  const [mode, setModeState] = useState(readMode)

  useEffect(() => {
    try { localStorage.setItem(MODE_KEY, mode) } catch { /* storage unavailable */ }
    try { document.documentElement.dataset.shellMode = mode } catch { /* no DOM */ }
  }, [mode])

  const value = useMemo(() => ({
    mode,
    setMode: (m) => setModeState(SHELL_MODES.includes(m) ? m : DEFAULT_MODE),
    toggleMode: () => setModeState((prev) => (prev === 'simple' ? 'advanced' : 'simple')),
  }), [mode])

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}

export function useMode() {
  return useContext(ModeContext)
}
