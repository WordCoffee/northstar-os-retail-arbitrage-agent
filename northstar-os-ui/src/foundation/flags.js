// Feature flags — client-side gating; ALWAYS enforced server-side too.
// Flags are read from the foundation context or default off.
const DEFAULTS = {
  foundationShell: true,
  pinnedDrawer: true,
  commandPalette: true,
  customerPreview: false, // preview entry hidden unless enabled
  servicePagesLive: false, // service pages still use existing backend until Phase 1C
}

export function getFlags(overrides = {}) {
  return { ...DEFAULTS, ...overrides }
}

export default DEFAULTS