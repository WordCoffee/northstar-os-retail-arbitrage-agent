// Rendered by the shell, above the chrome, so the notice about the auth posture
// appears on EVERY page — including the routes that are deliberately outside
// the shell. It used to be inline markup in App.jsx and pages/public/SignIn.jsx
// carried a comment claiming it rendered "via the shell"; this component is
// where that claim is true.

import { DEV_BANNER_TEXT, devBannerVisible } from './devBanner.js'

export default function DevBanner({ authMethod = null, localDev }) {
  if (!devBannerVisible({ authMethod, localDev })) return null
  return (
    <div
      data-testid="dev-banner"
      role="status"
      // Same paint-order fix as the owner-test banner: `.cosmic-canvas` is
      // position:fixed/z-index:0, so a static banner is painted underneath it.
      // Measured 2026-10-28: the banner occupied (0,0,1760x33) with background
      // rgb(180,67,47) and elementFromPoint at its centre still returned
      // CANVAS.cosmic-canvas — present in the DOM, invisible on screen.
      // Restyled 2026-11-05: it is an environment notice, not an error. The alarm
      // red made every page look broken on first load; the text is unchanged
      // (the smoke test and the rules both depend on it).
      style={{
        position: 'relative',
        zIndex: 10,
        background: '#232a2e',
        color: '#e6e1d8',
        textAlign: 'center',
        padding: '5px 12px',
        fontSize: 12.5,
        fontWeight: 600,
        letterSpacing: 0.2,
        borderBottom: '1px solid #39434a',
      }}
    >
      {DEV_BANNER_TEXT}
    </div>
  )
}
