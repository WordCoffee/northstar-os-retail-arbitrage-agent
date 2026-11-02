// The service registry — one entry per service, and the only place a new service
// is added. The shell, the tab bar, the scene manager and the theme system all
// read this file; nothing else keeps a parallel list.
//
// Two catalogues exist in the repo and this file reconciles them:
//   * `src/data/services.js` — the navigation catalogue (groups, routes, icons)
//   * `src/App.jsx` — the routed rooms (design studio, listings, PPC, …)
// Services that are routes but not in the nav catalogue are marked
// `source: 'app-route'` so the difference stays visible instead of being hidden.
//
// Fields (all required by the invariant test):
//   id            stable key, matches the route id where one exists
//   label         what a human reads
//   group         nav group
//   route         the path the workspace lives at
//   kind          workspace | studio | account | onboarding | admin
//   scene         scene id the scene manager loads (see SCENES)
//   theme         theme id (see THEMES) — the "sports car" accent shift
//   workspaceType how the outlet renders it
//   tools         Bojo tool ids this service can use (empty is honest)
//   entitlementKey key a production gate would check

import { SERVICES } from './services.js'

/** Scene ids. The scene engine ships `default` first; the rest land in U6/U9–U11. */
export const SCENES = {
  default: { id: 'default', label: 'Starfield', built: true },
  studio: { id: 'studio', label: 'Ringed gas giant', built: false },
  ppc: { id: 'ppc', label: 'Asteroid field', built: false },
  research: { id: 'research', label: 'Black hole', built: false },
  goose: { id: 'goose', label: 'Comet pass', built: false },
}

/** Theme ids. Tokens live in `src/styles/themes.css` from U4; ids are stable here. */
export const THEMES = {
  neutral: { id: 'neutral', accent: '#7fb0ff', accentSoft: '#1d2a44' },
  studio: { id: 'studio', accent: '#e8b04b', accentSoft: '#3a2c12' },
  ppc: { id: 'ppc', accent: '#ef6f5a', accentSoft: '#3d1d18' },
  research: { id: 'research', accent: '#9d8bff', accentSoft: '#2a2447' },
  goose: { id: 'goose', accent: '#5fd3a2', accentSoft: '#12332a' },
  ledger: { id: 'ledger', accent: '#8fd0c8', accentSoft: '#15302e' },
  monitor: { id: 'monitor', accent: '#c9d1d9', accentSoft: '#242a31' },
  account: { id: 'account', accent: '#b9b2a6', accentSoft: '#2b2823' },
}

export const WORKSPACE_TYPES = {
  canvas: { id: 'canvas', label: 'Canvas editor' },
  report: { id: 'report', label: 'Report / upload' },
  list: { id: 'list', label: 'List / finder' },
  monitor: { id: 'monitor', label: 'Monitoring board' },
  chat: { id: 'chat', label: 'Assistant workspace' },
  account: { id: 'account', label: 'Account' },
  onboarding: { id: 'onboarding', label: 'Onboarding' },
  admin: { id: 'admin', label: 'Admin' },
}

const GROUP_LOOK = {
  Workspace: { theme: 'neutral', scene: 'default' },
  Sourcing: { theme: 'goose', scene: 'goose' },
  Listings: { theme: 'neutral', scene: 'default' },
  Social: { theme: 'neutral', scene: 'default' },
  Advertising: { theme: 'ppc', scene: 'ppc' },
  AutothinK: { theme: 'research', scene: 'research' },
  Monitoring: { theme: 'monitor', scene: 'default' },
  Account: { theme: 'account', scene: 'default' },
  Internal: { theme: 'ledger', scene: 'default' },
  'Private Beta': { theme: 'account', scene: 'default' },
  'Beta Operations': { theme: 'account', scene: 'default' },
}

