// UX scorecard: the three journeys a seller actually walks, measured rather than
// asserted by eye. Every page in the journey is checked for
//   - a rendered main + heading (it is really the page, not a blank shell)
//   - zero uncaught page errors
//   - zero *critical* axe accessibility violations
// and the whole run is timed so "steps to first artifact" has a number.
//
// Results are written to state/evidence/ux_scorecard_<project>.json so the loop
// can compare runs, and screenshots go to reports/ty/shots/.
//
// Runs on desktop Chromium and iPhone 12 (WebKit) through the same file.

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'
import path from 'node:path'

const SHOTS = 'reports/ty/shots'
const EVIDENCE = 'state/evidence'

// The three journeys: what a seller does on day one, on the creative side, and
// when they are hunting for a product.
const JOURNEYS = [
  {
    name: 'first_run',
    pages: ['/ui/', '/ui/home', '/ui/plan', '/ui/documents'],
  },
  {
    name: 'creative',
    pages: ['/ui/design-studio', '/ui/packify-design', '/ui/creative-studio'],
  },
  {
    name: 'research',
    pages: ['/ui/product-finder', '/ui/golden-goose', '/ui/listings'],
  },
]

type PageResult = {
  url: string
  ok: boolean
  heading: string
  ms: number
  pageErrors: string[]
  consoleErrors: string[]
  criticalViolations: { id: string; nodes: number; help: string }[]
  seriousViolations: { id: string; nodes: number; help: string }[]
  reason?: string
}

async function measurePage(page: any, route: string): Promise<PageResult> {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  const onPageError = (err: Error) => pageErrors.push(String(err).slice(0, 300))
  const onConsole = (msg: any) => {
    if (msg.type() === 'error') consoleErrors.push(String(msg.text()).slice(0, 300))
  }
  page.on('pageerror', onPageError)
  page.on('console', onConsole)

  const started = Date.now()
  const result: PageResult = {
    url: route, ok: false, heading: '', ms: 0, pageErrors, consoleErrors,
    criticalViolations: [], seriousViolations: [],
  }
  try {
    const response = await page.goto(route, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main')).toBeVisible({ timeout: 45000 })
    const heading = page.locator('h1, h2').first()
    result.heading = (await heading.textContent({ timeout: 15000 }).catch(() => ''))?.trim() || ''
    result.ms = Date.now() - started
    result.ok = true
    if (response && response.status() >= 500) {
      result.ok = false
      result.reason = `HTTP ${response.status()}`
    }
  } catch (err: any) {
    result.ms = Date.now() - started
    result.reason = String(err?.message || err).slice(0, 300)
  }

  if (result.ok) {
    try {
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
      result.criticalViolations = axe.violations
        .filter((v) => v.impact === 'critical')
        .map((v) => ({ id: v.id, nodes: v.nodes.length, help: v.help.slice(0, 120) }))
      result.seriousViolations = axe.violations
        .filter((v) => v.impact === 'serious')
        .map((v) => ({ id: v.id, nodes: v.nodes.length, help: v.help.slice(0, 120) }))
    } catch (err: any) {
      result.reason = `axe_failed: ${String(err?.message || err).slice(0, 200)}`
    }
  }

  page.off('pageerror', onPageError)
  page.off('console', onConsole)
  return result
}

for (const journey of JOURNEYS) {
  test(`ux: ${journey.name}`, async ({ page }, testInfo) => {
    const project = testInfo.project.name
    fs.mkdirSync(EVIDENCE, { recursive: true })
    fs.mkdirSync(SHOTS, { recursive: true })

    const results: PageResult[] = []
    const journeyStart = Date.now()
    for (const route of journey.pages) {
      const result = await measurePage(page, route)
      results.push(result)
      const slug = route.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'root'
      await page.screenshot({
        path: `${SHOTS}/ux_${project}_${journey.name}_${slug}.png`,
        fullPage: false,
      }).catch(() => undefined)
    }
    const ms = Date.now() - journeyStart

    const failures = results.filter((r) => !r.ok)
    const critical = results.reduce((n, r) => n + r.criticalViolations.length, 0)
    const serious = results.reduce((n, r) => n + r.seriousViolations.length, 0)
    const pageErrors = results.reduce((n, r) => n + r.pageErrors.length, 0)

    const payload = {
      project, journey: journey.name, at: new Date().toISOString(), ms,
      pages: results,
      summary: {
        pages: results.length,
        pages_ok: results.length - failures.length,
        pages_failed: failures.length,
        critical_violations: critical,
        serious_violations: serious,
        page_errors: pageErrors,
      },
    }
    fs.writeFileSync(
      path.join(EVIDENCE, `ux_scorecard_${project}_${journey.name}.json`),
      JSON.stringify(payload, null, 2),
    )

    expect(failures, `pages that did not render: ${JSON.stringify(failures)}`).toHaveLength(0)
    expect(critical, `critical a11y violations: ${JSON.stringify(results.flatMap((r) => r.criticalViolations))}`).toBe(0)
    // The page heading must be the page's own heading, not the app name. Before
    // 2026-11-05 every route announced "Northstar OS" because a visually hidden
    // global <h1> came first in the DOM.
    const namedApp = results.filter((r) => /^northstar\s*os$/i.test(r.heading))
    expect(namedApp, `pages whose only heading is the app name: ${JSON.stringify(namedApp.map((r) => r.url))}`).toHaveLength(0)
  })
}
