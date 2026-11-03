// U8 — bounded canvas instructions.
//
// This is the layer a Bojo instruction lands on. It is deliberately a PARSER and
// a REDUCER, not a router: the instruction arrives through the existing chat
// turn, and this module only answers "what does this sentence mean for the
// open document, and what is the smallest edit that satisfies it?".
//
// Rules that make it safe to hand a model's sentence to it:
//  • It only ever moves a property it names. No instruction creates a tool, a
//    file, a network call or a new layer kind.
//  • A sentence it does not understand is REFUSED (`null`), never approximated.
//    A confident wrong edit is worse than "I did not understand that".
//  • Every refusal names what is missing ("no headline on this canvas").
//  • Text is never generated; the operator's words are the text.

import {
  addText, lastLayerId,
} from './studioCanvas.js'
import { updateLayer } from '../studio/engine/doc.js'

export const SCALE_STEP = 0.2 // 20% per "bigger"/"smaller"
export const TEXT_MIN = 0.01
export const TEXT_MAX = 0.2

const clean = (s) => String(s || '').trim()
const lower = (s) => clean(s).toLowerCase().replace(/[.!?]+$/, '')

const BIGGER = /\b(bigger|larger|increase|grow|bump)\b/
const SMALLER = /\b(smaller|decrease|reduce|shrink|shrinkage)\b/

const ROLE_WORDS = [
  { role: 'headline', words: ['headline', 'title', 'heading'] },
  { role: 'subhead', words: ['subhead', 'subheading', 'subtitle', 'kicker'] },
  { role: 'body', words: ['body', 'body copy', 'paragraph', 'copy'] },
]

function roleFromText(text) {
  const t = lower(text)
  for (const entry of ROLE_WORDS) {
    if (entry.words.some((w) => t.includes(w))) return entry.role
  }
  return ''
}

/**
 * Read one instruction. Returns `null` when the sentence is not a canvas
 * instruction this module understands — the caller must then answer honestly
 * rather than guess.
 */
export function parseInstruction(text) {
  const raw = clean(text)
  if (!raw) return null
  const t = lower(raw)

  // "set the headline to Spring drop" / "change the title to X"
  const set = /^(?:please\s+)?(?:set|change|rename|make)\s+(?:the\s+)?(headline|title|heading|subhead|subheading|subtitle|body(?:\s+copy)?|copy)\s+(?:to|say|read)\s+(.+)$/.exec(t)
  if (set) {
    return { op: 'set_text', role: roleFromText(set[1]), text: clean(raw.slice(raw.toLowerCase().indexOf(set[2]))) }
  }

  // "make the headline bigger" / "make the headline 30% bigger"
  const scale = /^(?:please\s+)?(?:make|scale|resize)\s+(?:the\s+)?(headline|title|heading|subhead|subheading|subtitle|body(?:\s+copy)?|copy|selected layer|layer)\s+(?:(?:by\s+)?(\d{1,2})\s?%\s+)?(bigger|larger|smaller|decrease|increase|grow|reduce|shrink)$/.exec(t)
  if (scale) {
    const dir = BIGGER.test(scale[3]) ? 1 : -1
    const pct = scale[2] ? Math.min(90, Number(scale[2])) / 100 : SCALE_STEP
    return {
      op: 'scale_text',
      role: scale[1].includes('layer') ? '' : roleFromText(scale[1]),
      selected: scale[1].includes('layer'),
      factor: dir * pct,
    }
  }

  // "add a headline saying Fresh stock" / "add a subhead"
  const add = /^(?:please\s+)?add\s+(?:a|an)\s+(headline|title|heading|subhead|subheading|subtitle|body(?:\s+copy)?)\s*(?:saying|that says|with the text)?\s*(.*)$/.exec(t)
  if (add) {
    const role = roleFromText(add[1]) || 'headline'
    const rest = clean(add[2])
    return { op: 'add_text', role, text: rest ? clean(raw.slice(raw.toLowerCase().indexOf(rest))) : '' }
  }

  // "select the headline" / "select the image"
  const select = /^(?:please\s+)?select\s+(?:the\s+)?(headline|title|subhead|body|image|photo|shape|background|first layer|last layer)$/.exec(t)
  if (select) return { op: 'select', what: select[1] }

  // "swap in the cutout" / "swap in plate.png"
  const swap = /^(?:please\s+)?(?:swap|replace|switch)\s+(?:in|to)\s+(?:the\s+)?(.+)$/.exec(t)
  if (swap) return { op: 'swap_asset', name: clean(raw.slice(raw.toLowerCase().indexOf(swap[1]))) }

  return null
}

function findTextLayer(doc, { role = '', selected = '' } = {}) {
  const texts = doc.layers.filter((l) => l.kind === 'text')
  if (selected) {
    const sel = texts.find((l) => l.id === selected)
    return sel || null
  }
  if (role) return texts.find((l) => l.role === role) || null
  return texts.length === 1 ? texts[0] : null
}

/**
 * Apply a parsed instruction to a document. Pure: returns a new document and a
 * summary, or a refusal that names the reason. `selected` is the current
 * selection id, `assets` the canvas assets.
 */
