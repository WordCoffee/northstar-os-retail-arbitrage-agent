// Shell view switch (S0; renamed 2026-10-30).
//
// The naming rule drops "Simple" from user-visible copy: the default
// view is not a dumbed-down mode, it is THE view. The internal mode id stays
// 'simple' because routes, gates and stored preference keys depend on it -
// renaming state to rename a label is how you break a shell.
//
// V3 entitlement rule: the Advanced option only renders when the backend granted
// `advanced_view` (AutothinK tier / platform admins). Lower tiers get a static
// "Standard" chip - honest, not a dead control.
//
// Lives in the Settings dialog since 2026-10-30 (it is a preference, not a
// primary action). Testid unchanged so harnesses keep working.
import { useMode } from '../context/ModeContext.jsx'

export default function ShellModeToggle() {
  const { mode, advancedAllowed, toggleMode } = useMode()
  const isAdvanced = mode !== 'simple'

  if (!advancedAllowed) {
    return (
      <span
        className="shell-mode-toggle"
        data-testid="ns-shell-mode"
        data-mode={mode}
        data-advanced-allowed="0"
        title="Northstar view. The Advanced view needs a qualifying plan."
      >
        <span className="shell-mode-opt is-on">Northstar</span>
      </span>
    )
  }

  return (
    <button
      type="button"
      className="shell-mode-toggle"
      data-testid="ns-shell-mode"
      data-mode={mode}
      data-advanced-allowed="1"
      onClick={toggleMode}
      title={isAdvanced ? 'Switch to Northstar' : 'Switch to the Advanced view'}
      aria-label={`View: ${isAdvanced ? 'Advanced view' : 'Northstar'}. Activate to switch.`}
    >
      <span className={`shell-mode-opt ${isAdvanced ? '' : 'is-on'}`}>Northstar</span>
      <span className={`shell-mode-opt ${isAdvanced ? 'is-on' : ''}`}>Advanced</span>
    </button>
  )
}
