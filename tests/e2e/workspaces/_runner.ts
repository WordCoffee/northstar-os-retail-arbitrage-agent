// The click path every core workspace has to pass, written ONCE.
//
// The six spec files in this directory are a few lines each: they name a service
// and call `runCoreWorkspace`. That is deliberate — the acceptance is that the
// UI renders the workspaces FROM `ty/northstar_workspaces.json`, so the test
// reads the same file the UI reads. Six copies of the assertions would be six
// places for the file to drift out from under.
//
// What each workspace proves, on desktop Chromium and iPhone 12 WebKit:
//   1. its own view renders (the page's anchor and its own <h1>), inside a
//      workspace frame whose data-ws-* attributes match the file;
//   2. the scene the file names is the scene the bed paints, and the bed fired
//      `northstar:scene` for it (the scene-events item);
//   3. the DevBanner is present, exactly once, painted above the workspace — the
//      production negative is proved by src/shell/devBanner.test.js under
//      `npm run test:ui`, because a local dev run cannot produce a JWT session;
//   4. clicking a declared view changes the URL, the frame's view and the tab
//      context Bojo receives (`__northstarWorkspaceTab` and the
//      `northstar:workspace-tab` event), which is the open-tab-context item;
//   5. `?billing=enforce` refuses the service through `canUseService` and shows
//      the refusal instead of the page — the gate is a stub, no billing runs.
//
// LOCALHOST ONLY (127.0.0.1:8101) per the narrow e2e exception in AGENTS.md.
// Headless only: `state/vision/PAUSE` is active, so nothing here opens or drives
// a visible browser window.

import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const WORKSPACE_PROJECTS = ['desktop-chromium', 'iphone-12-webkit']

const ARTIFACT = () => resolve(process.cwd(), 'ty', 'northstar_workspaces.json')

export type WorkspaceSpec = {
  id: string
  core_role: string
  click_path_view: string
  label: string
  service: string
  route: string
  page_title: string
  page_anchor: string
  scene: { id: string; label: string; variant: string }
  views: {
    param: string
    default: string
    tabs: Array<{ id: string; label: string }>
  }
  bojo_tool: { id: string; status: string; owner: string }
  gate: { entitlement_key: string; denied: string }
}

export type Artifact = {
  scene_workspaces_schema: string
  core_six: Array<{ role: string; service: string }>
  default_scene: { service: string; label: string; variant: string }
  default_workspace: { id: string; scene: { id: string } }
  scene_workspaces: WorkspaceSpec[]
}

export function artifact(): Artifact {
  return JSON.parse(readFileSync(ARTIFACT(), 'utf8')) as Artifact
}

export function specFor(serviceId: string): WorkspaceSpec {
  const spec = artifact().scene_workspaces.find((w) => w.id === serviceId)
  if (!spec) throw new Error(`${serviceId} is not described in ty/northstar_workspaces.json`)
  return spec
}

/** A URL for the workspace, with extra query params appended. */
export function urlFor(route: string, params: Record<string, string> = {}): string {
  const qs = new URLSearchParams(params).toString()
  return `/ui${route}${qs ? `?${qs}` : ''}`
}

const visiblePanel = (page: Page, id: string) => page.locator(`#wst-panel-${id}`)

/** The frame of the open tab. */
const frameOf = (page: Page, id: string) => visiblePanel(page, id).getByTestId('ws-frame')

type TabContext = {
  tabId?: string
  serviceId?: string
  workspace?: string
  tool?: string
  view?: string
  path?: string
}

/**
 * Record the two document events before any app script runs. `addInitScript` is
 * the only way to be listening for the FIRST `northstar:scene` and the first
 * `northstar:workspace-tab` — both are dispatched during the first paint.
 */
async function recordEvents(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as {
      __sceneEvents: Array<Record<string, unknown>>
      __tabEvents: Array<Record<string, unknown>>
    }
    w.__sceneEvents = []
    w.__tabEvents = []
    document.addEventListener('northstar:scene', (event) => {
      w.__sceneEvents.push((event as CustomEvent).detail as Record<string, unknown>)
    })
    document.addEventListener('northstar:workspace-tab', (event) => {
      w.__tabEvents.push((event as CustomEvent).detail as Record<string, unknown>)
    })
  })
}

