// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — HOOK / AD STRUCTURES  (REA candidate V3)
//
// Reverse-engineered from the sources read for reports/video_ad_structures_
// 20261028.md, not invented here. Every template names the sources that show
// it, and every source carries a confidence label:
//
//   REPORTED  the claim came from a vendor/practitioner page (no reproducible
//             data behind it) — the STRUCTURE is usable, the PERFORMANCE claim
//             is not. No template below promises lift.
//
// The timing windows are the one thing the sources agree on: the hook lands in
// 1-3 s, the body carries one promise, the CTA closes. Where the sources
// disagree (exact shot lengths), this file does not pick a winner — it exposes
// the window as data so an operator can set it.
//
// Platform duration windows are the published ones (Amazon SB 6-45 s / store
// 2-20 s, X <= 15 s recommended, TikTok up to 10 min with 21-34 s recommended);
// the Amazon numbers are the ones already enforced in VideoUgc.jsx.
// ═══════════════════════════════════════════════════════════════════════════

export const HOOK_SOURCES = {
  'truefuture': {
    id: 'truefuture', label: 'TrueFuture — the science of the short-form hook',
    url: 'https://www.truefuturemedia.com/articles/science-of-short-form-video-hooks',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'open on evidence/action/result, never a logo; see-it/understand-it/anticipate-it',
  },
  'vyra': {
    id: 'vyra', label: 'Vyra — how to write a hook',
    url: 'https://www.usevyra.com/how-to/write-a-hook',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'start on movement; 3-5 word on-screen hook held ~2 s',
  },
  'clipping-culture': {
    id: 'clipping-culture', label: 'Clipping Culture — 8 hook formulas',
    url: 'https://clippingculture.com/blog/short-form-video-hooks-guide',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'open on payoff or problem; "flag the mistake" formula',
  },
  'moonb': {
    id: 'moonb', label: 'Moonb — short video ads (2026)',
    url: 'https://www.moonb.io/blog/short-video-ads',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'length-by-objective table; open on a frustration the viewer knows',
  },
  'adligator': {
    id: 'adligator', label: 'Adligator — short-form ads: hooks, length, frameworks',
    url: 'https://adligator.com/blog/short-form-video-ads-facebook-instagram',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'fixed hook/value/proof/CTA structure; 15-30 s direct response',
  },
  'captions': {
    id: 'captions', label: 'Captions — video hook writing',
    url: 'https://captions.ai/help/guides/marketing/hook-writing',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'hook inside 1-3 s on short-form; mistake hook named for Shorts',
  },
  'creatify': {
    id: 'creatify', label: 'Creatify — YouTube ads that convert (2026)',
    url: 'https://creatify.ai/blog/youtube-ads-how-to-create-video-ads-that-convert-in-2026',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'hook > problem > tension > solution > proof > CTA',
  },
  'adssensor': {
    id: 'adssensor', label: 'AdsSensor — the first 3 seconds',
    url: 'https://adssensor.com/blog/short-form-video-ads-creative-guide',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'hook 0-3 s, value 3-10 s, then proof, then CTA; captions are mandatory (sound-off)',
  },
  'sovran': {
    id: 'sovran', label: 'Sovran — hook / body / CTA framework',
    url: 'https://sovran.ai/blog/hook-body-cta-video-editor-the-ultimate-guide-to-creating-high-converting-video-ads-in-2025',
    pulled: '2026-10-28', confidence: 'REPORTED',
    shows: 'beat windows: hook 1-3 s, body 7-20 s, CTA 2-5 s',
  },
}

// Published duration windows. `source` says where each came from.
export const DURATION_WINDOWS = {
  amazonSbVideo: { min: 6, max: 45, source: 'sbv (registry, VideoUgc.jsx:19)' },
  amazonStore: { min: 2, max: 20, source: 'sbv (registry, VideoUgc.jsx:19)' },
  xVideo: { min: 0, max: 140, source: 'x-creative-specs (2:20 supported)' },
  tiktok: { min: 4, max: 600, source: 'tiktok-infeed (up to 10 min)' },
}

/**
 * Five structures, each a beat list. Beats are fractions of the total duration
 * so one template renders at 12 s or 30 s without rewriting the plan.
 */
