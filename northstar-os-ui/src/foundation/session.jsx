// Session context provider — organization, role, permissions, environment, preview.
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import foundationApi, { getDevSession, setDevSession, getToken, setToken } from './api.js'
import { LOCAL_DEV } from './dev.js'
import { getFlags } from './flags.js'

const SessionContext = createContext(null)

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within <SessionProvider>')
  return ctx
}

export function hasPerm(session, permission) {
  if (!session || !session.permissions) return false
  if (!permission) return true
  return session.permissions.includes(permission)
}

const ANON = {
  loaded: false,
  authenticated: false,
  error: null,
  userId: '',
  organizations: [],
  activeOrganizationId: null,
  role: null,
  environment: 'production',
  viewContext: 'normal',
  permissions: [],
  isPreview: false,
  preview: null,
  flags: getFlags(),
  ownerTestMode: false,
  ownerTestModeBanner: null,
  authMethod: null,
}

// Owner-authorized dev-only exception: a Vite dev build never blocks on
// sign-in. If the backend cannot resolve a session (unreachable, or a temp
// store without the demo membership), the provider adopts the same demo
// identity the loopback shim uses. Production builds are compile-time
// unaffected (LOCAL_DEV is false and the branch is eliminated).
const DEV_DEMO_SESSION = {
  userId: 'demo-t2',
  organizations: [{ id: 'org-t2', name: 'T2 Holdings LLC', role: 'operator' }],
  activeOrganizationId: 'org-t2',
  role: 'operator',
  environment: 'development',
  permissions: ['approve', 'draft', 'preview', 'request_refresh', 'run_local',
                'view', 'view_approvals', 'view_audit', 'view_ledger', 'view_providers'],
  isPreview: false,
  preview: null,
  ownerTestMode: false,
  ownerTestModeBanner: null,
  authMethod: 'dev_shim',
}

function devBypassSession() {
  return { ...ANON, ...DEV_DEMO_SESSION, loaded: true, authenticated: true }
}

