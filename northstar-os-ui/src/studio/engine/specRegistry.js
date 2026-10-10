// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — AMAZON SPEC REGISTRY
//
// The single source of truth for every Amazon creative spec the Design Studio
// can export. Every row carries a source id from research/design-studio/sources.db
// and a pulled-at date, because Amazon updates these.
//
// Phase 2 (2026-10-10): built from the Track B research. This file SUPERSEDES
// the inline `module:` annotations in presets.js and is the only place sizes,
// caps, aspect rules and safe zones should be read from.
//
// Safe zones are NORMALISED (0..1 of the canvas) so one zone renders correctly
// at every size. A safe zone is a KEEP-OUT box: content that matters must sit
// outside it (for crop zones) or inside it (for keep zones).
// ═══════════════════════════════════════════════════════════════════════════

const PULLED = '2026-10-10'

// ── Source ids (mirror research/design-studio/sources.db URLs) ────────────────
export const SPEC_SOURCES = {
  'img-guide': { id: 'img-guide', label: 'Amazon Product image guide (G1881)', url: 'https://sellercentral.amazon.com/help/hub/reference/external/G1881', pulled: PULLED, quality: 5 },
  'aplus-guide': { id: 'aplus-guide', label: 'Amazon A+ content guidelines (GW8U76SSNTRTBX7)', url: 'https://sellercentral.amazon.com/help/hub/reference/external/GW8U76SSNTRTBX7', pulled: PULLED, quality: 5 },
  'aplus-modules': { id: 'aplus-modules', label: 'Amazon A+ Standard Modules template guide (PDF)', url: 'https://m.media-amazon.com/images/G/35/sp-marketing-toolkit/Sellerfacingguides/BO/Standard_A_Module_Templates.pdf', pulled: PULLED, quality: 5 },
  'aplus-size': { id: 'aplus-size', label: 'Amazon A+ Content type/image size table (G202102930)', url: 'https://sellercentral.amazon.com/help/hub/reference/external/G202102930', pulled: PULLED, quality: 5 },
  'premium-a': { id: 'premium-a', label: 'Amazon Premium A+ Module Guide (PDF)', url: 'https://m.media-amazon.com/images/G/01/BX_Marketing/2023/AMZ_Guide_Premium_A_Module_05b.pdf', pulled: PULLED, quality: 5 },
  'stores-pdf': { id: 'stores-pdf', label: 'Amazon Stores Creative Asset Requirements (US, PDF)', url: 'https://m.media-amazon.com/images/G/01/AmazonStores/Amazon_Stores_Creative_Asset_Requirements_US._V510761039_.pdf', pulled: PULLED, quality: 5 },
  'stores-tiles': { id: 'stores-tiles', label: 'Amazon Stores tile sizes + image tiles help', url: 'https://m.media-amazon.com/images/G/01/AmazonStores/Help/en/Tile_sizes.html', pulled: PULLED, quality: 5 },
  'stores-hero': { id: 'stores-hero', label: 'Amazon Stores hero image help', url: 'https://m.media-amazon.com/images/G/01/AmazonStores/Help/en/Hero_Image.html', pulled: PULLED, quality: 5 },
  'stores-content': { id: 'stores-content', label: 'Amazon Ads: Content tiles on Stores (updated 2026-07-22)', url: 'https://advertising.amazon.com/help/GBX4ZFVHAKXKA5WM', pulled: PULLED, quality: 5 },
  'sbv': { id: 'sbv', label: 'Amazon Sponsored Brands video ad specs', url: 'https://advertising.amazon.com/resources/ad-specs/sponsored-brands-video', pulled: PULLED, quality: 5 },
  'sbv-api': { id: 'sbv-api', label: 'Amazon Sponsored Brands video Ads API guide (vertical)', url: 'https://advertising.amazon.com/API/docs/en-us/guides/sponsored-brands/ads/video', pulled: PULLED, quality: 5 },
  'dsp-types': { id: 'dsp-types', label: 'Amazon DSP ad types / size list (updated 2026-08-11)', url: 'https://advertising.amazon.com/help/GRHZG63TKWBCZYLJ', pulled: PULLED, quality: 5 },
  'ads-overview': { id: 'ads-overview', label: 'Amazon Ads ad specifications overview (updated 2026-09-02)', url: 'https://advertising.amazon.com/help/GAULLQNSRGXQKDFW', pulled: PULLED, quality: 5 },
  'suppression': { id: 'suppression', label: 'Amazon suppressed listings (G200898440)', url: 'https://sellercentral.amazon.com/help/hub/reference/external/G200898440', pulled: PULLED, quality: 5 },
  'style-guides': { id: 'style-guides', label: 'Amazon product page style guides (G200270100)', url: 'https://sellercentral.amazon.com/help/hub/reference/external/G200270100', pulled: PULLED, quality: 5 },
  'listing-quality': { id: 'listing-quality', label: 'Amazon listing quality (G200786710)', url: 'https://sellercentral.amazon.com/gp/help/external/G200786710', pulled: PULLED, quality: 5 },
  'premium-elig': { id: 'premium-elig', label: 'Premium A+ eligibility update (Seller Central forum)', url: 'https://sellercentral.amazon.com/seller-forums/discussions/t/301e6741-8ef5-485f-8829-a14c55647f9c', pulled: PULLED, quality: 3 },
  'flat-file': { id: 'flat-file', label: 'Amazon flat-file column schema (AMALYZE vendor guide)', url: 'https://amalyze.com/resources/guides/listing/amazon-listing-flatfile-creation', pulled: PULLED, quality: 3 },
}

