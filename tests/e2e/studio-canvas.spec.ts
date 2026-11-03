// U7 — the Design Studio canvas workspace. Localhost only (Playwright Test is
// the sanctioned path for tests/e2e against 127.0.0.1).
//
// The pass criterion from the work order: create a design, add text and an
// image, undo, export, reload and see it restored — on desktop and on the
// iPhone/WebKit profile. Everything below is driven through the interface; no
// engine API is called directly, because the last bug in this room hid behind
// endpoints that were fine while the surface was broken.

import { test, expect, type Page } from '@playwright/test'
import { statSync } from 'node:fs'

const WORKBENCH = '/ui/workbench'
const STORE_KEY = 'ns-ds-canvas'

// A real 1×1 PNG. The canvas decodes whatever it is given; the point of the
// test is the click path, not the pixel content.
const PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
const PNG_BUFFER = Buffer.from(PNG_B64, 'base64')

// Rendering a whole studio inside a tab is heavier than a static page.
test.describe.configure({ timeout: 120000 })

const isPhone = () => test.info().project.name.includes('mobile')

test.beforeEach(async ({ page }) => {
  // Clear once, through a real navigation. An addInitScript would run again on
  // the reload this test depends on and erase the very autosave it asserts.
  await page.goto('/ui/home')
  await page.evaluate((key) => {
    try { localStorage.removeItem(key) } catch { /* storage unavailable */ }
    try { window.sessionStorage.removeItem('ns-ux-tabs') } catch { /* ignore */ }
  }, STORE_KEY)
})

// The control must be the topmost element at its own centre, or the fixed scene
// layer is eating the tap (U3's lesson, reused here).
async function expectTopmost(page: Page, testId: string) {
  const el = page.getByTestId(testId)
  await expect(el).toBeVisible({ timeout: 30000 })
  await el.scrollIntoViewIfNeeded()
  const box = await el.boundingBox()
  expect(box, `${testId} has no bounding box`).not.toBeNull()
  const hit = await page.evaluate(({ x, y, id }) => {
    const node = document.elementFromPoint(x, y)
    if (!node) return 'none'
    if (node.closest(`[data-testid="${id}"]`)) return 'self'
    const cls = typeof node.className === 'string' ? node.className : ''
    return `${node.tagName.toLowerCase()}.${cls}`.replace(/\.$/, '')
  }, { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2, id: testId })
  expect(hit, `${testId} is covered by ${hit}`).toBe('self')
}

// Phones hide the inspector behind the layers button.
async function openPanel(page: Page) {
  const toggle = page.getByTestId('cw-panel-toggle')
  if (await toggle.isVisible()) {
    const expanded = await toggle.getAttribute('aria-expanded')
    if (expanded !== 'true') await toggle.click()
  }
  await expect(page.getByTestId('cw-panel')).toBeVisible()
}

async function openStudio(page: Page) {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('canvas-workspace')).toBeVisible({ timeout: 30000 })
}

test('create a design, add text and an image, undo, export, reload, restored', async ({ page }) => {
  await openStudio(page)

  // ── the canvas exists and is empty apart from its background ────────────
  await openPanel(page)
  await expect(page.getByTestId('cw-doc-size')).toContainText('1080x1080')
  await page.getByTestId('cw-panel-layers').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(1)

  // ── add text and type into it ───────────────────────────────────────────
  await expectTopmost(page, 'cw-add-text')
  await page.getByTestId('cw-add-text').click()
  await expect(page.getByTestId('cw-text-input')).toBeVisible()
  await page.getByTestId('cw-text-input').fill('Hello Northstar')
  await expect(page.getByTestId('cw-text-input')).toHaveValue('Hello Northstar')

  // ── add an image through the real file input ────────────────────────────
  await expectTopmost(page, 'rail-image')
  await page.getByTestId('rail-image').click()
  await page.getByTestId('cw-image-input').setInputFiles({
    name: 'plate.png',
    mimeType: 'image/png',
    buffer: PNG_BUFFER,
  })
  await expect(page.getByTestId('cw-asset').first()).toBeVisible({ timeout: 15000 })

  await openPanel(page)
  await page.getByTestId('cw-panel-layers').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(3)
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'Hello Northstar' })).toHaveCount(1)

  // ── undo removes the image, not the text ────────────────────────────────
  await expectTopmost(page, 'cw-undo')
  await page.getByTestId('cw-undo').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(2)
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'Hello Northstar' })).toHaveCount(1)

  // ── export a real PNG ───────────────────────────────────────────────────
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 20000 }).catch(() => null),
    page.getByTestId('cw-export-png').click(),
  ])
  if (download) {
    const file = await download.path()
    expect(file, 'the export produced no file').toBeTruthy()
    const size = statSync(file!).size
    expect(size, 'the exported PNG is empty').toBeGreaterThan(100)
    expect(download.suggestedFilename()).toMatch(/\.png$/)
  } else {
    // Some headless engines do not surface a blob download. The surface still
    // reports the REAL byte count it produced, so assert that instead.
    await expect(page.getByTestId('cw-export-status')).toContainText('PNG')
    const attr = await page.getByTestId('canvas-workspace').getAttribute('data-last-export')
    const bytes = Number(String(attr).split(' ')[1])
    expect(bytes).toBeGreaterThan(100)
  }

  // ── the autosave really holds the post-undo document ────────────────────
  await page.waitForFunction((key) => {
    const raw = localStorage.getItem(key)
    if (!raw) return false
    try {
      const rec = JSON.parse(raw)
      return Array.isArray(rec?.doc?.layers) && rec.doc.layers.length === 2
    } catch { return false }
  }, STORE_KEY, { timeout: 15000 })

  // ── reload and see it restored ──────────────────────────────────────────
  await page.reload()
  await expect(page.getByTestId('canvas-workspace')).toBeVisible({ timeout: 30000 })
  await openPanel(page)
  await page.getByTestId('cw-panel-layers').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(2)
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'Hello Northstar' })).toHaveCount(1)
  // The undone image did not come back: undo is part of what was saved.
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'plate.png' })).toHaveCount(0)
  await expect(page.getByTestId('cw-save-state')).toContainText('Restored')
})