export function applyInstruction(doc, instruction, { selected = '', assets = [] } = {}) {
  if (!instruction) {
    return { ok: false, error: 'I did not understand that as a canvas instruction. Nothing was changed.', doc }
  }
  if (!doc || !Array.isArray(doc.layers)) {
    return { ok: false, error: 'No canvas is open. Nothing was changed.', doc }
  }

  if (instruction.op === 'set_text') {
    const layer = findTextLayer(doc, { role: instruction.role })
    if (!layer) {
      return { ok: false, error: `There is no ${instruction.role || 'text'} layer on this canvas. Add one first.`, doc }
    }
    const next = updateLayer(doc, layer.id, { text: instruction.text })
    return { ok: true, doc: next, layerId: layer.id, summary: `Set the ${layer.role || 'text'} to "${instruction.text}".` }
  }

  if (instruction.op === 'scale_text') {
    // "the selected layer" means exactly that: with nothing selected, refuse
    // rather than quietly picking the only text layer.
    if (instruction.selected && !selected) {
      return { ok: false, error: 'No text layer is selected. Select one on the canvas first.', doc }
    }
    const layer = findTextLayer(doc, { role: instruction.role, selected: instruction.selected ? selected : '' })
    if (!layer) {
      const why = instruction.selected
        ? 'No text layer is selected.'
        : `There is no ${instruction.role || 'text'} layer on this canvas.`
      return { ok: false, error: `${why} Nothing was changed.`, doc }
    }
    const before = Number(layer.size ?? 0.05)
    const after = Math.max(TEXT_MIN, Math.min(TEXT_MAX, before * (1 + instruction.factor)))
    if (Math.abs(after - before) < 0.0005) {
      return { ok: false, error: `The ${layer.role || 'text'} is already at the ${instruction.factor > 0 ? 'largest' : 'smallest'} size this canvas allows.`, doc }
    }
    const next = updateLayer(doc, layer.id, { size: after })
    return {
      ok: true,
      doc: next,
      layerId: layer.id,
      summary: `Made the ${layer.role || 'text'} ${Math.round(Math.abs(instruction.factor) * 100)}% ${instruction.factor > 0 ? 'bigger' : 'smaller'} (${Math.round(before * 100)}% -> ${Math.round(after * 100)}% of the canvas height).`,
    }
  }

  if (instruction.op === 'add_text') {
    const preset = instruction.role === 'subhead' ? 'subhead' : instruction.role === 'body' ? 'body' : 'headline'
    const next = addText(doc, { text: instruction.text || 'Your headline', preset })
    return { ok: true, doc: next, layerId: lastLayerId(next), summary: `Added a ${preset} layer.` }
  }

  if (instruction.op === 'select') {
    const what = instruction.what
    const byKind = { image: 'image', photo: 'image', shape: 'shape', background: 'bg' }[what]
    const texts = doc.layers.filter((l) => l.kind === 'text')
    let layer = null
    if (byKind) layer = doc.layers.find((l) => l.kind === byKind)
    else if (what === 'first layer') layer = doc.layers[0]
    else if (what === 'last layer') layer = doc.layers[doc.layers.length - 1]
    else {
      const role = roleFromText(what)
      layer = texts.find((l) => l.role === role) || null
    }
    if (!layer) return { ok: false, error: `There is no ${what} layer to select.`, doc }
    return { ok: true, doc, layerId: layer.id, summary: `Selected ${layer.name || layer.kind}.` }
  }

  if (instruction.op === 'swap_asset') {
    const wanted = lower(instruction.name)
    const asset = assets.find((a) => lower(a.name) === wanted)
      || assets.find((a) => lower(a.name).includes(wanted))
      || assets.find((a) => lower(a.id) === wanted)
    if (!asset) {
      return {
        ok: false,
        error: assets.length
          ? `No asset matches "${instruction.name}". This canvas holds: ${assets.map((a) => a.name).join(', ')}.`
          : `This canvas has no assets yet. Upload one first.`,
        doc,
      }
    }
    const target = doc.layers.find((l) => l.id === selected && l.kind === 'image')
      || doc.layers.find((l) => l.kind === 'image')
    if (!target) {
      return { ok: false, error: 'There is no image layer to swap. Add one first.', doc }
    }
    const next = updateLayer(doc, target.id, { assetId: asset.id, name: asset.name })
    return { ok: true, doc: next, layerId: target.id, summary: `Swapped ${asset.name} into the image layer.` }
  }

  return { ok: false, error: `The "${instruction.op}" instruction is not implemented. Nothing was changed.`, doc }
}

/** The short description Bojo is given about the open canvas. */
export function describeCanvas(doc, { selected = '', assets = [] } = {}) {
  if (!doc || !Array.isArray(doc.layers)) return null
  return {
    id: doc.id,
    name: doc.name,
    contentType: doc.contentType || '',
    w: doc.w,
    h: doc.h,
    selected: selected || '',
    layers: doc.layers.map((l) => ({
      id: l.id,
      kind: l.kind,
      name: l.name || l.kind,
      role: l.role || '',
      text: l.kind === 'text' ? String(l.text || '') : undefined,
      size: l.kind === 'text' ? l.size : undefined,
    })),
    assets: assets.map((a) => ({ id: a.id, name: a.name })),
  }
}

export default { parseInstruction, applyInstruction, describeCanvas, SCALE_STEP }
