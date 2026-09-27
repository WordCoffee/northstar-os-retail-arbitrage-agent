export const NAV_GROUPS = [
  { id: 'command', label: 'Command', icon: 'command', sections: [
    { id: 'command-center', label: 'Command Center', route: '/home', roles: ['operator', 'platform_admin'] },
  ]},
  { id: 'research', label: 'Research', icon: 'flask', sections: [
    { id: 'sourcescout', label: 'SourceScout', route: '/product-finder', roles: ['operator', 'platform_admin'] },
    { id: 'golden-goose', label: 'Golden Goose Finder', route: '/golden-goose', roles: ['operator', 'platform_admin'] },
    { id: 'listing-guardian', label: 'Listing Guardian', route: '/listings', roles: ['operator', 'platform_admin'] },
    { id: 'keyword-tracker', label: 'Keyword Tracker', route: '/keyword-tracker', roles: ['operator', 'platform_admin'], status: 'Concept' },
    { id: 'competitor-monitor', label: 'Competitor Monitor', route: '/competitor-monitor', roles: ['operator', 'platform_admin'], status: 'Concept' },
  ]},
  { id: 'grow', label: 'Grow', icon: 'chart', sections: [
    { id: 'listingforge', label: 'ListingForge', route: '/listingforge', roles: ['operator', 'platform_admin'], status: 'Concept' },
    { id: 'adpilot', label: 'AdPilot', route: '/adpilot', roles: ['operator', 'platform_admin'], status: 'Concept' },
    { id: 'socialpulse', label: 'SocialPulse', route: '/socialpulse', roles: ['operator', 'platform_admin'], status: 'Concept' },
    { id: 'creative-studio', label: 'Creative Studio', route: '/creative-studio', roles: ['operator', 'platform_admin'], status: 'Concept' },
  ]},
  { id: 'operate', label: 'Operate', icon: 'layers', sections: [
    { id: 'profitability', label: 'Profitability Dashboard', route: '/profitability', roles: ['operator', 'platform_admin'] },
    { id: 'commerce-ops', label: 'Commerce Ops', route: '/commerce-ops', roles: ['operator', 'platform_admin'], status: 'Concept' },
    { id: 'monitoring', label: 'Monitoring', route: '/monitoring', roles: ['operator', 'platform_admin'] },
  ]},
  { id: 'systems', label: 'Systems', icon: 'cpu', sections: [
    { id: 'autothink', label: 'AutothinK', route: '/autothink', roles: ['operator', 'platform_admin'] },
    { id: 'memory-bank', label: 'Memory Bank', route: '/memory-bank', roles: ['operator', 'platform_admin'], status: 'Internal' },
    { id: 'shared-data', label: 'Shared Data Layer', route: '/shared-data', roles: ['operator', 'platform_admin'], status: 'Internal' },
    { id: 'provider-adapters', label: 'Provider Adapters', route: '/provider-adapters', roles: ['operator', 'platform_admin'], status: 'Internal' },
    { id: 'master-brain', label: 'Master Brain', route: '/master-brain', roles: ['operator', 'platform_admin'], status: 'Internal' },
  ]},
  { id: 'role-specific', label: 'Workspace', icon: 'users', sections: [
    { id: 'customer-workspace', label: 'Customer Workspace', route: '/customer-workspace', roles: ['customer'] },
    { id: 'beta-ops', label: 'Beta Operations', route: '/beta-ops', roles: ['platform_admin'] },
    { id: 'administration', label: 'Administration', route: '/admin', roles: ['platform_admin'] },
  ]},
]

export function findNavItem(route) {
  for (const g of NAV_GROUPS) {
    for (const s of g.sections) {
      if (s.route === route) return { group: g, section: s }
    }
  }
  return null
}

export function canUseRole(section, role) {
  return section.roles.includes('all') || section.roles.includes(role)
}

export function sectionsForRole(role) {
  return NAV_GROUPS
    .filter(g => g.sections.some(s => canUseRole(s, role)))
    .map(g => ({ ...g, sections: g.sections.filter(s => canUseRole(s, role)) }))
    .filter(g => g.sections.length > 0)
}
