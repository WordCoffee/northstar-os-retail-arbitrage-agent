// SCENE REGISTRY — which scene a service gets.
//
// A scene is a palette + a poster + a handful of motion numbers, not a shader
// program. The poster is one of the ten FLUX galactic plates already shipped in
// `src/assets/galactic/` (via `galacticVariants.js`), so the still-frame
// fallback and the animated plate are the same picture: switching to the
// fallback is a change of motion, not a change of place.
//
// Everything here is pure data + pure lookups: no React, no DOM, no fetches.
// `sceneRegistry.test.js` pins the service list, so a new tab route without a
// scene fails a test instead of showing the home scene under the wrong label.

import { variantById, DEFAULT_VARIANT } from '../shell/galacticVariants.js'

/** The scene used when a route is not a workspace (chat-first /home, admin…). */
export const DEFAULT_SCENE_SERVICE = 'home'

// service id -> { label, variant, route, spec }
//   route: the URL prefix this service owns (longest prefix wins)
//   spec:  the numbers the 2D painter reads (star count, drift, orbit arcs, focus)
const SERVICE_SCENES = {
  'design-studio': {
    label: 'Carina Ridge', variant: 'carina-cliffs', route: '/design-studio',
    spec: { stars: 74, drift: 0.55, arcs: 2, ax: 0.62, ay: 0.54 },
  },
  'product-finder': {
    label: 'Orion Cradle', variant: 'orion-nursery', route: '/product-finder',
    spec: { stars: 104, drift: 0.4, arcs: 3, ax: 0.44, ay: 0.58 },
  },
  'golden-goose': {
    label: 'Pulsar Heart', variant: 'crab-pulsar', route: '/golden-goose',
    spec: { stars: 88, drift: 0.62, arcs: 2, ax: 0.55, ay: 0.5 },
  },
  listings: {
    label: 'Globular Core', variant: 'globular-core', route: '/listings',
    spec: { stars: 132, drift: 0.3, arcs: 3, ax: 0.5, ay: 0.56 },
  },
  listingforge: {
    label: 'Andromeda Spiral', variant: 'andromeda-spiral', route: '/listingforge',
    spec: { stars: 92, drift: 0.45, arcs: 4, ax: 0.52, ay: 0.6 },
  },
  adpilot: {
    label: 'Meteor Rain', variant: 'meteor-rain', route: '/adpilot',
    spec: { stars: 80, drift: 0.72, arcs: 1, ax: 0.46, ay: 0.62 },
  },
  socialpulse: {
    label: 'Rose Galaxy', variant: 'rose-galaxy', route: '/socialpulse',
    spec: { stars: 96, drift: 0.38, arcs: 3, ax: 0.56, ay: 0.52 },
  },
  profitability: {
    label: 'Seven Sisters', variant: 'pleiades-veil', route: '/profitability',
    spec: { stars: 68, drift: 0.28, arcs: 2, ax: 0.48, ay: 0.5 },
  },
  autothink: {
    label: 'Lensed Disk', variant: 'black-hole-disk', route: '/autothink',
    spec: { stars: 118, drift: 0.34, arcs: 3, ax: 0.5, ay: 0.54 },
  },
  'keyword-tracker': {
    label: 'Magellanic Reef', variant: 'magellanic-reef', route: '/keyword-tracker',
    spec: { stars: 110, drift: 0.5, arcs: 2, ax: 0.58, ay: 0.58 },
  },
  'competitor-monitor': {
    label: 'Orion Cradle', variant: 'orion-nursery', route: '/competitor-monitor',
    spec: { stars: 86, drift: 0.42, arcs: 2, ax: 0.42, ay: 0.56 },
  },
  home: {
    label: 'Deep Field', variant: DEFAULT_VARIANT, route: '',
    spec: { stars: 120, drift: 0.25, arcs: 3, ax: 0.5, ay: 0.58 },
  },
}

export const SCENE_SERVICE_IDS = Object.keys(SERVICE_SCENES)

// A dark, accent-tinted sky, derived once instead of hand-tuned twelve times:
// the poster is the bright object, the sky behind it is the same hue at 12%.
function tint(hex, amount) {
  const value = String(hex || '#8fb4ff').replace('#', '')
  const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value
  const n = parseInt(full.slice(0, 6), 16)
  if (Number.isNaN(n)) return '#05070d'
  const channel = (shift) => Math.round((((n >> shift) & 255) * amount) + 6)
  const to2 = (v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0')
  return `#${to2(channel(16))}${to2(channel(8))}${to2(channel(0))}`
}

function buildScene(serviceId) {
  const spec = SERVICE_SCENES[serviceId] || SERVICE_SCENES[DEFAULT_SCENE_SERVICE]
  const variant = variantById(spec.variant) || variantById(DEFAULT_VARIANT)
  const accent = variant?.surface?.accent || '#8fb4ff'
  return {
    id: serviceId in SERVICE_SCENES ? serviceId : DEFAULT_SCENE_SERVICE,
    serviceId: serviceId in SERVICE_SCENES ? serviceId : DEFAULT_SCENE_SERVICE,
    label: spec.label,
    variantId: variant?.id || DEFAULT_VARIANT,
    poster: variant?.image || '',
    accent,
    sky: [tint(accent, 0.34), '#04060b'],
    spec: { ...spec.spec },
  }
}

const CACHE = new Map()

/** The scene a service renders. Unknown ids get the home scene, never null. */
export function sceneForService(serviceId = DEFAULT_SCENE_SERVICE) {
  const key = serviceId in SERVICE_SCENES ? serviceId : DEFAULT_SCENE_SERVICE
  if (!CACHE.has(key)) CACHE.set(key, buildScene(key))
  return CACHE.get(key)
}

/** Longest route prefix wins, on a segment boundary. Pure. */
export function sceneServiceIdForPath(pathname = '/') {
  const path = String(pathname).replace(/\/+$/, '') || '/'
  let best = null
  let bestLength = -1
  for (const id of SCENE_SERVICE_IDS) {
    const route = SERVICE_SCENES[id].route
    if (!route) continue
    const normalized = route.replace(/\/+$/, '')
    const owns = path === normalized || path.startsWith(`${normalized}/`)
    if (owns && normalized.length > bestLength) {
      best = id
      bestLength = normalized.length
    }
  }
  return best || DEFAULT_SCENE_SERVICE
}

/** Every service id a tab can open. Kept beside the map so tests can pin it. */
export function sceneServiceRoutes() {
  return SCENE_SERVICE_IDS
    .filter((id) => SERVICE_SCENES[id].route)
    .map((id) => ({ id, route: SERVICE_SCENES[id].route }))
}
