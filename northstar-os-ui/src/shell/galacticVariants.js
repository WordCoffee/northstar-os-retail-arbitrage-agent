// ═══════════════════════════════════════════════════════════════════════════
// GALACTIC VARIANTS — ten complete looks, not ten colour swatches.
//
// Every variant sets three independent layers:
//
//   1. SCENE  — shader uniforms: disk temperature, exposure, camera
//               inclination and distance, galaxy brightness, focus tint.
//               These change the PHYSICS framing, so the hole is a different
//               size, a different angle and a different temperature.
//   2. SURFACE— panel alpha, blur, radius, border, accent, glow. This is the
//               material the UI is cut from: obsidian glass, smoked sheet,
//               matte, ice, ember.
//   3. LAYOUT — header alignment, chip geometry, rail width, density,
//               composer treatment.
//
// So "pick the winner" is a real decision about a look, not a hue.
//
// Selected with ?galactic=<id> (falls back to the stored choice, then to
// 'event-horizon'). Nothing here calls the network.
// ═══════════════════════════════════════════════════════════════════════════

export const GALACTIC_VARIANTS = [
  {
    id: 'event-horizon',
    name: 'Event Horizon',
    intent: 'The Interstellar frame itself: gold disk, obsidian glass, quiet chrome.',
    scene: { temp: 1.0, expo: 1.0, incl: 5.6, dist: 16.0, gal: 1.0, tint: [1.0, 0.95, 0.86] },
    surface: {
      panel: 'rgba(9, 13, 22, 0.42)', blur: 22, radius: 18,
      border: 'rgba(150, 170, 220, 0.20)', accent: '#f0b46a',
      glow: 'rgba(240, 180, 106, 0.30)', sheen: 'rgba(255,255,255,0.05)',
    },
    layout: { align: 'space-between', chip: 'pill', rail: '264px', density: 1.0, composer: 'line' },
  },
  {
    id: 'gargantua',
    name: 'Gargantua',
    intent: 'Closer, larger, hotter. The hole dominates and the UI floats inside its halo.',
    scene: { temp: 1.12, expo: 1.05, incl: 7.4, dist: 12.5, gal: 0.7, tint: [1.0, 0.92, 0.80] },
    surface: {
      panel: 'rgba(12, 10, 8, 0.40)', blur: 26, radius: 26,
      border: 'rgba(255, 196, 120, 0.26)', accent: '#ffc06a',
      glow: 'rgba(255, 170, 90, 0.38)', sheen: 'rgba(255, 226, 180, 0.07)',
    },
    layout: { align: 'space-between', chip: 'pill', rail: '264px', density: 1.05, composer: 'line' },
  },
  {
    id: 'sagittarius',
    name: 'Sagittarius A*',
    intent: 'Cooler, redder, dimmer — the real thing at 4 million suns, not a movie.',
    scene: { temp: 0.72, expo: 0.86, incl: 4.2, dist: 18.0, gal: 0.85, tint: [0.95, 0.78, 0.72] },
    surface: {
      panel: 'rgba(10, 8, 10, 0.46)', blur: 16, radius: 0,
      border: 'rgba(214, 150, 140, 0.20)', accent: '#d98b7a',
      glow: 'rgba(200, 120, 110, 0.28)', sheen: 'rgba(255,255,255,0.04)',
    },
    layout: { align: 'flex-start', chip: 'rect', rail: '248px', density: 0.96, composer: 'line' },
  },
  {
    id: 'andromeda',
    name: 'Andromeda Drift',
    intent: 'The galaxy is the hero; the hole is a distant companion. Wide, teal, airy.',
    scene: { temp: 0.95, expo: 0.95, incl: 6.2, dist: 22.0, gal: 1.9, tint: [0.78, 1.0, 0.94] },
    surface: {
      panel: 'rgba(8, 16, 20, 0.34)', blur: 30, radius: 22,
      border: 'rgba(140, 232, 214, 0.22)', accent: '#6ee7d0',
      glow: 'rgba(110, 231, 208, 0.30)', sheen: 'rgba(214,255,246,0.06)',
    },
    layout: { align: 'space-between', chip: 'pill', rail: '300px', density: 1.08, composer: 'line' },
  },
  {
    id: 'photon-ring',
    name: 'Photon Ring',
    intent: 'Almost nothing: black field, one bright ring, ice accents. Instrument, not poster.',
    scene: { temp: 1.35, expo: 0.78, incl: 2.4, dist: 14.0, gal: 0.0, tint: [0.80, 0.90, 1.0] },
    surface: {
      panel: 'rgba(4, 6, 10, 0.58)', blur: 10, radius: 6,
      border: 'rgba(180, 210, 255, 0.18)', accent: '#9ec5ff',
      glow: 'rgba(120, 170, 255, 0.26)', sheen: 'rgba(255,255,255,0.05)',
    },
    layout: { align: 'flex-start', chip: 'rect', rail: '236px', density: 0.94, composer: 'line' },
  },
  {
    id: 'nebula-bloom',
    name: 'Nebula Bloom',
    intent: 'Luminous and soft: heavy nebula, magenta wash, deep glass, generous curves.',
    scene: { temp: 0.88, expo: 1.10, incl: 8.6, dist: 17.5, gal: 1.5, tint: [1.0, 0.74, 0.96] },
    surface: {
      panel: 'rgba(16, 10, 26, 0.36)', blur: 34, radius: 28,
      border: 'rgba(226, 160, 255, 0.26)', accent: '#e0a6ff',
      glow: 'rgba(210, 130, 255, 0.36)', sheen: 'rgba(255,220,255,0.07)',
    },
    layout: { align: 'space-between', chip: 'pill', rail: '264px', density: 1.06, composer: 'line' },
  },
  {
    id: 'quasar',
    name: 'Quasar',
    intent: 'Extreme Doppler asymmetry, blue-white jet, electric accent, compact density.',
    scene: { temp: 1.28, expo: 1.0, incl: 5.0, dist: 13.5, gal: 0.9, tint: [0.74, 0.88, 1.0] },
    surface: {
      panel: 'rgba(6, 10, 18, 0.38)', blur: 18, radius: 12,
      border: 'rgba(130, 190, 255, 0.26)', accent: '#5aa9ff',
      glow: 'rgba(90, 169, 255, 0.34)', sheen: 'rgba(220,240,255,0.06)',
    },
    layout: { align: 'flex-start', chip: 'pill', rail: '252px', density: 0.92, composer: 'line' },
  },
  {
    id: 'void-architecture',
    name: 'Void Architecture',
    intent: 'No visible disk: shadow, starfield, and hard architectural edges. Neutral.',
    scene: { temp: 0.9, expo: 0.62, incl: 0.9, dist: 15.0, gal: 0.55, tint: [0.86, 0.88, 0.92] },
    surface: {
      panel: 'rgba(8, 9, 12, 0.55)', blur: 8, radius: 0,
      border: 'rgba(190, 196, 210, 0.16)', accent: '#c9ceda',
      glow: 'rgba(160, 170, 190, 0.22)', sheen: 'rgba(255,255,255,0.04)',
    },
    layout: { align: 'flex-start', chip: 'rect', rail: '240px', density: 0.90, composer: 'line' },
  },
  {
    id: 'solar-ash',
    name: 'Solar Ash',
    intent: 'Ember light: high temperature, burnt-orange surfaces, small hole, right rail.',
    scene: { temp: 1.18, expo: 1.08, incl: 9.5, dist: 19.0, gal: 0.8, tint: [1.0, 0.80, 0.62] },
    surface: {
      panel: 'rgba(18, 11, 8, 0.42)', blur: 20, radius: 14,
      border: 'rgba(255, 170, 120, 0.24)', accent: '#ff9d63',
      glow: 'rgba(255, 140, 80, 0.34)', sheen: 'rgba(255,220,190,0.06)',
    },
    layout: { align: 'space-between', chip: 'pill', rail: '272px', density: 1.02, composer: 'line' },
  },
  {
    id: 'observatory',
    name: 'Observatory',
    intent: 'Documentary register: muted, desaturated, thin rules. The UI steps back.',
    scene: { temp: 0.82, expo: 0.80, incl: 6.8, dist: 20.5, gal: 1.1, tint: [0.86, 0.94, 0.90] },
    surface: {
      panel: 'rgba(10, 14, 13, 0.48)', blur: 12, radius: 3,
      border: 'rgba(150, 190, 175, 0.18)', accent: '#8fd0b4',
      glow: 'rgba(120, 200, 170, 0.22)', sheen: 'rgba(240,255,250,0.05)',
    },
    layout: { align: 'flex-start', chip: 'rect', rail: '256px', density: 0.95, composer: 'line' },
  },
]

