// THE WORKSPACE FRAME — one surface, rendered from the workspace specs.
//
// Every core service used to reach the operator as a page with no statement of
// what it was: which scene it paints, which views it has, which Bojo tool it
// opens, or whether the plan entitles it at all. The frame states those four
// facts above the page, and it reads them from
// `src/data/workspaceSpecs.json` (mirrored from
// `ty/northstar_workspaces.json`) instead of being copied six times.
//
// It is mounted by `WorkspacePanels.jsx` inside the tab's pinned location, so
// `useLocation()` here is the tab's own URL — the view a hidden background tab
// reports is the view it had when it was left, not the tab in front.
//
// Three deliberate limits:
//   • A service with no spec gets NO frame. The fallback is the default scene
//     and the room's own page (see `defaultWorkspace()`), because a frame that
//     describes nothing is worse than no frame.
//   • The frame does not duplicate the room's tab strip: the room already
//     renders its own (RoomTabs / the Design Studio's section picker) and it
//     owns the click. The frame declares the same view list and reports which
//     one is active, so a room that renames a view without updating the file is
//     caught by the click-path test.
//   • The gate is a STUB. `canUseService` decides; no billing exists, nothing is
//     charged, and the production branch is reachable only through the
//     dev-only `?billing=enforce` switch, which a production build compiles
//     out. A refused workspace shows the refusal instead of the page, which is
//     the honest render: the page would present controls the plan cannot use.

import { useLocation } from 'react-router-dom'
import { useSession } from '../foundation/session.jsx'
import { LOCAL_DEV } from '../foundation/dev.js'
import {
  billingStubEnforced,
  resolveView,
  viewLabel,
  workspaceForService,
  workspaceGate,
  workspaceScene,
} from '../lib/workspaceSpecs.js'

const BAR = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: 8,
  padding: '6px 2px 8px',
  marginBottom: 6,
  borderBottom: '1px solid var(--divider)',
  fontSize: 11.5,
  lineHeight: 1.4,
}

const CHIP = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '1px 7px',
  borderRadius: 999,
  border: '1px solid var(--divider)',
  background: 'var(--surface)',
  color: 'var(--ink-mid)',
  fontSize: 11,
  whiteSpace: 'nowrap',
}

function Chip({ testId, name, value, tone, children }) {
  return (
    <span
      style={tone ? { ...CHIP, color: tone } : CHIP}
      data-testid={testId}
      data-name={name}
      data-value={value}
    >
      {children}
    </span>
  )
}

export default function WorkspaceFrame({ serviceId = '', children = null }) {
  const workspace = workspaceForService(serviceId)
  const location = useLocation()
  const session = useSession()

  // No spec: the room keeps its page, untouched. The scene falls back on its
  // own (sceneRegistry answers `home` for a service it does not know).
  if (!workspace) return children

  const search = location.search || ''
  const view = resolveView(workspace, search)
  const scene = workspaceScene(workspace)
  const enforce = billingStubEnforced(search, LOCAL_DEV)
  const gate = workspaceGate(workspace, session, { enforce })
  const tool = workspace.bojo_tool || {}

  const report = {
    id: workspace.id,
    service: workspace.service,
    coreRole: workspace.core_role || '',
    label: workspace.label,
    route: workspace.route,
    path: location.pathname,
    view,
    sceneId: scene.id,
    sceneVariant: scene.variant,
    tool: tool.id || '',
    gateMode: gate.mode,
    gateAllowed: !!gate.allowed,
  }

  return (
    <div
      data-testid="ws-frame"
      data-ws-id={workspace.id}
      data-ws-service={workspace.service}
      data-ws-core={workspace.core_role || ''}
      data-ws-label={workspace.label}
      data-ws-route={workspace.route}
      data-ws-view={view}
      data-ws-scene={scene.id}
      data-ws-scene-variant={scene.variant}
      data-ws-tool={tool.id || ''}
      data-ws-tool-status={tool.status || ''}
      data-ws-gate={gate.mode}
      data-ws-gate-allowed={gate.allowed ? 'true' : 'false'}
      data-ws-report={JSON.stringify(report)}
    >
      <div style={BAR} role="group" aria-label={`${workspace.label} workspace`}>
        <Chip testId="ws-name" name="workspace" value={workspace.id}>
          <strong style={{ fontWeight: 600, color: 'var(--ink)' }}>{workspace.label}</strong>
        </Chip>
        <Chip testId="ws-scene-chip" name="scene" value={scene.id}>
          scene: {scene.label}
        </Chip>
        <Chip testId="ws-tool-chip" name="bojo_tool" value={tool.id || ''}>
          Bojo: {tool.id || 'no tool'}
        </Chip>
        <Chip
          testId="ws-gate-chip"
          name="gate"
          value={gate.mode}
          tone={gate.allowed ? undefined : 'var(--danger, #a5522f)'}
        >
          {`plan: ${gate.mode}`}
        </Chip>
        <Chip testId="ws-view-chip" name="view" value={view}>
          view: {viewLabel(workspace, view)}
        </Chip>
        {/* The declared view list — read-only on purpose; the room owns the click. */}
        <span data-testid="ws-views" style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 4 }}>
          {(workspace.views?.tabs || []).map((tab) => (
            <span
              key={tab.id}
              data-testid={`ws-view-${tab.id}`}
              data-view={tab.id}
              data-active={tab.id === view ? 'true' : 'false'}
              style={{
                ...CHIP,
                borderStyle: tab.id === view ? 'solid' : 'dashed',
                color: tab.id === view ? 'var(--ink)' : 'var(--ink-low)',
                fontWeight: tab.id === view ? 600 : 400,
              }}
            >
              {tab.label}
            </span>
          ))}
        </span>
      </div>

      {gate.allowed ? children : (
        <div className="card" data-testid="ws-gate-denied" style={{ padding: 18 }}>
          <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 6 }}>
            {workspace.label} is not on this plan
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ink-mid)', margin: '0 0 6px' }}>
            The plan check refused this workspace:{' '}
            <code data-testid="ws-gate-reason">{gate.reason}</code>.
          </p>
          <p style={{ fontSize: 12, color: 'var(--ink-low)', margin: 0 }}>
            Needs <code>{workspace.gate?.entitlement_key || 'an entitlement'}</code>, or studio
            credit. This is a stub gate: no billing runs, no credit is spent, and the production
            decision belongs on the server.
          </p>
        </div>
      )}
    </div>
  )
}