export function SessionProvider({ children }) {
  const [session, setSession] = useState(ANON)
  const [dev, setDev] = useState(() => {
    const existing = getDevSession()
    if (LOCAL_DEV && !existing.userId) {
      return setDevSession({ userId: 'demo-t2', orgId: 'org-t2', role: 'operator', env: 'development', previewId: '' })
    }
    return existing
  })
  const [tokenPresent, setTokenPresent] = useState(!!getToken())

  // Returns a SNAPSHOT of the resolved identity so callers can decide on the
  // real result instead of assuming success (SignIn's dev-shim fallback uses
  // this). The React state below is still the source of truth for the app.
  //
  // `attempt` is the retry counter for TRANSIENT failures only. A 429 on
  // /environment used to land in the generic branch below and, on a cold page
  // load, leave `authenticated:false` — which bounced the operator to /sign-in
  // mid-session (and, under LOCAL_DEV, into a /home <-> /sign-in redirect loop,
  // because /sign-in immediately redirects back to /home). One bounded retry
  // keeps a transient blip from being reported as a signed-out identity.
  const refresh = useCallback(async (attempt = 0) => {
    // ui_mode is a PUBLIC signal (available pre-auth) so signed-out clients
    // also land in the correct beta entry state (never the legacy shell).
    let uiMode = 'full'
    try {
      const m = await foundationApi.uiMode()
      uiMode = m.ui_mode || 'full'
    } catch { /* keep default */ }
    // Always resolve identity from the backend (/me). Hosted identity comes from
    // the HttpOnly session cookie; local-dev identity via the explicit dev shim.
    try {
      const [me, env, active] = await Promise.all([
        foundationApi.me(),
        foundationApi.environment(),
        foundationApi.previewActive().catch(() => ({ active: false, preview: null })),
      ])
      if (!me.user_id && LOCAL_DEV) {
        setSession(devBypassSession())
        return { authenticated: true, userId: DEV_DEMO_SESSION.userId, devBypass: true }
      }
      setSession((s) => ({
        ...s,
        loaded: true,
        authenticated: !!me.user_id,
        error: null,
        userId: me.user_id || '',
        organizations: me.organizations || [],
        activeOrganizationId: me.active_organization_id,
        role: me.role || null,
        environment: env.environment,
        viewContext: env.view_context,
        uiMode: env.ui_mode || uiMode,
        permissions: me.permissions || [],
        isPreview: !!env.is_preview,
        preview: active.active ? active.preview : null,
        ownerTestMode: !!env.owner_test_mode,
        ownerTestModeBanner: env.owner_test_mode_banner || null,
        authMethod: env.auth_method || null,
      }))
      return { authenticated: !!me.user_id, userId: me.user_id || '', suspended: false }
    } catch (e) {
      // 401 → signed out / expired / revoked session.
      if (e.status === 401) {
        setToken('')
        if (LOCAL_DEV) {
          setSession(devBypassSession())
          return { authenticated: true, userId: DEV_DEMO_SESSION.userId, devBypass: true }
        }
        setSession((s) => ({ ...ANON, loaded: true, authenticated: false }))
        return { authenticated: false, userId: '', status: e.status }
      }
      // 403 with org_lifecycle_blocked → account suspended/paused/cancelled:
      // show a clear account-status screen instead of a generic error.
      if (e.status === 403 && (e.detail?.code || e.code) === 'org_lifecycle_blocked') {
        const blockState = e.detail?.state || ''
        setSession((s) => ({
          ...s, loaded: true, authenticated: true, suspended: true,
          suspensionState: blockState,
          suspensionMessage: e.detail?.message || 'access is currently disabled for this account',
          error: null,
        }))
        return { authenticated: true, userId: '', suspended: true, status: e.status }
      }
      // 429 / 5xx / network: the backend is busy, not signing us out. Retry once
      // before reporting anything, so a transient blip does not flip the UI to
      // signed-out state and discard an established identity.
      const retriable = !e.status || e.status === 429 || e.status >= 500
      if (retriable && attempt < 1) {
        await new Promise((resolve) => setTimeout(resolve, 900))
        return refresh(attempt + 1)
      }
      if (LOCAL_DEV) {
        setSession(devBypassSession())
        return { authenticated: true, userId: DEV_DEMO_SESSION.userId, devBypass: true }
      }
      setSession((s) => ({ ...s, loaded: true, error: e }))
      return { authenticated: false, userId: '', error: e, status: e.status, retriable: true }
    }
  }, [])

  useEffect(() => { refresh() }, [refresh, dev, tokenPresent])

  const updateDev = useCallback(async (patch) => {
    const next = setDevSession(patch)
    setDev(next)
    return await refresh()
  }, [refresh])

  const signIn = useCallback(async (token) => {
    setToken(token)
    setTokenPresent(true)
    await refresh()
    return session
  }, [refresh])

  const signOut = useCallback(async () => {
    // Revoke the hosted cookie session (best-effort), then clear local state.
    try { await foundationApi.logout() } catch { /* already signed out */ }
    setToken('')
    setDevSession({ userId: '', orgId: '', role: '', env: 'production', previewId: '' })
    setDev(getDevSession())
    setTokenPresent(false)
    setSession((s) => ({ ...ANON, loaded: true, authenticated: false }))
  }, [])

  const startPreview = useCallback(async ({ targetOrganizationId, targetRole, reason }) => {
    const res = await foundationApi.previewStart({
      target_organization_id: targetOrganizationId,
      target_role: targetRole || null,
      reason,
    })
    updateDev({ previewId: res.preview_id })
    return res
  }, [updateDev])

  const endPreview = useCallback(async () => {
    const pid = getDevSession().previewId
    if (pid) await foundationApi.previewEnd(pid)
    updateDev({ previewId: '' })
  }, [updateDev])

  const value = { ...session, refresh, dev, updateDev, signIn, signOut,
                  startPreview, endPreview,
                  hasPerm: (p) => hasPerm(session, p) }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export default SessionProvider