export function runCoreWorkspace(serviceId: string) {
  const spec = specFor(serviceId)
  const artifactDoc = artifact()
  const target = spec.views.tabs.find((tab) => tab.id === spec.click_path_view)
  const hasClick = !!target && spec.click_path_view !== spec.views.default

  test.describe(`${spec.label} (${spec.core_role}) workspace`, () => {
    test.beforeEach(async ({}, testInfo) => {
      test.skip(
        !WORKSPACE_PROJECTS.includes(testInfo.project.name),
        `workspace click-path runs on ${WORKSPACE_PROJECTS.join(' and ')}`,
      )
    })

    test(`is one of the six the artifact names`, async () => {
      const row = artifactDoc.core_six.find((c) => c.service === serviceId)
      expect(row, `${serviceId} is missing from core_six`).toBeTruthy()
      expect(row?.role).toBe(spec.core_role)
    })

    test('renders its own view inside a workspace frame, on its own scene', async ({ page }) => {
      await recordEvents(page)
      await page.goto(urlFor(spec.route), { waitUntil: 'domcontentloaded' })

      const frame = frameOf(page, spec.id)
      await expect(frame).toBeVisible({ timeout: 45000 })

      // 1. The file's identity, in the DOM.
      await expect(frame).toHaveAttribute('data-ws-id', spec.id)
      await expect(frame).toHaveAttribute('data-ws-route', spec.route)
      await expect(frame).toHaveAttribute('data-ws-core', spec.core_role)
      await expect(frame).toHaveAttribute('data-ws-view', spec.views.default)
      await expect(frame).toHaveAttribute('data-ws-tool', spec.bojo_tool.id)
      await expect(frame).toHaveAttribute('data-ws-gate', 'dev_open')
      await expect(frame).toHaveAttribute('data-ws-gate-allowed', 'true')

      // 2. The room's OWN view, not a generic shell: its page anchor and its
      //    own heading.
      await expect(visiblePanel(page, spec.id).locator(spec.page_anchor).first())
        .toBeVisible({ timeout: 45000 })
      await expect(visiblePanel(page, spec.id).locator('h1.page-title').first())
        .toHaveText(spec.page_title)

      // 3. Every declared view is on the frame, and the default one is marked.
      for (const tab of spec.views.tabs) {
        await expect(frame.getByTestId(`ws-view-${tab.id}`)).toHaveCount(1)
      }
      await expect(frame.getByTestId(`ws-view-${spec.views.default}`))
        .toHaveAttribute('data-active', 'true')

      // 4. The scene: the bed paints the file's scene, exactly one bed exists,
      //    and the bed FIRED an event naming it.
      const bed = page.getByTestId('scene-bed')
      await expect(bed).toHaveCount(1)
      await expect(bed).toHaveAttribute('data-scene-id', spec.scene.id)
      await expect(bed).toHaveAttribute('data-scene-variant', spec.scene.variant)
      await expect(page.locator('[data-testid="scene-bed"] canvas, [data-testid="scene-bed"] img'))
        .toHaveCount(1)

      await expect.poll(async () => page.evaluate(() => {
        const w = window as unknown as { __sceneEvents: Array<{ sceneId?: string }> }
        return (w.__sceneEvents || []).map((e) => e.sceneId)
      }), { timeout: 20000 }).toContain(spec.scene.id)

      const sceneEvents = await page.evaluate(() => {
        const w = window as unknown as { __sceneEvents: Array<Record<string, unknown>> }
        return w.__sceneEvents || []
      })
      const event = sceneEvents.find((e) => e.sceneId === spec.scene.id) as Record<string, unknown>
      expect(event, 'no northstar:scene event carried the scene id').toBeTruthy()
      expect(event.variantId).toBe(spec.scene.variant)
      expect(event.serviceId).toBe(spec.id)

      // 5. The DevBanner: present once, and painted ABOVE the workspace.
      const banner = page.getByTestId('dev-banner')
      await expect(banner).toHaveCount(1)
      await expect(banner).toBeVisible()
      await expect(banner).toContainText('DEV: AUTH DISABLED')
      const bannerBox = await banner.boundingBox()
      const frameBox = await frame.boundingBox()
      expect(bannerBox && frameBox && bannerBox.y < frameBox.y,
        'the dev banner must sit above the workspace, not under it').toBe(true)

      // 6. Exactly one workspace frame in the shell.
      await expect(page.getByTestId('ws-frame')).toHaveCount(1)
    })

    test('the click path moves the declared view and hands the tab to Bojo', async ({ page }) => {
      await recordEvents(page)
      await page.goto(urlFor(spec.route), { waitUntil: 'domcontentloaded' })
      const frame = frameOf(page, spec.id)
      await expect(frame).toBeVisible({ timeout: 45000 })

      const published = async (): Promise<TabContext | null> => page.evaluate(() => {
        const w = window as unknown as { __northstarWorkspaceTab?: Record<string, unknown> }
        return (w.__northstarWorkspaceTab || null) as Record<string, unknown> | null
      })

      // The shell publishes what Bojo reads at send time: tab, workspace, tool.
      const first = await published()
      expect(first, 'the shell published no tab context').not.toBeNull()
      expect(first?.tabId).toBe(spec.id)
      expect(first?.workspace).toBe(spec.id)
      expect(first?.tool).toBe(spec.bojo_tool.id)
      expect(first?.view).toBe(spec.views.default)

      if (!hasClick) {
        // One view: the visit IS the click path, and the frame must say so
        // rather than offering a control that changes nothing.
        await expect(frame.locator('[data-view]')).toHaveCount(1)
        return
      }

      // The ROOM owns the click (its own tab strip / section picker); the frame
      // only declares the list. A room that renames a view without updating the
      // file fails here.
      await visiblePanel(page, spec.id)
        .getByRole('button', { name: target!.label, exact: true })
        .first()
        .click()

      await expect(frame).toHaveAttribute('data-ws-view', spec.click_path_view, { timeout: 20000 })
      await expect(frame.getByTestId(`ws-view-${spec.click_path_view}`))
        .toHaveAttribute('data-active', 'true')
      if (spec.views.param) {
        await expect(page).toHaveURL(
          new RegExp(`[?&]${spec.views.param}=${spec.click_path_view}(&|$)`))
      }

      await expect.poll(async () => (await published())?.view, { timeout: 20000 })
        .toBe(spec.click_path_view)

      const moved = await published()
      expect(moved?.tabId).toBe(spec.id)
      expect(moved?.serviceId).toBe(spec.id)
      expect(moved?.workspace).toBe(spec.id)
      expect(moved?.tool).toBe(spec.bojo_tool.id)
      expect(moved?.path).toBe(spec.route)

      // The same object went out on the event channel, which is how a listener
      // (rather than a poller) learns about the switch.
      const tabEvents = await page.evaluate(() => {
        const w = window as unknown as { __tabEvents: Array<Record<string, unknown>> }
        return w.__tabEvents || []
      })
      const carried = tabEvents.map((e) => e.view)
      expect(carried).toContain(spec.views.default)
      expect(carried).toContain(spec.click_path_view)
      const lastEvent = tabEvents[tabEvents.length - 1]
      expect(lastEvent.tool).toBe(spec.bojo_tool.id)
      expect(lastEvent.workspace).toBe(spec.id)
    })

    test('canUseService refuses the service when the plan does not entitle it', async ({ page }) => {
      // Dev-only switch: reaches the production branch of canUseService without
      // pretending dev is production, and makes no charge.
      await recordEvents(page)
      await page.goto(urlFor(spec.route, { billing: 'enforce' }), { waitUntil: 'domcontentloaded' })

      const frame = frameOf(page, spec.id)
      await expect(frame).toBeVisible({ timeout: 45000 })
      await expect(frame).toHaveAttribute('data-ws-gate', 'denied')
      await expect(frame).toHaveAttribute('data-ws-gate-allowed', 'false')

      const denied = frame.getByTestId('ws-gate-denied')
      await expect(denied).toBeVisible()
      await expect(denied).toContainText(spec.label)
      await expect(denied).toContainText('no studio credit')
      await expect(denied).toContainText(spec.gate.entitlement_key)
      await expect(frame.getByTestId('ws-gate-reason')).toHaveText('no studio credit')

      // The refusal REPLACES the page: a refused workspace must not present the
      // controls the plan cannot use.
      await expect(visiblePanel(page, spec.id).locator(spec.page_anchor)).toHaveCount(0)
      // The scene still paints: the refusal is about entitlement, not the venue.
      await expect(page.getByTestId('scene-bed')).toHaveAttribute('data-scene-id', spec.scene.id)
    })
  })
}
