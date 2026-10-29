// ═══════════════════════════════════════════════════════════════════════════
// SECTION OUTPUT PACKS — storyboard / social asset pack / packaging spec
//
// Item 9 of the 2026-10-11 directive. Video & UGC, Social and Packaging get a
// downloadable OUTPUT DOCUMENT built from the operator's own fields and the
// section's pre-flight report. NOTHING is rendered or generated here: a pack is
// a plan the operator executes with their own tools and footage.
//
// Pure functions, no imports, no network. Every field the operator did not
// supply stays UNKNOWN (never guessed). Every pack carries its pre-flight
// summary and states plainly that rendering is out of scope.
// ═══════════════════════════════════════════════════════════════════════════

import { buildVariantMatrix } from './variants.js'

const UNKNOWN = (what) => `UNKNOWN - ${what}`

function preflightOf(report = {}) {
  return {
    verdict: report.verdict || 'UNKNOWN',
    checked: report.checked ?? null,
    total: report.total ?? null,
    exportable: report.verdict ? report.verdict !== 'block' : false,
    note: 'The pack inherits this verdict from the section pre-flight; a blocked verdict means the pack is a checklist, not an upload-ready document.',
  }
}

function fieldOrUnknown(meta, id, what) {
  const v = meta?.[id]
  if (v === undefined || v === null || v === '') return UNKNOWN(what)
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  return v
}

function base(section, spec, meta, report, kind) {
  return {
    kind,
    section,
    format: spec ? { id: spec.id, label: spec.label, w: spec.w, h: spec.h, media: spec.media } : null,
    source_of_format: spec ? (spec.confidence || spec.source || 'registry') : 'UNKNOWN',
    generated_for: fieldOrUnknown(meta, 'filename', 'no export filename recorded'),
    preflight: preflightOf(report),
    no_rendering: true,
    no_generation: true,
    disclaimer: 'This pack is a plan and a checklist. The studio renders and generates nothing; you produce the asset with your own footage and tools.',
  }
}

// ── Video & UGC: storyboard pack ──────────────────────────────────────────
export function buildStoryboardPack({ spec, meta = {}, report = {} } = {}) {
  const duration = Number(meta.durationSeconds) || null
  const sceneCount = duration ? Math.max(1, Math.ceil(duration / 5)) : null
  return {
    ...base('video-ugc', spec, meta, report, 'storyboard_pack'),
    hook: fieldOrUnknown(meta, 'hook', 'write the first-3-seconds hook'),
    duration_seconds: duration ?? UNKNOWN('no duration recorded'),
    caption_text: fieldOrUnknown(meta, 'captionText', 'no caption text recorded'),
    scenes: sceneCount
      ? Array.from({ length: sceneCount }, (_, i) => ({
          index: i + 1,
          approx_start_s: i * 5,
          approx_end_s: Math.min(duration, (i + 1) * 5),
          frame_slot: `scene-${i + 1}.png`,
          on_screen_text: i === 0 ? fieldOrUnknown(meta, 'hook', 'hook') : '',
          note: 'Fill this frame with your own footage or still; the studio does not render frames.',
        }))
      : UNKNOWN('no duration recorded, so no scene breakdown can be derived'),
    disclosure: {
      synthetic_people: !!meta.syntheticPeople,
      xmp_marker_will_be_written: !!meta.syntheticPerformerTag,
      note: 'Disclosure state is carried from the section fields; the pack never decides it for you.',
    },
    production_notes: [
      'Mute-first: design for autoplay without sound; captions are separate assets.',
      'Keep text out of the platform UI strip and the bottom-right corner.',
      'No letterbox or pillar-box bars; do not end abruptly.',
    ],
  }
}

// ── Social: asset pack ────────────────────────────────────────────────────
export function buildSocialAssetPack({ spec, meta = {}, report = {} } = {}) {
  const targets = Array.isArray(meta.targets) ? meta.targets : []
  return {
    ...base('social', spec, meta, report, 'social_asset_pack'),
    placements: [
      { slot: 'primary', size: spec ? `${spec.w}x${spec.h}` : UNKNOWN('no format selected'), asset: fieldOrUnknown(meta, 'filename', 'no filename recorded') },
      { slot: 'alt_text', text: fieldOrUnknown(meta, 'altText', 'write the alt text'), required: true },
    ],
    // One master, every placement: the matrix says what each crop keeps and what
    // survives all of them. With no master/targets recorded it says so rather
    // than inventing a safe region.
    variants: (meta.master && targets.length)
      ? buildVariantMatrix({ master: meta.master, targets, focal: meta.focal })
      : UNKNOWN('record the master canvas (meta.master) and target placements (meta.targets)'),
    copy: {
      caption: fieldOrUnknown(meta, 'caption', 'write the caption'),
      link_title: fieldOrUnknown(meta, 'linkTitle', 'write the link title'),
    },
    reuse_checks: [
      'If this asset is reused as a listing main image it must pass the main-image rules: pure white background, 85% fill, no overlays.',
      'Amazon Attribution is the documented way to measure social traffic reaching Amazon; it is NOT wired in this build, so no reach figure is claimed.',
    ],
    note: 'Social copy is a platform concern; the pack carries only what you recorded.',
  }
}

// ── Packaging: spec sheet ─────────────────────────────────────────────────
export function buildPackagingSpec({ spec, meta = {}, report = {} } = {}) {
  return {
    ...base('packaging', spec, meta, report, 'packaging_spec'),
    pack_format: fieldOrUnknown(meta, 'packFormat', 'record the pack format'),
    dieline_reference: fieldOrUnknown(meta, 'dielineRef', 'record the dieline reference'),
    print_export_target: fieldOrUnknown(meta, 'exportTarget', 'record the print export target'),
    placement_instructions: [
      'Front panel: product name and net contents per your label requirements.',
      'Listing images of the pack must satisfy the main-image rules if used as the main image.',
      'Keep the actual pack identical to what is depicted: the buyer must receive what is shown.',
    ],
    hard_boundaries: [
      'A mock-up or digitally altered product image is NEVER Brand Registry enrollment proof: that requires an actual photograph.',
      'A packaging mockup is not a listing main image unless it satisfies the main-image rules.',
      'This build does not generate dielines or 3D folds.',
    ],
  }
}

// Human-readable rendering, used for the .md download.
export function packToMarkdown(pack) {
  if (!pack || typeof pack !== 'object') return '# Pack\n\nUNKNOWN - no pack was built.\n'
  const lines = [`# ${String(pack.kind || 'pack').replace(/_/g, ' ')}`, '']
  const walk = (v, indent = '') => {
    if (v === null || v === undefined) return
    if (Array.isArray(v)) {
      for (const item of v) {
        if (item && typeof item === 'object') {
          lines.push(`${indent}- `)
          walk(item, indent + '  ')
        } else {
          lines.push(`${indent}- ${String(item)}`)
        }
      }
      return
    }
    if (typeof v === 'object') {
      for (const [k, val] of Object.entries(v)) {
        if (val && typeof val === 'object') {
          lines.push(`${indent}**${k}**`)
          walk(val, indent + '  ')
        } else {
          lines.push(`${indent}- ${k}: ${val === undefined || val === null || val === '' ? 'UNKNOWN' : String(val)}`)
        }
      }
      return
    }
    lines.push(`${indent}- ${String(v)}`)
  }
  walk(pack)
  lines.push('', '> Rendering and generation are out of scope: this document is a plan.')
  return lines.join('\n') + '\n'
}
