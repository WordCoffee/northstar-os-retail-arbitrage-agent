// U2: the registry is the single place a service is defined, and the gate is the
// single place entitlement is decided. These tests fail when an entry is added
// without a scene, a theme or a workspace type — the point of the registry.

import test from 'node:test'
import assert from 'node:assert/strict'

import { SERVICES } from '../data/services.js'
import {
  INTERACTIVE_SERVICES,
  SCENES,
  SERVICE_REGISTRY,
  THEMES,
  WORKSPACE_TYPES,
  getService,
  servicesForGroup,
} from '../data/serviceRegistry.js'
import { GATE_MODES, canUseService, serviceAccessMap } from './serviceGate.js'

const REQUIRED = ['id', 'label', 'group', 'route', 'kind', 'scene', 'theme',
                  'workspaceType', 'tools', 'entitlementKey']

test('every service carries every required field', () => {
  for (const entry of SERVICE_REGISTRY) {
    for (const field of REQUIRED) {
      assert.ok(entry[field] !== undefined && entry[field] !== null,
        `${entry.id || '?'} has no ${field}`)
    }
    assert.ok(Array.isArray(entry.tools), `${entry.id} tools must be an array`)
  }
})

test('scene, theme and workspace type all resolve to a known id', () => {
  for (const entry of SERVICE_REGISTRY) {
    assert.ok(SCENES[entry.scene], `${entry.id} scene ${entry.scene} is not in SCENES`)
    assert.ok(THEMES[entry.theme], `${entry.id} theme ${entry.theme} is not in THEMES`)
    assert.ok(WORKSPACE_TYPES[entry.workspaceType],
      `${entry.id} workspaceType ${entry.workspaceType} is not in WORKSPACE_TYPES`)
  }
})

test('ids are unique and lookup works both ways', () => {
  const ids = SERVICE_REGISTRY.map((e) => e.id)
  assert.equal(new Set(ids).size, ids.length)
  for (const id of ids) assert.equal(getService(id).id, id)
  assert.equal(getService('not-a-service'), null)
})

test('the navigation catalogue is fully represented', () => {
  const navIds = SERVICES.flatMap((group) => group.items.map((item) => item.id))
  for (const id of navIds) {
    assert.ok(getService(id), `nav service ${id} is missing from the registry`)
  }
})

test('the studio is registered as a canvas workspace on its own scene', () => {
  const studio = getService('design-studio')
  assert.equal(studio.workspaceType, 'canvas')
  assert.equal(studio.scene, 'studio')
  assert.equal(studio.kind, 'studio')
  assert.ok(studio.tools.length > 0)
})

test('entitlement keys are namespaced per service', () => {
  for (const entry of SERVICE_REGISTRY) {
    assert.equal(entry.entitlementKey, `studio.${entry.id}`)
  }
})

test('interactive services are a subset and non-empty', () => {
  assert.ok(INTERACTIVE_SERVICES.length > 0)
  for (const entry of INTERACTIVE_SERVICES) {
    assert.ok(entry.interactive)
    assert.ok(entry.kind === 'workspace' || entry.kind === 'studio')
  }
  assert.ok(INTERACTIVE_SERVICES.length < SERVICE_REGISTRY.length,
    'onboarding and admin routes are not workspaces')
})

test('servicesForGroup returns only that group', () => {
  const rows = servicesForGroup('Sourcing')
  assert.ok(rows.length >= 2)
  for (const row of rows) assert.equal(row.group, 'Sourcing')
  assert.deepEqual(servicesForGroup('No Such Group'), [])
})

test('the gate is open in dev and names why', () => {
  const decision = canUseService({}, 'design-studio')
  assert.equal(decision.allowed, true)
  assert.equal(decision.mode, GATE_MODES.dev)
  assert.match(decision.reason, /open in dev/)
})

test('the gate refuses an unknown service instead of throwing', () => {
  const decision = canUseService({}, 'ghost-service')
  assert.equal(decision.allowed, false)
  assert.equal(decision.mode, GATE_MODES.unknown)
})

test('the production branch denies without credit and allows with it', () => {
  const denied = canUseService({}, 'design-studio', { enforceBilling: true })
  assert.equal(denied.allowed, false)
  assert.equal(denied.mode, GATE_MODES.denied)

  const credit = canUseService({ studioCredit: 3 }, 'design-studio', { enforceBilling: true })
  assert.equal(credit.allowed, true)
  assert.equal(credit.mode, GATE_MODES.entitled)

  const entitled = canUseService(
    { entitlements: { 'studio.design-studio': true } }, 'design-studio',
    { enforceBilling: true })
  assert.equal(entitled.allowed, true)
})

test('the access map answers for every interactive service', () => {
  const map = serviceAccessMap({}, { registry: INTERACTIVE_SERVICES })
  assert.equal(Object.keys(map).length, INTERACTIVE_SERVICES.length)
  for (const decision of Object.values(map)) assert.equal(decision.allowed, true)
})
