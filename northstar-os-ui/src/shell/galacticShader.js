// ═══════════════════════════════════════════════════════════════════════════
// GALACTIC / INTERSTELLAR — the backdrop shader, as source of truth.
//
// The live shell used to mount a pure-CSS scene while this box's real WebGL
// renderer sat unimported. This file replaces both: one physically-motivated
// frame, rendered once at full quality, then panned by CSS.
//
// WHAT IS PHYSICAL, AND WHAT IS A DELIBERATE APPROXIMATION
//   • Photon paths are integrated, not faked: null geodesics near a
//     Schwarzschild hole obey d²u/dφ² + u = 1.5·Rs·u², solved with RK4 in
//     u = 1/r. Every equatorial crossing is one image of the disk, so the
//     primary image, the secondary lifted over the shadow and the higher-order
//     images that form the photon ring all fall out of the same loop.
//   • The shadow's size is the real critical impact parameter, 3√3·M = 2.598 Rs.
//   • The disk is a slab with a vertical profile, not a razor plane: a plane
//     produces a singular image along its own screen trace and tears. The slab
//     is integrated as optical depth per step, which is also how real
//     raymarchers do it.
//   • Temperature follows the thin-disk law T ∝ r^(-3/4), inner edge at the
//     ISCO (3 Rs). Colour is a blackbody fit, not a chosen gradient.
//   • Doppler beaming uses β = √(Rs/2r) and δ = 1/(γ(1−βcosθ)), intensity
//     ∝ δ³, so one limb is brighter and bluer. Gravitational redshift
//     √(1−Rs/r) dims the inner edge. That asymmetry is not a gradient.
//   • Galaxies are procedural: logarithmic arms, anti-phase dust lanes, a warm
//     bulge, HII knots. Generated geometry, not photographs.
//
// ES 1.00 on purpose: this ships to a plain webgl context with no
// extensions, so it must run on an integrated fallback too.
// ═══════════════════════════════════════════════════════════════════════════

export const VERT = `
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`

