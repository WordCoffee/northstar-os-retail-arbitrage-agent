// The only canvas in the workbench (U5).
//
// One scene at a time: this component owns a single <canvas>, the controller
// owns one animation frame handle, and unmounting cancels both. The tier decides
// the frame cap (`still` paints one frame and stops), visibilitychange pauses the
// loop so a background tab costs nothing, and the event bus changes the mood.

import { useEffect, useRef, useState } from 'react'

import { chooseTier, FPS_CAP, probeEnvironment } from '../lib/sceneTiers.js'
import { modeForEvent, sceneBus } from '../lib/sceneBus.js'
import { createSceneController, bindVisibility } from './sceneController.js'
import { createScene } from './scenes.js'
import './scene.css'

export default function SceneHost({ sceneId = 'default' }) {
  const canvasRef = useRef(null)
  const modeRef = useRef('calm')
  const controllerRef = useRef(null)
  const [tier] = useState(() => (
    typeof window === 'undefined' ? 'still' : chooseTier(probeEnvironment())
  ))
  const [mode, setMode] = useState('calm')

  // Workspace events re-tone the scene. Subscribed once, unsubscribed on unmount.
  useEffect(() => {
    const unsubscribe = sceneBus.subscribe((event) => {
      const next = modeForEvent(event)
      modeRef.current = next
      setMode(next)
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d')
    if (!ctx) return undefined

    const field = createScene(sceneId, {
      width: window.innerWidth,
      height: window.innerHeight,
      density: tier === 'cinematic' ? 9000 : 16000,
    })
    // Phone GPUs are software-rendered in some browsers; one device pixel per
    // CSS pixel on the reduced tier is the difference between a scene and a slide.
    const dpr = tier === 'cinematic' ? Math.min(1.5, window.devicePixelRatio || 1) : 1

    const resize = () => {
      const w = window.innerWidth
      const h = window.innerHeight
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      field.resize(w, h)
      // The still tier has no loop, so a resize (phone rotation) must repaint
      // once or the canvas is left stretched and stale.
      const c = controllerRef.current
      if (c && !c.looping) c.start()
    }
    resize()
    window.addEventListener('resize', resize)

    const controller = createSceneController({
      fpsCap: FPS_CAP[tier] ?? 30,
      requestFrame: (cb) => window.requestAnimationFrame(cb),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
      draw: ({ dt, t }) => field.draw(ctx, { dt, t, mode: modeRef.current }),
    })
    controllerRef.current = controller
    controller.start()

    const unbind = bindVisibility(window, {
      onHide: () => controller.pause(),
      onShow: () => controller.resume(),
    })

    if (import.meta.env.DEV) {
      window.__northstarScene = {
        tier,
        get frames() { return controller.frames },
        get running() { return controller.running },
        get paused() { return controller.paused },
        emit: (event) => sceneBus.emit(event),
        get mode() { return modeRef.current },
        stop: () => controller.stop(),
      }
    }

    return () => {
      window.removeEventListener('resize', resize)
      unbind()
      controller.stop()
      controllerRef.current = null
      if (import.meta.env.DEV) delete window.__northstarScene
    }
  }, [tier, sceneId])

  return (
    <div className="wb-scene" data-testid="scene-host" data-scene={sceneId}
         data-tier={tier} data-mode={mode} aria-hidden="true">
      <canvas ref={canvasRef} className="wb-scene-canvas" data-testid="scene-canvas" />
    </div>
  )
}
