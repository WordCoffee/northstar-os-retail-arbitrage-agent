// Per-service theme tokens (U4).
//
// The "sports car" shift: the shell is neutral by default and takes on a service's
// accent the moment that service is the active tab. Themes are data, not CSS
// classes with hand-copied colours, so a contrast test can prove every one of
// them against the worst frame the scene engine is allowed to paint.
//
// Contrast model: panels are translucent glass, so the background a user actually
// reads against is `glass over sceneWorst`, not the flat panel colour. Every
// theme declares the brightest colour its scene may reach behind the glass
// (`sceneWorst`); `worstComposite()` blends and the test measures that.
//
// Nothing here renders. Components read the CSS variables this module emits.

import { THEMES as REGISTRY_THEMES, SERVICE_REGISTRY } from '../data/serviceRegistry.js'

/** Text must reach WCAG AA against the worst composite. */
export const AA_TEXT = 4.5
/** Non-text UI (borders, icons, focus rings) must reach AA large/UI. */
export const AA_UI = 3

export const BASE_TOKENS = {
  ink: '#f2f6fb',
  inkDim: '#d7e1ec',
  surface: '#161d27',
  surface2: '#1d2633',
  // 0.72 keeps the scene legible behind the glass while ink stays above AA even
  // over the brightest frame (see the contrast test: worst pixel, not average).
  glassAlpha: 0.72,
  glass2Alpha: 0.8,
  line: 'rgba(255, 255, 255, 0.12)',
}

// The brightest frame each scene may paint behind the glass. U5's scene engine
// must clamp to this value; the contrast test fails if a theme has no budget.
const SCENE_WORST = {
  neutral: '#2a3550',
  studio: '#4a3418',
  ppc: '#472220',
  research: '#332a5c',
  goose: '#16382c',
  ledger: '#173533',
  monitor: '#2a3038',
  account: '#2e2a24',
}

// Ink used on top of the accent (primary glass buttons). Dark enough that the
// accent itself can stay vivid without failing AA on its own surface.
const ACCENT_INK = {
  neutral: '#08111f',
  studio: '#1a1204',
  ppc: '#1b0a07',
  research: '#100c28',
  goose: '#04231a',
  ledger: '#05201e',
  monitor: '#0d1116',
  account: '#141210',
}

export function hexToRgb(hex) {
  const s = String(hex).replace('#', '').trim()
  const full = s.length === 3 ? s.split('').map(c => c + c).join('') : s
  if (!/^[0-9a-f]{6}$/i.test(full)) throw new Error(`not a hex colour: ${hex}`)
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ]
}

export function toHex(rgb) {
  return '#' + rgb.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('')
}

/** Composite `fg` at `alpha` over an opaque `bg`. */
export function compositeOver(fg, alpha, bg) {
  const f = hexToRgb(fg)
  const b = hexToRgb(bg)
  return toHex(f.map((v, i) => v * alpha + b[i] * (1 - alpha)))
}

export function relativeLuminance(hex) {
  const channel = (v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = hexToRgb(hex)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

export function contrastRatio(a, b) {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** The brightest composite a glass panel can have in this theme. */
export function worstComposite(themeId) {
  const t = tokensFor(themeId)
  if (!t) throw new Error(`unknown theme: ${themeId}`)
  return compositeOver(BASE_TOKENS.surface, BASE_TOKENS.glassAlpha, t.sceneWorst)
}

export function themeIds() {
  return Object.keys(REGISTRY_THEMES)
}

export function tokensFor(themeId) {
  const base = REGISTRY_THEMES[themeId]
  if (!base) return null
  return {
    id: themeId,
    accent: base.accent,
    accentSoft: base.accentSoft,
    accentInk: ACCENT_INK[themeId],
    sceneWorst: SCENE_WORST[themeId],
  }
}

/**
 * CSS custom properties for a theme. Unknown ids fall back to neutral rather
 * than emitting an empty map (a shell with no tokens renders transparent text).
 */
export function themeVars(themeId) {
  const t = tokensFor(themeId) || tokensFor('neutral')
  return {
    '--wb-accent': t.accent,
    '--wb-accent-soft': t.accentSoft,
    '--wb-accent-ink': t.accentInk,
    '--wb-ink': BASE_TOKENS.ink,
    '--wb-ink-dim': BASE_TOKENS.inkDim,
    '--wb-glass': `rgba(${hexToRgb(BASE_TOKENS.surface).join(', ')}, ${BASE_TOKENS.glassAlpha})`,
    '--wb-glass-2': `rgba(${hexToRgb(BASE_TOKENS.surface2).join(', ')}, ${BASE_TOKENS.glass2Alpha})`,
    '--wb-line': BASE_TOKENS.line,
    '--wb-scene-worst': t.sceneWorst,
    '--wb-solid': BASE_TOKENS.surface,
    '--wb-shift-ms': '600ms',
  }
}

/**
 * One entry per service in the registry, so the unit snapshot covers every
 * service rather than only every theme (two services can share a theme).
 */
export function serviceThemeSnapshot() {
  const out = {}
  for (const service of SERVICE_REGISTRY) {
    out[service.id] = { theme: service.theme, vars: themeVars(service.theme) }
  }
  return out
}
