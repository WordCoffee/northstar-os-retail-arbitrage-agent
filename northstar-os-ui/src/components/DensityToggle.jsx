import { useEffect, useState } from 'react'

/**
 * View density (item 14). Three profiles, one attribute on <html>, persisted.
 *
 * The tokens do the work (tokens.css: --density-*), so switching density never
 * re-renders a page's layout logic - the cascade handles it.
 */
export const DENSITIES = ['compact', 'comfortable', 'spacious']
const KEY = 'northstar.density'
const DEFAULT = 'comfortable'

function read() {
  try {
    const saved = localStorage.getItem(KEY)
    if (DENSITIES.includes(saved)) return saved
  } catch { /* private mode / disabled storage: fall through to default */ }
  return DEFAULT
}

export default function DensityToggle({ compact = false }) {
  const [density, setDensity] = useState(read)

  useEffect(() => {
    document.documentElement.dataset.density = density
    try { localStorage.setItem(KEY, density) } catch { /* non-fatal */ }
  }, [density])

  return (
    <div className="density-toggle" role="group" aria-label="View density">
      {!compact && <span className="density-toggle__label">Density</span>}
      {DENSITIES.map((value) => (
        <button
          key={value}
          type="button"
          className={`density-toggle__btn ${density === value ? 'is-active' : ''}`}
          aria-pressed={density === value}
          onClick={() => setDensity(value)}
        >
          {value.charAt(0).toUpperCase()}
          <span className="sr-only">{value}</span>
        </button>
      ))}
    </div>
  )
}
