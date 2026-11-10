// The chat turn body, and the one part of it the shell owns: the open tab.
//
// ux-07 made the shell publish what it can see about the selected workspace tab
// (`tabSummary` in shell/tabRoutes.js) three ways: a `data-tab-summary`
// attribute on the shell frame, `globalThis.__northstarWorkspaceTab`, and a
// `northstar:workspace-tab` event. Read here at send time — the attribute first
// because React writes it during render, the global as the fallback — so a turn
// carries the page the operator is actually looking at.
//
// The published summary is bigger than a model needs and says nothing about
// page content the shell cannot read (it deliberately does not invent state).
// This module narrows it to the four facts a sentence about the page needs:
// `{ id, route, title, state }`. No DOM dump, and no tab at all when the
// location is not a workspace — an absent field means "no tabs", which is a
// different statement from a tab with nothing in it.

/** Narrow the shell's published summary to `{ id, route, title, state }`, or undefined. */
export function tabContextFromSummary(summary) {
  if (!summary || typeof summary !== 'object') return undefined
  const id = typeof summary.tabId === 'string' ? summary.tabId : ''
  if (!id) return undefined

  const path = typeof summary.path === 'string' ? summary.path : ''
  const search = typeof summary.search === 'string' ? summary.search : ''

  // The state digest is only what the shell recorded: the workspace's own
  // view/filters and which other workspaces are open. Scroll offset is a UI
  // detail the model cannot use, so it is not forwarded.
  const state = {}
  if (summary.view) state.view = summary.view
  if (summary.query && Object.keys(summary.query).length) state.query = { ...summary.query }
  if (Array.isArray(summary.openTabs)) {
    const openTabs = summary.openTabs.map((t) => (t && t.id ? t.id : '')).filter(Boolean)
    if (openTabs.length) state.openTabs = openTabs
  }
  if (Number.isFinite(summary.tabCount)) state.tabCount = summary.tabCount

  return {
    id,
    route: `${path}${search}`,
    title: summary.label || summary.serviceId || id,
    state,
  }
}

/**
 * Read the tab the shell published, if any.
 *
 * `doc`/`glob` are injectable so this is testable without a browser. Both are
 * optional and a location that is not a workspace simply publishes no tab.
 */
export function readPublishedTab(
  doc = typeof document !== 'undefined' ? document : null,
  glob = typeof globalThis !== 'undefined' ? globalThis : null,
) {
  // The DOM attribute is written during the shell's render, so it is the
  // freshest view when a turn is sent straight after a switch.
  try {
    const attr = doc && typeof doc.querySelector === 'function'
      ? doc.querySelector('[data-tab-summary]')?.getAttribute('data-tab-summary')
      : ''
    if (attr) return tabContextFromSummary(JSON.parse(attr))
  } catch { /* unreadable attribute: fall through to the global */ }

  try {
    return tabContextFromSummary(glob?.__northstarWorkspaceTab)
  } catch { return undefined }
}

/**
 * Build the body for one chat turn.
 *
 * `tab` is added only when a workspace tab is open; `canvas` only when the
 * workbench published one. Both are omitted rather than `null`/`{}` so the
 * receiver can tell "nothing open" apart from "open but empty".
 */
export function buildTurnBody({
  content,
  think = true,
  media = 'auto',
  thinking = 'standard',
  mode = 'standard',
  style = 'balanced',
  attachments = [],
  canvas = undefined,
  tab = undefined,
} = {}) {
  const body = {
    content,
    think,
    media,
    thinking,
    mode,
    style,
    attachments: Array.isArray(attachments) ? attachments : [],
  }
  if (canvas) body.canvas = canvas
  if (tab) body.tab = tab
  return body
}
