// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — PRESETS
// Shared vocabulary for the Product Designer and the Design Studio: output
// formats, brand kits, scene/backdrop recipes, lighting rigs, and layout
// templates. Every value here is deterministic and local — nothing in this
// file contacts a provider or fabricates a measurement.
// ═══════════════════════════════════════════════════════════════════════════

// ── Output formats ────────────────────────────────────────────────────────────
// `px` values are the real canvas raster sizes the engine renders at.
export const FORMAT_GROUPS = [
  {
    id: 'ads', label: 'Paid ads',
    formats: [
      { id: 'meta-feed', label: 'Meta feed', w: 1080, h: 1080, group: 'Square', channel: 'Meta' },
      { id: 'meta-story', label: 'Meta / Reels story', w: 1080, h: 1920, group: 'Vertical', channel: 'Meta' },
      { id: 'google-display', label: 'Google display', w: 1200, h: 628, group: 'Landscape', channel: 'Google' },
      { id: 'google-square', label: 'Google square', w: 1200, h: 1200, group: 'Square', channel: 'Google' },
      { id: 'tiktok', label: 'TikTok / Shorts', w: 1080, h: 1920, group: 'Vertical', channel: 'TikTok' },
      { id: 'sponsored-brand', label: 'Sponsored brand', w: 1200, h: 628, group: 'Landscape', channel: 'Amazon Ads' },
    ],
  },
  {
    id: 'social', label: 'Social content',
    formats: [
      { id: 'ig-post', label: 'Instagram post', w: 1080, h: 1350, group: 'Portrait', channel: 'Instagram' },
      { id: 'ig-carousel', label: 'Instagram carousel', w: 1080, h: 1080, group: 'Square', channel: 'Instagram' },
      { id: 'pin', label: 'Pinterest pin', w: 1000, h: 1500, group: 'Portrait', channel: 'Pinterest' },
      { id: 'x-post', label: 'X post', w: 1600, h: 900, group: 'Landscape', channel: 'X' },
      { id: 'linkedin', label: 'LinkedIn post', w: 1200, h: 627, group: 'Landscape', channel: 'LinkedIn' },
      { id: 'yt-thumb', label: 'YouTube thumbnail', w: 1280, h: 720, group: 'Landscape', channel: 'YouTube' },
    ],
  },
  {
    id: 'listing', label: 'Listing & A+',
    formats: [
      { id: 'amz-main', label: 'Amazon main image', w: 2000, h: 2000, group: 'Main', channel: 'Amazon' },
      { id: 'amz-alt', label: 'Amazon secondary', w: 1600, h: 1600, group: 'Secondary', channel: 'Amazon' },
      // ── A+ Basic (standard) modules — VERIFIED from Amazon's asset-creation
      //    guide. Prior values (970x600 / 300x300 / 970x300) were guesses and
      //    were wrong; these are the published minimums.
      { id: 'aplus-overlay-dark', label: 'A+ image & dark text overlay', w: 970, h: 300, group: 'A+ Basic', channel: 'Amazon A+', module: 'Image & Dark Text Overlay' },
      { id: 'aplus-overlay-light', label: 'A+ image & light text overlay', w: 970, h: 300, group: 'A+ Basic', channel: 'Amazon A+', module: 'Image & Light Text Overlay' },
      { id: 'aplus-sidebar-main', label: 'A+ single image & sidebar', w: 300, h: 400, group: 'A+ Basic', channel: 'Amazon A+', module: 'Single Image & Sidebar' },
      { id: 'aplus-sidebar-side', label: 'A+ sidebar panel', w: 350, h: 175, group: 'A+ Basic', channel: 'Amazon A+', module: 'Single Image & Sidebar (sidebar)' },
      { id: 'aplus-single', label: 'A+ single image', w: 300, h: 300, group: 'A+ Basic', channel: 'Amazon A+', module: 'Single Left / Right Image' },
      { id: 'aplus-four-text', label: 'A+ four images & text', w: 200, h: 200, group: 'A+ Basic', channel: 'Amazon A+', module: 'Four Images & Text' },
      { id: 'aplus-comparison', label: 'A+ comparison chart', w: 150, h: 300, group: 'A+ Basic', channel: 'Amazon A+', module: 'Comparison Chart' },
      { id: 'aplus-four-highlights', label: 'A+ four image highlights', w: 400, h: 400, group: 'A+ Basic', channel: 'Amazon A+', module: 'Four Image Highlights' },
      { id: 'aplus-quadrant', label: 'A+ text quadrant', w: 135, h: 135, group: 'A+ Basic', channel: 'Amazon A+', module: 'Four Images / Text Quadrant' },
      { id: 'aplus-three-text', label: 'A+ three images & text', w: 300, h: 300, group: 'A+ Basic', channel: 'Amazon A+', module: 'Three Images & Text' },
      // ── A+ Premium modules — VERIFIED from Amazon's Premium A+ module guide.
      { id: 'aplus-premium-full', label: 'A+ Premium full image', w: 1464, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Full Image' },
      { id: 'aplus-premium-bg-text', label: 'A+ Premium bg image with text', w: 1464, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Background Image with Text' },
      { id: 'aplus-premium-four-text', label: 'A+ Premium four images & text', w: 300, h: 225, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Four Images & Text' },
      { id: 'aplus-premium-dual-text', label: 'A+ Premium dual images with text', w: 650, h: 350, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Dual Images with Text' },
      { id: 'aplus-premium-single-text', label: 'A+ Premium single image with text', w: 800, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Single Image with Text' },
      { id: 'aplus-premium-cmp1', label: 'A+ Premium comparison table 1', w: 200, h: 225, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Comparison Table 1' },
      { id: 'aplus-premium-cmp2', label: 'A+ Premium comparison table 2', w: 300, h: 225, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Comparison Table 2' },
      { id: 'aplus-premium-cmp3', label: 'A+ Premium comparison table 3', w: 488, h: 700, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Comparison Table 3' },
      { id: 'aplus-premium-carousel', label: 'A+ Premium image carousel', w: 1464, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Simple Image Carousel' },
      { id: 'aplus-premium-nav', label: 'A+ Premium navigation carousel', w: 1464, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Navigation Carousel' },
      { id: 'aplus-premium-hotspots', label: 'A+ Premium hotspots', w: 1464, h: 600, group: 'A+ Premium', channel: 'Amazon A+', module: 'Premium Hotspots 1 / 2' },
      { id: 'storefront', label: 'Storefront hero', w: 1920, h: 640, group: 'Brand site', channel: 'Brand site' },
      { id: 'brand-story-desktop', label: 'Brand Story carousel (desktop)', w: 1464, h: 625, group: 'Brand Story', channel: 'Amazon A+', module: 'Brand Carousel Background' },
      { id: 'brand-story-mobile', label: 'Brand Story carousel (mobile)', w: 463, h: 625, group: 'Brand Story', channel: 'Amazon A+', module: 'Brand Carousel Background (mobile)' },
    ],
  },
  {
    id: 'docs', label: 'Docs & decks',
    note: 'Breadth modelled on Canva\'s output surface: the same document fabric renders a deck, a board, a print piece and a web hero.',
    formats: [
      { id: 'deck-16x9', label: 'Presentation (16:9)', w: 1920, h: 1080, group: 'Deck', channel: 'Deck' },
      { id: 'deck-4x3', label: 'Presentation (4:3)', w: 1024, h: 768, group: 'Deck', channel: 'Deck' },
      { id: 'doc-letter', label: 'Document (Letter)', w: 1275, h: 1650, group: 'Document', channel: 'Document' },
      { id: 'board-a3', label: 'Whiteboard (A3)', w: 3508, h: 4961, group: 'Board', channel: 'Whiteboard' },
      { id: 'print-poster', label: 'Poster (A3)', w: 3508, h: 4961, group: 'Print', channel: 'Print' },
      { id: 'print-label', label: 'Product label', w: 1275, h: 1650, group: 'Print', channel: 'Print' },
      { id: 'email-hero', label: 'Email hero', w: 1200, h: 628, group: 'Email', channel: 'Email' },
      { id: 'web-hero', label: 'Web hero', w: 2400, h: 1000, group: 'Web', channel: 'Web' },
      { id: 'web-og', label: 'Social / OG card', w: 1200, h: 630, group: 'Web', channel: 'Web' },
    ],
  },
  {
    id: 'video', label: 'Video frames',
    formats: [
      { id: 'reel-frame', label: 'Reel frame 9:16', w: 1080, h: 1920, group: 'Vertical', channel: 'Video' },
      { id: 'landscape-frame', label: 'Landscape frame', w: 1920, h: 1080, group: 'Landscape', channel: 'Video' },
      { id: 'square-frame', label: 'Square frame', w: 1080, h: 1080, group: 'Square', channel: 'Video' },
    ],
  },
]

export const ALL_FORMATS = FORMAT_GROUPS.flatMap(g => g.formats)

export function formatById(id) {
  return ALL_FORMATS.find(f => f.id === id) || null
}

export function formatsForChannel(channel) {
  return ALL_FORMATS.filter(f => f.channel === channel)
}

// ── Brand kits ────────────────────────────────────────────────────────────────
// Operator-editable. The defaults are honest placeholders the operator owns;
// nothing is inferred from a live brand registry.
export const DEFAULT_BRAND_KITS = [
  {
    id: 'kit-pine',
    name: 'Pine & Bone',
    note: 'House default — paper surfaces, forest ink.',
    palette: ['#f5f0e8', '#e8e2d8', '#1d4a1d', '#c4941a', '#a04020'],
    ink: '#1a1a1a',
    paper: '#f5f0e8',
    accent: '#c4941a',
    headingFont: 'Libre Baskerville',
    bodyFont: 'DM Sans',
    voice: 'Calm, precise, evidence-first.',
  },
  {
    id: 'kit-wordcoffee',
    name: 'Word Coffee',
    note: 'Sample kit — from a local work brief.',
    palette: ['#f7f2ea', '#2b1d16', '#7a4a2b', '#c9a227', '#e0d3bd'],
    ink: '#2b1d16',
    paper: '#f7f2ea',
    accent: '#c9a227',
    headingFont: 'Libre Baskerville',
    bodyFont: 'DM Sans',
    voice: 'Warm, unhurried, craft-led.',
  },
  {
    id: 'kit-mogra',
    name: 'Mogra Organics',
    note: 'Sample kit — from a local work brief.',
    palette: ['#f4f7f0', '#1f3320', '#4a7a4a', '#d8a13a', '#ffffff'],
    ink: '#1f3320',
    paper: '#f4f7f0',
    accent: '#4a7a4a',
    headingFont: 'Libre Baskerville',
    bodyFont: 'DM Sans',
    voice: 'Clean, botanical, plain-spoken.',
  },
]

// ── Scene recipes (Product Designer backdrops) ────────────────────────────────
// A scene is a deterministic gradient/geometry recipe drawn on the canvas — it
// ships with the product composite. No photographic stock is bundled or fetched.
export const SCENES = [
  {
    id: 'scene-studio-paper',
    name: 'Paper studio',
    note: 'Soft seamless sweep, even key light. Listing-safe.',
    bg: ['#f7f4ee', '#e6dfd3'],
    floor: 'rgba(26,26,26,0.06)',
    key: { angle: 135, intensity: 0.85, spread: 0.55 },
    rim: { color: '#ffffff', intensity: 0.35 },
    ambient: 0.62,
    backdrop: 'sweep',
  },
  {
    id: 'scene-warm-linen',
    name: 'Warm linen',
    note: 'Warm key from the right, cool fill left.',
    bg: ['#efe6d8', '#d8c8b2'],
    floor: 'rgba(122,74,43,0.10)',
    key: { angle: 65, intensity: 0.95, spread: 0.4 },
    rim: { color: '#ffe9c9', intensity: 0.45 },
    ambient: 0.55,
    backdrop: 'sweep',
  },
  {
    id: 'scene-deep-pine',
    name: 'Deep pine',
    note: 'Dark premium set. Strong rim, deep shadow.',
    bg: ['#16281a', '#0c150e'],
    floor: 'rgba(0,0,0,0.35)',
    key: { angle: 120, intensity: 1.0, spread: 0.35 },
    rim: { color: '#c4941a', intensity: 0.55 },
    ambient: 0.3,
    backdrop: 'sweep',
  },
  {
    id: 'scene-ochre-flat',
    name: 'Ochre flat',
    note: 'Single flat colour, hard shadow. Graphic ad look.',
    bg: ['#c4941a', '#b0820f'],
    floor: 'rgba(26,26,26,0.14)',
    key: { angle: 90, intensity: 1.0, spread: 0.2 },
    rim: { color: '#ffffff', intensity: 0.2 },
    ambient: 0.8,
    backdrop: 'flat',
  },
  {
    id: 'scene-marble',
    name: 'Marble top',
    note: 'Cool stone surface for beauty / supplement shots.',
    bg: ['#eef1f4', '#d6dde4'],
    floor: 'rgba(26,46,26,0.07)',
    key: { angle: 100, intensity: 0.9, spread: 0.45 },
    rim: { color: '#ffffff', intensity: 0.4 },
    ambient: 0.6,
    backdrop: 'surface',
  },
  {
    id: 'scene-sage',
    name: 'Sage gradient',
    note: 'Two-stop vertical wash, neutral fill.',
    bg: ['#dfe8dd', '#b8ccb8'],
    floor: 'rgba(29,90,29,0.08)',
    key: { angle: 150, intensity: 0.8, spread: 0.6 },
    rim: { color: '#ffffff', intensity: 0.3 },
    ambient: 0.68,
    backdrop: 'sweep',
  },
]

export function sceneById(id) {
  return SCENES.find(s => s.id === id) || SCENES[0]
}

// ── Lighting rigs (3D packaging studio) ──────────────────────────────────────
export const LIGHTING = [
  { id: 'three-point', name: 'Three point', note: 'Key + fill + rim. Default product look.', key: 1.0, fill: 0.45, rim: 0.5, ambient: 0.55 },
  { id: 'softbox', name: 'Softbox', note: 'Broad, even, low contrast. Catalogue safe.', key: 0.75, fill: 0.7, rim: 0.25, ambient: 0.75 },
  { id: 'dramatic', name: 'Dramatic rim', note: 'Hard key, deep falloff, strong rim.', key: 1.15, fill: 0.2, rim: 0.85, ambient: 0.28 },
  { id: 'golden', name: 'Golden hour', note: 'Warm key, warm rim, soft ambient.', key: 1.0, fill: 0.35, rim: 0.6, ambient: 0.45, warm: true },
  { id: 'flat', name: 'Flat packshot', note: 'Even light both sides. Print / dieline use.', key: 0.6, fill: 0.6, rim: 0.15, ambient: 0.9 },
]

export function lightingById(id) {
  return LIGHTING.find(l => l.id === id) || LIGHTING[0]
}

// ── Box presets (3D packaging studio) ────────────────────────────────────────
export const BOX_PRESETS = [
  { id: 'carton', name: 'Carton', note: 'Retail carton, 3 visible faces.', size: [1.0, 1.35, 0.28] },
  { id: 'pouch', name: 'Stand-up pouch', note: 'Wide, shallow, tall gusset.', size: [1.15, 1.5, 0.42] },
  { id: 'bottle', name: 'Bottle', note: 'Tall narrow pack, cap band on top.', size: [0.7, 1.7, 0.7] },
  { id: 'sleeve', name: 'Mailer box', note: 'Long flat shipping box.', size: [1.6, 0.9, 0.3] },
  { id: 'cube', name: 'Gift cube', note: 'Square box, lid band.', size: [1.1, 1.1, 1.1] },
]

export function boxPresetById(id) {
  return BOX_PRESETS.find(b => b.id === id) || BOX_PRESETS[0]
}

// ── Mockup surfaces (Product Designer mockup tab) ─────────────────────────────
// Geometry is drawn locally; artwork is the operator's own file.
export const MOCKUP_SURFACES = [
  { id: 'tee', name: 'T-shirt', note: 'Chest print, 11in × 12in print area.', area: { x: 0.34, y: 0.28, w: 0.32, h: 0.34 }, tint: '#f2f2ee' },
  { id: 'hoodie', name: 'Hoodie', note: 'Left-chest placement.', area: { x: 0.36, y: 0.34, w: 0.2, h: 0.2 }, tint: '#33352f' },
  { id: 'tote', name: 'Tote bag', note: 'Front panel.', area: { x: 0.3, y: 0.4, w: 0.4, h: 0.36 }, tint: '#e8e2d8' },
  { id: 'mug', name: 'Mug', note: 'Wrap print, both sides mirrored.', area: { x: 0.3, y: 0.32, w: 0.4, h: 0.3 }, tint: '#ffffff' },
  { id: 'label', name: 'Product label', note: 'Front label on a jar.', area: { x: 0.28, y: 0.3, w: 0.44, h: 0.42 }, tint: '#dcd6c8' },
  { id: 'box-face', name: 'Box face', note: 'Single flat face, print-ready.', area: { x: 0.22, y: 0.14, w: 0.56, h: 0.72 }, tint: '#f7f4ee' },
]

// ── Camera presets (3D view) ─────────────────────────────────────────────────
export const CAMERA_PRESETS = [
  { id: 'hero', name: 'Hero 3/4', note: 'Yaw -28°, pitch 12°. The default hero angle.', yaw: -28, pitch: 12, fov: 900 },
  { id: 'front', name: 'Front on', note: 'Yaw 0°, pitch 0°. Flat packshot.', yaw: 0, pitch: 0, fov: 900 },
  { id: 'top', name: 'Top down', note: 'Yaw 0°, pitch 62°. Shows the cap / lid face.', yaw: 0, pitch: 62, fov: 900 },
  { id: 'low', name: 'Low angle', note: 'Yaw 22°, pitch -18°. Tall imposing shot.', yaw: 22, pitch: -18, fov: 900 },
  { id: 'profile', name: 'Profile', note: 'Yaw -90°, pitch 4°. Side panel / dieline check.', yaw: -90, pitch: 4, fov: 900 },
]

// ── Copy ladder (Simple mode only exposes 3 rungs) ────────────────────────────
export const COPY_ROLES = [
  { id: 'headline', label: 'Headline', note: 'One line. The promise.', maxWords: 12 },
  { id: 'subhead', label: 'Sub-head', note: 'One line. The qualifier.', maxWords: 20 },
  { id: 'bullet', label: 'Bullet', note: 'Short proof point.', maxWords: 14 },
  { id: 'cta', label: 'Call to action', note: 'Verb first.', maxWords: 5 },
  { id: 'legal', label: 'Legal / disclosure', note: 'Small print. Never auto-hidden.', maxWords: 40 },
]

// ── Template recipes ─────────────────────────────────────────────────────────
// A template is a layer list in normalised coordinates (0..1 of the canvas), so
// one template renders correctly at every format size. Layer kinds are defined
// in engine/doc.js.
export const TEMPLATES = [
  {
    id: 'tpl-hero-paper',
    name: 'Hero — paper',
    family: 'Ad creative',
    note: 'Product left, copy right, offer badge.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#f5f0e8' },
      { kind: 'shape', shape: 'rect', x: 0.55, y: 0, w: 0.45, h: 1, fill: '#e8e2d8' },
      { kind: 'product', x: 0.04, y: 0.16, w: 0.5, h: 0.68, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.57, y: 0.18, w: 0.38, h: 0.2, text: 'Your headline here', size: 0.072, weight: 700, color: '#1a1a1a', align: 'left' },
      { kind: 'text', role: 'subhead', x: 0.57, y: 0.4, w: 0.38, h: 0.14, text: 'One line of support copy', size: 0.038, weight: 400, color: '#5a5a4a', align: 'left' },
      { kind: 'badge', x: 0.57, y: 0.62, w: 0.24, h: 0.09, text: 'LEARN MORE', fill: '#1d4a1d', color: '#f5f0e8', size: 0.026 },
    ],
  },
  {
    id: 'tpl-split-bold',
    name: 'Split — bold claim',
    family: 'Social post',
    note: 'Full-bleed type over a colour block.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#1d4a1d' },
      { kind: 'shape', shape: 'circle', x: 0.5, y: 0.46, w: 0.24, h: 0.24, fill: '#c4941a' },
      { kind: 'text', role: 'headline', x: 0.1, y: 0.12, w: 0.8, h: 0.26, text: 'BIG CLAIM', size: 0.11, weight: 700, color: '#f5f0e8', align: 'center', uppercase: true },
      { kind: 'product', x: 0.3, y: 0.42, w: 0.4, h: 0.4, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'cta', x: 0.1, y: 0.86, w: 0.8, h: 0.08, text: 'Shop now', size: 0.034, weight: 600, color: '#c4941a', align: 'center' },
    ],
  },
  {
    id: 'tpl-feature-grid',
    name: 'Feature grid',
    family: 'Listing image',
    note: 'Product top, three feature tiles below.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#ffffff' },
      { kind: 'product', x: 0.28, y: 0.04, w: 0.44, h: 0.42, fit: 'contain', shadow: false, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.06, y: 0.48, w: 0.88, h: 0.08, text: 'WHAT YOU GET', size: 0.042, weight: 700, color: '#1a1a1a', align: 'center', uppercase: true },
      { kind: 'shape', shape: 'rect', x: 0.06, y: 0.6, w: 0.26, h: 0.32, fill: '#f5f0e8', radius: 0.02 },
      { kind: 'shape', shape: 'rect', x: 0.37, y: 0.6, w: 0.26, h: 0.32, fill: '#f5f0e8', radius: 0.02 },
      { kind: 'shape', shape: 'rect', x: 0.68, y: 0.6, w: 0.26, h: 0.32, fill: '#f5f0e8', radius: 0.02 },
      { kind: 'text', role: 'bullet', x: 0.09, y: 0.63, w: 0.2, h: 0.26, text: 'Feature one', size: 0.03, weight: 500, color: '#5a5a4a', align: 'center' },
      { kind: 'text', role: 'bullet', x: 0.4, y: 0.63, w: 0.2, h: 0.26, text: 'Feature two', size: 0.03, weight: 500, color: '#5a5a4a', align: 'center' },
      { kind: 'text', role: 'bullet', x: 0.71, y: 0.63, w: 0.2, h: 0.26, text: 'Feature three', size: 0.03, weight: 500, color: '#5a5a4a', align: 'center' },
    ],
  },
  {
    id: 'tpl-aplus-banner',
    name: 'A+ banner',
    family: 'A+ content',
    note: '1464x600 wide banner with a lifestyle band (Amazon Premium Full Image minimum).',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#f7f4ee' },
      { kind: 'shape', shape: 'rect', x: 0, y: 0.72, w: 1, h: 0.28, fill: '#e8e2d8' },
      { kind: 'product', x: 0.06, y: 0.1, w: 0.34, h: 0.5, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.46, y: 0.14, w: 0.48, h: 0.12, text: 'Brand story headline', size: 0.055, weight: 700, color: '#1a1a1a', align: 'left' },
      { kind: 'text', role: 'subhead', x: 0.46, y: 0.29, w: 0.48, h: 0.2, text: 'Supporting paragraph text goes here.', size: 0.03, weight: 400, color: '#5a5a4a', align: 'left' },
      { kind: 'badge', x: 0.46, y: 0.56, w: 0.2, h: 0.07, text: 'EXPLORE', fill: '#1d4a1d', color: '#f5f0e8', size: 0.022 },
    ],
  },
  {
    id: 'tpl-reel-cover',
    name: 'Reel cover',
    family: 'Vertical video',
    note: 'Safe-zone aware vertical cover frame.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#0c150e' },
      { kind: 'shape', shape: 'circle', x: 0.5, y: 0.34, w: 0.5, h: 0.5, fill: '#1d4a1d' },
      { kind: 'product', x: 0.26, y: 0.12, w: 0.48, h: 0.46, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.1, y: 0.62, w: 0.8, h: 0.12, text: 'HOOK TEXT', size: 0.075, weight: 700, color: '#f5f0e8', align: 'center', uppercase: true },
      { kind: 'text', role: 'subhead', x: 0.14, y: 0.75, w: 0.72, h: 0.08, text: 'Keep above the platform UI', size: 0.032, weight: 400, color: '#b0afa0', align: 'center' },
    ],
  },
  // ── Docs, decks, boards, print, web ────────────────────────────────────────
  {
    id: 'tpl-deck-title',
    name: 'Deck — title slide',
    family: 'Presentation',
    note: 'Title, subtitle and a presenter slot.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#f5f0e8' },
      { kind: 'shape', shape: 'rect', x: 0, y: 0, w: 0.02, h: 1, fill: '#1d4a1d' },
      { kind: 'text', role: 'headline', x: 0.09, y: 0.3, w: 0.78, h: 0.2, text: 'Presentation title', size: 0.062, weight: 700, color: '#1a1a1a', align: 'left' },
      { kind: 'text', role: 'subhead', x: 0.09, y: 0.53, w: 0.7, h: 0.1, text: 'Subtitle or one-line framing', size: 0.034, weight: 400, color: '#5a5a4a', align: 'left' },
      { kind: 'text', role: 'legal', x: 0.09, y: 0.88, w: 0.6, h: 0.05, text: 'Presenter · date', size: 0.022, weight: 500, color: '#8a8a7a', align: 'left' },
    ],
  },
  {
    id: 'tpl-board',
    name: 'Whiteboard frame',
    family: 'Whiteboard',
    note: 'Moodboard / planning board with a caption band.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#ffffff' },
      { kind: 'shape', shape: 'rect', x: 0.04, y: 0.04, w: 0.44, h: 0.42, fill: '#f5f0e8', radius: 0.006 },
      { kind: 'shape', shape: 'rect', x: 0.52, y: 0.04, w: 0.44, h: 0.42, fill: '#e8e2d8', radius: 0.006 },
      { kind: 'shape', shape: 'rect', x: 0.04, y: 0.5, w: 0.44, h: 0.42, fill: '#e8e2d8', radius: 0.006 },
      { kind: 'shape', shape: 'rect', x: 0.52, y: 0.5, w: 0.44, h: 0.42, fill: '#f5f0e8', radius: 0.006 },
      { kind: 'text', role: 'headline', x: 0.04, y: 0.94, w: 0.9, h: 0.04, text: 'BOARD CAPTION', size: 0.022, weight: 700, color: '#1a1a1a', align: 'left', uppercase: true },
    ],
  },
  {
    id: 'tpl-print-poster',
    name: 'Poster',
    family: 'Print',
    note: 'A3 poster with a bleed-safe text well.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#1d4a1d' },
      { kind: 'shape', shape: 'circle', x: 0.55, y: 0.1, w: 0.34, h: 0.34, fill: '#c4941a' },
      { kind: 'text', role: 'headline', x: 0.1, y: 0.5, w: 0.8, h: 0.24, text: 'POSTER HEADLINE', size: 0.09, weight: 700, color: '#f5f0e8', align: 'left', uppercase: true },
      { kind: 'text', role: 'subhead', x: 0.1, y: 0.76, w: 0.8, h: 0.1, text: 'Supporting line, short enough to read at a distance.', size: 0.032, weight: 400, color: '#d9d3c6', align: 'left' },
      { kind: 'text', role: 'legal', x: 0.1, y: 0.9, w: 0.8, h: 0.05, text: 'Legal / source line', size: 0.02, weight: 400, color: '#a8b3a4', align: 'left' },
    ],
  },
  {
    id: 'tpl-email-hero',
    name: 'Email hero',
    family: 'Email',
    note: 'Wide email hero with a single CTA.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#f7f4ee' },
      { kind: 'shape', shape: 'rect', x: 0.56, y: 0, w: 0.44, h: 1, fill: '#e8e2d8' },
      { kind: 'product', x: 0.6, y: 0.16, w: 0.36, h: 0.68, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.06, y: 0.22, w: 0.46, h: 0.2, text: 'Email hero headline', size: 0.05, weight: 700, color: '#1a1a1a', align: 'left' },
      { kind: 'text', role: 'subhead', x: 0.06, y: 0.45, w: 0.44, h: 0.16, text: 'One line of supporting copy.', size: 0.03, weight: 400, color: '#5a5a4a', align: 'left' },
      { kind: 'badge', x: 0.06, y: 0.66, w: 0.24, h: 0.09, text: 'SHOP NOW', fill: '#1d4a1d', color: '#f5f0e8', size: 0.024 },
    ],
  },
  {
    id: 'tpl-web-hero',
    name: 'Web hero',
    family: 'Web',
    note: 'Storefront / landing hero band.',
    palette: 'kit-pine',
    layers: [
      { kind: 'bg', fill: '#0c150e' },
      { kind: 'shape', shape: 'ellipse', x: 0.6, y: 0.1, w: 0.5, h: 0.8, fill: 'rgba(29,90,29,0.55)' },
      { kind: 'product', x: 0.62, y: 0.14, w: 0.34, h: 0.72, fit: 'contain', shadow: true, label: 'Product' },
      { kind: 'text', role: 'headline', x: 0.07, y: 0.3, w: 0.5, h: 0.2, text: 'Hero headline', size: 0.055, weight: 700, color: '#f5f0e8', align: 'left' },
      { kind: 'text', role: 'subhead', x: 0.07, y: 0.53, w: 0.46, h: 0.12, text: 'One supporting line, then the CTA.', size: 0.03, weight: 400, color: '#b0afa0', align: 'left' },
      { kind: 'badge', x: 0.07, y: 0.7, w: 0.2, h: 0.075, text: 'GET STARTED', fill: '#c4941a', color: '#0c150e', size: 0.022 },
    ],
  },
]

