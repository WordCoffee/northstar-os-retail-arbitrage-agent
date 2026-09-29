// Explicit local-development switch (P2-T5c).
//
// The dev identity shim (X-User-Id headers / local demo sign-in) is enabled ONLY
// when this is true: a Vite dev build, or a test harness that explicitly sets
// `window.__NORTHSTAR_LOCAL_DEV__ = true`. It is never a fallback for a failed
// login, an unavailable backend, or an absent cookie.
export const LOCAL_DEV =
  (typeof window !== 'undefined' && window.__NORTHSTAR_LOCAL_DEV__ === true) ||
  (typeof import.meta !== 'undefined' && !!(import.meta.env && import.meta.env.DEV))

export default LOCAL_DEV