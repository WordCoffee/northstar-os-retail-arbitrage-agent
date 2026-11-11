// block3-workspaces: the workspace specs are data, and these tests keep the
// data honest.
//
// Three things are pinned here, and each one is a failure that would otherwise
// reach the operator:
//
//   1. the renderable mirror (`src/data/workspaces.js`) and the artifact
//      (`ty/northstar_workspaces.json#scene_workspaces`) say the same thing â€”
//      a UI copy that drifts is a second source of truth;
//   2. every described workspace is a real place: the route is a `<Route>` in
//      App.jsx, the service is in the registry with the same route, the tab is
//      a tab route with a panel, and the scene is one the scene registry ships;
//   3. the view resolver and the gate answer the way the frame renders them,
//      including the dev-only billing stub that must never turn itself on.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { WORKSPACE_SPECS } from '../data/workspaces.js'
import { SERVICE_REGISTRY, getService } from '../data/serviceRegistry.js'
import { TAB_ROUTE_PATTERNS, tabSummary } from '../shell/tabRoutes.js'
import { tabContextFromSummary } from '../chat/turnBody.js'
import {
  BILLING_STUB_PARAM,
  BILLING_STUB_VALUE,
  MIRRORED_KEYS,
  allWorkspaces,
  billingStubEnforced,
  coreSix,
  defaultScene,
  defaultWorkspace,
  resolveView,
  viewLabel,
  workspaceForService,
  workspaceGate,
  workspaceScene,
} from './workspaceSpecs.js'

const here = dirname(fileURLToPath(import.meta.url))
const ARTIFACT = resolve(here, '../../../ty/northstar_workspaces.json')
const APP = readFileSync(resolve(here, '../App.jsx'), 'utf8')
const ROUTE_PATHS = [...APP.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1])
// The scene registry and the panel map both import browser-only assets/JSX, so
// they are pinned as SOURCE (the same technique tabRoutes.test.js uses for
// App.jsx): a spec must name a scene id and a variant the registry really has.
const SCENE_REGISTRY_SRC = readFileSync(resolve(here, '../scenes/sceneRegistry.js'), 'utf8')
const PANELS_SRC = readFileSync(resolve(here, '../shell/WorkspacePanels.jsx'), 'utf8')

function loadArtifact() {
  return JSON.parse(readFileSync(ARTIFACT, 'utf8'))
}

test('the mirror and the artifact describe the same workspaces, key by key', () => {
  const artifact = loadArtifact()
  assert.equal(artifact.scene_workspaces_schema, WORKSPACE_SPECS.schema,
    'the artifact and the mirror disagree on the schema id')
  assert.deepEqual(artifact.core_six, WORKSPACE_SPECS.core_six)
  assert.deepEqual(artifact.default_scene, WORKSPACE_SPECS.default_scene)
  assert.deepEqual(artifact.default_workspace, WORKSPACE_SPECS.default_workspace)
  assert.deepEqual(artifact.scene_workspaces, WORKSPACE_SPECS.workspaces,
    'ty/northstar_workspaces.json#scene_workspaces and src/data/workspaces.js have drifted')
  // The block the lane added is additive: the generated part is untouched.
  for (const key of ['schema', 'count', 'layout_distribution', 'workspaces', 'generated_from']) {
    assert.ok(key in artifact, `the artifact lost its generated key ${key}`)
  }
  assert.deepEqual(MIRRORED_KEYS.slice().sort(), ['core_six', 'default_scene', 'default_workspace', 'workspaces'])
})

test('the six named services each carry a workspace', () => {
  const six = coreSix()
  assert.equal(six.length, 6)
  assert.deepEqual(six.map((row) => row.role),
    ['design', 'listings', 'ppc', 'golden-goose', 'research', 'product-pictures'])
  for (const row of six) {
    const spec = workspaceForService(row.service)
    assert.ok(spec, `${row.service} is one of the core six but has no workspace spec`)
    assert.equal(spec.core_role, row.role)
  }
  assert.equal(allWorkspaces().length, six.length,
    'a workspace exists that is not one of the core six; the file claims six')
})

