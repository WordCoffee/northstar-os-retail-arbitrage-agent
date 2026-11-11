#!/usr/bin/env node
// Regenerate `src/data/workspaces.js` from `ty/northstar_workspaces.json`.
//
// The artifact is the source of truth; the UI needs a JS module (not JSON) for
// two reasons recorded in the generated header: Node's ESM loader refuses a bare
// JSON import from a unit test, and Dockerfile.ui builds from `northstar-os-ui/`
// alone, where `ty/` does not exist.
//
// Run from the repo root or from `northstar-os-ui/`:
//   node northstar-os-ui/scripts/sync-workspaces.mjs
//
// `src/lib/workspaceSpecs.test.js` fails when the two files disagree, so a
// forgotten run is a red test rather than a silent drift.

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const UI_ROOT = resolve(here, '..')
const ARTIFACT = resolve(UI_ROOT, '..', 'ty', 'northstar_workspaces.json')
const TARGET = resolve(UI_ROOT, 'src', 'data', 'workspaces.js')

const artifact = JSON.parse(readFileSync(ARTIFACT, 'utf8'))

const doc = {
  schema: artifact.scene_workspaces_schema,
  mirrored_from: 'ty/northstar_workspaces.json#scene_workspaces',
  note: ('The renderable copy of the scene_workspaces block. '
    + '`src/lib/workspaceSpecs.test.js` fails when this file and '
    + 'ty/northstar_workspaces.json disagree, so the UI cannot drift into a second source '
    + 'of truth.'),
  core_six: artifact.core_six,
  default_scene: artifact.default_scene,
  default_workspace: artifact.default_workspace,
  workspaces: artifact.scene_workspaces,
}

const header = `// The workspace specs, as data. GENERATED - do not hand-edit.
//
// Source of truth: ty/northstar_workspaces.json (scene_workspaces block).
// Regenerate with: node northstar-os-ui/scripts/sync-workspaces.mjs
//
// Emitted as a JS module rather than a .json file because this file is imported
// by src/lib/workspaceSpecs.js, which is unit-tested with \`node --test\`: Node's
// ESM loader refuses a bare JSON import without a \`with { type: 'json' }\`
// attribute, and Vite 5 rewrites the attribute away in some build paths. One
// plain module works in both.
//
// src/lib/workspaceSpecs.test.js fails when this object and the artifact
// disagree.

`

writeFileSync(TARGET, `${header}export const WORKSPACE_SPECS = ${JSON.stringify(doc, null, 2)}\n\nexport default WORKSPACE_SPECS\n`, 'utf8')

console.log(`wrote ${TARGET}`)
console.log(`workspaces: ${doc.workspaces.map((w) => w.id).join(', ')}`)
