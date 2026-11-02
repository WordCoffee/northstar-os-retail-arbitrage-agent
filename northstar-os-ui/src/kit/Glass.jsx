// The glass kit (U4): the small set of surfaces every service workspace is built
// from. They read the theme variables emitted by `lib/serviceThemes.js` and own no
// colours of their own, so a service switch re-skins them without a re-render
// contract and a contrast test covers all of them at once.

import { forwardRef } from 'react'

function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

export const GlassPanel = forwardRef(function GlassPanel(
  { as: Tag = 'section', tone = 'panel', className, children, ...rest }, ref,
) {
  return (
    <Tag ref={ref} className={cx('glass', `glass-${tone}`, className)} {...rest}>
      {children}
    </Tag>
  )
})

export function GlassTab({ active = false, className, children, ...rest }) {
  return (
    <button
      type="button"
      className={cx('glass-tab', active && 'is-active', className)}
      aria-current={active ? 'page' : undefined}
      {...rest}
    >
      {children}
    </button>
  )
}

export function GlassButton({ variant = 'ghost', className, children, ...rest }) {
  return (
    <button type="button" className={cx('glass-btn', `is-${variant}`, className)} {...rest}>
      {children}
    </button>
  )
}

export const GlassInput = forwardRef(function GlassInput({ className, ...rest }, ref) {
  return <input ref={ref} className={cx('glass-input', className)} {...rest} />
})

/**
 * A vertical tool rail. `items` are `{ id, label, icon? }`; the rail never
 * invents an entry, and an empty list renders nothing rather than an empty box.
 */
export function ToolRail({ items = [], active = '', onSelect, label = 'Tools', className }) {
  if (!items.length) return null
  return (
    <nav className={cx('glass-rail', className)} aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={cx('glass-rail-item', item.id === active && 'is-active')}
          aria-pressed={item.id === active}
          title={item.label}
          data-testid={`rail-${item.id}`}
          onClick={() => onSelect && onSelect(item.id)}
        >
          {item.icon || null}
          <span className="glass-rail-label">{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
