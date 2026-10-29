// Component 2 — "Velvet Status Banner" (spec §b.2). Focusable informational
// strip: the focus state brightens the top sheen and sharpens the text
// shadow (spec §b.2 / §c.2).

const TONES = { ok: 'ok', warn: 'warn', error: 'error' }

export default function StatusBanner({ tone = 'ok', label, children, ...rest }) {
  const toneClass = TONES[tone] ? ` status-banner--${tone}` : ''
  return (
    <div className={`status-banner${toneClass}`} role="status" tabIndex={0} {...rest}>
      <span className="status-banner-dot" aria-hidden="true" />
      <span className="status-banner-label">{label}</span>
      <span className="status-banner-text">{children}</span>
    </div>
  )
}
