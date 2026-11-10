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
