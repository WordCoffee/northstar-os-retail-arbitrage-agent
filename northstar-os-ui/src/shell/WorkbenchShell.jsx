// The workbench shell — Bojo docked on the left, service tabs across the top, one
// workspace swapping underneath.
//
// Tabs stay mounted and are hidden with `hidden`, so a workspace keeps its local
// state when the user flips to another service and back. The scene layer, theme
// tokens and per-service workspaces land in U4–U12; this unit is the frame those
// units hang on.

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import ChatSurface from '../chat/ChatSurface.jsx'
import { INTERACTIVE_SERVICES, getService } from '../data/serviceRegistry.js'
import { themeVars } from '../lib/serviceThemes.js'
import { useThemeShift } from '../kit/useThemeShift.js'
import SceneHost from '../scene/SceneHost.jsx'
import { useWorkspace } from './WorkspaceTabs.jsx'
import { TAB_PANELS } from './WorkspacePanels.jsx'

// Service id -> the page component that already implements it. One map, shared
// with the shell's workspace tabs (`WorkspacePanels.jsx`); a service without an
// entry renders an honest placeholder that names what is missing, never a blank
// panel.
const WORKSPACES = TAB_PANELS

function NotWired({ service }) {
  // A catalogue entry is not a page: `source: 'app-route'` entries have a real
  // route in App.jsx, the rest are names the catalogue carries without one.
  const hasPage = service.source === 'app-route'
  return (
    <div className="wb-empty" data-testid="wb-not-wired" data-service-id={service.id}>
      <h2>{service.label}</h2>
      {hasPage ? (
        <>
          <p>
            This service is registered ({service.workspaceType}) but its workspace is not
            wired into the workbench yet. It still opens from the room shell.
          </p>
          <p className="wb-muted">Route: {service.route}</p>
        </>
      ) : (
        <>
          <p>
            {service.label} is a catalogue entry ({service.workspaceType}) with no page of its
            own yet. Nothing is hidden: there is nothing here to show.
          </p>
          <p className="wb-muted">Planned route: {service.route} · scene: {service.scene}</p>
        </>
      )}
    </div>
  )
}

