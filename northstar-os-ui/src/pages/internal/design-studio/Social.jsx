// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: SOCIAL
// // Social output planned against the same registry and pre-flight as everything
// else. No Amazon spec applies to a social format, so those formats are
// honestly labelled UNSOURCED for Amazon purposes and cannot be exported as an
// Amazon asset.
// Every spec comes from the registry; every rule comes from the engine.
// ???????????????????????????????????????????????????????????????????????????

import SectionWorkspace from './SectionWorkspace.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'

const GROUPS = SPEC_GROUPS.filter(g => ['Listing gallery', 'Store tiles'].includes(g.id))


const FIELDS = [
  { id: 'caption', kind: 'textarea', rows: 3, maxLength: 2200, label: 'Caption',
    note: 'Social copy is a platform concern, not an Amazon one. Amazon Attribution is the documented mechanism for measuring social traffic that reaches Amazon (not wired in this build).' },
  { id: 'linkTitle', kind: 'text', maxLength: 60, label: 'Link title', note: 'If this asset is reused in a Store tile, the link title obscures 19% (rectangle) or 12% (square) of the bottom band.' },
]

const RULES = [
  { label: 'Amazon specs do not cover social', tone: 'flag', detail: 'There is no Amazon main-image or A+ rule for a social post. This section reuses the same compliance engine only where an Amazon spec genuinely applies (for example when the same asset is reused in the gallery or a Store tile).', source: 'spec registry ? 2026-10-10' },
  { label: 'Attribution, not guessing', tone: 'flag', detail: 'Amazon documents Amazon Attribution as the way to measure external traffic. It is not wired in this build, so no reach or conversion figure is claimed here.', source: 'research ? 2026-10-10' },
  { label: 'Reuse is checked, not assumed', tone: 'flag', detail: 'An asset reused as a listing main image inherits the white-background, 85%-fill and no-overlay blocks from that format.', source: 'product image guide ? 2026-10-10' },
]

const SLOTS = [
  { id: 'amz-secondary', label: 'Reusable 1600x1600', specId: 'amz-secondary', icon: 'image' },
  { id: 'store-tile-square', label: 'Store reuse 1:1', specId: 'store-tile-small', icon: 'grid' },
  { id: 'amz-main', label: 'If used as main', specId: 'amz-main', icon: 'star' },
]

export default function Social() {
  return (
    <SectionWorkspace
      title="Social"
      subtitle="Social output on the same pre-flight ? Amazon rules apply only where the asset is reused on Amazon"
      groups={GROUPS} defaultSpecId="amz-secondary"
      fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
      canvasFitWidth={560} testId="social-workspace"
    />
  )
}
