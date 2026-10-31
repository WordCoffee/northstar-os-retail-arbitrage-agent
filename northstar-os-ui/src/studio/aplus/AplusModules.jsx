import { useEffect, useRef, useState } from 'react'
import { APLUS_METRICS, copyBandRect, tileOffsets } from './metrics.js'
import './aplus.css'

/**
 * Amazon A+ module renderers (Phase 1, item 1).
 *
 * Each module renders at its EXACT canvas size and is then scaled as one block,
 * so layout is never re-flowed and copy never re-wraps differently on a phone
 * (Amazon scales A+ inside a fixed column; it does not reflow it).
 *
 * Scale is measured, not guessed: a ResizeObserver on the frame gives the real
 * available width.
 */
function useFitScale(designWidth) {
  const ref = useRef(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const measure = () => {
      const available = el.clientWidth || designWidth
      setScale(Math.min(1, Math.max(0.3, available / designWidth)))
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [designWidth])

  return { ref, scale }
}

function Frame({ kind, children, imageUrl, imageAlt = '' }) {
  const { w, h } = APLUS_METRICS.canvas[kind]
  const { ref, scale } = useFitScale(w)
  return (
    <div className="aplus-frame" ref={ref} style={{ height: Math.round(h * scale) }}>
      <div
        className="aplus-canvas"
        style={{ width: w, height: h, transform: `scale(${scale})` }}
        role="img"
        aria-label={`A+ module: ${kind}`}
        data-module={kind}
        data-design-width={w}
        data-design-height={h}
      >
        {imageUrl ? <img className="aplus-image" src={imageUrl} alt={imageAlt} /> : <div className="aplus-plate" />}
        {children}
      </div>
    </div>
  )
}

/** Standard image header with text: 970x600, copy band on one side. */
export function HeaderModule({ headline, body, imageUrl, imageAlt, copySide = 'left' }) {
  const band = copyBandRect('header', copySide)
  return (
    <Frame kind="header" imageUrl={imageUrl} imageAlt={imageAlt}>
      <div
        className={`aplus-copy aplus-copy--${band.align}`}
        style={{ left: band.x, top: 0, width: band.w, height: band.h }}
      >
        {headline && <h2 className="aplus-h">{headline}</h2>}
        {body && <p className="aplus-p">{body}</p>}
      </div>
    </Frame>
  )
}

/** Standard three-image module: three 300x300 tiles, 20px gap, centred. */
export function ThreeFeature({ items = [], imageUrl }) {
  const offsets = tileOffsets('three_tiles')
  const { w, h } = APLUS_METRICS.tile.three_tiles
  return (
    <Frame kind="three_tiles" imageUrl={imageUrl}>
      {offsets.map((x, i) => {
        const item = items[i] || {}
        return (
          <div key={i} className="aplus-tile" style={{ left: x, top: 0, width: w, height: h }}>
            {item.imageUrl
              ? <img className="aplus-tile-img" src={item.imageUrl} alt={item.alt || ''} />
              : <div className="aplus-plate aplus-plate--tile" />}
            {item.label && <span className="aplus-tile-label">{item.label}</span>}
          </div>
        )
      })}
    </Frame>
  )
}

/** Comparison chart: 970x600, 90px header, 250px label column, two 360px columns. */
export function ComparisonChart({ columns = [], rows = [], imageUrl }) {
  const { w, h } = APLUS_METRICS.canvas.comparison
  const { labelW, headerH, rows: rowCount } = APLUS_METRICS.comparison
  const colW = Math.floor((w - labelW) / 2)
  const rowH = Math.floor((h - headerH) / rowCount)
  return (
    <Frame kind="comparison" imageUrl={imageUrl}>
      <div className="aplus-comp-header" style={{ left: 0, top: 0, width: w, height: headerH }}>
        {columns.slice(0, 2).map((c, i) => (
          <span key={i} className="aplus-comp-title" style={{ left: labelW + i * colW, width: colW }}>
            {c}
          </span>
        ))}
      </div>
      {rows.slice(0, rowCount).map((row, r) => (
        <div key={r} className="aplus-comp-row" style={{ top: headerH + r * rowH, height: rowH }}>
          <span className="aplus-comp-label" style={{ left: 0, width: labelW }}>{row.label}</span>
          {[row.a, row.b].map((value, i) => (
            <span key={i} className="aplus-comp-cell" style={{ left: labelW + i * colW, width: colW }}>
              {value}
            </span>
          ))}
        </div>
      ))}
    </Frame>
  )
}

export function AplusModule({ kind, ...props }) {
  if (kind === 'header') return <HeaderModule {...props} />
  if (kind === 'three_tiles') return <ThreeFeature {...props} />
  if (kind === 'comparison') return <ComparisonChart {...props} />
  return <Frame kind={kind} imageUrl={props.imageUrl}>{null}</Frame>
}

export default AplusModule
