// Component 3 — "Marble Ambient Backdrop" (spec §b.3) + the global SVG
// filter bank (spec §b.1 / §d.1). The filters live in one hidden <svg> so
// every component can reference them by id.

export function BaroqueFilters() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
      <defs>
        <filter id="micro-surface-noise" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>
  )
}

// Fixed full-screen backdrop. `dimmed` darkens it to 0.8 while a modal is
// open (spec §b.3 interaction).
export default function BaroqueBackdrop({ dimmed = false }) {
  return (
    <div className={`ambient-backdrop${dimmed ? ' is-dimmed' : ''}`} aria-hidden="true">
      <div className="baroque-shaft" />
    </div>
  )
}
