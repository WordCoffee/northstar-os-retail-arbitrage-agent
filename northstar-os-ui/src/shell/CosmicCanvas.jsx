// ═══════════════════════════════════════════════════════════════════════════
// COSMIC CANVAS (V4.2 · Film-faithful Gargantua)
//
// One full-screen WebGL fragment shader — no textures, no video, one quad.
// Rebuilt from the ground up after the operator's note that the previous
// purple-planet scene "looks really fake and not like Interstellar at all".
//
// What actually makes the film's black hole read as real, and what this does:
//   • VIEWING ANGLE — the disc is seen almost exactly edge-on (we sit a few
//     degrees above its plane), so it collapses into a thin sweeping band
//     instead of a fat cartoon ring.                       (ky = vertical squash)
//   • LENSING — the disc's far side is bent up and OVER the shadow, forming the
//     arch above it, with a fainter counterpart beneath.   (arch + arch2 terms)
//   • PHOTON RING — a razor-thin, almost-white ring hugging the shadow edge.
//   • SHADOW — the hole itself is pure black and slightly larger than the
//     photon ring; it occludes the disc except where the near side crosses in
//     front of it.                                         (sphere + frontMask)
//   • DOPPLER BEAMING — the side rotating toward us is dramatically brighter
//     and hotter; the receding side falls off.             (beam, archBeam)
//   • COLOUR TEMPERATURE — white-hot inner edge → amber → deep ember outward.
//     Not purple.                                          (hot/mid/cold ramp)
//   • STAR LENSING — background stars are dragged tangentially as they approach
//     the hole (the Einstein-ring smear).                  (defl warp)
//   • GRADE — restrained nebula, dust-laned Milky Way, fine film grain, gentle
//     vignette, ACES-style shoulder. No saturated blobs behind the text.
//
// The brain-working pulse (u_pulse) now flares the inner disc and tightens the
// photon ring instead of enlarging cartoon moons.
//
// Perf contract (RTX 5080 16 GB, shared with Ollama + ComfyUI): single quad,
// DPR capped, paused on hidden tab, one static frame under
// prefers-reduced-motion, honest CSS fallback when WebGL is unavailable.
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
uniform float u_idle;
// T2 (Thorn v5.0 "preset-driven visual shifts"). The active Master Brain focus
// biases the ATMOSPHERE only — nebula warmth, a horizon band, a distant planet
// limb. The accretion disc and photon ring stay film-gold in every mode: the
// moment a preset tints the hero object it stops reading as Interstellar.
uniform vec3 u_tint;
uniform float u_horizon;
uniform float u_planet;

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
    p = p * 2.03 + vec2(11.3, -7.9);
    a *= 0.5;
  }
  return v;
}

// Stars live in pixel space so a cell keeps its true size at any DPR.
// Magnitude is cubed: many faint stars, a few bright ones — like a real sky.
// Each layer drifts at its own rate so the sky has real depth parallax.
float starField(vec2 px, float cellPx, float density, float drift) {
  vec2 g = (px + vec2(drift * u_time * 7.0, -drift * u_time * 2.6)) / cellPx;
  vec2 id = floor(g);
  vec2 f = fract(g);
  float h = hash21(id);
  if (h > density) return 0.0;
  vec2 pos = vec2(hash21(id + 13.1), hash21(id + 27.7));
  float d = length(f - pos);
  float size = mix(0.045, 0.150, hash21(id + 7.31));
  float mag = pow(hash21(id + 3.17), 3.0);
  return mag * smoothstep(size, 0.0, d);
}

// GALACTIC 1 - star colour temperature: a three-stop blackbody-ish ramp
// (blue-white -> white -> amber) instead of a two-colour lerp.
vec3 starTint(float h) {
  float t = fract(h * 7.31);
  vec3 cool = vec3(0.68, 0.78, 1.00);
  vec3 white = vec3(1.00, 0.98, 0.94);
  vec3 warm = vec3(1.00, 0.86, 0.66);
  return t < 0.5 ? mix(cool, white, t * 2.0) : mix(white, warm, (t - 0.5) * 2.0);
}

