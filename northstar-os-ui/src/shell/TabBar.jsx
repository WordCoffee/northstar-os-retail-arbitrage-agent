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

import { useRef } from 'react'

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
                aria-label={`Close ${tab.label} tab`}
                title={`Close ${tab.label}`}
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
    </div>
  )
}
