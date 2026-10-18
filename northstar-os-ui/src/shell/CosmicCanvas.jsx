// ═══════════════════════════════════════════════════════════════════════════
// COSMIC CANVAS (V3 S6 · cinematic grade pass) — "watching Interstellar"
//
// One full-screen WebGL fragment shader. No textures, no video files — every
// pixel is procedural, which is why the whole environment costs one quad:
//
//   • deep-space base with a faint fbm nebula wash
//   • a Milky Way band with dark dust lanes
//   • two parallax star fields (sharp twinkle)
//   • a distant Gargantua-style accretion disc (upper-left): glowing tilted
//     ring, black sphere occlusion, photon ring, fake top-half lensing
//   • the deep-purple Master Brain planet: day/night terminator, cloud
//     banding, night-side sparkle, atmosphere rim
//   • two orbiting moons that SCALE UP while the brain works (pulse)
//   • expanding energy halo rings while the brain works
//   • film grain, vignette, filmic tone curve, slow camera drift + breathing
//
// Perf contract (RTX 5080 16 GB, shared with Ollama + ComfyUI): single quad,
// DPR capped (default 1.5, governor may lower it), animation pauses on hidden
// tab, prefers-reduced-motion renders one static frame, honest CSS fallback
// when WebGL is unavailable.
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
precision highp float;
varying vec2 v_uv;
uniform vec2 u_res;
uniform float u_time;
uniform float u_pulse;

// ── hashes / noise ──────────────────────────────────────────────────────────
float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.04 + vec2(11.3, -7.9);
    a *= 0.5;
  }
  return v;
}

// ── stars: pixel-space fields with independent twinkle ──────────────────────
// (px = pixel coords so cell size survives any DPR; sizes are cell fractions)
float starField(vec2 px, float cellPx, float density, float drift) {
  vec2 g = (px + vec2(u_time * drift * 18.0, -u_time * drift * 7.0)) / cellPx;
  vec2 id = floor(g);
  vec2 f = fract(g);
  float h = hash21(id);
  if (h > density) return 0.0;
  vec2 pos = vec2(hash21(id + 13.1), hash21(id + 27.7));
  float d = length(f - pos);
  float size = mix(0.055, 0.17, hash21(id + 7.31));
  float tw = 0.5 + 0.5 * sin(u_time * (1.3 + h * 2.2) + h * 41.0);
  return tw * smoothstep(size, 0.0, d);
}

