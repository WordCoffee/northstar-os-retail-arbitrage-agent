// ═══════════════════════════════════════════════════════════════════════════
// GALACTIC BACKDROP — Interstellar scene for the Simple shell.
//
// Replaces the CSS-only backdrop that was live before. The shader in
// galacticShader.js integrates real null geodesics, so the black hole is lensed
// rather than drawn; this component's job is to get that frame on screen at a
// resolution this box can afford and to keep the shell's existing contract.
//
// CONTRACT KEPT (the things that are the same either way):
//   • <canvas data-cosmic-theme data-cosmic-tint> — the focus atmosphere is
//     still observable on the element, still eased, never a hard jump.
//   • prefers-reduced-motion → one static frame, no drift.
//   • WebGL unavailable or context lost → the CSS scene underneath shows, and
//     the reason is written to data-cosmic-fallback / data-cosmic-lost.
//   • pointer-events: none, z-index 0, aria-hidden.
//
// COST: the frame is rendered once per size/theme change, not per animation
// frame. A 1600×900 frame measured 2.1 s including process start in the
// headless harness, so a governed in-browser frame is a few hundred ms. The
// motion the eye sees afterwards is a CSS Ken Burns pan plus film grain; the
// GPU is idle while the operator reads.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef } from 'react'
import CelestialBackdrop from './CelestialBackdrop.jsx'
import { FRAG, VERT } from './galacticShader.js'
import { variantById, applyVariant } from './galacticVariants.js'

// Focus → atmosphere. Identical table to the renderer this replaces, because
// verify-galactic-themes.cjs asserts these exact targets.
export const GALACTIC_THEMES = {
  auto: [1.00, 0.95, 0.86],
  create: [1.00, 0.86, 0.66],
  grow: [0.80, 1.00, 0.86],
  research: [0.74, 0.86, 1.00],
  operate: [0.92, 0.95, 1.00],
  autothink: [0.84, 0.80, 1.00],
}

export const GALACTIC_THEME_IDS = Object.keys(GALACTIC_THEMES)

const MAX_PIXELS = 2_200_000 // protects the GPU shared with ComfyUI/Ollama

function tintFor(id) {
  return GALACTIC_THEMES[id] || GALACTIC_THEMES.auto
}

// Deterministic meteor placement: the same theme looks the same on every load,
// but each theme gets a different field and a different fall direction.
function seeded(seed) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

function MeteorField({ variant }) {
  const motion = variant?.motion || {}
  const meteors = useMemo(() => {
    const count = Math.max(0, Math.min(40, Number(motion.meteors) || 0))
    const seed = String(variant?.id || 'cosmos').split('').reduce((a, c) => a + c.charCodeAt(0), 7)
    const rand = seeded(seed)
    return Array.from({ length: count }, (_, i) => ({
      id: `${variant?.id || 'cosmos'}-${i}`,
      x: Math.round(rand() * 120 - 10),
      y: Math.round(rand() * 76 - 8),
      delay: (rand() * 14).toFixed(2),
      duration: (Number(motion.speed) || 16) * (0.62 + rand() * 0.85),
      len: Math.round((Number(motion.length) || 160) * (0.55 + rand() * 0.9)),
      opacity: (0.35 + rand() * 0.55).toFixed(2),
      angle: (Number(motion.angle) || 28) + (rand() * 10 - 5),
    }))
  }, [variant, motion])
  if (!meteors.length) return null
  return (
    <div className="galactic-meteors" aria-hidden="true" data-meteor-count={meteors.length}>
      {meteors.map((m) => (
        <span
          key={m.id}
          className="galactic-meteor"
          style={{
            '--mx': `${m.x}%`,
            '--my': `${m.y}%`,
            '--mdelay': `${m.delay}s`,
            '--mdur': `${m.duration}s`,
            '--mlen': `${m.len}px`,
            '--mopacity': m.opacity,
            '--mangle': `${m.angle}deg`,
          }}
        />
      ))}
    </div>
  )
}

function compile(gl, type, src) {
  const sh = gl.createShader(type)
  gl.shaderSource(sh, src)
  gl.compileShader(sh)
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    // A shader typo must be loud: it would otherwise look like "the backdrop
    // is just dark tonight".
    console.error('[galactic] shader compile failed:', gl.getShaderInfoLog(sh))
    gl.deleteShader(sh)
    return null
  }
  return sh
}

