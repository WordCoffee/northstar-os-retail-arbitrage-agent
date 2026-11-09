// Which routes render INSIDE the shell chrome, and which are deliberately
// outside it.
//
// `App.jsx` registers 72 routes. Five of them are entry surfaces a signed-out
// visitor must be able to use without any chrome in the way:
//
//   /beta          marketing landing (also hosts the #support section)
//   /beta/accept   invite redemption
//   /sign-in       credentials / dev redirect
//   /recovery      account recovery
//   /legal         legal documents
//
// Everything else — every room, every admin screen, the catch-all and the
// `Not Found` page — renders inside `<ShellLayout>` (TopNav + side nav +
// workspace outlet).
//
// `/beta-signup` is a PUBLIC path (an invitee has no session yet) but it is a
// catalogue room with its own page, so it stays INSIDE the shell. `matches`
// compares path segments, so `/beta-signup` is not treated as `/beta`.

export const SHELL_EXEMPT_PATHS = ['/beta', '/beta/accept', '/sign-in', '/recovery', '/legal']

// Public but inside the shell: no session required, chrome still rendered.
export const PUBLIC_SHELL_PATHS = ['/beta-signup']

export const PUBLIC_PATHS = [...SHELL_EXEMPT_PATHS, ...PUBLIC_SHELL_PATHS]

function matches(path, base) {
  return path === base || path.startsWith(base + '/')
}

/** True when the path must render WITHOUT the shell chrome. */
export function isShellExempt(path = '') {
  return SHELL_EXEMPT_PATHS.some((base) => matches(path, base))
}

/** True when the path is reachable without a session. */
export function isPublicPath(path = '') {
  return PUBLIC_PATHS.some((base) => matches(path, base))
}