test('every workspace states id, route, scene, tabs, tool and gate', () => {
  const ids = new Set()
  for (const spec of allWorkspaces()) {
    for (const key of ['id', 'core_role', 'label', 'service', 'route', 'page',
      'page_title', 'page_anchor', 'scene', 'views', 'bojo_tool', 'gate', 'why']) {
      assert.ok(spec[key] !== undefined && spec[key] !== null, `${spec.id || '?'} has no ${key}`)
    }
    assert.equal(spec.id, spec.service, `${spec.id}: id and service must agree`)
    assert.ok(!ids.has(spec.id), `duplicate workspace id ${spec.id}`)
    ids.add(spec.id)
    assert.match(spec.route, /^\//, `${spec.id}: route must be absolute`)
    assert.ok(spec.scene.id && spec.scene.variant, `${spec.id}: scene needs an id and a variant`)
    assert.ok(Array.isArray(spec.views.tabs) && spec.views.tabs.length > 0,
      `${spec.id}: a workspace with no views is not a workspace`)
    assert.ok(spec.views.tabs.some((tab) => tab.id === spec.views.default),
      `${spec.id}: default view ${spec.views.default} is not one of its tabs`)
    assert.ok(spec.bojo_tool.id, `${spec.id}: name the Bojo tool it opens`)
    assert.equal(spec.bojo_tool.source, 'ty/bojo_tool_list.json')
    assert.equal(spec.gate.entitlement_key, `studio.${spec.service}`,
      `${spec.id}: the gate must use the registry's entitlement key`)
    assert.match(spec.gate.decided_by, /serviceGate\.js::canUseService/)
    assert.ok(spec.why.length >= 40, `${spec.id}: why is too short to argue the shape`)
  }
})

test('every workspace route is a real route, tab, panel and service', () => {
  for (const spec of allWorkspaces()) {
    assert.ok(ROUTE_PATHS.includes(spec.route) || ROUTE_PATHS.includes(`${spec.route}/*`),
      `${spec.id}: ${spec.route} is not registered in App.jsx`)
    const service = getService(spec.id)
    assert.ok(service, `${spec.id} is not in the service registry`)
    assert.equal(service.route, spec.route, `${spec.id}: registry route and spec route differ`)
    assert.equal(service.interactive, true, `${spec.id} must be an interactive service`)
    assert.ok(TAB_ROUTE_PATTERNS[spec.id], `${spec.id} is not a tab route`)
    assert.ok(new RegExp(`['"]?${spec.id}['"]?:\\s*lazy\\(`).test(PANELS_SRC),
      `${spec.id} has no workspace panel in WorkspacePanels.jsx`)
    assert.ok(TAB_ROUTE_PATTERNS[spec.id].includes(spec.route)
      || TAB_ROUTE_PATTERNS[spec.id].includes(`${spec.route}/*`),
      `${spec.id}: no tab pattern matches ${spec.route}`)
  }
})

test('every workspace paints the scene the scene registry actually ships', () => {
  const ids = new Set(SERVICE_REGISTRY.map((entry) => entry.id))
  const blockFor = (sceneId) => {
    const quoted = SCENE_REGISTRY_SRC.split(`'${sceneId}': {`)[1]
    if (quoted) return quoted
    const bare = SCENE_REGISTRY_SRC.split(`\n  ${sceneId}: {`)[1]
    return bare || ''
  }
  for (const spec of allWorkspaces()) {
    const block = blockFor(spec.scene.id)
    assert.ok(block, `${spec.id}: ${spec.scene.id} is not a scene in sceneRegistry.js`)
    const end = block.indexOf('\n  },')
    const body = end === -1 ? block : block.slice(0, end)
    assert.ok(body.includes(`variant: '${spec.scene.variant}'`),
      `${spec.id}: the spec names variant ${spec.scene.variant}, the registry does not`)
    assert.ok(body.includes(`label: '${spec.scene.label}'`),
      `${spec.id}: the spec names scene label ${spec.scene.label}, the registry does not`)
    assert.ok(body.includes(`route: '${spec.route}'`),
      `${spec.id}: the scene registry does not map ${spec.route} to this scene`)
    assert.ok(ids.has(spec.service))
  }
})

test('a service with no spec gets no frame and the default scene', () => {
  assert.equal(workspaceForService('not-a-service'), null)
  assert.equal(workspaceForService('profitability'), null,
    'profitability is not one of the core six; it must fall through to its own page')
  assert.equal(defaultScene().service, 'home')
  assert.match(SCENE_REGISTRY_SRC, /DEFAULT_SCENE_SERVICE = 'home'/)
  assert.equal(workspaceScene(null).id, 'home')
  const fallback = defaultWorkspace()
  assert.equal(fallback.id, 'default')
  assert.equal(fallback.scene.id, 'home')
  assert.deepEqual(fallback.views.tabs, [])
})

test('the view resolver reads the room own query key and falls back', () => {
  const listings = workspaceForService('listings')
  assert.equal(resolveView(listings, ''), 'alerts')
  assert.equal(resolveView(listings, '?view=diffs'), 'diffs')
  assert.equal(resolveView(listings, '?view=not-a-view'), 'alerts',
    'an unknown view must fall back to the declared default')
  assert.equal(viewLabel(listings, 'diffs'), 'Diffs')

  const studio = workspaceForService('design-studio')
  assert.equal(studio.views.param, 'section')
  assert.equal(resolveView(studio, '?section=listing-images'), 'listing-images')
  assert.equal(resolveView(studio, '?view=listing-images'), 'canvas',
    'the studio uses ?section=, so a ?view= must not select a section')

  const pictures = workspaceForService('product-pictures')
  assert.equal(resolveView(pictures, '?view=anything'), 'workspace',
    'a workspace with no query param has exactly one view')
})

test('the gate opens in dev, refuses an unentitled plan, and names the key', () => {
  const spec = workspaceForService('listings')
  const dev = workspaceGate(spec, {})
  assert.equal(dev.allowed, true)
  assert.equal(dev.mode, 'dev_open')

  const denied = workspaceGate(spec, {}, { enforce: true })
  assert.equal(denied.allowed, false)
  assert.equal(denied.mode, 'denied')
  assert.match(denied.reason, /no studio credit/)

  const entitled = workspaceGate(spec, { entitlements: { 'studio.listings': true } }, { enforce: true })
  assert.equal(entitled.allowed, true)
  assert.equal(entitled.mode, 'entitled')

  const credit = workspaceGate(spec, { studioCredit: 2 }, { enforce: true })
  assert.equal(credit.allowed, true)

  // No spec: the frame is not rendered at all, so the gate must not invent a refusal.
  assert.equal(workspaceGate(null, {}).allowed, true)
})

test('the billing stub is a dev-only switch and never turns itself on', () => {
  assert.equal(billingStubEnforced(`?${BILLING_STUB_PARAM}=${BILLING_STUB_VALUE}`, false), false,
    'a production build must compile the stub out')
  assert.equal(billingStubEnforced(`?${BILLING_STUB_PARAM}=${BILLING_STUB_VALUE}`, true), true)
  assert.equal(billingStubEnforced('?billing=1', true), false)
  assert.equal(billingStubEnforced('', true), false)
  assert.equal(billingStubEnforced('?billing=ENFORCE', true), false)
})

test('the open tab hands Bojo the workspace, the view and the tool', () => {
  const spec = workspaceForService('adpilot')
  const tabs = [{
    id: 'adpilot', serviceId: 'adpilot', label: 'AdPilot',
    path: '/adpilot', search: '?view=terms', href: '/adpilot?view=terms',
  }]
  const summary = tabSummary({
    tabs,
    activeTab: tabs[0],
    scrollTop: 0,
    at: '2026-11-11T00:00:00.000Z',
    workspace: spec.id,
    tool: spec.bojo_tool.id,
  })
  assert.equal(summary.workspace, 'adpilot')
  assert.equal(summary.tool, 'plan_campaign')
  assert.equal(summary.view, 'terms')

  const context = tabContextFromSummary(summary)
  assert.deepEqual(context, {
    id: 'adpilot',
    route: '/adpilot?view=terms',
    title: 'AdPilot',
    state: { view: 'terms', query: { view: 'terms' }, workspace: 'adpilot', tool: 'plan_campaign', openTabs: ['adpilot'], tabCount: 1 },
  })

  // A service with no spec publishes an empty workspace and tool, not a guess.
  const bare = tabSummary({ tabs: [], activeTab: null, at: '2026-11-11T00:00:00.000Z' })
  assert.equal(bare.workspace, '')
  assert.equal(bare.tool, '')
  assert.equal(tabContextFromSummary(bare), undefined)
})