export const DEFAULT_VARIANT = 'event-horizon'

export function variantById(id) {
  return GALACTIC_VARIANTS.find((v) => v.id === id) || GALACTIC_VARIANTS[0]
}

// ?galactic=<id or 1-based index>, then the stored choice, then the default.
export function resolveVariant(search, stored) {
  const want = String(search || '')
  const match = /[?&]galactic=([^&]+)/.exec(want)
  if (match) {
    const raw = decodeURIComponent(match[1])
    const byId = GALACTIC_VARIANTS.find((v) => v.id === raw)
    if (byId) return byId
    const idx = Number(raw)
    if (Number.isFinite(idx) && idx >= 1 && idx <= GALACTIC_VARIANTS.length) {
      return GALACTIC_VARIANTS[idx - 1]
    }
  }
  if (stored) {
    const byStored = GALACTIC_VARIANTS.find((v) => v.id === stored)
    if (byStored) return byStored
  }
  return variantById(DEFAULT_VARIANT)
}

// Applies a variant to the document as CSS custom properties. Everything visual
// downstream reads these, so the stylesheet has no per-variant branches.
export function applyVariant(variant, root = document.documentElement) {
  const { surface, layout } = variant
  root.dataset.galacticVariant = variant.id
  const set = (k, v) => root.style.setProperty(k, v)
  set('--gal-panel', surface.panel)
  set('--gal-blur', `${surface.blur}px`)
  set('--gal-radius', `${surface.radius}px`)
  set('--gal-border', surface.border)
  set('--gal-accent', surface.accent)
  set('--gal-glow', surface.glow)
  set('--gal-sheen', surface.sheen)
  set('--gal-align', layout.align)
  set('--gal-rail', layout.rail)
  set('--gal-density', String(layout.density))
  root.dataset.galacticChip = layout.chip
}
