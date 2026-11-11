// block3-workspaces — the DEFAULT SCENE fallback, for everything that is not one
// of the core six.
//
// The claim being tested is narrow on purpose: a route with no workspace spec
// renders NO workspace frame and paints the DEFAULT SCENE from the file
// (`default_scene`), not a scene of its own. Services that DO carry their own
// scene entry in `scenes/sceneRegistry.js` (profitability, socialpulse, …) keep
// it — the fallback is what an undescribed room gets, which is every catalogue
// room, /admin, /home and the customer rooms.
//
// LOCALHOST ONLY (127.0.0.1:8101), headless, per AGENTS.md.

import { test, expect, type Page } from '@playwright/test'
import { WORKSPACE_PROJECTS, artifact, urlFor } from './_runner'

const defaultScene = artifact().default_scene

async function recordSceneEvents(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __sceneEvents: Array<Record<string, unknown>> }
    w.__sceneEvents = []
    document.addEventListener('northstar:scene', (event) => {
      w.__sceneEvents.push((event as CustomEvent).detail as Record<string, unknown>)
    })
  })
}

test.describe('the default scene fallback', () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !WORKSPACE_PROJECTS.includes(testInfo.project.name),
      `workspace click-path runs on ${WORKSPACE_PROJECTS.join(' and ')}`,
    )
  })

  test('the artifact names a default scene the scene registry ships', async () => {
    expect(defaultScene.service).toBe('home')
    expect(defaultScene.variant).toBe('orion-nursery')
    expect(defaultScene.label).toBe('Deep Field')
    const fallback = artifact().default_workspace
    expect(fallback.id).toBe('default')
    expect(fallback.scene.id).toBe('home')
  })

  test('a catalogue room paints the default scene and gets no workspace frame', async ({ page }) => {
    await recordSceneEvents(page)
    await page.goto(urlFor('/hub'), { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('shell-chrome')).toBeVisible({ timeout: 45000 })

    // No frame: the file describes six workspaces, and /hub is not one of them.
    await expect(page.getByTestId('ws-frame')).toHaveCount(0)

    const bed = page.getByTestId('scene-bed')
    await expect(bed).toHaveCount(1)
    await expect(bed).toHaveAttribute('data-scene-id', defaultScene.service)
    await expect(bed).toHaveAttribute('data-scene-variant', defaultScene.variant)

    await expect.poll(async () => page.evaluate(() => {
      const w = window as unknown as { __sceneEvents: Array<{ sceneId?: string }> }
      return (w.__sceneEvents || []).map((e) => e.sceneId)
    }), { timeout: 20000 }).toContain(defaultScene.service)
  })

  test('a second undescribed room takes the same fallback', async ({ page }) => {
    await recordSceneEvents(page)
    await page.goto(urlFor('/keywords'), { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('shell-chrome')).toBeVisible({ timeout: 45000 })
    await expect(page.getByTestId('ws-frame')).toHaveCount(0)
    await expect(page.getByTestId('scene-bed')).toHaveAttribute('data-scene-id', defaultScene.service)
  })

  test('a described workspace is never served the default scene by accident', async ({ page }) => {
    // The negative of the fallback: one of the six must NOT paint the home field.
    await recordSceneEvents(page)
    await page.goto(urlFor('/listings'), { waitUntil: 'domcontentloaded' })
    const bed = page.getByTestId('scene-bed')
    await expect(bed).toHaveCount(1, { timeout: 45000 })
    await expect(bed).not.toHaveAttribute('data-scene-id', defaultScene.service)
    await expect(page.getByTestId('ws-frame')).toHaveCount(1)
  })
})