export default function WorkbenchShell() {
  const { open, active, activeService, summary, openService, activate, close } = useWorkspace()
  const [pickerOpen, setPickerOpen] = useState(false)
  // On a phone the tab strip is collapsed behind the switcher, so "show my tabs"
  // and "add a service" are two different panels. They used to share one flag,
  // which meant tapping + Service also opened the tab strip and tapping the
  // switcher rendered the picker underneath it.
  const [tabsOpen, setTabsOpen] = useState(false)
  const [dockOpen, setDockOpen] = useState(true)
  const [sheet, setSheet] = useState('peek')
  const navigate = useNavigate()

  // The sports-car shift: the active service's theme re-skins the cockpit.
  const themeId = activeService?.theme || 'neutral'
  const shifting = useThemeShift(themeId)

  // Phone layout: the dock is replaced by a bottom sheet, and the dock's own
  // ChatSurface is not rendered at all. CSS-hiding it left its effects running
  // and made the phone view slow enough to time out.
  const [narrow, setNarrow] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(max-width: 760px)').matches
      : false
  ))
  useEffect(() => {
    if (!window.matchMedia) return undefined
    const mq = window.matchMedia('(max-width: 760px)')
    const onChange = (e) => setNarrow(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // A tab mounts the first time it is opened, then stays mounted (hidden when
  // inactive) so its state survives a switch. Mounting every open tab up front
  // made the shell unusable: two heavy workspaces started their effects at once.
  const [visited, setVisited] = useState(() => new Set([active]))
  if (!visited.has(active)) {
    const next = new Set(visited)
    next.add(active)
    setVisited(next)
  }

  const tabs = useMemo(
    () => open.map((id) => ({ id, service: getService(id) })).filter((t) => t.service),
    [open],
  )
  const available = useMemo(
    () => INTERACTIVE_SERVICES.filter((s) => !open.includes(s.id)),
    [open],
  )

  return (
    <div className={`wb-shell ${dockOpen ? 'dock-open' : 'dock-closed'} ${shifting ? 'is-shifting' : ''}`}
         data-testid="workbench-shell" data-wb-theme={themeId} style={themeVars(themeId)}
         data-canvas-id={summary.canvas?.id || ''}
         data-canvas-layers={summary.canvas ? String(summary.canvas.layers.length) : ''}>
      <SceneHost sceneId={activeService?.scene || 'default'} />
      {!narrow && (
      <aside className="wb-dock glass" data-testid="bojo-dock" data-collapsed={dockOpen ? '0' : '1'}>
        <div className="wb-dock-head">
          <span className="wb-dock-title">Bojo</span>
          <button type="button" className="btn btn-ghost btn-sm" data-testid="wb-dock-toggle"
                  aria-expanded={dockOpen}
                  onClick={() => setDockOpen((v) => !v)}>
            {dockOpen ? 'Collapse' : 'Expand'}
          </button>
        </div>
        {dockOpen && (
          <div className="wb-dock-body" data-testid="bojo-dock-body">
            <ChatSurface
              heading="Bojo"
              sub={`Northstar · ${activeService?.label || 'workspace'}`}
              onOpenAdvanced={null}
            />
          </div>
        )}
      </aside>
      )}

      <section className="wb-main">
        <div className="wb-tabbar glass" data-testid="wb-tabbar">
          <button type="button" className="btn btn-sm wb-switcher" data-testid="wb-switcher"
                  aria-expanded={tabsOpen}
                  aria-label={`Workspace tabs: ${activeService?.label || 'Workspace'}`}
                  onClick={() => { setTabsOpen((v) => !v); setPickerOpen(false) }}>
            {activeService?.label || 'Workspace'} ▾
          </button>
          <div className={`wb-tabs ${tabsOpen ? 'is-open' : ''}`} data-testid="wb-tabs">
            {tabs.map(({ id, service }) => (
              <div key={id} className={`wb-tab ${id === active ? 'is-active' : ''}`}>
                <button type="button" className="wb-tab-btn" data-testid={`wb-tab-${id}`}
                        aria-current={id === active ? 'page' : undefined}
                        onClick={() => { activate(id); setPickerOpen(false); setTabsOpen(false) }}>
                  {service.label}
                </button>
                <button type="button" className="wb-tab-close" data-testid={`wb-close-${id}`}
                        aria-label={`Close ${service.label}`}
                        onClick={() => close(id)}>×</button>
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-sm wb-add" data-testid="wb-add"
                  aria-haspopup="menu" aria-expanded={pickerOpen}
                  onClick={() => { setPickerOpen((v) => !v); setTabsOpen(false) }}>
            + Service
          </button>
        </div>

        {pickerOpen && (
          <div className="wb-picker glass glass-panel-raised" role="menu" data-testid="wb-picker">
            {available.length === 0 && <div className="wb-muted">Every service is already open.</div>}
            {available.map((service) => (
              <button key={service.id} type="button" className="wb-picker-item" role="menuitem"
                      data-testid={`wb-open-${service.id}`}
                      onClick={() => { openService(service.id); setPickerOpen(false) }}>
                <span>{service.label}</span>
                <span className="wb-muted">{service.group} · {service.workspaceType}</span>
              </button>
            ))}
          </div>
        )}

        <div className="wb-outlet glass" data-testid="wb-outlet">
          {tabs.map(({ id, service }) => {
            const Component = WORKSPACES[id]
            return (
              <div key={id} className="wb-tabpanel" hidden={id !== active}
                   data-testid={`wb-panel-${id}`} data-service={id}>
                {Component && visited.has(id) ? <Component /> : (Component ? null : <NotWired service={service} />)}
              </div>
            )
          })}
        </div>
      </section>

      <button type="button" className="wb-sheet-toggle" data-testid="wb-sheet-toggle"
              onClick={() => setSheet((s) => (s === 'peek' ? 'half' : s === 'half' ? 'full' : 'peek'))}>
        Bojo · {sheet}
      </button>

      <div className={`wb-sheet is-${sheet}`} data-testid="wb-sheet" data-state={sheet}>
        <div className="wb-sheet-head">
          <span>Bojo</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSheet('peek')}>
            Close
          </button>
        </div>
        {sheet !== 'peek' && (
          <div className="wb-sheet-body">
            <ChatSurface heading="Bojo" sub={`Northstar · ${activeService?.label || 'workspace'}`}
                         onOpenAdvanced={null} />
          </div>
        )}
      </div>

      <button type="button" className="wb-back" onClick={() => navigate('/home')}>← Home</button>
    </div>
  )
}