export function templateById(id) {
  return TEMPLATES.find(t => t.id === id) || null
}

// ── Generation request vocabulary (honest provider boundary) ──────────────────
export const GEN_PURPOSES = [
  { id: 'product-scene', label: 'Product scene', note: 'Pack shot in a generated environment.', family: 'Image' },
  { id: 'lifestyle', label: 'Lifestyle', note: 'Product in use, human context.', family: 'Image' },
  { id: 'background', label: 'Backdrop only', note: 'Scene without the product for compositing.', family: 'Image' },
  { id: 'variant-style', label: 'Style variant', note: 'Re-skin an approved master.', family: 'Image' },
  { id: 'ugc-clip', label: 'UGC clip', note: 'Spokesperson short-form clip.', family: 'Video' },
  { id: 'motion', label: 'Product motion', note: 'Turntable / orbit animation.', family: 'Video' },
  { id: 'hook-clip', label: 'Ad hook clip', note: 'First 3 seconds of a paid ad.', family: 'Video' },
]

export const GEN_TIERS = [
  { id: 'draft', label: 'Draft', note: 'Cheapest model. Iterate fast.', cost: 1 },
  { id: 'final', label: 'Final', note: 'Top-tier model. Print / live ad ready.', cost: 4 },
]

export const PROVIDER_BOUNDARY = {
  image: {
    label: 'Local image engine',
    engine: 'ComfyUI',
    env: 'COMFYUI_URL',
    gate: 'MEDIA_GEN_LIVE',
    models: 'FLUX.2 klein / FLUX.1 dev (weights must be installed)',
  },
  video: {
    label: 'Video / short-clip engine',
    engine: 'fal (Kling / Wan / Veo)',
    env: 'fal provider key',
    gate: 'MEDIA_GEN_LIVE',
    models: 'No local video pipeline exists in this build',
  },
}
