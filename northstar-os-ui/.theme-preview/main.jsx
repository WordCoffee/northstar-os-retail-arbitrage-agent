import React, { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import GalacticBackdrop from '../src/shell/GalacticBackdrop.jsx'
import { GALACTIC_VARIANTS, variantById } from '../src/shell/galacticVariants.js'
import '../src/styles/galactic.css'
import '../src/galactic/galactic.css'
import './preview.css'

function App() {
  const initial = useMemo(() => {
    const wanted = new URLSearchParams(window.location.search).get('galactic')
    return variantById(wanted) || GALACTIC_VARIANTS[0]
  }, [])
  const [variant, setVariant] = useState(initial)

  return (
    <div className="galactic-preview">
      <GalacticBackdrop themeId="auto" variant={variant} maxDpr={1.25} />
      <div className="galactic-preview-scrim" />
      <main className="galactic-preview-content">
        <header className="galactic-preview-head">
          <div>
            <p className="galactic-preview-kicker">NORTHSTAR OS</p>
            <h1>Galactic themes</h1>
            <p className="galactic-preview-sub">
              Ten complete looks: scene physics, surface material and layout.
            </p>
          </div>
          <span className="galactic-preview-badge">LIVE PREVIEW</span>
        </header>

        <section className="galactic-preview-stage" aria-label="Theme preview">
          <div className="galactic-preview-panel">
            <span className="galactic-preview-label">CURRENT LOOK</span>
            <h2>{variant.name}</h2>
            <p>{variant.intent}</p>
            <div className="galactic-preview-swatches">
              <span style={{ background: variant.surface.accent }} />
              <span style={{ background: variant.surface.panel }} />
              <span style={{ background: variant.surface.border }} />
            </div>
            <div className="galactic-preview-metrics">
              <div><strong>PLATE</strong><span>FLUX 3 · {variant.motion.duration}s drift</span></div>
              <div><strong>MOTION</strong><span>{variant.motion.meteors} meteors · {variant.motion.angle}°</span></div>
              <div><strong>SURFACE</strong><span>{variant.surface.radius}px glass / {variant.surface.blur}px blur</span></div>
              <div><strong>LAYOUT</strong><span>{variant.layout.rail} rail · {variant.layout.chip} chips</span></div>
            </div>
          </div>
          <div className="galactic-preview-note">
            <p>This is a read-only theme preview. No account, data or controls are exposed.</p>
            <p>Use the swatches below to compare all ten variants.</p>
          </div>
        </section>

        <section className="galactic-preview-picker" aria-label="Choose a Galactic theme">
          {GALACTIC_VARIANTS.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className={item.id === variant.id ? 'is-active' : ''}
              onClick={() => setVariant(item)}
              title={item.intent}
            >
              <span className="galactic-preview-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="galactic-preview-name">{item.name}</span>
              <span className="galactic-preview-chip" style={{ background: item.surface.accent }} />
            </button>
          ))}
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