export const FRAG = `
precision highp float;

varying vec2 v_uv;
uniform vec2  u_res;
uniform float u_time;      // frozen for the static plate; drives disk shear
uniform vec3  u_tint;      // the focus atmosphere (product contract)
uniform float u_quality;   // 0 = draft pass, 1 = final (enables supersampling)
uniform float u_expo;      // exposure trim per theme variant
uniform float u_temp;      // disk temperature multiplier per variant
uniform float u_incl;      // camera height above the disk plane (inclination)
uniform float u_dist;      // camera distance (apparent size of the hole)
uniform float u_gal;       // galaxy brightness multiplier
uniform vec3  u_grade;     // variant colour grade, applied before the tone map

const float BCRIT = 2.598;   // 3√3 M in Rs units
const float RIN   = 3.00;    // ISCO
const float ROUT  = 9.0;     // outer edge fades well before it can cut the frame

// ── hashes & noise ─────────────────────────────────────────────────────────
float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm3(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 3; i++) {
    v += a * vnoise(p);
    p = p * 2.07 + vec2(13.7, -9.1);
    a *= 0.5;
  }
  return v;
}

float fbm5(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * vnoise(p);
    p = p * 2.03 + vec2(11.3, -7.9);
    a *= 0.5;
  }
  return v;
}

// ── blackbody colour (Tanner Helland fit, 1000K–40000K) ────────────────────
vec3 blackbody(float kelvin) {
  float t = clamp(kelvin, 1000.0, 40000.0) / 100.0;
  vec3 c;
  if (t <= 66.0) {
    c.r = 1.0;
    c.g = clamp(0.3900815788 * log(t) - 0.6318414437, 0.0, 1.0);
  } else {
    c.r = clamp(1.2929361860 * pow(t - 60.0, -0.1332047592), 0.0, 1.0);
    c.g = clamp(1.1298908608 * pow(t - 60.0, -0.0755148492), 0.0, 1.0);
  }
  if (t >= 66.0)      c.b = 1.0;
  else if (t <= 19.0) c.b = 0.0;
  else c.b = clamp(0.5432067891 * log(t - 10.0) - 1.1962540891, 0.0, 1.0);
  return c;
}

// ── star field: three depths, blackbody-tinted, magnitude cubed ────────────
vec3 starLayer(vec2 px, float cell, float density, float gain) {
  vec2 g = px / cell;
  vec2 id = floor(g);
  vec2 f = fract(g);
  float h = hash21(id + 11.7);
  if (h > density) return vec3(0.0);
  vec2 pos = vec2(hash21(id + 13.1), hash21(id + 27.7));
  float d = length(f - pos);
  float mag = pow(hash21(id + 3.17), 3.4);
  float size = mix(0.030, 0.085, hash21(id + 7.31));
  float core = smoothstep(size, 0.0, d);
  float halo = smoothstep(size * 5.0, 0.0, d) * 0.22;
  vec3 col = blackbody(2200.0 + 15000.0 * pow(hash21(id + 5.5), 1.6));
  return col * (core + halo) * mag * gain;
}

// Diffraction spikes on the few brightest stars only — anamorphic, never a
// cross on every dot.
vec3 starSpikes(vec2 px, float cell) {
  vec2 g = px / cell;
  vec2 id = floor(g);
  vec2 f = fract(g);
  if (hash21(id + 41.7) > 0.06) return vec3(0.0);
  vec2 pos = vec2(hash21(id + 13.1), hash21(id + 27.7));
  vec2 d = abs(f - pos);
  float s = exp(-d.x * 26.0) * exp(-d.y * 420.0)
          + exp(-d.y * 26.0) * exp(-d.x * 420.0);
  return blackbody(7000.0) * s * pow(hash21(id + 3.17), 2.0) * 0.9;
}

// ── one spiral galaxy: log arms, anti-phase dust, warm bulge, HII knots ────
vec3 galaxy(vec2 uv, vec2 centre, float radius, float rot, float incl,
            vec3 armCol, vec3 coreCol, float gain) {
  vec2 q = uv - centre;
  float s = sin(rot), c = cos(rot);
  q = mat2(c, -s, s, c) * q;
  q.y /= incl;

  float r = length(q);
  if (r > radius) return vec3(0.0);

  float th = atan(q.y, q.x);
  float phase = 2.0 * th + 3.9 * log(max(r, 0.006));
  float arm = 0.5 + 0.5 * cos(phase);
  arm = pow(arm, 2.6);

  float disk  = exp(-r * 6.2) * (0.22 + 1.15 * arm);
  float dust  = pow(0.5 + 0.5 * cos(phase + 3.14159265), 5.0);
  float bulge = exp(-r * 30.0) * 1.7 + exp(-r * 9.0) * 0.30;

  float clump = 0.55 + 0.85 * fbm5(q * 11.0 + 5.3);
  float knots = smoothstep(0.78, 0.97, fbm3(q * 26.0 + 1.7)) * arm * 0.9;

  vec3 col = armCol * disk * clump;
  col += vec3(0.95, 0.42, 0.55) * knots * exp(-r * 4.0) * 0.55;
  col += coreCol * bulge;

  col *= 1.0 - dust * 0.62 * smoothstep(0.0, 0.10, r);
  col *= 1.0 - smoothstep(radius * 0.75, radius, r);
  return col * gain;
}

// ── nebula: filamentary, additive, kept away from the reading column ───────
vec3 nebula(vec2 uv, float gain) {
  vec2 q = uv * 2.3;
  float n = fbm5(q + vec2(0.31, -0.17));
  float fil = fbm5(q * 2.7 + vec2(5.1, 1.9));
  float body = smoothstep(0.42, 0.92, n * 0.75 + fil * 0.45);
  float band = exp(-pow(abs(uv.y + uv.x * 0.55 - 0.06) * 3.1, 2.0));
  vec3 cool = vec3(0.20, 0.32, 0.68);
  vec3 warm = vec3(0.62, 0.34, 0.30);
  vec3 col = mix(cool, warm, smoothstep(0.30, 0.85, fil));
  return col * body * band * gain * 0.55;
}

// ── accretion disk ────────────────────────────────────────────────────────
// Returns emission per unit optical depth. "density" is the radial/turbulent
// profile alone; the path integral (slab crossing) is applied by the caller.
vec3 diskEmission(vec3 hit, vec3 viewDir, float time, out float density) {
  float r = length(hit.xz);

  if (r < RIN * 0.94 || r > ROUT) { density = 0.0; return vec3(0.0); }

  // Keplerian shear: inner material laps the outer. This is what curves the
  // streaks instead of leaving them radially straight.
  float ang   = atan(hit.z, hit.x);
  float omega = 1.0 / pow(max(r, 1.0), 1.5);
  float a     = ang + time * omega * 1.15;

  float turb = fbm3(vec2(a * 1.7, r * 0.95));
  float fine = fbm3(vec2(a * 5.5, r * 2.6 + 2.7));

  density = smoothstep(RIN, RIN * 1.55, r)
          * (1.0 - smoothstep(ROUT * 0.45, ROUT, r));
  density *= (0.34 + 1.25 * turb) * (0.72 + 0.52 * fine);
  density *= 1.0 + 1.55 * exp(-max(r - RIN, 0.0) * 2.6);
  density = min(density, 1.0);

  // thin-disk temperature, inner edge hottest. 6800 K rather than 11000 K
  // because a 10000 K blackbody tone-maps to flat white, and this disk is gold.
  float T = 1050.0 + 5750.0 * u_temp * pow(RIN / max(r, RIN), 0.75);
  vec3 bb = blackbody(T);
  // multiply, not mix: mixing toward white desaturates the rim to grey
  bb *= vec3(1.06, 0.855, 0.63);

  // relativistic beaming: the approaching limb is brighter and bluer
  vec3  vel  = normalize(vec3(-hit.z, 0.0, hit.x));
  float beta = clamp(sqrt(0.5 / max(r, 1.30)), 0.0, 0.86);
  float ct   = dot(vel, -viewDir);
  float gam  = 1.0 / sqrt(max(0.04, 1.0 - beta * beta));
  float dop  = 1.0 / max(0.08, gam * (1.0 - beta * ct));
  float grav = sqrt(max(0.04, 1.0 - 1.0 / max(r, 1.05)));

  float intensity = pow(dop, 2.9) * grav;
  return bb * intensity * 0.86 * u_expo;
}

// ── the geodesic equation, in u = 1/r ─────────────────────────────────────
float geodesicAccel(float u) {
  return -u + 1.5 * u * u;
}

// ── one primary ray ───────────────────────────────────────────────────────
vec3 shade(vec2 d) {
  vec2 uv = v_uv;
  vec2 px = uv * u_res;

  // Camera ~12° above the disk plane: the disk opens into an ellipse and the
  // far side still wraps. 1.30 ≈ 1/tan(21°) → a 42° vertical field.
  vec3 ro = vec3(0.0, u_incl, -u_dist);
  vec3 ww = normalize(vec3(0.0, 0.0, 0.0) - ro);
  vec3 uu = normalize(cross(vec3(0.0, 1.0, 0.0), ww));
  vec3 vv = cross(ww, uu);
  vec3 rd = normalize(d.x * uu + d.y * vv + 1.30 * ww);

  float b = length(cross(ro, rd));

  // ── background ───────────────────────────────────────────────────────────
  vec3 col = vec3(0.0035, 0.0050, 0.0110);
  float g = u_gal;
  col += nebula(uv, 1.0) * mix(vec3(1.0), u_tint, 0.55);

  col += g * galaxy(uv, vec2(0.13, 0.74), 0.155, 0.62, 1.85,
                vec3(0.42, 0.60, 1.05), vec3(1.00, 0.86, 0.64), 0.42);
  col += g * galaxy(uv, vec2(0.93, 0.22), 0.075, -1.35, 2.10,
                vec3(0.55, 0.66, 0.98), vec3(1.00, 0.82, 0.58), 0.26);

  col += starLayer(px, 3.4, 0.075, 3.4);
  col += starLayer(px, 1.9, 0.045, 2.4);
  col += starLayer(px, 1.1, 0.024, 1.5);
  col += starSpikes(px, 2.6);

  // ── the disk, integrated along the photon path ──────────────────────────
  vec3  diskCol = vec3(0.0);
  float diskA   = 0.0;
  bool  captured = false;

  vec3  e1 = normalize(ro);
  float r0 = length(ro);
  vec3  tv = rd - e1 * dot(rd, e1);
  float tl = length(tv);
  vec3  bh = tl > 1e-6 ? tv / tl : vec3(0.0, 0.0, -1.0);

  float u  = 1.0 / r0;
  float w  = -(1.0 / r0) * (dot(rd, e1) / max(tl, 1e-6));   // du/dφ
  float ph = 0.0;
  vec3  prev = ro;

  const float DPHI = 0.022;

  for (int i = 0; i < 420; i++) {
    float k1u = w;                       float k1w = geodesicAccel(u);
    float k2u = w + 0.5 * DPHI * k1w;    float k2w = geodesicAccel(u + 0.5 * DPHI * k1u);
    float k3u = w + 0.5 * DPHI * k2w;    float k3w = geodesicAccel(u + 0.5 * DPHI * k2u);
    float k4u = w + DPHI * k3w;          float k4w = geodesicAccel(u + DPHI * k3u);
    u += (DPHI / 6.0) * (k1u + 2.0 * k2u + 2.0 * k3u + k4u);
    w += (DPHI / 6.0) * (k1w + 2.0 * k2w + 2.0 * k3w + k4w);
    ph += DPHI;
    u = max(u, 0.0012);

    if (u > 1.0) { captured = true; break; }

    float r = 1.0 / u;
    vec3  P = r * (cos(ph) * e1 + sin(ph) * bh);

    // One image per crossing. A sign change is interpolated WITHIN the step, so
    // the sample is sub-step accurate. Where the path merely grazes the plane
    // (no sign change inside a step) the nearest approach fades in with a
    // Gaussian weight instead of dropping out — that is what removes the tear
    // along the plane's screen trace without quantising the disk into teeth.
    {
      float rp = length(prev);
      float hh = 0.012 + 0.0060 * rp;
      float dens;
      if (prev.y * P.y < 0.0) {
        float lam = prev.y / (prev.y - P.y);
        vec3 hit = mix(prev, P, lam);
        vec3 em = diskEmission(hit, normalize(P - prev), u_time, dens);
        float a = clamp(dens, 0.0, 1.0);
        diskCol += em * a * (1.0 - diskA);
        diskA   += a * (1.0 - diskA);
      } else {
        float apy = abs(prev.y);
        float ay  = abs(P.y);
        float mn  = min(apy, ay);
        if (mn < hh * 4.0) {
          vec3 hit = ay < apy ? P : prev;
          float w = exp(-pow(mn / hh, 2.0));
          vec3 em = diskEmission(hit, normalize(P - prev), u_time, dens);
          float a = clamp(dens * w, 0.0, 1.0) * 0.5;
          diskCol += em * a * (1.0 - diskA);
          diskA   += a * (1.0 - diskA);
        }
      }
    }

    prev = P;

    if (u < 0.0025 && w < 0.0) break;
    if (diskA > 0.997) break;
  }

  vec3 base = captured ? vec3(0.0) : col;
  col = base * (1.0 - diskA) + diskCol;

  // The rim is already produced by the disk's higher-order images; this adds
  // only a whisper of over-exposure on the last stable orbit.
  float ring = exp(-abs(b - BCRIT * 1.02) * 62.0);
  col += vec3(1.0, 0.90, 0.74) * ring * 0.10;

  return col;
}

// ── main ──────────────────────────────────────────────────────────────────
void main() {
  vec2 uv = v_uv;
  vec2 px = uv * u_res;
  float aspect = u_res.x / max(1.0, u_res.y);

  // Offset the hole so the reading column keeps a dark, quiet field.
  vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
  vec2 d = p - vec2(0.30, 0.015) * vec2(aspect, 1.0);

  // The horizon is a hard threshold in the solver, so it aliases at one sample
  // per pixel. Supersample only where the hole actually is.
  vec3 ro = vec3(0.0, u_incl, -u_dist);
  vec3 ww = normalize(vec3(0.0, 0.0, 0.0) - ro);
  vec3 uu = normalize(cross(vec3(0.0, 1.0, 0.0), ww));
  vec3 vv = cross(ww, uu);
  vec3 rd0 = normalize(d.x * uu + d.y * vv + 1.30 * ww);
  float b0 = length(cross(ro, rd0));

  vec3 col;
  if (b0 < 3.7 && u_quality > 0.5) {
    vec2 o = vec2(0.0018, 0.0018);
    col  = shade(d + vec2(-o.x, -o.y));
    col += shade(d + vec2( o.x, -o.y));
    col += shade(d + vec2(-o.x,  o.y));
    col += shade(d + vec2( o.x,  o.y));
    col *= 0.25;
  } else {
    col = shade(d);
  }

  // ── grade ───────────────────────────────────────────────────────────────
  // dithered darks: kills the banding a 16-bit ramp shows on OLED
  col += (hash21(px + vec2(3.1, 7.7)) - 0.5) * (0.006 - 0.004 * u_quality);

  // elliptical vignette, shaped to the panel
  float vign = length((uv - 0.5) * vec2(1.0, 0.82));
  col *= 1.0 - 0.46 * vign * 1.10;

  // keep the reading column usable without a heavy scrim
  float column = exp(-pow((uv.x - 0.5) * 3.05, 2.0));
  col *= 1.0 - 0.30 * column;

  col *= u_grade;
  col = max(col - 0.0025, 0.0);
  vec3 x = col * 1.16;
  col = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
  col = pow(col, vec3(0.94));

  gl_FragColor = vec4(col, 1.0);
}
`
