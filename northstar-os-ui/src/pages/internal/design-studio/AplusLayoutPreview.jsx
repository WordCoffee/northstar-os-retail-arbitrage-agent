import { useState } from 'react'
import { HeaderModule, ThreeFeature, ComparisonChart } from '../../../studio/aplus/AplusModules.jsx'
import { APLUS_METRICS } from '../../../studio/aplus/metrics.js'

/**
 * Live geometry preview for the A+ modules (Phase 1 mounting).
 *
 * This is not a mock: the modules below are the same components that render a
 * real module, placed at their exact Amazon canvas size and scaled as one block.
 * Editing the copy here proves the safe area and the copy band before any asset
 * is rendered, which is the point of having geometry computed rather than
 * hand-placed.
 */
export default function AplusLayoutPreview() {
  const [headline, setHeadline] = useState('Organic Lion’s Mane, stone-ground in small batches')
  const [body, setBody] = useState('Fruiting body only. No mycelium, no fillers, no added sugar — 60 servings per pouch.')
  const [imageUrl, setImageUrl] = useState('')
  const [labels, setLabels] = useState(['Fruiting body', 'Third-party tested', '60 servings'])
  const [rows, setRows] = useState([
    { label: 'Fruiting body only', a: 'Yes', b: 'No' },
    { label: 'Added fillers', a: 'None', b: 'Maltodextrin' },
    { label: 'Servings per pouch', a: '60', b: '30' },
    { label: 'Third-party tested', a: 'Every batch', b: 'Unstated' },
  ])

  const setLabel = (i, v) => setLabels((prev) => prev.map((x, j) => (j === i ? v : x)))

  return (
    <div className="ds-aplus-layout" style={{ display: 'grid', gap: 28, paddingTop: 8 }}>
      <section>
        <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
          <h3 style={{ margin: 0 }}>Header — {APLUS_METRICS.canvas.header.w}×{APLUS_METRICS.canvas.header.h}</h3>
          <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
            copy band {Math.round(APLUS_METRICS.copyBand * 100)}% · inset {APLUS_METRICS.safeInset}px
          </span>
        </header>
        <div style={{ display: 'grid', gap: 8, margin: '10px 0 14px' }}>
          <input className="field" value={headline} maxLength={160} onChange={(e) => setHeadline(e.target.value)}
                 aria-label="Header headline" />
          <textarea className="field" rows={2} value={body} maxLength={1000} onChange={(e) => setBody(e.target.value)}
                    aria-label="Header body" />
          <input className="field" value={imageUrl} placeholder="Optional image URL (/api/assets/... or https://)"
                 onChange={(e) => setImageUrl(e.target.value)} aria-label="Header image URL" />
        </div>
        <HeaderModule headline={headline} body={body} imageUrl={imageUrl || undefined} imageAlt="Preview plate" />
      </section>

      <section>
        <h3 style={{ margin: 0 }}>Three feature — {APLUS_METRICS.canvas.three_tiles.w}×{APLUS_METRICS.canvas.three_tiles.h}</h3>
        <p style={{ fontSize: 12, color: 'var(--ink-soft)', margin: '4px 0 10px' }}>
          three {APLUS_METRICS.tile.three_tiles.w}×{APLUS_METRICS.tile.three_tiles.h} tiles, {APLUS_METRICS.tile.three_tiles.gap}px gaps, centred
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
          {labels.map((label, i) => (
            <input key={i} className="field" value={label} onChange={(e) => setLabel(i, e.target.value)}
                   aria-label={`Tile ${i + 1} label`} />
          ))}
        </div>
        <ThreeFeature items={labels.map((label) => ({ label }))} />
      </section>

      <section>
        <h3 style={{ margin: 0 }}>Comparison chart — {APLUS_METRICS.canvas.comparison.w}×{APLUS_METRICS.canvas.comparison.h}</h3>
        <p style={{ fontSize: 12, color: 'var(--ink-soft)', margin: '4px 0 10px' }}>
          header {APLUS_METRICS.comparison.headerH}px · label column {APLUS_METRICS.comparison.labelW}px · {APLUS_METRICS.comparison.rows} rows
        </p>
        <ComparisonChart columns={['Northstar', 'Typical brand']} rows={rows} />
      </section>
    </div>
  )
}