export default function GalacticBackdrop({ themeId = 'auto', maxDpr = 1.25, variant }) {
  const canvasRef = useRef(null)
  const themeRef = useRef(themeId)
  const variantRef = useRef(variant || variantById('orion-nursery'))
  const dprRef = useRef(maxDpr)
  const tintRef = useRef([...tintFor(themeId)])
  const stateRef = useRef(null)
  themeRef.current = themeId
  variantRef.current = variant || variantById('orion-nursery')
  dprRef.current = maxDpr
  const hasImage = !!variant?.image

  const paint = useCallback((theme) => {
    const st = stateRef.current
    const canvas = canvasRef.current
    if (!st || !canvas || !st.ok) return

    const scene = (variantRef.current && variantRef.current.scene) || {}
    const dpr = Math.min(window.devicePixelRatio || 1, Math.max(0.75, dprRef.current))
    let w = Math.max(1, Math.floor(canvas.clientWidth * dpr))
    let h = Math.max(1, Math.floor(canvas.clientHeight * dpr))
    const pixels = w * h
    if (pixels > MAX_PIXELS) {
      const k = Math.sqrt(MAX_PIXELS / pixels)
      w = Math.max(1, Math.floor(w * k))
      h = Math.max(1, Math.floor(h * k))
    }
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }

    const { gl, prog, u } = st
    gl.viewport(0, 0, w, h)
    if (u.uRes) gl.uniform2f(u.uRes, w, h)
    if (u.uTime) gl.uniform1f(u.uTime, 18.0) // frozen: the shear pattern is art
    if (u.uQuality) gl.uniform1f(u.uQuality, 1.0)
    const tint = tintFor(theme)
    if (u.uTint) gl.uniform3f(u.uTint, tint[0], tint[1], tint[2])

    // Variant scene parameters. Defaults keep the shipped look identical when
    // no variant is supplied.
    if (u.uExpo) gl.uniform1f(u.uExpo, scene.expo ?? 1.0)
    if (u.uTemp) gl.uniform1f(u.uTemp, scene.temp ?? 1.0)
    if (u.uIncl) gl.uniform1f(u.uIncl, scene.incl ?? 5.6)
    if (u.uDist) gl.uniform1f(u.uDist, scene.dist ?? 16.0)
    if (u.uGal) gl.uniform1f(u.uGal, scene.gal ?? 1.0)
    if (u.uGrade) {
      const raw = scene.tint || [1, 1, 1]
      const max = Math.max(raw[0], raw[1], raw[2]) || 1
      gl.uniform3f(u.uGrade, raw[0] / max, raw[1] / max, raw[2] / max)
    }

    gl.drawArrays(gl.TRIANGLES, 0, 3)

    canvas.dataset.cosmicTheme = theme
    canvas.dataset.galacticRender = 'final'
    canvas.dataset.galacticPixels = `${w}x${h}`
    if (variantRef.current) canvas.dataset.galacticVariant = variantRef.current.id
  }, [])

  useEffect(() => {
    if (hasImage) return undefined
    const canvas = canvasRef.current
    if (!canvas) return undefined

    const fallback = (why) => {
      canvas.dataset.cosmicFallback = '1'
      if (why) canvas.dataset.cosmicLost = why
      canvas.dataset.galacticRender = 'css-fallback'
    }

    let gl = null
    try {
      gl = canvas.getContext('webgl', {
        antialias: false,
        alpha: false,
        powerPreference: 'low-power',
        preserveDrawingBuffer: false,
      }) || canvas.getContext('experimental-webgl')
    } catch {
      gl = null
    }
    if (!gl) { fallback('webgl_unavailable'); return undefined }

    const vs = compile(gl, gl.VERTEX_SHADER, VERT)
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG)
    if (!vs || !fs) { fallback('shader_compile'); return undefined }

    const prog = gl.createProgram()
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      fallback('program_link')
      return undefined
    }
    gl.useProgram(prog)

    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const loc = gl.getAttribLocation(prog, 'a_pos')
    gl.enableVertexAttribArray(loc)
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)

    stateRef.current = {
      ok: true,
      gl,
      prog,
      u: {
        uRes: gl.getUniformLocation(prog, 'u_res'),
        uTime: gl.getUniformLocation(prog, 'u_time'),
        uTint: gl.getUniformLocation(prog, 'u_tint'),
        uQuality: gl.getUniformLocation(prog, 'u_quality'),
        uExpo: gl.getUniformLocation(prog, 'u_expo'),
        uTemp: gl.getUniformLocation(prog, 'u_temp'),
        uIncl: gl.getUniformLocation(prog, 'u_incl'),
        uDist: gl.getUniformLocation(prog, 'u_dist'),
        uGal: gl.getUniformLocation(prog, 'u_gal'),
        uGrade: gl.getUniformLocation(prog, 'u_grade'),
      },
    }

    delete canvas.dataset.cosmicFallback
    delete canvas.dataset.cosmicLost

    // First paint, then a second one after the browser has settled the layout
    // (the shell measures into a flex frame; painting before that wastes the
    // most expensive frame of the session on the wrong size).
    paint(themeRef.current)
    const settle = setTimeout(() => paint(themeRef.current), 260)

    const onResize = () => paint(themeRef.current)
    let resizeTimer = 0
    const debounced = () => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(onResize, 220)
    }
    window.addEventListener('resize', debounced)

    const onLost = (event) => {
      event.preventDefault()
      fallback('context_lost')
    }
    canvas.addEventListener('webglcontextlost', onLost, false)

    return () => {
      clearTimeout(settle)
      clearTimeout(resizeTimer)
      window.removeEventListener('resize', debounced)
      canvas.removeEventListener('webglcontextlost', onLost, false)
      stateRef.current = null
      try { gl.deleteProgram(prog) } catch { /* context may already be gone */ }
    }
  }, [paint, hasImage])

  // A different variant is a different scene: repaint, and publish its CSS
  // custom properties so the surface material follows on the same tick.
  useEffect(() => {
    const v = variant || variantById('orion-nursery')
    applyVariant(v)
    paint(themeRef.current)
  }, [variant, paint])

  // Focus change: ease the observable tint (the harness reads it mid-flight),
  // then repaint the plate. The canvas dips in opacity so the swap reads as a
  // shift in atmosphere rather than a hard cut.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const from = [...tintRef.current]
    const to = tintFor(themeId)
    const start = performance.now()
    const DUR = 900
    let raf = 0
    let painted = false

    const step = (now) => {
      const t = Math.min(1, (now - start) / DUR)
      const k = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
      const cur = from.map((v, i) => v + (to[i] - v) * k)
      canvas.dataset.cosmicTint = cur.map((v) => v.toFixed(3)).join(',')
      if (!painted && t >= 0.45) {
        painted = true
        canvas.classList.add('gb-swapping')
        paint(themeId)
        requestAnimationFrame(() => canvas.classList.remove('gb-swapping'))
      }
      if (t < 1) {
        raf = requestAnimationFrame(step)
      } else {
        tintRef.current = [...to]
        canvas.dataset.cosmicTint = to.map((v) => v.toFixed(3)).join(',')
      }
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [themeId, paint])

  const active = variant || variantById('orion-nursery')
  const motion = active.motion || {}
  return (
    <div className={`galactic ${hasImage ? 'galactic--image' : ''}`}
         data-testid="galactic-backdrop" data-galactic-variant={active.id} aria-hidden="true">
      {/* The CSS scene is not dead code: it is the documented fallback when the
          GPU path is unavailable, and it shows through a lost context. */}
      <CelestialBackdrop />
      {hasImage ? (
        <img
          className="galactic-cluster"
          src={active.image}
          alt=""
          draggable="false"
          style={{
            '--cluster-zoom': motion.zoom || 1.06,
            '--cluster-x': motion.x || '0%',
            '--cluster-y': motion.y || '0%',
            '--cluster-duration': `${motion.duration || 100}s`,
            '--cluster-origin': motion.origin || '50% 50%',
          }}
        />
      ) : (
        <canvas ref={canvasRef} className="galactic-plate" data-testid="galactic-plate" />
      )}
      <MeteorField variant={active} />
      <div className="galactic-grain" />
      <div className="galactic-vignette" />
    </div>
  )
}
