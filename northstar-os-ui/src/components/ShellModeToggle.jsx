// Global Simple | Advanced shell switch (S0). Lives in the top nav; every
// room reads the same state via useMode(). Distinct testid so harnesses can
// address it without colliding with the per-room studio ModeToggle.
import { useMode } from '../context/ModeContext.jsx'

export default function ShellModeToggle() {
  const { mode, toggleMode } = useMode()
  const next = mode === 'simple' ? 'Advanced' : 'Simple'
  return (
    <button
      type="button"
      className="shell-mode-toggle"
      data-testid="ns-shell-mode"
      data-mode={mode}
      onClick={toggleMode}
      title={`Switch to ${next} mode`}
      aria-label={`Shell mode: ${mode}. Switch to ${next}.`}
    >
      <span className="shell-mode-opt">Simple</span>
      <span className="shell-mode-opt">Advanced</span>
    </button>
  )
}