export const HOOK_TEMPLATES = [
  {
    id: 'H1', name: 'Open on the payoff',
    beats: [
      { id: 'hook', from: 0.0, to: 0.125, job: 'show the finished result' },
      { id: 'name', from: 0.125, to: 0.25, job: 'say what it is in one line' },
      { id: 'mechanism', from: 0.25, to: 0.83, job: 'how it works, visibly' },
      { id: 'cta', from: 0.83, to: 1.0, job: 'one call to action' },
    ],
    slots: { hook: { max: 60, required: true }, product: { max: 40, required: true } },
    sources: ['truefuture', 'vyra', 'clipping-culture'],
  },
  {
    id: 'H2', name: 'Name the problem',
    beats: [
      { id: 'hook', from: 0.0, to: 0.17, job: 'the frustration, in the viewer words' },
      { id: 'cause', from: 0.17, to: 0.42, job: 'why it happens' },
      { id: 'fix', from: 0.42, to: 0.83, job: 'the product resolving it' },
      { id: 'cta', from: 0.83, to: 1.0, job: 'one call to action' },
    ],
    slots: { hook: { max: 60, required: true }, product: { max: 40, required: true } },
    sources: ['moonb', 'adligator', 'creatify'],
  },
  {
    id: 'H3', name: 'The mistake',
    beats: [
      { id: 'hook', from: 0.0, to: 0.17, job: 'name the mistake' },
      { id: 'cost', from: 0.17, to: 0.42, job: 'what it costs' },
      { id: 'fix', from: 0.42, to: 0.83, job: 'the correction' },
      { id: 'cta', from: 0.83, to: 1.0, job: 'one call to action' },
    ],
    slots: { hook: { max: 60, required: true }, product: { max: 40, required: true } },
    sources: ['clipping-culture', 'captions'],
    evidence: 'thin',
    evidence_gap: 'only two independent sources show the mistake hook; nobody else names it',
  },
  {
    id: 'H4', name: 'Unsolicited proof',
    beats: [
      { id: 'hook', from: 0.0, to: 0.17, job: 'the number or the test, on screen' },
      { id: 'method', from: 0.17, to: 0.67, job: 'how it was measured' },
      { id: 'context', from: 0.67, to: 0.83, job: 'what it means for the buyer' },
      { id: 'cta', from: 0.83, to: 1.0, job: 'one call to action' },
    ],
    slots: { hook: { max: 60, required: true }, proof: { max: 40, required: true } },
    sources: ['adligator', 'creatify', 'adssensor'],
  },
  {
    id: 'H5', name: 'Before / after flash',
    beats: [
      { id: 'hook', from: 0.0, to: 0.125, job: 'before and after in one frame pair' },
      { id: 'delta', from: 0.125, to: 0.29, job: 'name the difference' },
      { id: 'how', from: 0.29, to: 0.83, job: 'how it is done' },
      { id: 'cta', from: 0.83, to: 1.0, job: 'one call to action' },
    ],
    slots: { hook: { max: 60, required: true }, product: { max: 40, required: true } },
    sources: ['moonb', 'truefuture'],
    evidence: 'thin',
    evidence_gap: 'before/after is named by two sources; neither shows a timed example',
  },
]

export function hookTemplate(templateId) {
  const t = HOOK_TEMPLATES.find(x => x.id === templateId)
  if (!t) {
    throw new Error(`unknown hook template ${JSON.stringify(templateId)}; `
      + `known: ${HOOK_TEMPLATES.map(x => x.id).join(', ')}`)
  }
  return t
}

/**
 * Turn a template + slot values into a timed storyboard.
 * Refuses when a required slot is missing or over its character budget — it does
 * not pad or invent copy.
 */
export function storyboardFromTemplate(templateId, slots = {}, { durationSeconds = 12, platform = 'amazonSbVideo' } = {}) {
  const template = hookTemplate(templateId)
  const duration = Number(durationSeconds)
  const errors = []

  const window = DURATION_WINDOWS[platform]
  if (!window) errors.push(`unknown platform window ${platform}`)
  else if (duration < window.min || duration > window.max) {
    errors.push(`duration ${duration}s is outside the ${platform} window `
      + `${window.min}-${window.max}s (${window.source})`)
  }

  for (const [name, rule] of Object.entries(template.slots)) {
    const value = slots[name]
    if (rule.required && (value === undefined || value === null || String(value).trim() === '')) {
      errors.push(`slot '${name}' is required`)
      continue
    }
    if (value !== undefined && String(value).length > rule.max) {
      errors.push(`slot '${name}' is ${String(value).length} chars; the cap is ${rule.max}`)
    }
  }

  const beats = template.beats.map(b => ({
    id: b.id,
    job: b.job,
    start_s: Number((b.from * duration).toFixed(2)),
    end_s: Number((b.to * duration).toFixed(2)),
    text: slots[b.id] ?? (b.id === 'hook' ? slots.hook ?? '' : ''),
  }))

  return {
    ok: errors.length === 0,
    errors,
    template: { id: template.id, name: template.name, sources: template.sources },
    duration_s: duration,
    platform,
    beats,
    captions_required: true,
    note: 'Structure only. The sources are practitioner pages; none of them proves '
        + 'a performance lift, so this plan makes no lift claim.',
  }
}
