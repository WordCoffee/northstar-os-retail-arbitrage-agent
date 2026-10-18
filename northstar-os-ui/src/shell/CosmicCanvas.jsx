// ═══════════════════════════════════════════════════════════════════════════
// COSMIC CANVAS (V3 S6) — procedural 2K intergalactic backdrop.
//
// One full-screen WebGL fragment shader: drifting nebulae, twinkling star
// field, a deep-purple Master Brain planet with a rim light and two orbiting
// moons. The planet pulses while the Master Brain is working (`active`).
//
// Deliberate choices (see the V3 plan):
//   • PROCEDURAL, not a 30-minute 2K video loop — infinite, seamless, and it
//     costs one full-screen quad instead of hundreds of MB of texture. The
//     16 GB card is shared with Ollama + ComfyUI; the canvas must stay cheap.
//   • DPR capped at 1.5, animation pauses when the tab is hidden, and
//     `prefers-reduced-motion` renders a single static frame.
//   • No WebGL (or shader failure) ⇒ honest fallback: the CSS gradient class
//     stays (no crash, no fake).
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useRef } from 'react'

const VERT = `
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`

const FRAG = `
precision mediump float;
varying vec2 v_uv;
uniform vec2 u_res;
uniform float u_time;
uniform float u_pulse;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = v_uv;
  vec2 p = (uv - 0.5) * vec2(u_res.x / max(u_res.y, 1.0), 1.0);
  float t = u_time * 0.02;

  // Nebulae
  float n1 = fbm(p * 2.2 + vec2(t, -t * 0.6));
  float n2 = fbm(p * 4.1 - vec2(t * 0.7, t * 0.4));
  vec3 col = mix(vec3(0.012, 0.014, 0.035), vec3(0.115, 0.055, 0.215),
                 smoothstep(0.32, 0.95, n1));
  col += vec3(0.05, 0.025, 0.12) * smoothstep(0.5, 0.98, n2) * 0.9;

  // Star field
  vec2 sp = uv * u_res / 2.6;
  vec2 si = floor(sp);
  vec2 sf = fract(sp);
  float rnd = hash(si);
  float star = step(0.9983, rnd);
  vec2 c = vec2(hash(si + 11.3), hash(si + 27.7));
  float d = length(sf - c);
  float tw = 0.55 + 0.45 * sin(u_time * 1.8 + rnd * 41.0);
  col += star * tw * vec3(0.85, 0.88, 1.0) * smoothstep(0.1, 0.0, d);

  // Master Brain planet (deep purple, rim light, slow terminator drift)
  vec2 pc = vec2(0.30 + 0.035 * sin(t * 1.6), 0.055 + 0.02 * cos(t * 1.1));
  float R = 0.235;
  float dist = length(p - pc);
  float disc = smoothstep(R, R - 0.004, dist);
  vec3 base = vec3(0.185, 0.085, 0.335);
  float lightd = dot(normalize(p - pc + 1e-6), normalize(vec2(-0.6, 0.7)));
  vec3 lit = mix(base * 0.32, base * 1.32, lightd * 0.5 + 0.5);
  float rim = smoothstep(0.36, 0.02, abs(dist - R));
  col = mix(col, lit + vec3(0.52, 0.36, 0.95) * rim * 0.55, disc);

  // Energy pulse while the Master Brain works
  float ringPos = R + 0.03 + 0.11 * fract(u_time * 0.16);
  float ring = u_pulse * smoothstep(0.055, 0.0, abs(dist - ringPos));
  col += ring * vec3(0.30, 0.42, 1.0) * 0.85;

  // Orbiting moons (scale their glow with the pulse so focus reads visually)
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    float ang = u_time * (0.22 + fi * 0.11) + fi * 2.1;
    float mr = R + 0.13 + fi * 0.075;
    vec2 mp = pc + vec2(cos(ang), sin(ang) * 0.55) * mr;
    float md = length(p - mp);
    float moon = smoothstep(0.013, 0.007, md);
    col = mix(col, vec3(0.72, 0.70, 0.62) * (0.9 + 0.5 * u_pulse),
              moon * (0.75 + 0.25 * fi));
  }

  // Vignette + gentle blue floor so paper content above stays legible
  col *= 1.0 - 0.38 * length(uv - 0.5);
  col += vec3(0.02, 0.02, 0.05) * (1.0 - uv.y);
  gl_FragColor = vec4(col, 1.0);
}
`

function compile(gl, type, src) {
  const sh = gl.createShader(type)
  gl.shaderSource(sh, src)
  gl.compileShader(sh)
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    gl.deleteShader(sh)
    return null
  }
  return sh
}

export default function CosmicCanvas({ active = false }) {
  const canvasRef = useRef(null)
  const pulseRef = useRef(0)
  const activeRef = useRef(active)
  activeRef.current = active

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    let gl = null
    try {
      gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' })
        || canvas.getContext('experimental-webgl')
    } catch { gl = null }
    if (!gl) {
      canvas.dataset.cosmicFallback = '1'
      return undefined
    }
    const vs = compile(gl, gl.VERTEX_SHADER, VERT)
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG)
    if (!vs || !fs) {
      canvas.dataset.cosmicFallback = '1'
      return undefined
    }
    const prog = gl.createProgram()
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      canvas.dataset.cosmicFallback = '1'
      return undefined
    }
    gl.useProgram(prog)
    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const loc = gl.getAttribLocation(prog, 'a_pos')
    gl.enableVertexAttribArray(loc)
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)
    const uRes = gl.getUniformLocation(prog, 'u_res')
    const uTime = gl.getUniformLocation(prog, 'u_time')
    const uPulse = gl.getUniformLocation(prog, 'u_pulse')

    const reduced = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      const w = Math.max(1, Math.floor(canvas.clientWidth * dpr))
      const h = Math.max(1, Math.floor(canvas.clientHeight * dpr))
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
      }
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(uRes, canvas.width, canvas.height)
    }

    let raf = 0
    let hidden = false
    const start = performance.now()
    const draw = (now) => {
      const t = (now - start) / 1000
      // Ease the pulse toward the busy state (no popping)
      const target = activeRef.current ? 1 : 0
      pulseRef.current += (target - pulseRef.current) * 0.05
      gl.uniform1f(uTime, t)
      gl.uniform1f(uPulse, pulseRef.current)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
      if (!reduced && !hidden) raf = requestAnimationFrame(draw)
    }

    resize()
    const onResize = () => { resize(); if (reduced) draw(performance.now()) }
    const onVis = () => {
      hidden = document.visibilityState === 'hidden'
      if (!reduced) {
        if (!hidden) { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw) }
        else cancelAnimationFrame(raf)
      }
    }
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVis)
    raf = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', onVis)
      try { gl.deleteBuffer(buf); gl.deleteProgram(prog); gl.deleteShader(vs); gl.deleteShader(fs) } catch { /* teardown */ }
    }
  }, [])

  return <canvas ref={canvasRef} className="cosmic-canvas" aria-hidden="true" data-testid="cosmic-canvas" />
}
