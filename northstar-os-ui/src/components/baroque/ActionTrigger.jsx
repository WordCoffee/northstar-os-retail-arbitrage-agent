// Component 4 — "Gilded Call-to-Action Trigger" (spec §b.4).
// Mouse-tracked anisotropic highlight (--mouse-x/--mouse-y via
// LightSourceTracker) + click ripple (spec §c.1 / §c.3).

import { useBaroqueInteractive } from './baroque.js'

export default function ActionTrigger({ label, onClick, variant = 'primary', ...rest }) {
  const ref = useBaroqueInteractive()
  const variantClass = variant === 'ghost' ? ' cta-trigger--ghost' : ''
  return (
    <button ref={ref} className={`cta-trigger${variantClass}`} onClick={onClick} {...rest}>
      {label}
    </button>
  )
}
