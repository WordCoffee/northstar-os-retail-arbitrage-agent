// The workspace tab strip.
//
// Accessibility shape is the WAI-ARIA tabs pattern with automatic activation:
//   • one `role="tablist"`, one `role="tab"` per open workspace
//   • `aria-selected` on the tab whose panel is showing, `aria-controls` ->
//     the panel id the shell assigns (`wst-panel-<id>`)
//   • roving tabindex: only the active tab is in the Tab order, ArrowLeft/
//     ArrowRight/Home/End move focus AND switch tabs without a mouse
//   • Delete closes the focused tab
//
// The close control is a sibling of the tab, not a button nested inside it:
// interactive elements inside a tab are invalid ARIA, and a nested button
// also swallows the click that should activate the tab.
//
// It is also DECORATIVE for assistive tech (`aria-hidden`, `tabIndex=-1`).
// A tablist may own nothing but tabs, so a real, announced close button living
// inside the strip is an `aria-required-children` violation (impact: critical),
// measured by axe-core on every page with two or more open workspaces:
//
//   aria-required-children  .wst-list
//   "Element has children which are not allowed: button[aria-label]"
//
// The pointer affordance stays exactly where it was visually; the keyboard path
// (Delete on a focused tab, handled below) is the announced one, and the
// tablist's `aria-describedby` says so. See tests/e2e/a11y/tabbar_a11y.spec.ts.

import { useRef } from 'react'

// Visually hidden but announced (same pattern as ShellLayout's SR_ONLY).
const SR_ONLY = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0,0,0,0)',
  whiteSpace: 'nowrap',
  border: 0,
}

function tabButtons(listEl) {
  if (!listEl) return []
  return Array.from(listEl.querySelectorAll('[role="tab"]'))
}

export default function TabBar({ tabs = [], activeId = null, onActivate, onClose }) {
  const listRef = useRef(null)

  if (!tabs.length) return null

  const onKeyDown = (event) => {
    const buttons = tabButtons(listRef.current)
    if (!buttons.length) return
    const onTab = event.target?.getAttribute?.('role') === 'tab'
    const index = buttons.indexOf(document.activeElement)
    const at = index === -1 ? buttons.findIndex((b) => b.getAttribute('aria-selected') === 'true') : index
    const last = buttons.length - 1
    let next = null
    if (event.key === 'ArrowRight') next = buttons[at === last ? 0 : at + 1]
    else if (event.key === 'ArrowLeft') next = buttons[at <= 0 ? last : at - 1]
    else if (event.key === 'Home') next = buttons[0]
    else if (event.key === 'End') next = buttons[last]
    else if (event.key === 'Delete' || event.key === 'Backspace') {
      // Only from a tab itself: Delete on a close button must not close a
      // different (the selected) tab.
      if (!onTab) return
      const id = buttons[at]?.getAttribute('data-tab-id')
      if (id) {
        event.preventDefault()
        onClose(id)
      }
      return
    }
    if (!next) return
    event.preventDefault()
    // Automatic activation: focus moves first (the node keeps its identity),
    // then the shell switches, so focus is never lost in the re-render.
    next.focus()
    const id = next.getAttribute('data-tab-id')
    const tab = tabs.find((t) => t.id === id)
    if (tab) onActivate(tab)
  }

  return (
    <div className="wst-bar" data-testid="workspace-tabs" data-tab-count={tabs.length}>
      <div
        ref={listRef}
        role="tablist"
        aria-label="Open workspaces"
        aria-orientation="horizontal"
        aria-describedby="wst-keys-sr"
        className="wst-list"
        onKeyDown={onKeyDown}
      >
        {tabs.map((tab, index) => {
          const selected = tab.id === activeId
          // On a non-workspace route (/home) nothing is selected; keep the
          // first tab in the Tab order so the strip stays reachable.
          const tabbable = selected || (activeId === null && index === 0)
          return (
            <div
              key={tab.id}
              role="presentation"
              className={`wst-tab${selected ? ' is-active' : ''}`}
              data-testid={`tab-wrap-${tab.id}`}
            >
              <button
                type="button"
                role="tab"
                id={`wst-tab-${tab.id}`}
                data-tab-id={tab.id}
                data-testid={`tab-${tab.id}`}
                aria-selected={selected}
                aria-controls={`wst-panel-${tab.id}`}
                tabIndex={tabbable ? 0 : -1}
                title={tab.href || tab.path}
                className="wst-tab-btn"
                onClick={() => onActivate(tab)}
              >
                <span className="wst-tab-label">{tab.label}</span>
              </button>
              <button
                type="button"
                className="wst-tab-close"
                data-testid={`tab-close-${tab.id}`}
                aria-hidden="true"
                tabIndex={-1}
                title={`Close ${tab.label} (or press Delete on the tab)`}
                onClick={(event) => {
                  event.stopPropagation()
                  onClose(tab.id)
                }}
              >
                ×
              </button>
            </div>
          )
        })}
      </div>
      <span className="wst-hint" aria-hidden="true">← → to switch · Delete to close</span>
      {/* The announced keyboard path, because the × above is pointer-only. */}
      <span id="wst-keys-sr" className="sr-only" style={SR_ONLY}>
        Use the left and right arrow keys to switch workspace tabs; press Delete
        to close the focused tab.
      </span>
    </div>
  )
}
