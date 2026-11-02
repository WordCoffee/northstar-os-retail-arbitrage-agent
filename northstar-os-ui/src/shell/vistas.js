// VISTA LIBRARY — daily celestial vista rotation (Northstar plan §2.2).
// Deterministic daily seed: hash of UTC date + account, so a user sees the
// same vista all day and a different one tomorrow. Never random per reload.
export const VISTAS = [
  { id: 1, name: 'Gargantua approach', note: 'Film-faithful hole; disc plane low in frame' },
  { id: 2, name: 'Ring plane transit', note: 'Ice-ringed giant; thin rings crossing the frame' },
  { id: 3, name: 'Emission nebula field', note: 'Warm hydrogen tones; dark dust lanes' },
  { id: 4, name: 'Milky Way core rise', note: 'Dust-laned galactic band over a low horizon glow' },
  { id: 5, name: 'Comet pass', note: 'Bright nucleus + twin tails; slow drift' },
  { id: 6, name: 'Binary star rise', note: 'Twin suns low; long shadow gradient' },
  { id: 7, name: 'Deep field', note: 'Thousands of faint stars; one distant spiral galaxy' },
]

function hashSeed(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export function vistaForToday(accountId = '', now = null) {
  const d = now ? new Date(now) : new Date()
  const key = `${d.getUTCFullYear()}-${d.getUTCMonth() + 1}-${d.getUTCDate()}::${accountId || 'anon'}`
  const idx = hashSeed(key) % VISTAS.length
  return VISTAS[idx]
}

export function vistaIndexForToday(accountId = '', now = null) {
  const d = now ? new Date(now) : new Date()
  const key = `${d.getUTCFullYear()}-${d.getUTCMonth() + 1}-${d.getUTCDate()}::${accountId || 'anon'}`
  return hashSeed(key) % VISTAS.length
}