// ── Safe zones (normalised 0..1) ─────────────────────────────────────────────
// `keepOut` boxes are areas that will be obscured/cropped — keep nothing
// important there. `keepIn` is the area guaranteed visible — keep everything
// important inside it. Zones are per-format-id.
export const SAFE_ZONES = {
  // Amazon Store hero: below 1500px wide, up to 16% of left AND right is
  // cropped, and the brand logo covers an additional 18% of the left side.
  'store-hero': {
    note: 'Store hero crop + logo coverage',
    source: 'stores-hero',
    keepOut: [
      { x: 0, y: 0, w: 0.34, h: 1, label: 'Cropped / logo area (left 16% crop + 18% logo)' },
      { x: 0.84, y: 0, w: 0.16, h: 1, label: 'Cropped on small screens (right 16%)' },
    ],
    keepIn: { x: 0.34, y: 0.06, w: 0.5, h: 0.88, label: 'Always-visible centre safe area' },
  },
  // Store image tile with a link title: rectangle ~19% bottom obscured,
  // square ~12% bottom obscured.
  'store-tile-full': { note: 'Full-width tile with link title', source: 'stores-content', keepOut: [{ x: 0, y: 0.81, w: 1, h: 0.19, label: 'Link-title overlay (~19%)' }] },
  'store-tile-medium': { note: 'Medium tile with link title', source: 'stores-content', keepOut: [{ x: 0, y: 0.81, w: 1, h: 0.19, label: 'Link-title overlay (~19%)' }] },
  'store-tile-large': { note: 'Large tile with link title', source: 'stores-content', keepOut: [{ x: 0, y: 0.88, w: 1, h: 0.12, label: 'Link-title overlay (~12%)' }] },
  'store-tile-small': { note: 'Small tile with link title', source: 'stores-content', keepOut: [{ x: 0, y: 0.88, w: 1, h: 0.12, label: 'Link-title overlay (~12%)' }] },
  // Sponsored Brands video: no text in the bottom-right corner; keep text out
  // of the platform UI strip.
  'sbv-landscape': {
    note: 'Sponsored Brands video safe zone',
    source: 'sbv',
    keepOut: [
      { x: 0.78, y: 0.82, w: 0.22, h: 0.18, label: 'No text — bottom-right corner' },
      { x: 0, y: 0.9, w: 1, h: 0.1, label: 'Platform UI strip' },
    ],
    keepIn: { x: 0.04, y: 0.04, w: 0.92, h: 0.84, label: 'Legible content area (mute-first, mobile-readable)' },
  },
  'sbv-vertical': {
    note: 'Sponsored Brands vertical (9:16) safe zone',
    source: 'sbv-api',
    keepOut: [
      { x: 0.72, y: 0.8, w: 0.28, h: 0.2, label: 'No text — bottom-right corner' },
      { x: 0, y: 0.88, w: 1, h: 0.12, label: 'Platform UI strip' },
    ],
    keepIn: { x: 0.06, y: 0.06, w: 0.88, h: 0.8, label: 'Legible content area' },
  },
}