void main() {
  vec2 uv = v_uv;
  vec2 p = (uv - 0.5) * vec2(u_res.x / max(u_res.y, 1.0), 1.0);

  // slow camera drift + gentle breathing (Interstellar push-in)
  float t = u_time * 0.02;
  p += vec2(sin(u_time * 0.031), cos(u_time * 0.027)) * 0.008;
  p *= 1.0 + 0.018 * sin(t * 1.7);

  // ── 1. deep space base + nebula wash ──────────────────────────────────────
  vec3 col = vec3(0.010, 0.013, 0.034);
  float neb = fbm(p * 1.8 + vec2(t * 0.6, -t * 0.4));
  col += vec3(0.075, 0.034, 0.150) * smoothstep(0.32, 0.95, neb);
  col += vec3(0.034, 0.016, 0.085) * smoothstep(0.42, 0.98, fbm(p * 3.6 - vec2(t * 0.5)));

  // ── 2. Milky Way band with dust lanes ─────────────────────────────────────
  vec2 bandDir = normalize(vec2(0.55, -0.835));
  float bd = dot(p - vec2(-0.05, 0.10), bandDir);
  float band = exp(-bd * bd * 5.5);
  float core = exp(-bd * bd * 26.0);
  float lanes = fbm(p * 3.1 + vec2(2.0, 5.0));
  float dust = smoothstep(0.42, 0.80, fbm(p * 6.3 + vec2(9.0, 1.0)));
  col += band * vec3(0.16, 0.145, 0.24) * (0.55 + 0.65 * lanes);
  col += core * vec3(0.22, 0.195, 0.31) * (0.45 + 0.85 * lanes);
  col *= 1.0 - dust * band * 0.55;

  // ── 3. star fields (pixel-space, two densities, opposing parallax) ────────
  vec2 px = v_uv * u_res;
  float s1 = starField(px, 7.0, 0.045, 0.55);
  float s2 = starField(px, 4.2, 0.028, -0.25);
  col += s1 * vec3(0.85, 0.88, 1.00) * 0.85 + s2 * vec3(0.66, 0.70, 0.92) * 0.55;
  float s3 = starField(px, 12.0, 0.020, 0.35);
  col += s3 * vec3(0.95, 0.95, 1.0) * 1.35;

  // ── 4. distant Gargantua (upper-left, kept off the hero planet) ───────────
  vec2 gc = vec2(-0.680, 0.315);
  vec2 g = p - gc;
  float gd = length(g);
  vec2 q = g;
  q = mat2(0.92, -0.39, 0.39, 0.92) * q;
  q.y /= 0.30;
  float dd = length(q);
  float ringCore = smoothstep(0.010, 0.0, abs(dd - 0.118));
  float ringGlow = exp(-abs(dd - 0.118) * 14.0);
  float topHalf = smoothstep(-0.012, 0.018, g.y);
  float behind = smoothstep(0.044, 0.054, gd);          // front half occluded
  vec3 discCol = mix(vec3(1.0, 0.82, 0.55), vec3(1.0, 0.55, 0.30), fbm(q * 18.0));
  col += (ringCore * 1.7 + ringGlow * 0.55) * discCol
         * (topHalf * 1.20 + (1.0 - topHalf) * behind * 0.80);
  // black sphere + photon ring
  float sphere = smoothstep(0.0495, 0.0475, gd);
  col = mix(col, vec3(0.0), sphere);
  col += smoothstep(0.0016, 0.0, abs(gd - 0.0515)) * vec3(0.98, 0.82, 0.55) * 1.25;

  // ── 5. the Master Brain planet (deep purple, hero of the frame) ───────────
  // A MASSIVE body looming behind the glass — the Interstellar composition.
  vec2 pc = vec2(0.030 + 0.020 * sin(t * 1.6), 0.030 + 0.012 * cos(t * 1.1));
  float R = 0.300;
  float pd = length(p - pc);
  float disc = 1.0 - smoothstep(R - 0.0028, R, pd);
  vec2 pn = normalize(p - pc + 1e-6);
  vec3 L = normalize(vec3(-0.55, 0.70, 0.30));
  float day = dot(vec3(pn, 0.0), L) * 0.5 + 0.5;
  float limb = smoothstep(1.0, 0.55, length(pn));   // darken toward the limb
  float clouds = fbm((p - pc) * 3.5 + vec2(t * 0.8, t * 0.3)) * limb;
  vec3 dayCol = mix(vec3(0.160, 0.060, 0.340), vec3(0.550, 0.260, 0.850), clouds);
  vec3 nightCol = vec3(0.030, 0.012, 0.055);
  vec3 planet = mix(nightCol, dayCol, smoothstep(0.18, 0.62, day));
  // night-side city-light sparkle (pixel-space pinpricks)
  float sparks = starField((p - pc) * u_res, 3.2, 0.16, 0.0) * limb;
  planet += sparks * (1.0 - smoothstep(0.0, 0.50, day)) * vec3(0.85, 0.78, 0.55) * 0.30;
  col = mix(col, planet, disc);
  // atmosphere rim + outer halo (thin so the body reads as a 3D sphere)
  float atmo = 1.0 - smoothstep(0.0, 0.10, abs(pd - R));
  col += atmo * vec3(0.50, 0.34, 1.00) * (0.35 + 0.65 * day) * 0.55;
  col += exp(-max(pd - R, 0.0) * 4.0) * vec3(0.08, 0.05, 0.18) * (0.40 + 0.60 * day) * 0.50;

  // ── 6. energy halo rings while the brain works ────────────────────────────
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    float phase = fract(u_time * 0.14 + fi * 0.5);
    float ringPos = R + 0.025 + 0.115 * phase;
    float ring = smoothstep(0.045, 0.0, abs(pd - ringPos)) * (1.0 - phase);
    col += ring * vec3(0.30, 0.42, 1.0) * 0.55 * u_pulse;
  }

  // ── 7. orbiting moons — SCALE and brighten with the pulse ────────────────
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    float ang = u_time * (0.20 + fi * 0.10) + fi * 2.1;
    float mr = (R + 0.135 + fi * 0.075) * (1.0 + 0.20 * u_pulse);
    vec2 mp = pc + vec2(cos(ang), sin(ang) * 0.55) * mr;
    float md = length(p - mp);
    float moonR = 0.0125 * (1.0 + 0.35 * u_pulse);
    float moon = smoothstep(moonR, moonR * 0.55, md);
    col = mix(col, vec3(0.74, 0.72, 0.64) * (0.85 + 0.55 * u_pulse),
              moon * (0.72 + 0.28 * fi));
    // faint glow under the moon so the scale-up reads as "attention"
    col += smoothstep(moonR * 3.2, 0.0, md) * vec3(0.30, 0.30, 0.50) * 0.12 * u_pulse;
  }

  // ── 8. grade: vignette, film grain, ACES-ish curve ─────────────────────────
  col *= 1.0 - 0.42 * length(uv - 0.5);
  col += (hash21(v_uv * u_res + vec2(u_time * 61.7, u_time * 23.3)) - 0.5) * 0.018;
  // ACES approximation (keeps mid-tones luminous; only hot highlights roll off)
  vec3 x = col * 1.15;
  col = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
  col = pow(col, vec3(0.92));
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

export default function CosmicCanvas({ active = false, maxDpr = 1.5 }) {
  const canvasRef = useRef(null)
  const pulseRef = useRef(0)
  const dprRef = useRef(maxDpr)
  const activeRef = useRef(active)
  activeRef.current = active
  dprRef.current = maxDpr

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
      const dpr = Math.min(window.devicePixelRatio || 1, Math.max(0.75, dprRef.current))
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