// GALACTIC 2 - diffraction spikes on the FEW brightest stars only (anamorphic
// cross). A low density + a wide cell means only a handful of stars carry them.
float starSpikes(vec2 px, float cellPx, float density) {
  vec2 g = (px + vec2(u_time * 0.6, -u_time * 0.2)) / cellPx;
  vec2 id = floor(g);
  vec2 f = fract(g);
  float h = hash21(id + 41.7);
  if (h > density) return 0.0;
  vec2 pos = vec2(hash21(id + 13.1), hash21(id + 27.7));
  vec2 d = abs(f - pos);
  float core = exp(-d.x * 30.0) * exp(-d.y * 260.0)
             + exp(-d.y * 30.0) * exp(-d.x * 260.0);
  return core * pow(hash21(id + 3.17), 2.0);
}

// GALACTIC 4 - a shooting star every ~55 s, 0.4 s of life, and NEVER over the
// reading column: it returns 0 inside the central band where the prose sits.
float shootingStar(vec2 uv, float t) {
  if (abs(uv.x - 0.5) < 0.245) return 0.0;
  float period = 55.0;
  float slot = floor(t / period);
  float phase = fract(t / period);
  if (phase > 0.12) return 0.0;
  float y = 0.68 + 0.24 * hash21(vec2(slot, 3.1));
  float x0 = 0.10 + 0.75 * hash21(vec2(slot, 1.7));
  vec2 head = vec2(x0 + phase * 0.30, y - phase * 0.16);
  vec2 tail = head - vec2(0.045, -0.024);
  float life = smoothstep(0.0, 0.02, phase) * (1.0 - smoothstep(0.08, 0.12, phase));
  vec2 q = (uv - head) * vec2(u_res.x / max(u_res.y, 1.0), 1.0);
  vec2 q2 = (uv - tail) * vec2(u_res.x / max(u_res.y, 1.0), 1.0);
  float h1 = exp(-dot(q, q) * 9000.0);
  float h2 = exp(-dot(q2, q2) * 2600.0) * 0.35;
  return (h1 + h2) * life;
}

