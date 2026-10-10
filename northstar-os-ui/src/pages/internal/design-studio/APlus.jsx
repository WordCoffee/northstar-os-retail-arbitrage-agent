// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: A+ / BRAND STORY
// // Amazon A+ modules (Basic + Premium) and Brand Story carousels at the
// published sizes. Alt text is a REQUIRED field whose only documented purpose
// is describing the image for screen readers ? this workspace makes no SEO
// claim about it, because no Amazon source does.
// Every spec comes from the registry; every rule comes from the engine.
// ???????????????????????????????????????????????????????????????????????????

import { useLocation, useNavigate } from 'react-router-dom'
import SectionWorkspace from './SectionWorkspace.jsx'
import IndexingRegister from './IndexingRegister.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'

const GROUPS = SPEC_GROUPS.filter(g => ['A+ Basic', 'A+ Premium', 'Brand Story'].includes(g.id))


const FIELDS = [
  {
    id: 'altText', kind: 'textarea', rows: 3, required: true, maxLength: 200,
    label: 'Alt text (image keywords)',
    placeholder: 'Describe what the image shows, for someone who cannot see it.',
    note: 'Required by Amazon for every A+ module containing an image. Alt text that does not describe the image can result in content rejection. This is an accessibility requirement ? NOT a ranking feature.',
    source: 'A+ content guidelines (GW8U76SSNTRTBX7)', pulled: '2026-10-10',
  },
  {
    id: 'moduleHeadline', kind: 'text', maxLength: 160,
    label: 'Module headline',
    note: 'Amazon documents up to 160 characters of headline for an A+ module.',
    source: 'Seller Central forum teardown', pulled: '2026-10-10',
  },
  {
    id: 'moduleBody', kind: 'textarea', rows: 4, maxLength: 1000,
    label: 'Module body text',
    note: 'Amazon documents up to 1,000 characters of body text per image module.',
    source: 'Seller Central forum teardown', pulled: '2026-10-10',
  },
  { id: 'syntheticPeople', kind: 'toggle', label: 'This image contains photorealistic AI-generated people',
    note: 'If ticked, the disclosure tag below becomes required before export.' },
  { id: 'syntheticPerformerTag', kind: 'toggle', label: 'Disclosure tag will be written (contains-synthetic-performer)',
    note: 'Written to the dc:subject XMP field per the A+ guidelines, or read by the A+ Content Manager checkbox at upload.' },
]

const RULES = [
  { label: 'File limits', tone: 'block', detail: 'Individual A+ images must stay under 2 MB, be RGB (CMYK is not supported), and be at least 72 dpi. Animated GIFs are prohibited.', source: 'A+ content guidelines ? 2026-10-10' },
  { label: 'Alt text is required', tone: 'block', detail: 'Every module containing an image requires alt text that describes it for screen-reader users, or the content can be rejected.', source: 'A+ content guidelines ? 2026-10-10' },
  { label: 'Unique to A+', tone: 'flag', detail: 'Images and text must be unique to A+ ? reusing images already published in the listing gallery is rejected. One brand logo maximum.', source: 'A+ content guidelines ? 2026-10-10' },
  { label: 'Module counts', tone: 'flag', detail: `Basic A+ allows ${AMAZON_CAPS.aplus.modulesBasicMax} modules; Premium A+ allows ${AMAZON_CAPS.aplus.modulesPremiumMax}. Bulk upload is required above ${AMAZON_CAPS.aplus.bulkUploadAsinThreshold} ASINs.`, source: 'A+ size table ? 2026-10-10' },
  { label: 'Premium A+ gating', tone: 'flag', detail: 'Premium A+ eligibility requires a Brand Story module published on all brand-owned listings plus additional approved content.', source: 'Seller Central forum ? 2026-10-10' },
  { label: 'Upscaling does not happen', tone: 'flag', detail: 'An image smaller than the module minimum is not scaled up by Amazon, so an undersized asset stays undersized.', source: 'Premium A+ module guide ? 2026-10-10' },
]

const SLOTS = [
  { id: 'aplus-overlay-dark', label: 'Overlay 970x300', specId: 'aplus-overlay-dark', icon: 'image' },
  { id: 'aplus-sidebar-main', label: 'Sidebar 300x400', specId: 'aplus-sidebar-main', icon: 'image' },
  { id: 'aplus-single', label: 'Single 300x300', specId: 'aplus-single', icon: 'image' },
  { id: 'aplus-four-text', label: 'Four 200x200', specId: 'aplus-four-text', icon: 'grid' },
  { id: 'aplus-comparison', label: 'Chart 150x300', specId: 'aplus-comparison', icon: 'chart' },
  { id: 'aplus-premium-full', label: 'Premium 1464x600', specId: 'aplus-premium-full', icon: 'sparkle' },
  { id: 'aplus-premium-hotspots', label: 'Hotspots 1464x600', specId: 'aplus-premium-hotspots', icon: 'target' },
  { id: 'brand-story-desktop', label: 'Brand Story 1464x625', specId: 'brand-story-desktop', icon: 'stack' },
]

export default function APlus() {
  const location = useLocation()
  const navigate = useNavigate()
  const view = new URLSearchParams(location.search).get('view') === 'indexing' ? 'indexing' : 'modules'
  const go = (v) => navigate(`/design-studio?section=aplus${v === 'indexing' ? '&view=indexing' : ''}`, { replace: true })

  return (
    <>
      <div style={{ display: 'flex', gap: 8, padding: '10px 0 0' }}>
        <button className={`btn btn-sm ${view === 'modules' ? 'btn-primary' : ''}`} onClick={() => go('modules')}>Modules</button>
        <button className={`btn btn-sm ${view === 'indexing' ? 'btn-primary' : ''}`} onClick={() => go('indexing')} data-testid="sub-indexing-register">Indexing claims</button>
      </div>
      {view === 'indexing' ? (
        <IndexingRegister />
      ) : (
        <SectionWorkspace
          title="A+ / Brand Story"
          subtitle="Amazon A+ modules, Premium A+ and Brand Story carousels at the published sizes"
          groups={GROUPS} defaultSpecId="aplus-overlay-dark"
          fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
          canvasFitWidth={620} testId="aplus-workspace"
        />
      )}
    </>
  )
}
