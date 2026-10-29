// Component 1 — "Gilded Control Frame" (spec §b.1). The carved marble plinth
// with gold-leaf inlay that holds the stage's content.

export default function ControlFrame({ title, eyebrow, children }) {
  return (
    <section className="control-frame" tabIndex={0}>
      <div className="control-frame-inner">
        {eyebrow && <div className="baroque-eyebrow">{eyebrow}</div>}
        {title && <h2 className="baroque-frame-title">{title}</h2>}
        {children}
      </div>
    </section>
  )
}
