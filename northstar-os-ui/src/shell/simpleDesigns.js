// Ten Northstar compositions. This is a layout catalogue, not a palette
// catalogue: each design changes where the session rail, focus tabs, reading
// column and composer sit. Backgrounds are paired from the FLUX 3 Galactic set
// so a design reads as one complete room.
export const SIMPLE_DESIGNS = [
  {
    id: 'hearth',
    name: 'Hearth',
    intent: 'The default reading room: sessions at left, focus across the top, composer at the bottom.',
    backdrop: 'orion-nursery',
    note: 'Centered reading column · left session rail',
  },
  {
    id: 'zen',
    name: 'Zen',
    intent: 'One quiet column. Sessions and status recede; the transcript and composer own the screen.',
    backdrop: 'pleiades-veil',
    note: 'No rail · centered 860px column',
  },
  {
    id: 'observatory',
    name: 'Observatory',
    intent: 'Instrument deck: session history moves right, the reading column owns the left.',
    backdrop: 'globular-core',
    note: 'Right rail · left reading column',
  },
  {
    id: 'constellation',
    name: 'Constellation',
    intent: 'A wide sky and a bottom-weighted composer with focus tabs floating above the conversation.',
    backdrop: 'magellanic-reef',
    note: 'No rail · focus sky bar',
  },
  {
    id: 'split',
    name: 'Split Deck',
    intent: 'Two-column studio: session strip on the left, a narrow reading column, generous negative space.',
    backdrop: 'carina-cliffs',
    note: 'Split deck · left index',
  },
  {
    id: 'instrument',
    name: 'Instrument',
    intent: 'Technical panel: square corners, thin rules, compact mono labels and a fixed session index.',
    backdrop: 'crab-pulsar',
    note: 'Instrument grid · compact type',
  },
  {
    id: 'magazine',
    name: 'Magazine',
    intent: 'Editorial spread: an oversized serif title, an index rail, and a long, calm reading measure.',
    backdrop: 'andromeda-spiral',
    note: 'Editorial type · wide measure',
  },
  {
    id: 'theater',
    name: 'Theater',
    intent: 'The art is the room: one floating glass card, no rail, and a composer that sits in the light.',
    backdrop: 'rose-galaxy',
    note: 'Floating glass · no rail',
  },
  {
    id: 'workbench',
    name: 'Workbench',
    intent: 'Sessions become a horizontal strip above the conversation, leaving the full width for work.',
    backdrop: 'meteor-rain',
    note: 'Horizontal sessions · full-width chat',
  },
  {
    id: 'terminal',
    name: 'Terminal',
    intent: 'A dark operator console: monospace labels, tight spacing, green signal, no decoration.',
    backdrop: 'black-hole-disk',
    note: 'Console type · high density',
  },
]

export const DEFAULT_SIMPLE_DESIGN = 'hearth'

export function simpleDesignById(id) {
  return SIMPLE_DESIGNS.find((d) => d.id === id) || SIMPLE_DESIGNS[0]
}

export function resolveSimpleDesign(search, stored) {
  const want = String(search || '')
  const match = /[?&](?:simple|design)=([^&]+)/.exec(want)
  if (match) {
    const raw = decodeURIComponent(match[1])
    const byId = SIMPLE_DESIGNS.find((d) => d.id === raw)
    if (byId) return byId
    const idx = Number(raw)
    if (Number.isFinite(idx) && idx >= 1 && idx <= SIMPLE_DESIGNS.length) {
      return SIMPLE_DESIGNS[idx - 1]
    }
  }
  if (stored) {
    const byStored = SIMPLE_DESIGNS.find((d) => d.id === stored)
    if (byStored) return byStored
  }
  return simpleDesignById(DEFAULT_SIMPLE_DESIGN)
}
