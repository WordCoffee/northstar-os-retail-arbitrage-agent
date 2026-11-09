// The dev-auth notice is a claim about the BACKEND auth posture, so it follows
// the backend answer instead of a literal in the UI.
//
// The UI asks `/environment` (Northstar_backend/foundation/api/router.py) which
// reports `auth_method` resolved by `foundation/api/deps.py`:
//   "jwt"        a real signed session
//   "dev_shim"   the local loopback dev identity (deps.py `dev_shim_enabled()`
//                AND `is_local` AND an explicit header or dev_auto_session)
// `session.authMethod` carries that value unchanged (foundation/session.jsx).
//
// LOCAL_DEV is a second, compile-time signal: a Vite dev bundle is by definition
// a development build (src/foundation/dev.js), and on a cold start the session
// may not have resolved yet. Production builds compile both checks out to
// `false`, so the notice cannot appear there.

import { LOCAL_DEV } from '../foundation/dev.js'

export const DEV_BANNER_TEXT = 'DEV: AUTH DISABLED — local loopback only'

/** Whether the dev-auth notice applies to this session/build. */
export function devBannerVisible({ authMethod = null, localDev = LOCAL_DEV } = {}) {
  return !!localDev || authMethod === 'dev_shim'
}
