import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import ShellModeToggle from '../components/ShellModeToggle.jsx'
import DensityToggle from '../components/DensityToggle.jsx'

/**
 * Settings dialog (2026-10-30).
 *
 * The view switch used to sit in the top navigation, which made a preference
 * look like a primary action and put an entitlement-gated control in the most
 * crowded strip of the app. It lives here now, next to the other presentation
 * preferences.
 *
 * Modal rules: Escape closes, focus moves in and returns to the opener, the
 * backdrop is click-to-close, and the panel is labelled for screen readers.
 */
export default function SettingsModal({ open, onClose }) {
  const panelRef = useRef(null)
  const returnTo = useRef(null)
  const [tab, setTab] = useState('presentation')

  useEffect(() => {
    if (!open) return undefined
    returnTo.current = document.activeElement
    const t = setTimeout(() => {
      const first = panelRef.current?.querySelector('button, [href], input, select, textarea')
      if (first) first.focus()
    }, 0)
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey) }
  }, [open, onClose])

  useEffect(() => {
    if (open) return
    if (returnTo.current && typeof returnTo.current.focus === 'function') returnTo.current.focus()
  }, [open])

  if (!open) return null

  const TABS = [
    { id: 'presentation', label: 'Presentation' },
    { id: 'view', label: 'View' },
  ]

  return (
    <div className="settings-backdrop" onMouseDown={onClose}>
      <div
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        ref={panelRef}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="settings-head">
          <h2 className="settings-title">Settings</h2>
          <button type="button" className="settings-close" aria-label="Close settings" onClick={onClose}>
            <Icon name="x" size={16} />
          </button>
        </header>

        <div className="settings-tabs" role="tablist" aria-label="Settings sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`settings-tab ${tab === t.id ? 'is-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'presentation' && (
          <section className="settings-body" aria-label="Presentation">
            <div className="settings-row">
              <div>
                <p className="settings-row-title">View density</p>
                <p className="settings-row-hint">Row height and padding across lists and rooms.</p>
              </div>
              <DensityToggle />
            </div>
          </section>
        )}

        {tab === 'view' && (
          <section className="settings-body" aria-label="View">
            <div className="settings-row">
              <div>
                <p className="settings-row-title">Advanced view</p>
                <p className="settings-row-hint">
                  Inspectors, layer geometry, guides and raw prompt fields. Requires a plan that
                  includes the advanced view.
                </p>
              </div>
              <ShellModeToggle />
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
