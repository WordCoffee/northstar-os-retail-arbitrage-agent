// Global Simple | Advanced shell switch (S0, V3). Lives in the top nav; every
// room reads the same state via useMode(). Distinct testid so harnesses can
// address it without colliding with the per-room studio ModeToggle.
//
// V3: the Advanced option only renders when the backend granted the
// `advanced_view` ui gate (Keystone/AutothinK tiers, platform admins). Lower
// tiers see a single "Simple" pill — honest, not a dead control.
import { useMode } from '../context/ModeContext.jsx'

export default function ShellModeToggle() {
  const { mode, advancedAllowed, toggleMode } = useMode()
  const next = mode === 'simple' ? 'Advanced' : 'Simple'
  return (
    <button
      type="button"
      className="shell-mode-toggle"
      data-testid="ns-shell-mode"
      data-mode={mode}
      data-advanced-allowed={advancedAllowed ? '1' : '0'}
      onClick={advancedAllowed ? toggleMode : undefined}
      title={advancedAllowed ? `Switch to ${next} mode` : 'Simple view — the Advanced dev view needs a qualifying plan'}
      aria-label={advancedAllowed
        ? `Shell mode: ${mode}. Switch to ${next}.`
        : 'Shell mode: simple (Advanced view requires a qualifying plan)'}
    >
      <span className="shell-mode-opt">Simple</span>
      {advancedAllowed && <span className="shell-mode-opt">Advanced</span>}
    </button>
  )
}
