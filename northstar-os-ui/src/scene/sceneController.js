// The frame loop (U5) — extracted from the React component so load/unload,
// the frame-rate cap, the still-tier single frame and visibility pausing are
// all provable in a unit test without a browser.

/**
 * @param draw         called with { t, dt, frames } on each painted frame
 * @param fpsCap       60, 30, or 0 for exactly one frame
 * @param requestFrame injected rAF (tests pass a manual scheduler)
 * @param cancelFrame  injected cancel
 */
export function createSceneController({
  draw,
  fpsCap = 60,
  requestFrame,
  cancelFrame,
} = {}) {
  if (typeof draw !== 'function') throw new Error('createSceneController needs a draw function')
  if (typeof requestFrame !== 'function' || typeof cancelFrame !== 'function') {
    throw new Error('createSceneController needs requestFrame/cancelFrame')
  }

  let handle = null
  let last = null
  let running = false
  let paused = false
  let frames = 0

  const budget = () => (fpsCap > 0 ? 1000 / fpsCap : 0)

  function tick(t) {
    if (!running) return
    if (!paused) {
      const due = last === null || t - last >= budget() - 1 // 1 ms tolerance for timer jitter
      if (due) {
        const dt = last === null ? 16 : Math.min(t - last, 250)
        last = t
        draw({ t, dt, frames })
        frames += 1
        if (fpsCap === 0) {
          // still: one frame is the whole scene
          running = false
          handle = null
          return
        }
      }
    }
    handle = requestFrame(tick)
  }

  return {
    start() {
      if (running) return
      running = true
      last = null
      handle = requestFrame(tick)
    },
    stop() {
      running = false
      if (handle != null) {
        cancelFrame(handle)
        handle = null
      }
    },
    pause() {
      paused = true
      last = null
    },
    resume() {
      paused = false
      last = null
    },
    get running() { return running },
    get paused() { return paused },
    get frames() { return frames },
    get looping() { return fpsCap > 0 },
  }
}

/**
 * Bind the visibility contract. Returns the unbind function; the same listener
 * reference is removed, so nothing leaks when a scene unmounts.
 */
export function bindVisibility(win, { onHide, onShow } = {}) {
  if (!win || !win.document || !win.document.addEventListener) return () => {}
  const listener = () => {
    try {
      if (win.document.hidden) { if (onHide) onHide() } else if (onShow) onShow()
    } catch { /* never let a scene listener break the page */ }
  }
  win.document.addEventListener('visibilitychange', listener)
  return () => win.document.removeEventListener('visibilitychange', listener)
}
