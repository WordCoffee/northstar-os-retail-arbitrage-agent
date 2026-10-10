// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: ADS
// // Amazon ad creative: Sponsored Brands video (16:9 default), the 9:16 vertical
// variant flagged as date-sensitive, custom images, DSP display and brand
// assets. One row per ad product so a spec can never be borrowed across them.
// Every spec comes from the registry; every rule comes from the engine.
//
// The section carries TWO sub-views (?view=search-terms switches):
//   • Creative — the manufacturing surface (specs, fields, compositing).
//   • Search terms — imported ad evidence: reports in, briefs and variant
//     comparisons out (Phase 6 items 4-6). File data only; never live.
// ???????????????????????????????????????????????????????????????????????????

import { useLocation, useNavigate } from 'react-router-dom'
import SectionWorkspace from './SectionWorkspace.jsx'
import SearchTerms from './SearchTerms.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'

const GROUPS = SPEC_GROUPS.filter(g => ['SB video', 'SP video', 'Display video', 'Amazon video', 'Custom image', 'DSP display', 'Brand asset'].includes(g.id))


const FIELDS = [
  { id: 'headline', kind: 'text', maxLength: AMAZON_CAPS.ads.headlineMaxChars, label: 'Headline',
    note: `Amazon caps the headline at ${AMAZON_CAPS.ads.headlineMaxChars} characters (${AMAZON_CAPS.ads.headlineMaxCharsJP} in Japan). Sentence case ? ALL CAPS and Title Case are rejected for self-service ad products.`, source: 'Ads overview ? 2026-10-10' },
  { id: 'brandName', kind: 'text', maxLength: AMAZON_CAPS.ads.brandNameMaxChars, label: 'Brand name',
    note: `Hard cap of ${AMAZON_CAPS.ads.brandNameMaxChars} characters. The brand must appear in the logo or the headline.`, source: 'Brand Profile policy ? 2026-10-10' },
  { id: 'cta', kind: 'text', maxLength: AMAZON_CAPS.ads.ctaMaxChars - 1, label: 'Call to action',
    note: `Under ${AMAZON_CAPS.ads.ctaMaxChars} characters (${AMAZON_CAPS.ads.ctaMaxCharsJP} in Japan) with no punctuation.`, source: 'Brand Profile policy ? 2026-10-10' },
  { id: 'disclaimer', kind: 'text', maxLength: AMAZON_CAPS.ads.disclaimerMaxChars, label: 'Disclaimer',
    note: `Cap of ${AMAZON_CAPS.ads.disclaimerMaxChars} characters. Required for regulated categories.`, source: 'Sponsored Brands moderation ? 2026-10-10' },
  { id: 'durationSeconds', kind: 'number', min: 0, max: 300, label: 'Video duration (seconds)',
    note: 'Sponsored Brands video must be 6-45 seconds; 20 seconds or less is recommended. A duration outside the range blocks export.', source: 'SB video specs ? 2026-10-10' },
  { id: 'syntheticPeople', kind: 'toggle', label: 'Contains photorealistic AI-generated people', note: 'Triggers the disclosure requirement.' },
  { id: 'syntheticPerformerTag', kind: 'toggle', label: 'Disclosure tag will be written (contains-synthetic-performer)' },
]

