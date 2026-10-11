// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: PACKAGING & MOCKUPS
// // Packaging and mockup planning. HARD BOUNDARY: a mock-up or digitally
// altered product image is never Brand Registry enrollment proof, and it is
// never a listing main image unless it satisfies the main-image rules.
// Every spec comes from the registry; every rule comes from the engine.
// ???????????????????????????????????????????????????????????????????????????

import SectionWorkspace from './SectionWorkspace.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'
import { buildPackagingSpec } from '../../../studio/engine/outputPacks.js'

const GROUPS = SPEC_GROUPS.filter(g => ['Listing gallery', 'Store tiles'].includes(g.id))


const FIELDS = [
  { id: 'packFormat', kind: 'text', label: 'Pack format', placeholder: 'Carton / pouch / label...',
    note: 'Structure is chosen before artwork so the product fidelity is enforced by construction.' },
  { id: 'dielineRef', kind: 'text', label: 'Dieline reference',
    note: 'Record the dieline or supplier reference. This build does not generate dielines.' },
  { id: 'exportTarget', kind: 'text', label: 'Print export target', placeholder: 'DXF / AI / PDF',
    note: 'Print formats are not Amazon formats. The spec registry covers the Amazon surfaces; print output is recorded here for the operator.' },
]

const RULES = [
  { label: 'Never Brand Registry proof', tone: 'block', detail: 'A product image submitted for Brand Registry enrollment must be an ACTUAL PHOTO. Mock-ups and digitally altered images are not valid proof of IP ownership and can cause additional scrutiny or removal from the program.', source: 'Brand Registry Application Guide ? 2026-10-10' },
  { label: 'A mockup is not a main image', tone: 'block', detail: 'A packaging mockup used as a listing main image must satisfy the main-image rules: pure white RGB 255,255,255, 85% frame fill, and no text, logo, badge, border or watermark.', source: 'Product image guide ? 2026-10-10' },
  { label: 'Product accuracy', tone: 'flag', detail: 'Images must accurately represent the product and show only the product for sale. Packaging creative must not depict a pack the buyer will not receive.', source: 'Listing quality ? 2026-10-10' },
  { label: 'Dielines are out of scope here', tone: 'flag', detail: 'This build does not generate dielines or 3D folds. The 3D Product Scene section handles real geometry locally.', source: 'spec registry ? 2026-10-10' },
]

const SLOTS = [
  { id: 'amz-main', label: 'Pack on white', specId: 'amz-main', icon: 'star' },
  { id: 'amz-secondary', label: 'Mockup 1600', specId: 'amz-secondary', icon: 'package' },
  { id: 'store-tile-large', label: 'Store 1500', specId: 'store-tile-large', icon: 'grid' },
]

export default function Packaging() {
  return (
    <SectionWorkspace
      title="Packaging & Mockups"
      subtitle="Packaging and mockup planning with the Brand Registry and product-accuracy boundaries made explicit"
      groups={GROUPS} defaultSpecId="amz-main"
      fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
      canvasFitWidth={560} testId="packaging-workspace"
      packBuilder={buildPackagingSpec} packLabel="Spec sheet"
    />
  )
}
