// Shell mode vocabulary — one source for the internal ids, the display names and
// the migration of values stored by older builds.
//
// Naming rule (work order U1): the default experience is called **Northstar**.
// It used to be called "Simple mode"; that phrase does not appear in user-facing
// copy any more. The internal id stays 'simple' because routes, gates, CSS scope
// (html[data-shell-mode="simple"]) and the stored preference key depend on it —
// renaming state to rename a label is how a shell breaks. The only other named
// surface is **advanced view** (the room shell).
//
// `normaliseMode` accepts the legacy spellings so a session that stored
// 'northstar', 'standard' or 'advanced view' keeps working after the rename.

export const MODE_KEY = 'ns-shell-mode'

/** Canonical internal ids. Do not rename these. */
export const SHELL_MODES = ['simple', 'advanced']

export const DEFAULT_MODE = 'simple'

/** What a human reads. The default view is "Northstar", not "Simple". */
export const SHELL_DISPLAY_NAMES = {
  simple: 'Northstar',
  advanced: 'Advanced view',
}

/** Legacy / colloquial spellings that must still resolve. */
export const MODE_ALIASES = {
  simple: 'simple',
  northstar: 'simple',
  default: 'simple',
  standard: 'simple',
  advanced: 'advanced',
  'advanced view': 'advanced',
  'advanced-view': 'advanced',
  autothink: 'advanced',
}

/** Map any stored or requested value onto a canonical mode id. */
export function normaliseMode(value) {
  const key = String(value ?? '').trim().toLowerCase()
  return MODE_ALIASES[key] || DEFAULT_MODE
}

/** The label to render for a mode id (falls back to the canonical name). */
export function displayName(mode) {
  const id = normaliseMode(mode)
  return SHELL_DISPLAY_NAMES[id] || SHELL_DISPLAY_NAMES[DEFAULT_MODE]
}