const RULES = [
  { label: '16:9 is the default', tone: 'block', detail: 'Sponsored Brands video is 16:9 square pixel ONLY on the standard surface, at 1280x720, 1920x1080 or 3840x2160. Duration 6-45s, MP4/MOV, H.264 or H.265 Main/Baseline, 23.976-30fps, min 1 Mbps video, audio PCM/AAC/MP3 at 96 kbps and 44.1 kHz, 500 MB cap.', source: 'SB video ad specs ? 2026-10-10' },
  { label: '9:16 is a WARN, not a rule', tone: 'flag', detail: 'The vertical 9:16 variant appears in the Ads API guide (720x1280 / 1080x1920 / 2160x3840) and depends on campaign goal and surface availability. It is date-sensitive and is never treated as a blocking rule.', source: 'SB video Ads API guide ? 2026-10-10' },
  { label: 'No text bottom-right', tone: 'flag', detail: 'On-screen text must be legible on mobile and must not enter the bottom-right corner or the platform UI strip.', source: 'SB video specs ? 2026-10-10' },
  { label: 'One logo rule inverts', tone: 'block', detail: 'A brand LOGO must fill the entire image or sit on a solid colour background that fills the entire image. A custom IMAGE must NOT be a product image on a solid or transparent background. Brand name or logo must be identifiable for at least 3 seconds in video.', source: 'Brand Profile policy ? 2026-10-10' },
  { label: 'Separate ad products', tone: 'block', detail: 'Sponsored Products video, Sponsored Brands video, Sponsored Display video and Amazon Video Ads are different products with different specs. The SP video row has NO recorded source yet, so it cannot be exported ? a spec is never borrowed across products.', source: 'spec registry ? 2026-10-10' },
  { label: 'Amazon Video Ads', tone: 'flag', detail: 'Amazon-published for custom media: 1920x1080 (16:9) recommended, at least 15 FPS, audio 128 kbps at 44.1 kHz, recommended bit rate 2 Mbps, with a detail-page desktop placement listed at 970x250.', source: 'Amazon video ads specs ? 2026-10-10' },
]

const SLOTS = [
  { id: 'sbv-landscape', label: 'SB video 16:9', specId: 'sbv-landscape', icon: 'film' },
  { id: 'sbv-vertical', label: 'SB video 9:16', specId: 'sbv-vertical', icon: 'film' },
  { id: 'spv-video', label: 'SP video', specId: 'spv-video', icon: 'film' },
  { id: 'display-video', label: 'Display video', specId: 'display-video', icon: 'film' },
  { id: 'amazon-video-ads', label: 'Amazon video ads', specId: 'amazon-video-ads', icon: 'film' },
  { id: 'sb-custom-wide', label: 'Custom 1.91:1', specId: 'sb-custom-wide', icon: 'image' },
  { id: 'sb-custom-square', label: 'Custom 1:1', specId: 'sb-custom-square', icon: 'image' },
  { id: 'sb-custom-tall', label: 'Custom 9:16', specId: 'sb-custom-tall', icon: 'image' },
  { id: 'dsp-300x250', label: 'DSP 300x250', specId: 'dsp-300x250', icon: 'grid' },
  { id: 'dsp-970x250', label: 'DSP 970x250', specId: 'dsp-970x250', icon: 'grid' },
]

export default function Ads() {
  const location = useLocation()
  const navigate = useNavigate()
  const view = new URLSearchParams(location.search).get('view') === 'search-terms' ? 'search-terms' : 'creative'
  const go = (v) => navigate(`/design-studio?section=ads${v === 'search-terms' ? '&view=search-terms' : ''}`, { replace: true })

  return (
    <>
      <div style={{ display: 'flex', gap: 8, padding: '10px 0 0' }}>
        <button className={`btn btn-sm ${view === 'creative' ? 'btn-primary' : ''}`} onClick={() => go('creative')}>Creative</button>
        <button className={`btn btn-sm ${view === 'search-terms' ? 'btn-primary' : ''}`} onClick={() => go('search-terms')} data-testid="sub-search-terms">Search terms</button>
      </div>
      {view === 'search-terms' ? (
        <SearchTerms />
      ) : (
        <SectionWorkspace
          title="Ads"
          subtitle="Sponsored Brands video, the 9:16 variant, custom images, DSP display and brand assets"
          groups={GROUPS} defaultSpecId="sbv-landscape"
          fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
          canvasFitWidth={620} testId="ads-workspace"
        />
      )}
    </>
  )
}
