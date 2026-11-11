export const SERVICES = [
  {
    group: 'Workspace',
    icon: 'overview',
    items: [
      { id: 'hub', label: 'Operations Hub', route: '/hub', icon: 'gauge' },
      { id: 'ledger', label: 'The Ledger', route: '/ledger', icon: 'ledger' }
    ]
  },
  {
    group: 'Sourcing',
    icon: 'sourcing',
    items: [
      { id: 'prospector', label: 'Prospector', route: '/prospector', icon: 'prospector' },
      // One Golden Goose, at the real desk. The legacy /goldengoose route redirects
      // there (App.jsx); listing it again here counted the same product twice.
      { id: 'golden-goose', label: 'Golden Goose', route: '/golden-goose', icon: 'goose' }
    ]
  },
  {
    group: 'Listings',
    icon: 'listings',
    items: [
      { id: 'offerchisel', label: 'OfferChisel', route: '/offerchisel', icon: 'chisel' }
    ]
  },
  {
    group: 'Social',
    icon: 'social',
    items: [
      { id: 'towncrier', label: 'The Town Crier', route: '/towncrier', icon: 'crier' }
    ]
  },
  {
    group: 'Advertising',
    icon: 'advertising',
    items: [
      { id: 'auctioneer', label: 'The Auctioneer', route: '/auctioneer', icon: 'auctioneer' }
    ]
  },
  {
    group: 'AutothinK',
    icon: 'autothink',
    items: [
      { id: 'autothink', label: 'AutothinK', route: '/autothink', icon: 'brain' }
    ]
  },
  {
    group: 'Monitoring',
    icon: 'monitoring',
    items: [
      { id: 'thewatch', label: 'The Watch', route: '/thewatch', icon: 'watch' },
      { id: 'rankledger', label: 'RankLedger', route: '/rankledger', icon: 'rank' },
      { id: 'rivalboard', label: 'The Rival Board', route: '/rivalboard', icon: 'rival' }
    ]
  },
  {
    group: 'Account',
    icon: 'account',
    items: [
      { id: 'account', label: 'Account', route: '/account', icon: 'account' }
    ]
  },
  {
    group: 'Internal',
    icon: 'gauge',
    items: [
      { id: 'foundation', label: 'Foundation', route: '/foundation', icon: 'gauge', perm: 'request_refresh' },
      { id: 'jobs', label: 'Jobs & Schedules', route: '/jobs', icon: 'jobs', perm: 'request_refresh' },
      { id: 'keywords', label: 'Keywords & SEO', route: '/keywords', icon: 'rank', perm: 'request_refresh' }
    ]
  },
  {
    group: 'Private Beta',
    icon: 'lock',
    items: [
      { id: 'beta', label: 'Onboarding & Plan', route: '/beta', icon: 'check', perm: 'view' },
      { id: 'beta-support', label: 'Support', route: '/beta#support', icon: 'help', perm: 'view' },
      { id: 'beta-signup', label: 'Invite entry', route: '/beta-signup', icon: 'plus', perm: 'view' }
    ]
  },
  {
    group: 'Beta Operations',
    icon: 'shield',
    items: [
      { id: 'beta-ops', label: 'Tester Dashboard', route: '/beta-ops', icon: 'gauge', perm: 'platform_admin' }
    ]
  }
]

export const DOCK_ACTIONS = [
  { id: 'scan', label: 'Scan', route: '/prospector', icon: 'scan' },
  { id: 'generate', label: 'Generate', route: '/offerchisel', icon: 'generate' },
  { id: 'review', label: 'Review', route: '/auctioneer', icon: 'review' },
  { id: 'create', label: 'Create', route: '/towncrier', icon: 'create' },
  { id: 'account', label: 'Account', route: '/account', icon: 'account' }
]

export const routeToId = (route) => {
  for (const group of SERVICES) {
    for (const item of group.items) {
      if (item.route === route) return item.id
    }
  }
  return null
}