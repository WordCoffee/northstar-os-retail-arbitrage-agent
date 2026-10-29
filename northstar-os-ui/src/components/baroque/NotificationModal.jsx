// Component 5 — "Theatrical Notification Modal" (spec §b.5).
// Curtain + marble panel. The curtain is a sibling overlay (not the panel's
// ::before) because the panel's translate(-50%,-50%) transform makes it a
// containing block that would shrink a position:fixed ::before to the panel
// box — the sibling keeps the spec's full-stage curtain.

import { useEffect } from 'react'

export default function NotificationModal({ open, closing, onClose, title, children, actions }) {
  // Escape closes the modal.
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div
        className={`baroque-curtain${closing ? ' is-closing' : ''}`}
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        className={`notification-modal${closing ? ' is-closing' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <h3 className="baroque-modal-title">{title}</h3>
        <div className="baroque-modal-body">{children}</div>
        {actions && <div className="baroque-modal-actions">{actions}</div>}
      </div>
    </>
  )
}
