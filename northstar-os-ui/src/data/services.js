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
      { id: 'goldengoose', label: 'Golden Goose', route: '/goldengoose', icon: 'goose' }
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