void main() {
  vec2 uv = v_uv;
  float aspect = u_res.x / max(u_res.y, 1.0);
  vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

  // The film's camera is patient: a slow push-in and a barely-there drift.
  float t = u_time * 0.010;
  p += vec2(sin(u_time * 0.013), cos(u_time * 0.011)) * 0.0055;
  // 17: focal breathing - a slow 40 s push, not a visible sine
  p *= 1.0 + 0.005 * sin(u_time * 0.157);

  // ── 1. deep space: desaturated nebula + a dust-laned Milky Way ────────────
  vec3 col = vec3(0.011, 0.013, 0.022);
  float neb = fbm(p * 1.55 + vec2(t * 0.5, -t * 0.3));
  col += vec3(0.038, 0.050, 0.082) * smoothstep(0.36, 0.95, neb);
  // 6: nebula FILAMENTS - a ridged fbm (sharp crests) instead of soft blobs
  float fil = 1.0 - abs(2.0 * fbm(p * 2.35 + vec2(t * 0.35, t * 0.2)) - 1.0);
  col += vec3(0.030, 0.038, 0.062) * pow(fil, 3.0) * 0.55;
  float neb2 = fbm(p * 3.2 - vec2(t * 0.4, t * 0.2));
  col += vec3(0.052, 0.030, 0.066) * smoothstep(0.52, 0.98, neb2) * 0.65;

  vec2 bandDir = normalize(vec2(0.72, -0.69));
  float bd = dot(p - vec2(-0.10, 0.06), bandDir);
  float band = exp(-bd * bd * 7.0);
  float lanes = fbm(p * 2.6 + vec2(2.0, 5.0));
  float dust = smoothstep(0.44, 0.82, fbm(p * 5.4 + vec2(9.0, 1.0)));
  col += band * vec3(0.082, 0.085, 0.112) * (0.50 + 0.70 * lanes);
  col *= 1.0 - dust * band * 0.60;
  // GALACTIC 5 - a second dust layer that OCCLUDES (multiply), never adds, so the
  // lane structure reads as depth rather than as glow.
  float dust2 = smoothstep(0.50, 0.86, fbm(p * 9.0 + vec2(4.0, 2.0)));
  col *= 1.0 - dust2 * 0.18;

  // ── 1b. focus-driven atmosphere (T2 "preset-driven visual shifts") ────────
  // Restrained on purpose: the research is unambiguous that background luminance
  // belongs in the 2-8% band and that chroma belongs in small accents, or the
  // scenery starts competing with the prose sitting on the glass panel.
  col += vec3(0.026, 0.032, 0.054) * u_tint * smoothstep(0.30, 0.95, neb)
         * (0.55 + 0.9 * u_horizon);

  // horizon band — a broad, low glow the presets fade in and out
  float horizonY = p.y + 0.30;
  float horizon = exp(-abs(horizonY) * 8.0) * (1.0 - smoothstep(0.0, 0.95, abs(p.x)));
  col += u_tint * horizon * 0.050 * u_horizon;
  // 7: aurora ribbon just above the horizon - ~2% luminance, focus-tinted
  float aurora = exp(-abs(p.y + 0.24 + 0.03 * sin(p.x * 3.0 + u_time * 0.05)) * 22.0);
  col += u_tint * aurora * 0.020;

  // distant planet limb, mostly cropped by the right edge: depth, not a hero
  vec2 pl = vec2(0.78, -0.12);
  float pr = length(p - pl);
  float body = smoothstep(0.30, 0.285, pr);
  float rim = exp(-abs(pr - 0.296) * 70.0);
  float bands = fbm(vec2(atan(p.y - pl.y, p.x - pl.x) * 1.4, (pr - 0.29) * 9.0)
                       + vec2(u_time * 0.02, 0.0));
  col = mix(col, col * 0.84 + u_tint * (0.030 + 0.022 * bands), body * u_planet);
  // 8: terminator - the planet has a day/night edge, not uniform fill
  float day = smoothstep(-0.45, 0.45, dot(normalize(p - pl + 1e-6),
                                          normalize(vec2(-0.62, 0.48))));
  col = mix(col, col * (0.74 + 0.26 * day), body * u_planet);
  // 9: ring shadow - a thin dark band across the body from its own ring
  float ringShadow = exp(-abs((p.y - pl.y) + 0.018) * 90.0) * body * u_planet;
  col *= 1.0 - ringShadow * 0.35;
  col += u_tint * rim * 0.26 * u_planet;

  // ── 2. black hole frame: distant, massive, OUT of the reading column ──────
  // The bright disc must never sit under the text. The hole lives in the left
  // gutter; the band sweeps across the full frame behind the panel and re-emerges
  // on the right, which is also how the film frames it.
  vec2 bh = vec2(-0.660, 0.030);
  vec2 d = p - bh;
  float r = length(d);
  vec2 dir = d / max(r, 1e-5);
  float Rs = 0.095;                 // shadow radius
  float ky = 0.090;                 // vertical squash ⇒ near edge-on disc

  // ── 3. stars, dragged tangentially as they near the hole ─────────────────
  float defl = clamp((Rs * Rs) / max(r * r, Rs * Rs * 0.30), 0.0, 2.4);
  vec2 px = v_uv * u_res;
  vec2 pxw = px + dir * defl * u_res.y * 0.085;

  float fine   = starField(pxw, 3.4, 0.024, 1.00);   // parallax layers: 1x
  float mid    = starField(pxw * 0.62, 6.2, 0.050, 0.60);   //         0.6x
  float bright = starField(pxw * 0.40, 11.0, 0.028, 0.30);  //         0.3x
  // temperature-tinted stars (GALACTIC 1)
  col += fine   * starTint(hash21(floor(pxw / 3.4) + 5.1))    * 0.38;
  col += mid    * starTint(hash21(floor(pxw * 0.62 / 6.2) + 9.4)) * 0.70;
  col += bright * starTint(hash21(floor(pxw * 0.40 / 11.0) + 2.8)) * 1.10;
  // anamorphic spikes on the brightest few (GALACTIC 2)
  col += starSpikes(pxw * 0.40, 11.0, 0.006) * vec3(1.00, 0.97, 0.92) * 1.35;
  // GALACTIC 4 - a rare shooting star, only in the gutters (19: tail takes the focus tint)
  col += mix(vec3(0.92, 0.96, 1.00), u_tint, 0.35) * shootingStar(uv, u_time) * 0.85;

  // ── 4. the accretion disc: a thin band through the hole's plane ──────────
  // We look from a few degrees above the plane, so the near side sits slightly
  // BELOW the hole's centre and crosses in front of the shadow.
  vec2 dq = vec2(d.x, (d.y - 0.020) / ky);
  float R = length(dq);
  float Rin = 0.115, Rout = 1.05;

  float edgeIn  = smoothstep(Rin - 0.02, Rin + 0.05, R);
  float edgeOut = 1.0 - smoothstep(Rout - 0.55, Rout, R);
  float diskA = edgeIn * edgeOut;

  // Turbulence. The basis is deliberately only lightly squashed: sampling the
  // /already/ 11x-compressed disc frame produced scanline stripes rather than
  // flowing plasma.
  vec2 sw = vec2(dq.x * 2.6, d.y * 8.0) + vec2(R * 2.1, -R * 1.4) + t * 0.10;
  float turb = fbm(sw * 1.4);
  diskA *= 0.40 + 0.95 * smoothstep(0.26, 0.86, turb);

  // Depth split: the far half of the disc is occluded by the shadow, the near
  // half crosses IN FRONT of it. Two soft ramps — a single hard y-cut drew a
  // visible seam straight across the black disc.
  float frontSide = smoothstep(0.055, -0.030, d.y);
  float aBack  = diskA * (1.0 - frontSide);
  float aFront = diskA * frontSide;

  // Doppler beaming: the film's disk is famously SYMMETRIC — Double Negative
  // deliberately left the relativistic shift out to keep it golden. So this is
  // a whisper of asymmetry (≤1.35x), not a physics-paper render.
  float beam = clamp(1.0 + 0.34 * (-dq.x / max(R, 0.05)), 0.72, 1.36);
  float archBeam = clamp(1.0 + 0.26 * (-d.x / max(r, 0.05)), 0.80, 1.28);

  // Temperature ramp: white-hot inner edge → amber → deep ember.
  float rr = clamp((R - Rin) / max(Rout - Rin, 0.001), 0.0, 1.0);
  vec3 discCol = mix(vec3(1.00, 0.97, 0.93), vec3(1.00, 0.83, 0.58), smoothstep(0.0, 0.55, rr));
  discCol = mix(discCol, vec3(0.92, 0.45, 0.17), smoothstep(0.55, 1.0, rr));

  float flare = 1.0 + 0.40 * u_pulse;
  col += discCol * aBack * beam * 1.05 * flare;

  // ── 5. the lensed far side: an arch bent up over the shadow ──────────────
  float arch  = exp(-abs(r - Rs * 1.17) * 24.0) * smoothstep(-0.02, 0.10, d.y);
  float arch2 = exp(-abs(r - Rs * 1.05) * 38.0) * smoothstep(0.02, -0.10, d.y);
  col += discCol * arch  * archBeam * 0.85 * flare;
  col += discCol * arch2 * archBeam * 0.32;

  // ── 6. shadow, then the near disc in front of it, then the photon ring ───
  col *= 1.0 - smoothstep(Rs, Rs * 0.985, r);
  col += discCol * aFront * beam * 1.05 * flare;

  // 10: photon-ring shimmer - a slow breath tied to the brain pulse
  float shine = 1.55 + 0.35 * u_pulse + 0.10 * sin(u_time * 0.8);
  col += vec3(1.00, 0.90, 0.76) * exp(-abs(r - Rs * 1.022) * 520.0) * shine;
  // 12: chromatic bloom on the hottest edge - a warm fringe, not a halo
  float fringe = exp(-abs(r - Rs * 1.09) * 70.0);
  col.r += fringe * 0.055;
  col.b += fringe * 0.012;
  col += vec3(1.00, 0.72, 0.42) * exp(-abs(r - Rs * 1.06) * 30.0) * 0.30
         * (1.0 - smoothstep(Rs, Rs * 0.985, r));
  // 18: event-horizon shimmer - a faint ripple at the shadow edge
  col += u_tint * exp(-abs(r - Rs * 0.992) * 120.0) * 0.05;

  // ── 7. grade: vignette, film grain (stepped, never flickering), ACES ─────
  // 13: dither BEFORE the tone map - kills banding in the dark ramp
  col += (hash21(v_uv * u_res + vec2(3.1, 7.7)) - 0.5) * 0.004;
  // 16: two grain layers - fine at 12 fps, coarse at 3 fps (film, not video noise)
  float gt = floor(u_time * 12.0) / 12.0;
  float gt2 = floor(u_time * 3.0) / 3.0;
  col += (hash21(v_uv * u_res + vec2(gt * 61.7, gt * 23.3)) - 0.5) * 0.013;
  col += (hash21(v_uv * u_res * 0.5 + vec2(gt2 * 17.3, gt2 * 41.1)) - 0.5) * 0.008;
  // 15: elliptical vignette shaped to the panel - gutters darker than the centre
  col *= 1.0 - 0.42 * length((uv - 0.5) * vec2(1.0, 0.78)) * 1.15;
  // 20: idle dim - after a minute of no input the scenery steps back 15%
  col *= mix(1.0, 0.85, clamp(u_idle, 0.0, 1.0));
  // 14: filmic toe - blacks sit down without crushing the mid-tones
  col = max(col - 0.0035, 0.0);
  vec3 x = col * 1.12;
  col = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
  col = pow(col, vec3(0.93));
  gl_FragColor = vec4(col, 1.0);
}
`

// Focus → atmosphere ("preset-driven visual shifts", Thorn v5.0).
// The values are deliberately close to neutral: this shifts the MOOD of the
// scenery, it never repaints it. `tint` biases the nebula, the horizon band and
// the distant planet limb — the accretion disc stays film-gold in every mode.
const THEMES = {
  auto: { tint: [1.00, 0.95, 0.86], horizon: 0.22, planet: 0.00 },
  create: { tint: [1.00, 0.86, 0.66], horizon: 0.34, planet: 0.55 },
  grow: { tint: [0.80, 1.00, 0.86], horizon: 0.28, planet: 0.00 },
  research: { tint: [0.74, 0.86, 1.00], horizon: 0.26, planet: 0.45 },
  operate: { tint: [0.92, 0.95, 1.00], horizon: 0.18, planet: 0.00 },
  autothink: { tint: [0.84, 0.80, 1.00], horizon: 0.38, planet: 0.65 },
}
export const COSMIC_THEME_IDS = Object.keys(THEMES)
const EASE = 0.022                      // ~2s settle at 60fps; never a hard cut

function themeFor(id) {
  return THEMES[id] || THEMES.auto
}

function compile(gl, type, src) {
  const sh = gl.createShader(type)
  gl.shaderSource(sh, src)
  gl.compileShader(sh)
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    // Never fail silently: a shader typo must be visible, not just a CSS fallback.
    console.error('[cosmic] shader compile failed:', gl.getShaderInfoLog(sh))
    gl.deleteShader(sh)
    return null
  }
  return sh
}

export default function CosmicCanvas({ active = false, maxDpr = 1.5, themeId = 'auto' }) {
  const canvasRef = useRef(null)
  const pulseRef = useRef(0)
  // 20: idle dim - fed by real input activity, eased, never a jump.
  const idleRef = useRef(0)
  const lastInputRef = useRef(Date.now())
  const dprRef = useRef(maxDpr)
  const activeRef = useRef(active)
  const themeRef = useRef(themeId)
  const curRef = useRef({
    tint: [...themeFor(themeId).tint],
    horizon: themeFor(themeId).horizon,
    planet: themeFor(themeId).planet,
  })
  activeRef.current = active
  dprRef.current = maxDpr
  themeRef.current = themeId

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    let gl = null
    let vs = null
    let fs = null
    let prog = null
    let buf = null
    let uRes = null
    let uTime = null
    let uPulse = null
    let uTint = null
    let uHorizon = null
    let uPlanet = null
    let uIdle = null
    let lost = false
    let lastTint = ''

    // Honest fallback: the CSS scene under the canvas is what the operator sees
    // when the GPU path is unavailable. `data-cosmic-lost` keeps the REASON
    // observable instead of a mysterious dark rectangle.
    const fallback = (why) => {
      canvas.dataset.cosmicFallback = '1'
      if (why) canvas.dataset.cosmicLost = why
    }

    const reduced = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    // Build every GPU resource. Runs at mount and AGAIN after a context restore,
    // because a restored context has no programs, buffers or shader objects left.
    const boot = () => {
      try {
        gl = gl || canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' })
          || canvas.getContext('experimental-webgl')
      } catch { gl = null }
      if (!gl) { fallback(); return false }
      vs = compile(gl, gl.VERTEX_SHADER, VERT)
      fs = compile(gl, gl.FRAGMENT_SHADER, FRAG)
      if (!vs || !fs) { fallback(); return false }
      prog = gl.createProgram()
      gl.attachShader(prog, vs)
      gl.attachShader(prog, fs)
      gl.linkProgram(prog)
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { fallback(); return false }
      gl.useProgram(prog)
      buf = gl.createBuffer()
      gl.bindBuffer(gl.ARRAY_BUFFER, buf)
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
      const loc = gl.getAttribLocation(prog, 'a_pos')
      gl.enableVertexAttribArray(loc)
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)
      uRes = gl.getUniformLocation(prog, 'u_res')
      uTime = gl.getUniformLocation(prog, 'u_time')
      uPulse = gl.getUniformLocation(prog, 'u_pulse')
      uTint = gl.getUniformLocation(prog, 'u_tint')
      uHorizon = gl.getUniformLocation(prog, 'u_horizon')
      uPlanet = gl.getUniformLocation(prog, 'u_planet')
      uIdle = gl.getUniformLocation(prog, 'u_idle')
      lost = false
      delete canvas.dataset.cosmicFallback
      delete canvas.dataset.cosmicLost
      return true
    }

    const resize = () => {
      if (!gl || lost) return
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
    let lastFrame = performance.now()
    const start = performance.now()
    const draw = (now) => {
      // A lost context has no valid GL state: drawing would throw and the canvas
      // would freeze on its last frame. The CSS scene shows instead.
      if (lost || !gl || !prog) return
      const t = (now - start) / 1000
      // Frame-rate independent easing: EASE is defined per 1/60s, so a slow GPU
      // must not stretch the ~3.5s transition (it did, before this fix).
      const dt = Math.min(0.25, Math.max(0.001, (now - lastFrame) / 1000))
      lastFrame = now
      const k = 1 - Math.pow(1 - EASE, dt * 60)
      const target = activeRef.current ? 1 : 0
      pulseRef.current += (target - pulseRef.current) * (1 - Math.pow(1 - 0.05, dt * 60))
      // Ease the atmosphere toward the active focus's theme. Every value is
      // observable on the element (data-cosmic-theme / data-cosmic-tint) so the
      // shift is verifiable, not just asserted in a comment.
      const want = themeFor(themeRef.current)
      const cur = curRef.current
      for (let i = 0; i < 3; i += 1) cur.tint[i] += (want.tint[i] - cur.tint[i]) * k
      cur.horizon += (want.horizon - cur.horizon) * k
      cur.planet += (want.planet - cur.planet) * k
      gl.uniform1f(uTime, t)
      gl.uniform1f(uPulse, pulseRef.current)
      gl.uniform3f(uTint, cur.tint[0], cur.tint[1], cur.tint[2])
      gl.uniform1f(uHorizon, cur.horizon)
      gl.uniform1f(uPlanet, cur.planet)
      gl.uniform1f(uIdle, idleRef.current)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
      if (canvas.dataset.cosmicTheme !== themeRef.current) {
        canvas.dataset.cosmicTheme = themeRef.current
      }
      const tintStr = cur.tint.map((v) => v.toFixed(3)).join(',')
      if (tintStr !== lastTint) {
        canvas.dataset.cosmicTint = tintStr
        lastTint = tintStr
      }
      if (!reduced && !hidden) raf = requestAnimationFrame(draw)
    }

    const onResize = () => { resize(); if (reduced && !lost) draw(performance.now()) }
    const onVis = () => {
      hidden = document.visibilityState === 'hidden'
      if (!reduced) {
        if (!hidden && !lost) { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw) }
        else cancelAnimationFrame(raf)
      }
    }

    // ── WebGL context loss ────────────────────────────────────────────────
    // The GPU process can drop the context at any time: a driver reset, the tab
    // being discarded, or too many live contexts in one browser session. Without
    // this the canvas KEEPS ITS LAST FRAME forever and the shell looks frozen
    // rather than broken. Falls back to the CSS scene, retries exactly once when
    // the browser restores the context, and never spins.
    const onLost = (event) => {
      event.preventDefault()          // required, or the context can never come back
      lost = true
      cancelAnimationFrame(raf)
      fallback('context_lost')
      // eslint-disable-next-line no-console
      console.warn('[cosmic] WebGL context lost — showing the CSS scene')
    }
    const onRestored = () => {
      if (!boot()) return
      resize()
      lastFrame = performance.now()
      if (!hidden) { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw) }
    }
    canvas.addEventListener('webglcontextlost', onLost, false)
    canvas.addEventListener('webglcontextrestored', onRestored, false)

    if (boot()) {
      resize()
      raf = requestAnimationFrame(draw)
    }

    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVis)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', onVis)
      canvas.removeEventListener('webglcontextlost', onLost)
      canvas.removeEventListener('webglcontextrestored', onRestored)
      try { gl.deleteBuffer(buf); gl.deleteProgram(prog); gl.deleteShader(vs); gl.deleteShader(fs) } catch { /* teardown */ }
    }
  }, [])

  // 20: track real input so the scenery can step back after a minute of quiet.
  useEffect(() => {
    const bump = () => { lastInputRef.current = Date.now() }
    const events = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart']
    events.forEach((e) => window.addEventListener(e, bump, { passive: true }))
    const id = setInterval(() => {
      const target = Date.now() - lastInputRef.current > 60000 ? 1 : 0
      idleRef.current += (target - idleRef.current) * 0.08
    }, 500)
    return () => {
      events.forEach((e) => window.removeEventListener(e, bump))
      clearInterval(id)
    }
  }, [])

  return <canvas ref={canvasRef} className="cosmic-canvas" aria-hidden="true" data-testid="cosmic-canvas" />
}
