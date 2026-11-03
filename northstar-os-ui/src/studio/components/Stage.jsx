// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENTS — CANVAS STAGE
//
// The interactive editing surface: renders a design document, supports layer
// selection by hit-test, drag-to-move, drag-resize, a checkered backdrop,
// optional composition guides, and a floating zoom rail. Purely local — the
// stage never contacts a provider.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { renderDoc } from '../engine/doc.js'
import { snapBox } from '../../lib/studioCanvas.js'

const MIN_ZOOM = 0.2
const MAX_ZOOM = 4

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

export default function Stage({
  doc,
  assets = new Map(),
  selectedId = '',
  zoom = 1,
  onZoomChange,
  grid = null,
  onSelectLayer,
  onChangeLayer,
  onCommitLayer,
  advanced = false,
  badge,
  footer,
  emptyHint,
  minHeight = 260,
  maxHeight = 620,
  // U7: optional Canva-style snapping. Off by default, so the sections that
  // shipped before this unit keep their exact drag behaviour. `onGuides` is
  // called with the guides that actually fired, so the caller draws the line it
  // snapped to rather than a decorative one.
  snap = false,
  onGuides,
  guides = [],
  overlay = null,
}) {
  const wrapRef = useRef(null)
  const canvasRef = useRef(null)
  const [cssW, setCssW] = useState(560)
  const [drag, setDrag] = useState(null)

  // Observe the available width so the canvas fits its column.
  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect?.width || 560
      setCssW(Math.max(240, Math.round(w)))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const aspect = doc && doc.h ? doc.w / doc.h : 1
  const dispH = clamp(Math.round(cssW / aspect), minHeight, Math.max(minHeight, maxHeight))
  const dispW = Math.round(dispH * aspect)

  // ── paint ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !doc) return
    const dpr = Math.min(2, (typeof window !== 'undefined' && window.devicePixelRatio) || 1)
    const pxW = Math.max(1, Math.round(dispW * dpr * zoom))
    const pxH = Math.max(1, Math.round(dispH * dpr * zoom))
    if (canvas.width !== pxW || canvas.height !== pxH) {
      canvas.width = pxW
      canvas.height = pxH
    }
    const ctx = canvas.getContext('2d')
    renderDoc(ctx, doc, { W: pxW, H: pxH, assets, grid })
  }, [doc, assets, dispW, dispH, zoom, grid])

  // ── hit testing / dragging ──
  const toNorm = useCallback((clientX, clientY) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const r = canvas.getBoundingClientRect()
    return {
      x: clamp((clientX - r.left) / r.width, 0, 1),
      y: clamp((clientY - r.top) / r.height, 0, 1),
    }
  }, [])

  const hit = useCallback((nx, ny) => {
    if (!doc) return null
    for (let i = doc.layers.length - 1; i >= 0; i -= 1) {
      const l = doc.layers[i]
      if (l.visible === false || l.locked) continue
      if (l.kind === 'bg') continue
      const w = l.w ?? 0
      const h = l.h ?? 0
      if (nx >= (l.x ?? 0) && nx <= (l.x ?? 0) + w && ny >= (l.y ?? 0) && ny <= (l.y ?? 0) + h) return l
    }
    return null
  }, [doc])

  const selected = doc ? doc.layers.find(l => l.id === selectedId) : null

  const onPointerDown = (e) => {
    if (!doc) return
    const p = toNorm(e.clientX, e.clientY)
    if (!p) return
    const l = hit(p.x, p.y)
    if (!l) { onSelectLayer && onSelectLayer(''); return }
    onSelectLayer && onSelectLayer(l.id)
    if (l.locked) return
    e.currentTarget.setPointerCapture?.(e.pointerId)
    setDrag({ id: l.id, startX: p.x, startY: p.y, ox: l.x ?? 0, oy: l.y ?? 0, mode: 'move' })
  }

  const onPointerMove = (e) => {
    if (!drag || !doc) return
    const p = toNorm(e.clientX, e.clientY)
    if (!p) return
    const dx = p.x - drag.startX
    const dy = p.y - drag.startY
    const rawX = clamp(drag.ox + dx, -0.4, 1.2)
    const rawY = clamp(drag.oy + dy, -0.4, 1.2)
    if (snap) {
      const layer = doc.layers.find(l => l.id === drag.id)
      const box = snapBox(rawX, rawY, layer?.w ?? 0.2, layer?.h ?? 0.2)
      onChangeLayer && onChangeLayer(drag.id, { x: box.x, y: box.y })
      onGuides && onGuides(box.guides)
      return
    }
    onChangeLayer && onChangeLayer(drag.id, { x: rawX, y: rawY })
  }

  const endDrag = () => {
    if (drag) {
      onCommitLayer && onCommitLayer(drag.id)
      setDrag(null)
      onGuides && onGuides([])
    }
  }

  const handleResize = (e) => {
    if (!selected || !doc) return
    e.stopPropagation()
    e.preventDefault()
    const p = toNorm(e.clientX, e.clientY)
    if (!p) return
    const startW = selected.w ?? 0.2
    const startH = selected.h ?? 0.2
    const sx = selected.x ?? 0
    const sy = selected.y ?? 0
    const move = (ev) => {
      const q = toNorm(ev.clientX, ev.clientY)
      if (!q) return
      onChangeLayer && onChangeLayer(selected.id, {
        w: clamp(startW + (q.x - p.x), 0.02, 1),
        h: clamp(startH + (q.y - p.y), 0.02, 1),
      })
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      onCommitLayer && onCommitLayer(selected.id)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  if (!doc) {
    return (
      <div ref={wrapRef} className="stage-empty" style={{ minHeight }}>
        {emptyHint || 'No document open. Create or open a design to edit it here.'}
      </div>
    )
  }

  return (
    <div className="stage" ref={wrapRef}>
      <div className="stage-bar">
        <span className="text-mono stage-dims">{doc.w}×{doc.h}</span>
        {badge}
        <div className="stage-zoom">
          <button className="stage-zoom-btn" title="Zoom out" onClick={() => onZoomChange && onZoomChange(clamp(zoom - 0.25, MIN_ZOOM, MAX_ZOOM))}>−</button>
          <span className="text-mono stage-zoom-val">{Math.round(zoom * 100)}%</span>
          <button className="stage-zoom-btn" title="Zoom in" onClick={() => onZoomChange && onZoomChange(clamp(zoom + 0.25, MIN_ZOOM, MAX_ZOOM))}>+</button>
          <button className="stage-zoom-btn stage-zoom-fit" title="Fit to pane" onClick={() => onZoomChange && onZoomChange(1)}>Fit</button>
        </div>
      </div>

      <div className="stage-canvas-pane" style={{ minHeight }}>
        <div className="stage-checker" style={{ width: dispW * zoom, height: dispH * zoom }}>
          <canvas
            ref={canvasRef}
            className="stage-canvas"
            data-testid="stage-canvas"
            style={{ width: dispW * zoom, height: dispH * zoom }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          />
          {guides.map((g, i) => (
            g.axis === 'x'
              ? <div key={`gx${i}`} className="stage-guide stage-guide-x" style={{ left: `${g.at * 100}%` }} />
              : <div key={`gy${i}`} className="stage-guide stage-guide-y" style={{ top: `${g.at * 100}%` }} />
          ))}
          {overlay}
          {selected && selected.kind !== 'bg' && (
            <div
              className="stage-sel"
              style={{
                left: (selected.x ?? 0) * dispW * zoom,
                top: (selected.y ?? 0) * dispH * zoom,
                width: (selected.w ?? 0) * dispW * zoom,
                height: (selected.h ?? 0) * dispH * zoom,
                transform: selected.rot ? `rotate(${selected.rot}deg)` : undefined,
              }}
            >
              <span className="stage-sel-tag">{selected.name || selected.kind}</span>
              {advanced && !selected.locked && (
                <button className="stage-sel-handle" onPointerDown={handleResize} title="Resize layer" />
              )}
            </div>
          )}
        </div>
      </div>

      {footer && <div className="stage-foot">{footer}</div>}
    </div>
  )
}
