// Scene quality tiers (U5).
//
// `still` is a contract, not a preference: phones, reduced-motion and anything
// without WebGL/2D get ONE frame and no animation loop. `reduced` keeps the
// motion but caps the frame rate; `cinematic` is the desktop default.

export const TIERS = ['cinematic', 'reduced', 'still']

export const FPS_CAP = {
  cinematic: 60,
  reduced: 30,
  still: 0, // single frame, then stop
}

export function chooseTier(env = {}) {
  if (env.reducedMotion) return 'still'
  if (env.webgl === false) return 'still'
  if (env.saveData) return 'still'
  if (env.width && env.width <= 760) return 'reduced'
  if (env.coarsePointer) return 'reduced'
  if (typeof env.deviceMemory === 'number' && env.deviceMemory <= 4) return 'reduced'
  if (typeof env.hardwareConcurrency === 'number' && env.hardwareConcurrency <= 4) return 'reduced'
  return 'cinematic'
}

/** Read the environment once, defensively: any missing API degrades downward. */
export function probeEnvironment(win = typeof window !== 'undefined' ? window : null) {
  if (!win) return { webgl: false, reducedMotion: true }
  let reducedMotion = false
  try {
    reducedMotion = !!(win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches)
  } catch { reducedMotion = false }
  let webgl = true
  try {
    const probe = win.document && win.document.createElement('canvas')
    webgl = !!(probe && (probe.getContext('2d') || probe.getContext('webgl')))
  } catch { webgl = false }
  let coarsePointer = false
  try {
    coarsePointer = !!(win.matchMedia && win.matchMedia('(pointer: coarse)').matches)
  } catch { coarsePointer = false }
  return {
    reducedMotion,
    webgl,
    width: win.innerWidth || 0,
    coarsePointer,
    deviceMemory: win.navigator ? win.navigator.deviceMemory : undefined,
    hardwareConcurrency: win.navigator ? win.navigator.hardwareConcurrency : undefined,
    saveData: win.navigator ? win.navigator.connection && win.navigator.connection.saveData : undefined,
  }
}
