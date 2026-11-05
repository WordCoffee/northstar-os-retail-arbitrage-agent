// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: VIDEO & UGC CLIPS
// // Video and UGC clip planning against the same registry. Generation stays
// unarmed: this workspace plans, checks and exports your own footage only.
// Every spec comes from the registry; every rule comes from the engine.
// ???????????????????????????????????????????????????????????????????????????

import SectionWorkspace from './SectionWorkspace.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'
import { buildStoryboardPack } from '../../../studio/engine/outputPacks.js'

const GROUPS = SPEC_GROUPS.filter(g => ['SB video', 'SP video', 'Display video', 'Amazon video', 'Store tiles'].includes(g.id))


const FIELDS = [
  { id: 'hook', kind: 'text', maxLength: 60, label: 'Hook (first 3 seconds)',
    note: 'Amazon recommends showing the product within the first 3 seconds and delivering the core message within 5, because videos autoplay muted.' },
  { id: 'durationSeconds', kind: 'number', min: 0, max: 300, label: 'Clip duration (seconds)',
    note: 'For Amazon placements the Sponsored Brands range is 6-45s. Store background videos are 2-20s. An out-of-range duration blocks export.' },
  { id: 'captionText', kind: 'textarea', rows: 2, maxLength: 200, label: 'Caption / on-screen text',
    note: 'Caption text must not overlap the platform UI and must stay clear of the prohibited bottom-right corner.' },
  { id: 'syntheticPeople', kind: 'toggle', label: 'Clip contains photorealistic AI-generated people', note: 'Triggers the disclosure requirement.' },
  { id: 'syntheticPerformerTag', kind: 'toggle', label: 'Disclosure tag will be written (contains-synthetic-performer)' },
]

const RULES = [
  { label: 'Mute-first', tone: 'flag', detail: 'Videos launch muted. Rely on visuals over narration, add closed captions, and end on the brand logo. Amazon auto-loops the video.', source: 'SB video specs ? 2026-10-10' },
  { label: 'Safe areas', tone: 'flag', detail: 'Critical content must not obstruct the interface. No text in the bottom-right corner, and keep captions out of the platform UI strip.', source: 'SB video specs ? 2026-10-10' },
  { label: 'No black bars', tone: 'flag', detail: 'Amazon ad policy prohibits letterbox and pillar-box formatting, and video must not abruptly end or truncate.', source: 'Ads overview ? 2026-10-10' },
  { label: 'Human-feature guardrail', tone: 'flag',
    detail: 'Faces, hands and bodies are intercepted before a render with the warning: "Generations with human features and hands may generate poor results. We recommend ads that do not have these types of generations for a better overall product." An explicit human_features_ack is the only override, and it is audited.',
    source: 'video_guard ? 2026-11-05' },
  { label: 'Generation is unarmed', tone: 'flag', detail: 'No provider is connected. This workspace plans, checks and exports your own footage. Nothing is generated here.', source: 'provider boundary ? 2026-10-10' },
]

const SLOTS = [
  { id: 'sbv-landscape', label: 'SB 16:9', specId: 'sbv-landscape', icon: 'film' },
  { id: 'sbv-vertical', label: 'SB 9:16', specId: 'sbv-vertical', icon: 'film' },
  { id: 'amazon-video-ads', label: 'Amazon video', specId: 'amazon-video-ads', icon: 'film' },
  { id: 'store-video-full', label: 'Store video 16:9', specId: 'store-video-full', icon: 'film' },
  { id: 'store-video-large', label: 'Store video 2:2', specId: 'store-video-large', icon: 'film' },
]

export default function VideoUgc() {
  return (
    <SectionWorkspace
      title="Video & UGC Clips"
      subtitle="Clip planning, safe areas and export for Amazon placements ? generation stays unarmed"
      groups={GROUPS} defaultSpecId="sbv-landscape"
      fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
      canvasFitWidth={620} testId="video-ugc-workspace"
      packBuilder={buildStoryboardPack} packLabel="Storyboard"
    />
  )
}