test('the canvas zone is flat and opaque, never the scene behind it', async ({ page }) => {
  await openStudio(page)
  const zone = page.getByTestId('cw-canvas-zone')
  await expect(zone).toBeVisible()
  await zone.scrollIntoViewIfNeeded()

  const facts = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="cw-canvas-zone"]') as HTMLElement
    const style = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    // Probe the middle of the part that is actually on screen: the outlet
    // scrolls, and elementFromPoint cannot see below the viewport.
    const left = Math.max(0, r.left)
    const right = Math.min(window.innerWidth, r.right)
    const top = Math.max(0, r.top)
    const bottom = Math.min(window.innerHeight, r.bottom)
    const x = left + (right - left) / 2
    const y = top + (bottom - top) / 2
    const hit = document.elementFromPoint(x, y)
    return {
      background: style.backgroundColor,
      backdrop: style.backdropFilter || (style as any).webkitBackdropFilter || 'none',
      canvases: el.querySelectorAll('canvas').length,
      probe: { x, y, inside: !!(hit && hit.closest('[data-testid="cw-canvas-zone"]')) },
      topInsideZone: !!(hit && hit.closest('[data-testid="cw-canvas-zone"]')),
    }
  })

  // --wb-solid is #161d27 for every theme in the U4 snapshot.
  expect(facts.background).toBe('rgb(22, 29, 39)')
  expect(facts.backdrop).toBe('none')
  // Exactly one canvas: the artboard. A second one would be the scene.
  expect(facts.canvases).toBe(1)
  expect(facts.topInsideZone).toBe(true)
})

test('switching the content type resizes the canvas and keeps the layers', async ({ page }) => {
  await openStudio(page)
  await page.getByTestId('cw-add-text').click()

  await expectTopmost(page, 'cw-type-product')
  await page.getByTestId('cw-type-product').click()

  await openPanel(page)
  await page.getByTestId('cw-panel-properties').click()
  await expect(page.getByTestId('cw-doc-size')).toContainText('2000x2000')
  await page.getByTestId('cw-panel-layers').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(2)

  // The social type is a portrait canvas, not a scaled square.
  await page.getByTestId('cw-type-social').click()
  await page.getByTestId('cw-panel-properties').click()
  await expect(page.getByTestId('cw-doc-size')).toContainText('1440x1800')
})

test('the library tool wires to the sections that already own the work', async ({ page }) => {
  await openStudio(page)
  await expectTopmost(page, 'rail-library')
  await page.getByTestId('rail-library').click()
  await expectTopmost(page, 'cw-open-dashboard')
  await page.getByTestId('cw-open-dashboard').click()
  await expect(page.getByTestId('asset-dashboard')).toBeVisible({ timeout: 30000 })
  // Embedded in a tab, the section is component state: the shell must not have
  // navigated to /design-studio.
  expect(page.url()).toContain('/ui/workbench')
})

test('the phone layout does not overflow', async ({ page }) => {
  if (!isPhone()) test.skip()
  await openStudio(page)
  await openPanel(page)
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

// U8 — the canvas instruction layer. The sentence goes through the SAME entry
// point the workbench registers for a chat turn (useWorkspace.runCanvasCommand);
// the model is not in this loop, so this test proves the edit path, not a live
// model turn. What it asserts is the part that must not drift: the document
// changes, the change is readable back from the DOM, and an unknown sentence
// changes nothing.
test('a canvas instruction edits the open document, read back from the DOM', async ({ page }) => {
  await openStudio(page)
  await page.getByTestId('cw-add-text').click()
  await openPanel(page)
  await page.getByTestId('cw-panel-properties').click()
  await expect(page.getByTestId('cw-text-size')).toContainText('9.0%')

  // Bojo can see the canvas: the shell publishes the open document.
  await expect(page.getByTestId('workbench-shell')).toHaveAttribute('data-canvas-layers', '2')

  const result = await page.evaluate(() => window.__northstarCanvas.instruct('make the headline bigger'))
  expect(result.ok).toBe(true)
  expect(result.summary).toMatch(/bigger/)

  // The DOM is the proof: the panel reads the real size back.
  await expect(page.getByTestId('cw-text-size')).toContainText('10.8%')

  // A sentence that is not a canvas instruction changes nothing.
  const refused = await page.evaluate(() => window.__northstarCanvas.instruct('what is my ROI on this ASIN?'))
  expect(refused.ok).toBe(false)
  await expect(page.getByTestId('cw-text-size')).toContainText('10.8%')

  // And the edit is a normal document change: undo takes it back.
  await expectTopmost(page, 'cw-undo')
  await page.getByTestId('cw-undo').click()
  await expect(page.getByTestId('cw-text-size')).toContainText('9.0%')
})
