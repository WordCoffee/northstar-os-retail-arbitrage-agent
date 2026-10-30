/**
 * Skeleton primitives (work order UI-20, item 5).
 *
 * Skeletons beat spinners only when they mimic the FINAL layout, so these are
 * shape primitives, not a generic shimmer box: callers compose the same grid the
 * loaded content will use. Every wrapper is aria-busy and hides its shapes from
 * the accessibility tree, so a screen reader hears "loading", not twelve divs.
 */
import './skeletons.css'

export function SkeletonLine({ width = '100%', height }) {
  return <div className="skel skel-line" style={{ width, height }} />
}

export function SkeletonBlock({ ratio = '16 / 9', radius }) {
  return <div className="skel skel-block" style={{ aspectRatio: ratio, borderRadius: radius }} />
}

export function SkeletonAvatar({ size = 32 }) {
  return <div className="skel skel-avatar" style={{ width: size, height: size }} />
}

/** A card: avatar + two text lines + a block. The shape of most list rows. */
export function SkeletonCard({ lines = 2 }) {
  return (
    <div className="skel-card">
      <div className="skel-card-head">
        <SkeletonAvatar />
        <div className="skel-card-lines">
          <SkeletonLine width="40%" />
          <SkeletonLine width="20%" />
        </div>
      </div>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? '72%' : '100%'} />
      ))}
    </div>
  )
}

export function SkeletonRows({ count = 3, lines = 2 }) {
  return (
    <div className="skel-stack" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} lines={lines} />)}
    </div>
  )
}

export function SkeletonGrid({ count = 6, ratio = '4 / 3' }) {
  return (
    <div className="skel-grid" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: count }).map((_, i) => <SkeletonBlock key={i} ratio={ratio} />)}
    </div>
  )
}

export default SkeletonRows
