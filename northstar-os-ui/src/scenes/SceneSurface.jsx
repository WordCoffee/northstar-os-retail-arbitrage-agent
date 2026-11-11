// THE ONE CANVAS.
//
// `SceneSurface` is mounted once by the shell (`ShellLayout` → `SceneHost`), not
// once per page. It renders exactly one of two things:
//
//   • mode "live"    — a single <canvas> driven by `sceneEngine`'s animation loop
//   • mode "static"  — a poster <img> when WebGL2 is unavailable
//   • mode "reduced" — the same poster when prefers-reduced-motion is reduce
//
// The mode is decided at render time by `resolveSceneMode`, so it is already
// correct in the first paint and in server-rendered markup; the effect below
// only starts and stops the loop. Nothing renders an animation loop in the
// static or reduced modes — there is no requestAnimationFrame scheduled at all.
//
// `environment` is injectable on purpose: a test (or a browser lane) can force
// `{ webgl2: false }` and assert `data-scene-mode="static"` without owning a GPU.

import { useEffect, useRef, useState } from 'react'
import {
  SCENE_MODES,
  createSceneHost,
  readSceneEnvironment,
  resolveSceneMode,
} from './sceneEngine.js'
import { sceneForService } from './sceneRegistry.js'
import './scene.css'

/** The document event the bed fires when the scene it paints changes. */
export const SCENE_EVENT = 'northstar:scene'

export default function SceneSurface({
  serviceId = 'home',
  scene: sceneProp = null,
  environment = null,
  onModeChange = null,
}) {
  const scene = sceneProp || sceneForService(serviceId)
  const env = environment || readSceneEnvironment()
  const planned = resolveSceneMode(env)
  const [mode, setMode] = useState(planned)
  const canvasRef = useRef(null)
  const hostRef = useRef(null)
  const lastSceneRef = useRef(null)
  if (!hostRef.current) hostRef.current = createSceneHost()

  // Keep the callback out of the effect's dependency list: the shell passes a
  // setState function, but a plain inline arrow must not restart the loop.
  const notifyRef = useRef(onModeChange)
  notifyRef.current = onModeChange

  useEffect(() => {
    const host = hostRef.current
    if (planned !== SCENE_MODES.LIVE) {
      // No canvas is rendered in this branch, so there is nothing to animate.
      host.unmount()
      setMode(planned)
      if (notifyRef.current) notifyRef.current(planned)
      return undefined
    }
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const { runtime } = host.mount({
      canvas,
      scene,
      environment: env,
    })
    setMode(runtime.mode)
    if (notifyRef.current) notifyRef.current(runtime.mode, runtime.reason)
    return () => { host.unmount() }
  }, [scene.id, planned]) // eslint-disable-line react-hooks/exhaustive-deps

  // WHO CHANGED THE SCENE, AND TO WHAT.
  //
  // The bed is the one place a scene swap happens, so it is the one place that
  // can say so truthfully. The event carries the scene the registry resolved
  // (id, variant, label) and the mode the engine settled on, and it is
  // dispatched ONLY when that identity changes — not on every render, and not
  // for a mode flip inside the same scene.
  //
  // Why an event and not just the attribute: a listener (a browser lane, the
  // workspace frame, a future scene-aware tool) has to react to the change.
  // `data-scene-id` on the bed is the state; `northstar:scene` is the transition.
  useEffect(() => {
    const detail = {
      serviceId: scene.serviceId,
      sceneId: scene.id,
      variantId: scene.variantId,
      label: scene.label,
      mode,
      swappedFrom: lastSceneRef.current,
      at: new Date().toISOString(),
    }
    lastSceneRef.current = scene.id
    try { globalThis.__northstarScene = detail } catch { /* no global: not fatal */ }
    const doc = globalThis.document
    if (!doc || typeof doc.dispatchEvent !== 'function' || typeof globalThis.CustomEvent !== 'function') {
      return
    }
    doc.dispatchEvent(new globalThis.CustomEvent(SCENE_EVENT, { detail }))
  }, [scene.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // A background tab must not keep painting. The shell owns the only canvas, so
  // this is the single place frames are suspended.
  useEffect(() => {
    const doc = globalThis.document
    if (!doc || typeof doc.addEventListener !== 'function') return undefined
    const onVisibility = () => {
      const runtime = hostRef.current && hostRef.current.current
      if (!runtime) return
      if (doc.visibilityState === 'hidden') runtime.pause()
      else runtime.resume()
    }
    doc.addEventListener('visibilitychange', onVisibility)
    return () => doc.removeEventListener('visibilitychange', onVisibility)
  }, [])

  const live = mode === SCENE_MODES.LIVE
  return (
    <div
      className="scene-bed"
      role="presentation"
      aria-hidden="true"
      data-testid="scene-bed"
      data-scene-id={scene.id}
      data-scene-variant={scene.variantId}
      data-scene-label={scene.label}
      data-scene-mode={mode}
      data-scene-animated={live ? 'true' : 'false'}
    >
      {live ? (
        <canvas
          ref={canvasRef}
          className="scene-canvas"
          data-testid="scene-canvas"
          aria-hidden="true"
        />
      ) : (
        <img
          className="scene-poster"
          src={scene.poster}
          alt=""
          draggable="false"
          data-testid="scene-poster"
          data-scene-poster={scene.variantId}
        />
      )}
    </div>
  )
}
