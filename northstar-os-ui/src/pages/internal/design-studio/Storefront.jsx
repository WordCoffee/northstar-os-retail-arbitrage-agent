// ???????????????????????????????????????????????????????????????????????????
// DESIGN STUDIO ? SECTION: STOREFRONT
// // Amazon Store pages: hero with the documented crop + logo safe zone, and the
// four image-tile sizes. The hero overlay uses the STRICTER of two Amazon
// figures and says so on the canvas.
// Every spec comes from the registry; every rule comes from the engine.
// ???????????????????????????????????????????????????????????????????????????

import SectionWorkspace from './SectionWorkspace.jsx'
import { SPEC_GROUPS, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'

const GROUPS = SPEC_GROUPS.filter(g => ['Store header', 'Store tiles'].includes(g.id))


const FIELDS = [
  { id: 'heroHeadline', kind: 'text', maxLength: 80, label: 'Hero headline (text tile, not baked into the image)',
    note: 'Amazon does not encourage embedded image text because it is unreadable by external search engines and screen readers. Use the text tile or the Image with text tile.', source: 'Content tiles on Stores ? 2026-10-10' },
  { id: 'tileLinkTitle', kind: 'text', maxLength: 60, label: 'Tile link title',
    note: 'Adding a link title obscures about 19% of a rectangle tile or 12% of a square tile at the bottom ? the overlay shows the obscured band.' },
]

const RULES = [
  { label: 'Hero crop is real', tone: 'block', detail: 'Below 1500px wide the hero is cropped up to 16% on each side, and the brand logo covers a further 18% of the left. A second Amazon source states the hero safe area is 50% width. The overlay uses the stricter union: left 34%, right 25%, a 41%-wide visible band.', source: 'stores-hero + stores-pdf ? 2026-10-10' },
  { label: 'Link titles obscure the tile', tone: 'flag', detail: 'Rectangle tiles (medium, full width) lose about 19% at the bottom; square tiles (small, large) lose about 12%. Keep faces, logos and text out of those bands.', source: 'Content tiles on Stores ? 2026-10-10' },
  { label: 'Prefer text fields over baked text', tone: 'flag', detail: 'Embedded image text is unreadable by external search engines and screen readers. Use the Image with text tile, or a text tile.', source: 'Content tiles on Stores ? 2026-10-10' },
  { label: 'Tile limits', tone: 'flag', detail: `Gallery displays up to ${AMAZON_CAPS.store.galleryMaxImages} images at a 1500x750 minimum; product grid holds ${AMAZON_CAPS.store.productGridMax} products; the best-seller tile shows ${AMAZON_CAPS.store.bestSellerTileShows} products and appears automatically only when criteria are met.`, source: 'Stores help ? 2026-10-10' },
  { label: 'Tile file cap', tone: 'block', detail: `Image tiles and the hero carry a ${Math.round(AMAZON_CAPS.store.tilesMaxBytes / 1048576)} MB maximum file size.`, source: 'Stores creative requirements PDF ? 2026-10-10' },
]

const SLOTS = [
  { id: 'store-hero', label: 'Hero 3000x600', specId: 'store-hero', icon: 'image' },
  { id: 'store-logo', label: 'Logo 400x400', specId: 'store-logo', icon: 'star' },
  { id: 'store-tile-full', label: 'Tile full 3000x1500', specId: 'store-tile-full', icon: 'grid' },
  { id: 'store-tile-large', label: 'Tile large 1500x1500', specId: 'store-tile-large', icon: 'grid' },
  { id: 'store-tile-medium', label: 'Tile medium 1500x750', specId: 'store-tile-medium', icon: 'grid' },
  { id: 'store-tile-small', label: 'Tile small 750x750', specId: 'store-tile-small', icon: 'grid' },
  { id: 'store-video-full', label: 'Video tile full', specId: 'store-video-full', icon: 'film' },
]

export default function Storefront() {
  return (
    <SectionWorkspace
      title="Storefront"
      subtitle="Amazon Store hero and tile sizes, with the documented crop and overlay safe zones"
      groups={GROUPS} defaultSpecId="store-hero"
      fields={FIELDS} ruleNotes={RULES} slots={SLOTS}
      canvasFitWidth={760} testId="storefront-workspace"
    />
  )
}
