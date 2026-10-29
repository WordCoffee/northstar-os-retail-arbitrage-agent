// Baroque interactivity — LightSourceTracker, RippleEffect, ModalManager
// per spec §(d).1, rAF-throttled per §(d).2.

// ── LightSourceTracker (spec §d.4, rAF-throttled per §d.2) ──
// Tracks the cursor over an element and updates --mouse-x/--mouse-y on that
// element, plus the stage-wide --light-source-x/----light-source-y on the
// document root (spec §c.1: the cursor acts as the light source).
export class LightSourceTracker {
  constructor(element, { onMove } = {}) {
    this.element = element
    this.onMove = onMove
    this._pending = null
    this._raf = 0
    this._handler = (e) => {
      this._pending = e
      if (!this._raf) this._raf = requestAnimationFrame(() => this._flush())
    }
    element.addEventListener('mousemove', this._handler)
  }

  _flush() {
    this._raf = 0
    const e = this._pending
    this._pending = null
    if (!e) return
    const rect = this.element.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    this.element.style.setProperty('--mouse-x', `${x.toFixed(2)}%`)
    this.element.style.setProperty('--mouse-y', `${y.toFixed(2)}%`)
    const root = document.documentElement
    root.style.setProperty('--light-source-x', `${x.toFixed(2)}%`)
    root.style.setProperty('--light-source-y', `${y.toFixed(2)}%`)
    if (this.onMove) this.onMove(x, y)
  }

  destroy() {
    this.element.removeEventListener('mousemove', this._handler)
    if (this._raf) cancelAnimationFrame(this._raf)
    this._raf = 0
    this._pending = null
  }
}

// ── RippleEffect (spec §d.4) ──
// On click, spawns a .ripple span at the click point; removed after the
// 0.5s expansion finishes.
export class RippleEffect {
  constructor(element) {
    this.element = element
    this._handler = (e) => this.trigger(e)
    element.addEventListener('click', this._handler)
  }

  trigger(e) {
    const rect = this.element.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const ripple = document.createElement('span')
    ripple.className = 'ripple'
    ripple.style.left = `${x}px`
    ripple.style.top = `${y}px`
    this.element.appendChild(ripple)
    setTimeout(() => {
      if (ripple.parentNode) ripple.parentNode.removeChild(ripple)
    }, 500)
  }

  destroy() {
    this.element.removeEventListener('click', this._handler)
  }
}

// ── React hooks ──
import { useCallback, useEffect, useRef, useState } from 'react'

// Attaches a LightSourceTracker to the ref'd element.
export function useBaroqueLight(onMove) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const tracker = new LightSourceTracker(el, { onMove })
    return () => tracker.destroy()
  }, [onMove])
  return ref
}

// Attaches both LightSourceTracker and RippleEffect to the same node
// (used by ActionTrigger: cursor highlight + click ripple).
export function useBaroqueInteractive(onMove) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const light = new LightSourceTracker(el, { onMove })
    const ripple = new RippleEffect(el)
    return () => {
      light.destroy()
      ripple.destroy()
    }
  }, [onMove])
  return ref
}

// ── ModalManager (spec §d.1) ──
// Holds the panel mounted through the closing animation so the curtain can
// finish its draw before unmount.
export function useBaroqueModal() {
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const openModal = useCallback(() => {
    setOpen(true)
    setClosing(false)
  }, [])
  const closeModal = useCallback(() => {
    if (!open) return
    setClosing(true)
    setTimeout(() => {
      setOpen(false)
      setClosing(false)
    }, 850)
  }, [open])
  return { open, closing, openModal, closeModal }
}