/** Rooms that are routed but not in the nav catalogue. */
const APP_ROUTE_SERVICES = [
  { id: 'design-studio', label: 'Design Studio', group: 'Create', route: '/design-studio',
    kind: 'studio', scene: 'studio', theme: 'studio', workspaceType: 'canvas',
    tools: ['generate_image', 'list_templates', 'build_dieline'], source: 'app-route' },
  { id: 'product-finder', label: 'SourceScout', group: 'Sourcing', route: '/product-finder',
    kind: 'workspace', scene: 'goose', theme: 'goose', workspaceType: 'list',
    tools: ['scan_products'], source: 'app-route' },
  { id: 'golden-goose', label: 'Golden Goose', group: 'Sourcing', route: '/golden-goose',
    kind: 'workspace', scene: 'goose', theme: 'goose', workspaceType: 'list',
    tools: ['golden_goose_scan'], source: 'app-route' },
  { id: 'listings', label: 'Listing Guardian', group: 'Listings', route: '/listings',
    kind: 'workspace', scene: 'default', theme: 'neutral', workspaceType: 'monitor',
    tools: ['optimize_listing'], source: 'app-route' },
  { id: 'keyword-tracker', label: 'Keyword Tracker', group: 'Monitoring', route: '/keyword-tracker',
    kind: 'workspace', scene: 'default', theme: 'monitor', workspaceType: 'monitor',
    tools: ['track_keywords'], source: 'app-route' },
  { id: 'competitor-monitor', label: 'Competitor Monitor', group: 'Monitoring', route: '/competitor-monitor',
    kind: 'workspace', scene: 'default', theme: 'monitor', workspaceType: 'monitor',
    tools: ['watch_competitor'], source: 'app-route' },
  { id: 'listingforge', label: 'ListingForge', group: 'Listings', route: '/listingforge',
    kind: 'workspace', scene: 'default', theme: 'neutral', workspaceType: 'report',
    tools: ['compose_listing'], source: 'app-route' },
  { id: 'adpilot', label: 'AdPilot', group: 'Advertising', route: '/adpilot',
    kind: 'workspace', scene: 'ppc', theme: 'ppc', workspaceType: 'report',
    tools: ['plan_campaign'], source: 'app-route' },
  { id: 'socialpulse', label: 'SocialPulse', group: 'Social', route: '/socialpulse',
    kind: 'workspace', scene: 'default', theme: 'neutral', workspaceType: 'report',
    tools: ['plan_social'], source: 'app-route' },
  { id: 'profitability', label: 'Profitability', group: 'Workspace', route: '/profitability',
    kind: 'workspace', scene: 'default', theme: 'ledger', workspaceType: 'report',
    tools: ['margin_report'], source: 'app-route' },
]

const NAV_KIND = (id) => {
  if (id.startsWith('beta')) return 'onboarding'
  if (id === 'beta-ops') return 'admin'
  if (id === 'account') return 'account'
  if (id === 'autothink') return 'workspace'
  return 'workspace'
}

const NAV_WORKSPACE = (id, group) => {
  if (id.startsWith('beta') || id === 'beta-ops') return 'onboarding'
  if (id === 'account') return 'account'
  if (group === 'Monitoring') return 'monitor'
  if (group === 'AutothinK') return 'chat'
  if (group === 'Internal') return 'report'
  if (group === 'Workspace') return 'report'
  return 'list'
}

function fromNavCatalogue() {
  const rows = []
  for (const group of SERVICES) {
    for (const item of group.items) {
      const look = GROUP_LOOK[group.group] || GROUP_LOOK.Workspace
      rows.push({
        id: item.id,
        label: item.label,
        group: group.group,
        route: item.route,
        kind: NAV_KIND(item.id),
        scene: item.id === 'autothink' ? 'research' : look.scene,
        theme: item.id === 'autothink' ? 'research' : look.theme,
        workspaceType: NAV_WORKSPACE(item.id, group.group),
        tools: [],
        source: 'nav',
      })
    }
  }
  return rows
}

export const SERVICE_REGISTRY = [...fromNavCatalogue(), ...APP_ROUTE_SERVICES].map((entry) => ({
  ...entry,
  entitlementKey: `studio.${entry.id}`,
  interactive: entry.kind === 'workspace' || entry.kind === 'studio',
}))

const BY_ID = new Map(SERVICE_REGISTRY.map((entry) => [entry.id, entry]))

export function getService(id) {
  return BY_ID.get(id) || null
}

export function servicesForGroup(group) {
  return SERVICE_REGISTRY.filter((entry) => entry.group === group)
}

/** Interactive services are the ones the shell offers as workspaces/tabs. */
export const INTERACTIVE_SERVICES = SERVICE_REGISTRY.filter((entry) => entry.interactive)
