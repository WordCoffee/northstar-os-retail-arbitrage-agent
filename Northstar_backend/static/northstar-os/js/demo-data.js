/* ==========================================================================
   NORTHSTAR OS — DEMO DATA (embedded, labeled, zero network)
   Every record here is a DEMO FIXTURE (data-kind="demo"). Nothing here is
   live data, and the UI always renders a "demo" badge around it. Missing
   values stay as null and render as "—" — never fabricated.
   ========================================================================== */
(function () {
  'use strict';

  var demo = {
    hub: {
      kpis: [
        { label: 'Total Profit', value: '$11,483.22', kind: 'gold', sub: 'portfolio, 90 days (demo)' },
        { label: 'BSR Health', value: '3 / 10 assets', kind: 'good', sub: 'stable or improving (demo)' },
        { label: 'Open Gates', value: '8', kind: 'gold', sub: 'authorization required' },
        { label: 'Demo Mode', value: 'ON', kind: 'dim', sub: 'no live data, no live calls' },
      ],
      services: [
        { id: 'sourcescout', name: 'SourceScout', agent: 'Retail Arbitrage Agent', desc: 'Product sourcing, margin calc, velocity analysis, Kirkland-to-Amazon arbitrage detection.', class: 'Retail Arbitrage' },
        { id: 'listingforge', name: 'ListingForge', agent: 'Listing Optimizer Agent', desc: 'Title/bullet/description rewrites, A+ content, SEO, compliance screening, Rufus readiness.', class: 'Listing Optimization' },
        { id: 'adpilot', name: 'AdPilot', agent: 'Amazon Ads Agent', desc: 'PPC bid optimization, ACoS management, keyword harvesting, placement analysis, negatives.', class: 'Amazon Ads' },
        { id: 'socialpulse', name: 'SocialPulse', agent: 'Social Media Agent', desc: 'Post generation, scheduling copy, brand-voice content, creator outreach.', class: 'Social Media' },
      ],
    },

    sourcescout: {
      kpis: [
        { label: 'Qualified Deals', value: '4', kind: 'gold', sub: '$11+ net, ≥30% ROI (demo)' },
        { label: 'Avg Net / Unit', value: '$11.53', kind: 'gold', sub: 'Kirkland Minoxidil base (demo)' },
        { label: 'Catalog Items', value: '186', kind: 'good', sub: 'costco master list (demo)' },
        { label: 'Live Pull', value: 'GATED', kind: 'crimson', sub: 'authorization required' },
      ],
      rows: [
        { id: 'r1', asin: 'B0CP6LXPLK', name: "Kirkland Signature Minoxidil 5%", cost: 17.99, amazonPrice: 42.00, fbaFee: 8.43, net: 11.53, roi: 64.1, competition: 'Medium', estMonthly: 110, tier: 'Pass', status: 'ready', buyBox: true, invoice: 'clean', riskClean: false, consumable: true },
        { id: 'r2', asin: 'B08B5GZXHN', name: 'Organic Extra Virgin Olive Oil 2L', cost: 8.99, amazonPrice: 27.03, fbaFee: 6.10, net: 7.86, roi: 87.4, competition: 'Low', estMonthly: 40, tier: 'Pass', status: 'ready', buyBox: true, invoice: 'clean', riskClean: true, consumable: true },
        { id: 'r3', asin: 'B095MLHJ97', name: 'Kirkland Facial Towelettes 180ct', cost: 6.99, amazonPrice: 14.71, fbaFee: 4.62, net: 2.01, roi: 28.8, competition: 'High', estMonthly: 220, tier: 'Hold', status: 'needs_review', buyBox: false, invoice: 'unverified', riskClean: false, consumable: false },
        { id: 'r4', asin: 'B00MG4X4LK', name: 'Kirkland Ultra Clean Laundry Detergent', cost: null, amazonPrice: 21.19, fbaFee: 7.02, net: null, roi: null, competition: 'Medium', estMonthly: 95, tier: 'Unscored', status: 'needs_fee_verification', buyBox: true, invoice: 'clean', riskClean: true, consumable: true },
        { id: 'r5', asin: 'B0F87RXTVC', name: 'Word Coffee — Affirmation Cards for Moms', cost: 6.10, amazonPrice: 19.99, fbaFee: 4.01, net: 7.52, roi: 45.2, competition: 'Medium', estMonthly: 300, tier: 'Pass', status: 'ready', buyBox: true, invoice: 'clean', riskClean: true, consumable: true },
      ],
      livePull: {
        status: 'partial',
        provider: 'Bright Data (primary) / Firecrawl (fallback)',
        lastRun: '2026-09-06T08:01:06Z',
        requested: 53,
        resolved: 24,
        failures: [
          { status: 'url_not_found', count: 2, detail: 'genuine content 404s (10597, 1738408)' },
          { status: 'no_data_found', count: 5, detail: '0-byte empty-body Web-Unlocker artifact' },
          { status: 'transport_error', count: 1, detail: 'read timeout on api.brightdata.com — halted by circuit breaker' },
        ],
        note: 'evidence manifest from costco-discovery-runs (fixture) — partial run, failures typed exactly as captured',
      },
    },

    listingforge: {
      kpis: [
        { label: 'Listing Score', value: '79.6', kind: 'gold', sub: 'Moms B0F87RXTVC (fixture)' },
        { label: 'SEO', value: '30', kind: 'good', sub: 'weight 30%' },
        { label: 'Compliance', value: '0 blocks', kind: 'good', sub: '0 warnings (fixture)' },
        { label: 'Rufus Ready', value: '81', kind: 'gold', sub: 'rufusReadinessScore' },
      ],
      listings: [
        {
          id: 'L1', asin: 'B0F87RXTVC', brand: 'Word Coffee', product: 'Affirmation Cards for Moms',
          voice: 'word_coffee', provenance: 'fixture',
          title: 'Word Coffee Daily Affirmation Cards for Moms — 53 Hand-Crafted Cards',
          bullets: [
            '53 unique, research-backed daily affirmations designed to help moms refocus in 30 seconds',
            'Premium 350GSM soft-touch matte stock — a gift-ready, high-end tactile experience',
            'Pocket-sized 2.36 x 3.54 inches — morning ritual, purse, nightstand, or desk',
            'Analog wellness: screen-free mental reset for clarity, courage, and purpose',
            'Thoughtful gift for Mother\u2019s Day, new moms, and the overwhelm of everyday life',
          ],
          backendTerms: ['daily affirmations for women', 'mom affirmation cards', 'self care gifts for moms', 'gift for mom', 'mental health support', 'morning ritual'],
          scores: { seo: 30, conversion: 25, compliance: 20, visual: 10, rufus: 15, total: 79.6, rufusReadiness: 81 },
          scoreRaws: { seo: 82, conversion: 76, compliance: 73, visual: 88, rufus: 84 }, /* 0-100 per category; weighted sum = 79.6 */
          compliance: [
            { rule: 'absolute_superlative', severity: 'warn', term: 'best', message: 'Avoid unverifiable "best" claims.' },
          ],
          mediaPlan: { gallery: ['hero lifestyle', 'cards flat-lay', 'close-up 350GSM texture', 'gift box', 'mom using cards', 'detail cards set', 'size reference'], video: ['morning ritual unbox', '30-second reset', 'gift reveal', '3-card flip'], aPlus: ['story intro', 'quality materials', 'who it\u2019s for', 'ritual how-to', 'gifting occasions'] },
        },
        {
          id: 'L2', asin: 'B0F87JDPD4', brand: 'Word Coffee', product: 'Affirmation Cards for Women',
          voice: 'word_coffee', provenance: 'fixture',
          title: 'Word Coffee Affirmation Cards for Women — 53 Daily Mental Wellness Cards',
          bullets: [
            'A daily jolt of inspiration — for your mind, not your mug',
            '53 hand-crafted affirmations grounded in positive psychology and neuroplasticity',
            'Premium soft-touch matte finish, gift-ready premium box',
            'Niche gift angles: career woman, chef, host, and the self-improver on your list',
          ],
          backendTerms: ['affirmation cards for women', 'gift cards for women', 'career woman gift', 'yoga gifts for women', 'daily affirmations'],
          scores: { seo: 30, conversion: 25, compliance: 20, visual: 10, rufus: 15, total: 80.1, rufusReadiness: 84 },
          scoreRaws: { seo: 82, conversion: 78, compliance: 74, visual: 86, rufus: 84 }, /* 0-100 per category; weighted sum = 80.1 */
          compliance: [
            { rule: 'medical_claim', severity: 'block', term: 'cures', message: 'Medical claims are prohibited on Amazon listings.' },
          ],
          mediaPlan: { gallery: ['hero lifestyle', 'cards in hand', 'gift box', 'desk setup', 'woman journaling', 'cards spread', 'size reference'], video: ['unbox', 'daily use', 'gift moment', '30-second reset'], aPlus: ['story', 'quality', 'audience', 'ritual', 'gifting'] },
        },
      ],
      voices: [
        { id: 'word_coffee', brand: 'Word Coffee', notBeverage: true, tone: 'bold, clear, premium, emotionally honest, practical, non-cheesy', taglines: ['Fuel Your Focus.', 'Grab Word Coffee, not a cup.', 'Find Your Calm in the Chaos.'] },
      ],
    },

    adpilot: {
      kpis: [
        { label: 'Blended ACoS', value: '28.4%', kind: 'gold', sub: 'Word Coffee demo account (demo)' },
        { label: 'Winning Keywords', value: '128', kind: 'good', sub: 'harvested, demo' },
        { label: 'Tier 4 Spend', value: '$40/day', kind: 'gold', sub: 'Winners Exact' },
        { label: 'Live Sync', value: 'GATED', kind: 'crimson', sub: 'Amazon Ads API read' },
      ],
      tiers: [
        { tier: 1, name: 'Bench Auto', budget: 10, purpose: 'Discovery', strategy: 'Dynamic Bids — Down Only' },
        { tier: 2, name: 'Scale Broad', budget: 15, purpose: 'Explore new terms', strategy: 'Dynamic Bids — Down Only' },
        { tier: 3, name: 'Almost Winners', budget: 25, purpose: 'Validate 1\u201314 sales', strategy: 'Dynamic Bids — Down Only' },
        { tier: 4, name: 'Winners Exact', budget: 40, purpose: 'Scale 15+ sales', strategy: 'Dynamic Bids — Down Only' },
      ],
      keywords: [
        { id: 'k1', kw: 'affirmation cards for women', tier: 'Winners Exact', impressions: 11333, clicks: 640, orders: 99, spend: 412, acos: 27.1, movement: 'PROMOTED', auto: true, autoAction: 'Increase bid ≤ 10%' },
        { id: 'k2', kw: 'gift cards for women', tier: 'Winners Exact', impressions: 2090, clicks: 118, orders: 33, spend: 180, acos: 12.4, movement: 'PROMOTED', auto: true, autoAction: 'Increase bid ≤ 10%' },
        { id: 'k3', kw: 'mom affirmation cards', tier: 'Almost Winners', impressions: 1440, clicks: 82, orders: 7, spend: 99, acos: 41.2, movement: 'NO_CHANGE', auto: false, autoAction: 'Decrease bid 5\u201310%' },
        { id: 'k4', kw: 'coffee beans', tier: 'Negatives', impressions: 12, clicks: 3, orders: 0, spend: 4, acos: null, movement: 'DEMOTED', auto: true, autoAction: 'Add negative keyword' },
        { id: 'k5', kw: 'free printable affirmation cards', tier: 'Negatives', impressions: 8, clicks: 1, orders: 0, spend: 2, acos: null, movement: 'DEMOTED', auto: true, autoAction: 'Add negative keyword' },
      ],
      acosBands: [
        { band: '>45% and ≥10 clicks', action: '−10 to −30% bid', kind: 'crimson' },
        { band: '30\u201345%', action: '−5 to −10% bid', kind: 'gold' },
        { band: '15\u201330%', action: '+5 to +15% bid', kind: 'steel' },
        { band: '<15%', action: '+15 to +30% bid', kind: 'gold' },
      ],
      guardrails: [
        { action: 'Decrease bid ≤ 20%', zone: 'autonomous' },
        { action: 'Increase bid ≤ 10%', zone: 'autonomous' },
        { action: 'Add negative keyword', zone: 'autonomous' },
        { action: 'Promote keyword to higher tier', zone: 'autonomous' },
        { action: 'Increase bid > 10%', zone: 'needs_approval' },
        { action: 'Increase daily budget', zone: 'needs_approval' },
        { action: 'Create new campaign', zone: 'needs_approval' },
        { action: 'Pause all campaigns', zone: 'needs_approval' },
      ],
      placements: [
        { label: 'Top of Search', value: 54 },
        { label: 'Product Pages', value: 31 },
        { label: 'Rest of Search', value: 15 },
      ],
      bulkRows: [
        { sku: 'WC-MOMS-V1', campaign: 'WCF-WinnersExact', kwOrTargeting: 'affirmation cards for women', matchType: 'exact', bid: '1.05', decision: 'increase-10pct', reason: 'ACoS 27%, orders>0' },
        { sku: 'WC-MOMS-V1', campaign: 'WCF-AlmostWinners', kwOrTargeting: 'mom affirmation cards', matchType: 'phrase', bid: '0.42', decision: 'decrease-8pct', reason: 'ACoS 41%' },
        { sku: 'WC-WOMEN-V2', campaign: 'WCF-BenchAuto', kwOrTargeting: 'free printable affirmation cards', matchType: 'negative', bid: null, decision: 'add-negative', reason: '0 orders, repeat non-converter' },
      ],
    },

    socialpulse: {
      kpis: [
        { label: 'Channels', value: '3', kind: 'good', sub: 'Meta / TikTok / Instagram (demo)' },
        { label: 'Brand Voices', value: '1', kind: 'gold', sub: 'Word Coffee module loaded' },
        { label: 'Calendar Slots', value: '5', kind: 'good', sub: 'this week (demo)' },
        { label: 'Publishing', value: 'GATED', kind: 'crimson', sub: 'Meta / TikTok / IG APIs' },
      ],
      voices: [
        { id: 'word_coffee', brand: 'Word Coffee', notBeverage: true, tone: 'bold, clear, premium, emotionally honest, practical, non-cheesy', taglines: ['Grab Word Coffee, not a cup.', 'Fuel Your Focus.', 'Find Your Calm in the Chaos.', 'Brew Your Best Self.'] },
      ],
      posts: [
        { id: 'p1', brand: 'word_coffee', channel: 'meta', copy: 'Your daily dose of inspiration is here. Grab Word Coffee, not a cup.', hashtags: ['#WordCoffee', '#MomLife', '#MorningRitual'], slot: 'Mon 9:00 AM', saved: true },
        { id: 'p2', brand: 'word_coffee', channel: 'instagram', copy: 'Find Your Calm in the Chaos. 53 daily reminders for the overwhelm.', hashtags: ['#AnalogWellness', '#MentalRefill', '#GetUnstuck'], slot: 'Wed 8:30 AM', saved: true },
        { id: 'p3', brand: 'word_coffee', channel: 'tiktok', copy: '30-second mental reset: the morning ritual that is not a beverage.', hashtags: ['#WordCoffee', '#SelfCareGifts', '#MorningRitual'], slot: 'Fri 12:00 PM', saved: false },
      ],
      outreach: [
        { kind: 'creator', template: 'Hi {{creator}}, {{brand}} sends free product to aligned creators. {{product}} — would you like a unit to review?', macros: ['creator', 'brand', 'product'] },
        { kind: 'review_request', template: 'Thanks for your purchase of {{product}}. If you have time, please share honest feedback on the product page.', macros: ['product'], compliant: true },
      ],
      creatives: [
        { kind: 'ad', prompt: 'Meta ad creative: 4:5, golden-hour macro textures, warm cream background, "Grab Word Coffee, not a cup." bold serif headline.', aspect: '4:5' },
        { kind: 'photo', prompt: 'Lifestyle photo: hands holding the 350GSM card deck at a sunlit desk, coffee cup OUT OF FRAME (not a beverage product).', aspect: '1:1' },
        { kind: 'video', prompt: '15s vertical: morning unbox → 30-second reset flip → gift reveal. Caption: "Words That Wake You Up."', aspect: '9:16' },
      ],
    },

    subscriber: {
      gateStateNote: 'Demo fixture mirroring shared/subscription-plans.json and the profiles manifest. Plans mark which live gates they WOULD cover; gates are never flipped by a plan.',
      identity: {
        profileId: 't2-holdings-tyrone-johnson',
        kind: 'master_seed',
        owner: 'T2 Holdings LLC',
        principal: 'Tyrone Johnson (co-owner Tyler Edwards)',
        resolver: 'local_default',
        resolverNote: 'same pluggable resolver chain master_brain_profiles.py exposes — no live auth in beta',
      },
      subscription: {
        plan: 'autothink',
        status: 'active',
        since: '2026-09-12',
        billing: 'master_seed — no external billing wired in beta',
      },
      plans: [
        { id: 'foundation', name: 'Foundation', tier: 1, price: 0, services: ['sourcescout', 'listingforge', 'adpilot', 'socialpulse'], entitled_gates: [], blurb: 'Demo/read-only access' },
        { id: 'scout', name: 'Scout', tier: 1, price: 29, services: ['sourcescout', 'listingforge', 'adpilot', 'socialpulse'], entitled_gates: ['sourcescout_live_pull', 'sourcescout_enrich', 'listingforge_copy', 'adpilot_ads_read'], blurb: 'Product sourcing intelligence' },
        { id: 'mover', name: 'Mover', tier: 1, price: 79, services: ['sourcescout', 'listingforge', 'adpilot', 'socialpulse'], entitled_gates: ['sourcescout_live_pull', 'sourcescout_enrich', 'listingforge_copy', 'listingforge_media', 'adpilot_ads_read', 'socialpulse_attrib'], blurb: 'Full SourceScout + ListingForge + Ads' },
        { id: 'autothink', name: 'AutothinK', tier: 2, price: 149, services: ['sourcescout', 'listingforge', 'adpilot', 'socialpulse', 'autothink'], entitled_gates: ['sourcescout_live_pull', 'sourcescout_enrich', 'listingforge_copy', 'listingforge_media', 'adpilot_ads_read', 'adpilot_bulk_exec', 'socialpulse_attrib', 'socialpulse_publish', 'autothink_workspace'], blurb: 'Everything + AutothinK AI workspace' },
      ],
      gatesAlwaysOff: true,
      honesty: 'A plan marks which live gates it WOULD cover. Gates are never flipped by a plan; executing live still requires a fresh, named operator approval per action.',
    },
  };

  (typeof window !== 'undefined' ? window : globalThis).NS_DEMO = demo;
  if (typeof window !== 'undefined' && window.NS) window.NS.DEMO = function () { return demo; };
})();