// ── Amazon image / listing formats (authoritative sizes) ────────────────────
// `w`/`h` are the EXACT minimum published sizes. `caps` are hard limits.
export const AMAZON_SPECS = [
  // ── Listing gallery ──
  {
    id: 'amz-main', label: 'Listing main image', channel: 'Amazon listing', group: 'Gallery',
    w: 2000, h: 2000, minW: 1000, maxDim: 10000, minDim: 500,
    formats: ['JPEG', 'PNG', 'TIFF', 'GIF'], dpi: 72, colorSpace: 'sRGB', maxBytes: 10 * 1024 * 1024,
    rules: ['whiteBackground', 'fill85', 'noOverlay', 'photoOnly'], safe: null,
    source: 'img-guide',
    note: 'Pure white RGB 255,255,255. Product fills 85-100%. No text, logo, badge, border, watermark. Zoom needs >1000 px longest side.',
  },
  {
    id: 'amz-secondary', label: 'Listing secondary image', channel: 'Amazon listing', group: 'Gallery',
    w: 1600, h: 1600, minW: 1000, maxDim: 10000,
    formats: ['JPEG', 'PNG', 'TIFF', 'GIF'], dpi: 72, colorSpace: 'sRGB', maxBytes: 10 * 1024 * 1024,
    rules: ['noOverlayLoose'], safe: null, source: 'img-guide',
    note: 'Lifestyle, feature, scale, in-use. Text overlays are allowed on secondary slots (not the main).',
  },
  // ── A+ Content: Basic ──
  { id: 'aplus-overlay-dark', label: 'A+ image & dark text overlay', channel: 'Amazon A+', group: 'A+ Basic', w: 970, h: 300, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-overlay-light', label: 'A+ image & light text overlay', channel: 'Amazon A+', group: 'A+ Basic', w: 970, h: 300, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-sidebar-main', label: 'A+ single image & sidebar (main)', channel: 'Amazon A+', group: 'A+ Basic', w: 300, h: 400, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-sidebar-side', label: 'A+ single image & sidebar (side)', channel: 'Amazon A+', group: 'A+ Basic', w: 350, h: 175, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-single', label: 'A+ single left/right image', channel: 'Amazon A+', group: 'A+ Basic', w: 300, h: 300, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-four-text', label: 'A+ four images & text', channel: 'Amazon A+', group: 'A+ Basic', w: 200, h: 200, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-comparison', label: 'A+ comparison chart image', channel: 'Amazon A+', group: 'A+ Basic', w: 150, h: 300, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-four-highlights', label: 'A+ four image highlights', channel: 'Amazon A+', group: 'A+ Basic', w: 400, h: 400, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-quadrant', label: 'A+ quadrant image', channel: 'Amazon A+', group: 'A+ Basic', w: 135, h: 135, rules: ['aplusImageRules'], source: 'aplus-modules' },
  { id: 'aplus-three-text', label: 'A+ three images & text', channel: 'Amazon A+', group: 'A+ Basic', w: 300, h: 300, rules: ['aplusImageRules'], source: 'aplus-modules' },
  // ── A+ Content: Premium ──
  { id: 'aplus-premium-full', label: 'Premium A+ full image', channel: 'Amazon A+', group: 'A+ Premium', w: 1464, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-bg-text', label: 'Premium A+ background image with text', channel: 'Amazon A+', group: 'A+ Premium', w: 1464, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-four-text', label: 'Premium A+ four images & text', channel: 'Amazon A+', group: 'A+ Premium', w: 300, h: 225, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-dual-text', label: 'Premium A+ dual images with text', channel: 'Amazon A+', group: 'A+ Premium', w: 650, h: 350, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-single-text', label: 'Premium A+ single image with text', channel: 'Amazon A+', group: 'A+ Premium', w: 800, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-cmp1', label: 'Premium A+ comparison table 1', channel: 'Amazon A+', group: 'A+ Premium', w: 200, h: 225, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-cmp2', label: 'Premium A+ comparison table 2', channel: 'Amazon A+', group: 'A+ Premium', w: 300, h: 225, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-cmp3', label: 'Premium A+ comparison table 3', channel: 'Amazon A+', group: 'A+ Premium', w: 488, h: 700, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-carousel', label: 'Premium A+ image carousel', channel: 'Amazon A+', group: 'A+ Premium', w: 1464, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-nav', label: 'Premium A+ navigation carousel', channel: 'Amazon A+', group: 'A+ Premium', w: 1464, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  { id: 'aplus-premium-hotspots', label: 'Premium A+ hotspots', channel: 'Amazon A+', group: 'A+ Premium', w: 1464, h: 600, rules: ['aplusImageRules'], source: 'premium-a' },
  // ── Brand Story ──
  { id: 'brand-story-desktop', label: 'Brand Story carousel (desktop)', channel: 'Amazon A+', group: 'Brand Story', w: 1464, h: 625, rules: ['aplusImageRules'], source: 'aplus-size' },
  { id: 'brand-story-mobile', label: 'Brand Story carousel (mobile)', channel: 'Amazon A+', group: 'Brand Story', w: 463, h: 625, rules: ['aplusImageRules'], source: 'aplus-size' },
  // ── Storefront ──
  {
    id: 'store-hero', label: 'Store hero image', channel: 'Amazon Store', group: 'Store header',
    w: 3000, h: 600, maxH: 1200, maxBytes: 5 * 1024 * 1024, rules: ['storeSafeZone'], safe: 'store-hero', source: 'stores-hero',
    note: 'Cropped below 1500px wide: 16% each side + logo covers 18% of the left.',
  },
  { id: 'store-logo', label: 'Store brand logo', channel: 'Amazon Store', group: 'Store header', w: 400, h: 400, maxBytes: 5 * 1024 * 1024, rules: [], source: 'stores-hero' },
  { id: 'store-tile-full', label: 'Store image tile — full width', channel: 'Amazon Store', group: 'Store tiles', w: 3000, h: 1500, maxBytes: 5 * 1024 * 1024, rules: ['storeSafeZone', 'noEmbeddedText'], safe: 'store-tile-full', source: 'stores-pdf' },
  { id: 'store-tile-large', label: 'Store image tile — large', channel: 'Amazon Store', group: 'Store tiles', w: 1500, h: 1500, maxBytes: 5 * 1024 * 1024, rules: ['storeSafeZone', 'noEmbeddedText'], safe: 'store-tile-large', source: 'stores-pdf' },
  { id: 'store-tile-medium', label: 'Store image tile — medium', channel: 'Amazon Store', group: 'Store tiles', w: 1500, h: 750, maxBytes: 5 * 1024 * 1024, rules: ['storeSafeZone', 'noEmbeddedText'], safe: 'store-tile-medium', source: 'stores-pdf' },
  { id: 'store-tile-small', label: 'Store image tile — small', channel: 'Amazon Store', group: 'Store tiles', w: 750, h: 750, maxBytes: 5 * 1024 * 1024, rules: ['storeSafeZone', 'noEmbeddedText'], safe: 'store-tile-small', source: 'stores-pdf' },
  { id: 'store-video-full', label: 'Store video tile — full width', channel: 'Amazon Store', group: 'Store tiles', w: 3000, h: 1500, media: 'video', videoMinW: 1280, videoMinH: 640, aspectMin: 1.5, aspectMax: 2.667, videoFormat: 'MP4 H.264', source: 'stores-pdf' },
  { id: 'store-video-large', label: 'Store video tile — large', channel: 'Amazon Store', group: 'Store tiles', w: 1500, h: 1500, media: 'video', videoMinW: 640, videoMinH: 640, aspectMin: 0.75, aspectMax: 1.333, videoFormat: 'MP4 H.264', source: 'stores-pdf' },
  // ── Ads: Sponsored Brands video ──
  {
    id: 'sbv-landscape', label: 'Sponsored Brands video (16:9)', channel: 'Amazon Ads', group: 'SB video',
    w: 1920, h: 1080, media: 'video', allowedDims: [[1280, 720], [1920, 1080], [3840, 2160]],
    durationMin: 6, durationMax: 45, durationRecommended: 20,
    maxBytes: 500 * 1024 * 1024, videoFormats: ['MP4', 'MOV'], videoCodecs: ['H.264', 'H.265'],
    aspectRatio: 16 / 9, fpsAllowed: [23.976, 23.98, 24, 25, 29.97, 29.98, 30], videoBitrateMin: 1,
    audioCodecs: ['PCM', 'AAC', 'MP3'], audioBitrateMin: 96, audioSampleMin: 44100,
    rules: ['sbvSafeZone'], safe: 'sbv-landscape', source: 'sbv',
    note: 'Vertical 9:16 also supported (720x1280 / 1080x1920 / 2160x3840). Text legible on mobile; no text bottom-right.',
  },
  {
    id: 'sbv-vertical', label: 'Sponsored Brands video vertical (9:16)', channel: 'Amazon Ads', group: 'SB video',
    w: 1080, h: 1920, media: 'video', allowedDims: [[720, 1280], [1080, 1920], [2160, 3840]],
    durationMin: 6, durationMax: 45, durationRecommended: 20,
    maxBytes: 500 * 1024 * 1024, videoFormats: ['MP4', 'MOV'], videoCodecs: ['H.264', 'H.265'],
    aspectRatio: 9 / 16, fpsAllowed: [23.976, 23.98, 24, 25, 29.97, 29.98, 30], videoBitrateMin: 1,
    audioCodecs: ['PCM', 'AAC', 'MP3'], audioBitrateMin: 96, audioSampleMin: 44100,
    rules: ['sbvSafeZone'], safe: 'sbv-vertical', source: 'sbv-api',
  },
  // ── Ads: display ──
  { id: 'sb-logo', label: 'Sponsored Brands logo', channel: 'Amazon Ads', group: 'Brand asset', w: 400, h: 400, maxBytes: 1 * 1024 * 1024, formats: ['PNG', 'JPG'], rules: ['logoFillOrSolid'], source: 'sbv-api' },
  { id: 'sb-custom-wide', label: 'Custom image — wide 1.91:1', channel: 'Amazon Ads', group: 'Custom image', w: 1200, h: 628, minW: 600, maxBytes: 5 * 1024 * 1024, formats: ['JPEG', 'PNG'], rules: ['customImageNoFlatBg'], source: 'ads-overview' },
  { id: 'sb-custom-square', label: 'Custom image — square 1:1', channel: 'Amazon Ads', group: 'Custom image', w: 1200, h: 1200, minW: 600, maxBytes: 5 * 1024 * 1024, formats: ['JPEG', 'PNG'], rules: ['customImageNoFlatBg'], source: 'ads-overview' },
  { id: 'sb-custom-tall', label: 'Custom image — tall 9:16', channel: 'Amazon Ads', group: 'Custom image', w: 900, h: 1600, maxBytes: 5 * 1024 * 1024, formats: ['JPEG', 'PNG'], rules: ['customImageNoFlatBg'], source: 'ads-overview' },
  { id: 'dsp-300x250', label: 'DSP medium rectangle', channel: 'Amazon DSP', group: 'DSP display', w: 600, h: 500, displayW: 300, displayH: 250, rules: ['dspX2'], source: 'dsp-types' },
  { id: 'dsp-728x90', label: 'DSP leaderboard', channel: 'Amazon DSP', group: 'DSP display', w: 728, h: 90, source: 'dsp-types' },
  { id: 'dsp-160x600', label: 'DSP wide skyscraper', channel: 'Amazon DSP', group: 'DSP display', w: 160, h: 600, source: 'dsp-types' },
  { id: 'dsp-970x250', label: 'DSP billboard', channel: 'Amazon DSP', group: 'DSP display', w: 970, h: 250, maxBytes: 200 * 1024, source: 'dsp-types' },
  { id: 'dsp-mobile-320x50', label: 'DSP mobile leaderboard (2X)', channel: 'Amazon DSP', group: 'DSP display', w: 640, h: 100, displayW: 320, displayH: 50, maxBytes: 50 * 1024, rules: ['dspX2'], source: 'dsp-types' },
  { id: 'dsp-414x125', label: 'DSP mobile detail/search (2X)', channel: 'Amazon DSP', group: 'DSP display', w: 828, h: 250, displayW: 414, displayH: 125, maxBytes: 100 * 1024, rules: ['dspX2'], source: 'dsp-types' },
]

export const SPEC_BY_ID = Object.fromEntries(AMAZON_SPECS.map(s => [s.id, s]))
export function specById(id) { return SPEC_BY_ID[id] || null }
export function specsForChannel(channel) { return AMAZON_SPECS.filter(s => s.channel === channel) }

export const SPEC_GROUPS = (() => {
  const order = ['Gallery', 'A+ Basic', 'A+ Premium', 'Brand Story', 'Store header', 'Store tiles', 'SB video', 'Brand asset', 'Custom image', 'DSP display']
  const byGroup = {}
  for (const s of AMAZON_SPECS) {
    if (!byGroup[s.group]) byGroup[s.group] = { id: s.group, label: s.group, channel: s.channel, specs: [] }
    byGroup[s.group].specs.push(s)
  }
  return order.filter(g => byGroup[g]).map(g => byGroup[g])
})()

// ── Format caps extracted from the research (used by the compliance layer) ───
export const AMAZON_CAPS = {
  aplus: {
    maxBytes: 2 * 1024 * 1024,
    formats: ['JPG', 'BMP', 'PNG'],
    colorSpace: 'RGB',
    colorSpaceExcluded: 'CMYK',
    minDpi: 72,
    animatedGif: false,
    altTextRequired: true,
    imagesUniqueToAplus: true,
    maxBrandLogos: 1,
    modulesBasicMax: 5,
    modulesPremiumMax: 7,
    bulkUploadAsinThreshold: 1000,
    source: 'aplus-guide',
  },
  video: {
    durationMin: 6, durationMax: 45,
    formats: ['MP4', 'MOV'],
    codecs: ['H.264', 'H.265'],
    profiles: ['Main', 'Baseline'],
    fpsAllowed: [23.976, 23.98, 24, 25, 29.97, 29.98, 30],
    videoBitrateMinMbps: 1,
    audioBitrateMinKbps: 96,
    audioSampleMinHz: 44100,
    maxBytes: 500 * 1024 * 1024,
    source: 'sbv',
  },
  ads: {
    ctaMaxChars: 30,
    ctaMaxCharsJP: 15,
    headlineMaxChars: 50,
    headlineMaxCharsJP: 30,
    brandNameMaxChars: 25,
    bodyTextMaxChars: 100,
    disclaimerMaxChars: 60,
    brandVisibleSeconds: 3,
    dpi: 72,
    source: 'ads-overview',
  },
  store: {
    heroSafeZone: { centerOnly: true },
    embeddedTextDiscouraged: true,
    galleryMaxImages: 8,
    productGridMax: 100,
    bestSellerTileShows: 5,
    tilesMaxBytes: 5 * 1024 * 1024,
    source: 'stores-content',
  },
}

// ── AI policy (hard constraints on generated imagery) ────────────────────────
export const AI_POLICY = {
  syntheticPersonIptc: {
    keyword: 'contains-synthetic-performer',
    field: 'dc:subject (XMP)',
    when: 'photorealistic AI-generated people',
    whenNot: [
      'real people only (even if AI-altered)',
      'characters from films/games/expressive works',
      'no people in the image',
      'people who are not photorealistic',
    ],
    alternativeUi: 'A+ Content Manager "AI-generated" / "AI-generated people" checkbox at upload',
    source: 'aplus-guide',
  },
  brandRegistryEnrollment: {
    rule: 'Product images for Brand Registry enrollment must be ACTUAL PHOTOS; mock-ups and digitally altered images are not valid proof of IP ownership and may cause removal from the program.',
    source: 'aplus-guide',
  },
  productAccuracy: {
    rule: 'Images must accurately represent the product and show only the product for sale (main image). Claims in creative must match the detail page.',
    source: 'listing-quality',
  },
}

// ── Lifestyles exception (documented) ───────────────────────────────────────
export const MAIN_IMAGE_LIFESTYLE_ALLOWED = ['BED', 'BED_FRAME', 'MATTRESS', 'RUG', 'RUG_PAD', 'SOFA']

// ── Flat-file image columns (the export contract for bulk sets) ─────────────
export const FLAT_FILE_IMAGE_COLUMNS = [
  { col: 'main_image_url', role: 'main' },
  { col: 'swatch_image_url', role: 'swatch' },
  { col: 'other_image_url1', role: 'secondary', slot: 1 },
  { col: 'other_image_url2', role: 'secondary', slot: 2 },
  { col: 'other_image_url3', role: 'secondary', slot: 3 },
  { col: 'other_image_url4', role: 'secondary', slot: 4 },
  { col: 'other_image_url5', role: 'secondary', slot: 5 },
  { col: 'other_image_url6', role: 'secondary', slot: 6 },
  { col: 'other_image_url7', role: 'secondary', slot: 7 },
  { col: 'other_image_url8', role: 'secondary', slot: 8 },
]
