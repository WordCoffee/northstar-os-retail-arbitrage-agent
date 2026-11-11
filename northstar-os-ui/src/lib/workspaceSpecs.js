// The workspace specs: which core service workspaces exist, what each one
// shows, the scene under it, the view its tabs address, the Bojo tool it opens
// and the gate it needs.
//
// The data lives in `ty/northstar_workspaces.json#scene_workspaces` (the
// artifact the director and the service registry read) and is mirrored into
// `src/data/workspaceSpecs.json` because the Vite root is `northstar-os-ui/`:
// importing a file above the root resolves in `vite build` but the dev server
// refuses it (`server.fs.allow`), and Dockerfile.ui builds from the UI
// directory alone, where `ty/` does not exist. `workspaceSpecs.test.js`
// compares the two copies key by key, so the mirror cannot drift.
//
// Everything here is pure: no React, no DOM, no fetches. The frame component
// (`WorkspaceFrame.jsx`) renders whatever this module resolves.

import { WORKSPACE_SPECS as SPECS } from '../data/workspaces.js'
import { canUseService } from './serviceGate.js'

/** The keys the mirror must share with `ty/northstar_workspaces.json`. */
export const MIRRORED_KEYS = [
  'core_six',
  'default_scene',
  'default_workspace',
  'workspaces',
]

/** The dev-only query switch that exercises the production branch of the gate. */
export const BILLING_STUB_PARAM = 'billing'
export const BILLING_STUB_VALUE = 'enforce'

const BY_SERVICE = new Map(SPECS.workspaces.map((ws) => [ws.service, ws]))

/** Every workspace this file describes, in declaration order. */
export function allWorkspaces() {
  return SPECS.workspaces.slice()
}

/** The six the queue names, as `{ role, service }`. */
export function coreSix() {
  return SPECS.core_six.slice()
}

/**
 * The workspace that owns a service, or null.
 *
 * Null is the documented answer for every service that is not described here:
 * those rooms keep their own page, get the default scene, and get no frame.
 * A frame around a workspace nobody argued for is worse than no frame.
 */
export function workspaceForService(serviceId = '') {
  return BY_SERVICE.get(String(serviceId)) || null
}

/** The fallback every undescribed service takes. */
export function defaultWorkspace() {
  return SPECS.default_workspace
}

export function defaultScene() {
  return SPECS.default_scene
}

/**
 * Which declared view is showing.
 *
 * `param` is the query key the room already uses for its own tabs
 * (`view` for most rooms, `section` for the Design Studio). An unknown value
 * falls back to the spec's default rather than to nothing, so a stale link
 * cannot leave the frame reporting a view the workspace does not have.
 */
export function resolveView(workspace, search = '') {
  if (!workspace) return ''
  const views = workspace.views || {}
  const param = views.param || ''
  const declared = Array.isArray(views.tabs) ? views.tabs : []
  let requested = ''
  if (param) {
    try {
      requested = new URLSearchParams(String(search || '').replace(/^\?/, '')).get(param) || ''
    } catch { requested = '' }
  }
  if (requested && declared.some((tab) => tab.id === requested)) return requested
  const fallback = views.default || ''
  if (fallback && declared.some((tab) => tab.id === fallback)) return fallback
  return declared.length ? declared[0].id : ''
}

/** The label of a view id, or the id itself when the file does not name it. */
export function viewLabel(workspace, viewId) {
  const tabs = (workspace && workspace.views && workspace.views.tabs) || []
  const row = tabs.find((tab) => tab.id === viewId)
  return row ? row.label : String(viewId || '')
}

/**
 * Does this session's plan entitle the workspace's service?
 *
 * Delegates to `canUseService` — the single place entitlement is decided — and
 * never invents an answer. `enforce` is how a test (or `?billing=enforce` in a
 * dev build) reaches the production branch without pretending dev is
 * production. There is no billing here: no charge is made and no credit is
 * spent, which is why this is a stub.
 */
export function workspaceGate(workspace, session, { enforce = false } = {}) {
  if (!workspace) return { allowed: true, mode: 'unscoped', reason: 'no workspace spec' }
  return canUseService(session, workspace.service, { enforceBilling: enforce })
}

/** True when the dev-only billing stub is switched on in this URL. */
export function billingStubEnforced(search = '', localDev = false) {
  if (!localDev) return false
  try {
    return new URLSearchParams(String(search || '').replace(/^\?/, '')).get(BILLING_STUB_PARAM)
      === BILLING_STUB_VALUE
  } catch { return false }
}

/**
 * The scene a workspace paints: its own, else the default.
 *
 * The scene registry is still the renderer's source of truth; this only says
 * what the file claims, so a spec that names a scene the registry does not ship
 * is caught by the unit test instead of rendering the wrong bed.
 */
export function workspaceScene(workspace) {
  const scene = workspace && workspace.scene
  if (scene && scene.id) return scene
  const fallback = SPECS.default_scene
  return { id: fallback.service || 'home', label: fallback.label, variant: fallback.variant }
}
