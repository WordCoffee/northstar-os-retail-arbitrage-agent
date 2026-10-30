import { useState } from 'react'
import { moveItem, dragPreview } from '../lib/reorder.js'

/**
 * Drag-to-reorder with a live placeholder (item 10).
 *
 * Keyboard parity is not optional: Alt+ArrowUp/Down moves the focused row, so
 * reordering works without a pointer. The drag preview is computed by the same
 * pure function the tests cover, so the placeholder slot and the committed order
 * can never disagree.
 */
export default function Reorderable({
  items = [],
  onReorder,
  renderItem,
  label = 'Reorderable list',
}) {
  const [dragIndex, setDragIndex] = useState(null)
  const [overIndex, setOverIndex] = useState(null)

  const preview = dragIndex !== null && overIndex !== null
    ? dragPreview(items, dragIndex, overIndex)
    : null

  const shown = preview ? preview.items : items

  const commit = (to) => {
    if (dragIndex === null) return
    const next = moveItem(items, dragIndex, to)
    setDragIndex(null)
    setOverIndex(null)
    if (onReorder) onReorder(next)
  }

  const onKeyDown = (event, index) => {
    if (!event.altKey) return
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    const to = event.key === 'ArrowUp' ? index - 1 : index + 1
    if (to < 0 || to >= items.length) return
    if (onReorder) onReorder(moveItem(items, index, to))
  }

  return (
    <ul className="reorderable" aria-label={label}>
      {shown.map((item, index) => (
        <li
          key={item?.id ?? index}
          className={[
            'reorderable__row',
            dragIndex === index ? 'is-dragging' : '',
            preview && preview.placeholderIndex === index ? 'is-placeholder' : '',
          ].filter(Boolean).join(' ')}
          draggable
          tabIndex={0}
          onDragStart={() => { setDragIndex(index); setOverIndex(index) }}
          onDragOver={(e) => { e.preventDefault(); setOverIndex(index) }}
          onDrop={(e) => { e.preventDefault(); commit(index) }}
          onDragEnd={() => { setDragIndex(null); setOverIndex(null) }}
          onKeyDown={(e) => onKeyDown(e, index)}
          data-snap={index}
        >
          <span className="reorderable__grip" aria-hidden="true">⋮⋮</span>
          {renderItem ? renderItem(item, index) : String(item)}
        </li>
      ))}
    </ul>
  )
}
