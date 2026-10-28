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
  const refresh = useCallback(async () => {
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
      }))
      return { authenticated: !!me.user_id, userId: me.user_id || '', suspended: false }
    } catch (e) {
      // 401 → signed out / expired / revoked session.
      if (e.status === 401) {
        setToken('')
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
      setSession((s) => ({ ...s, loaded: true, error: e }))
      return { authenticated: false, userId: '', error: e, status: e.status }
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