// Explicit local-development switch (P2-T5c).
//
// The dev identity shim (X-User-Id headers / local demo sign-in) is enabled ONLY
// when the frontend itself is a Vite dev build. `import.meta.env.DEV` is
// replaced with a literal at build time, so:
//   • dev server        -> true  (shim branch compiled in)
//   • test build        -> false (built bundle; real credential login only)
//   • production build  -> false (branch eliminated; check-prod-bundle.cjs
//                                 asserts the shim identity, the demo
//                                 credentials and the X-User-Id emitter are all
//                                 ABSENT from the real dist)
// It is never a fallback for a failed login, an unavailable backend, or an
// absent cookie - and because it is now compile-time, setting a global at
// runtime cannot switch the shim on in any served bundle.
export const LOCAL_DEV = !!import.meta.env.DEV

export default LOCAL_DEV
