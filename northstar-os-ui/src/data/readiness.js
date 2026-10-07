// Single source of truth for room/service readiness labels across the suite.
// Mirrors docs/SERVICE_READINESS_MATRIX.md (Parallel Session A audit).
//
// Rules:
// - "ready" (green, pill-ok) is reserved for rooms that genuinely work locally
//   now. It is never used for sample/shell states.
// - Every other level maps to a non-green, clearly-labelled state.
// - `tone` values map to existing `.pill-<tone>` classes (tokens.css / app.css).

export const READINESS_LEVELS = {
  ready:    { label: 'Local',     tone: 'ok',          title: 'Fully working locally now (offline/local data).' },
  cached:   { label: 'Cached',    tone: 'muted',       title: 'Works from cached data; live provider scan is gated.' },
  partial:  { label: 'Partial',   tone: 'ochre',       title: 'Partly wired — some surfaces are still sample/limited.' },
  sample:   { label: 'Sample',    tone: 'warn',        title: 'Renders sample data only — no live backend wired yet.' },
  concept:  { label: 'Concept',   tone: 'muted',       title: 'Concept surface — not fully built.' },
  internal: { label: 'Internal',  tone: 'muted',       title: 'Internal read-only / management surface.' },
  provider: { label: 'LLM-gated', tone: 'unavailable', title: 'Requires a local model/provider (e.g. Ollama).' },
}

// Room id (nav section id) -> readiness level. Creative/media rooms
// (creative-studio, socialpulse, adpilot) are intentionally omitted so their
// nav status and page surface stay unchanged (owned by the creative session).
export const ROOM_READINESS = {
  'command-center': 'partial', // live system-signals read + real launch pathways; briefing still sample
  'sourcescout': 'cached',
  'golden-goose': 'ready',
  'listing-guardian': 'partial', // real local listing/identity records + sample triage
  'keyword-tracker': 'ready', // fully derived from local keyword store + foundation keyword service
  'competitor-monitor': 'partial', // real local product/source observations + sample competitor rows
  'profitability': 'partial', // backend economics engine + sample portfolio context
  'commerce-ops': 'ready', // fully derived from local identity queue + pipeline runs + foundation approvals
  'monitoring': 'ready', // fully derived from live local reads (error tracker, readiness, refresh registry)
  'autothink': 'provider',
  'memory-bank': 'internal',
  'shared-data': 'internal',
  'provider-adapters': 'internal',
  'master-brain': 'internal',
  'administration': 'ready',
  'beta-ops': 'ready',
}

// Route -> room id, so a room page can resolve its own readiness badge without
// importing the nav config (avoids a circular import). First path segment match.
export const ROUTE_ROOM = {
  '/home': 'command-center',
  '/product-finder': 'sourcescout',
  '/golden-goose': 'golden-goose',
  '/listings': 'listing-guardian',
  '/keyword-tracker': 'keyword-tracker',
  '/competitor-monitor': 'competitor-monitor',
  '/profitability': 'profitability',
  '/commerce-ops': 'commerce-ops',
  '/monitoring': 'monitoring',
  '/autothink': 'autothink',
  '/memory-bank': 'memory-bank',
  '/shared-data': 'shared-data',
  '/provider-adapters': 'provider-adapters',
  '/master-brain': 'master-brain',
  '/admin': 'administration',
  '/beta-ops': 'beta-ops',
}

export function readinessForRoom(id) {
  const level = ROOM_READINESS[id]
  if (!level) return null
  const meta = READINESS_LEVELS[level]
  return meta ? { level, ...meta } : null
}

export function readinessForRoute(pathname) {
  if (!pathname) return null
  const base = '/' + pathname.replace(/^\/+/, '').split('/')[0]
  return readinessForRoom(ROUTE_ROOM[base])
}