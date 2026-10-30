import { useCallback, useEffect, useRef, useState } from 'react'
import { visibleRange } from '../lib/virtual.js'

/**
 * Windowed list (item 9). Only the rows inside the viewport (plus overscan) are
 * mounted, so a 10k-line log scrolls at frame rate instead of choking the
 * reconciler.
 *
 * Fixed row height on purpose: measured heights turn scrolling into a layout
 * read per frame. Callers with variable content should clamp to one line.
 */
export default function VirtualList({
  items = [],
  rowHeight = 40,
  height = 320,
  overscan = 4,
  renderRow,
  className = '',
  ariaLabel = 'Virtualised list',
}) {
  const ref = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [viewport, setViewport] = useState(height)

  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const onScroll = () => setScrollTop(el.scrollTop)
    el.addEventListener('scroll', onScroll, { passive: true })
    setViewport(el.clientHeight || height)
    const ro = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(() => setViewport(el.clientHeight || height))
      : null
    if (ro) ro.observe(el)
    return () => {
      el.removeEventListener('scroll', onScroll)
      if (ro) ro.disconnect()
    }
  }, [height])

  const range = visibleRange({
    scrollTop, viewport, rowHeight, count: items.length, overscan,
  })

  const row = useCallback((item, index) => renderRow(item, index), [renderRow])
  const slice = items.slice(range.start, range.end)

  return (
    <div
      ref={ref}
      className={`vlist ${className}`.trim()}
      style={{ height, overflowY: 'auto', position: 'relative' }}
      role="list"
      aria-label={ariaLabel}
      aria-rowcount={items.length}
    >
      <div style={{ height: range.total, position: 'relative' }}>
        <div style={{ transform: `translateY(${range.offset}px)` }}>
          {slice.map((item, i) => (
            <div role="listitem" key={range.start + i} style={{ height: rowHeight, overflow: 'hidden' }}>
              {row(item, range.start + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
