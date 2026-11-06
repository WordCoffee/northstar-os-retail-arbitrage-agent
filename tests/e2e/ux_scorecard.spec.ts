// UX scorecard: journeys + service coverage + tab state + scene readability.
//
// Dimensions (all numeric, all written to state/evidence/ux_scorecard_*.json):
//   coverage      how many of the fixed service routes actually render
//   tab_state     the workbench tab bar exists and survives switching tabs
//   readability   contrast of panel text against its own panel, plus whether the
//                 panel is translucent (the thing that couples text to the scene)
//   a11y          critical axe violations per page
//   errors        uncaught page errors / console errors
//   dev_notice    the dev-environment notice is visible on EVERY route
//
// Runs on desktop Chromium and iPhone 12 WebKit. Never asserts on the presence
// of a feature that does not exist: an unavailable dimension is recorded as such.

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'
import path from 'node:path'

const SHOTS = 'reports/ty/shots'
const EVIDENCE = 'state/evidence'
const DEV_NOTICE = /DEV: AUTH DISABLED/i

const JOURNEYS = [
  { name: 'first_run', pages: ['/ui/', '/ui/home', '/ui/plan', '/ui/documents'] },
  { name: 'creative', pages: ['/ui/design-studio', '/ui/packify-design', '/ui/creative-studio'] },
  { name: 'research', pages: ['/ui/product-finder', '/ui/golden-goose', '/ui/listings'] },
]

// The services a seller can actually open. Coverage is measured against this
// fixed list, not against "whatever links happen to exist today".
const SERVICES = [
  '/ui/design-studio',
  '/ui/packify-design',
  '/ui/listingforge',
  '/ui/adpilot',
  '/ui/product-finder',
  '/ui/golden-goose',
  '/ui/keyword-tracker',
  '/ui/competitor-monitor',
  '/ui/monitoring',
  '/ui/workbench',
]

type Violation = {
  id: string; nodes: number; help: string; targets?: string[]; evidence?: string[]
}

type PageResult = {
  url: string
  ok: boolean
  heading: string
  ms: number
  devNotice: boolean
  pageErrors: string[]
  consoleErrors: string[]
  criticalViolations: Violation[]
  seriousViolations: Violation[]
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
    url: route, ok: false, heading: '', ms: 0, devNotice: false,
    pageErrors, consoleErrors, criticalViolations: [], seriousViolations: [],
  }
  try {
    const response = await page.goto(route, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main')).toBeVisible({ timeout: 45000 })
    // Let the 300 ms entry fade finish before measuring. `.fade-in` animates
    // opacity, and measuring a heading mid-fade reported #cccbc1 on paper
    // (1.43:1) for a heading that is actually near-black — a false positive.
    // A fixed wait, not getAnimations(): the celestial scene animates forever,
    // so waiting for "no running animations" never resolves.
    await page.waitForTimeout(450)
    result.devNotice = await page.getByText(DEV_NOTICE).first()
      .isVisible().catch(() => false)
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
      const shape = (v: any) => ({
        id: v.id,
        nodes: v.nodes.length,
        help: v.help.slice(0, 120),
        // The selector is what makes a violation fixable without guessing, and
        // the summary carries the measured fg/bg/ratio for a contrast failure.
        targets: v.nodes.slice(0, 3).map((n: any) => String(n.target?.[0] || '').slice(0, 120)),
        evidence: v.nodes.slice(0, 2).map((n: any) => String(n.failureSummary || '').slice(0, 200)),
      })
      result.criticalViolations = axe.violations.filter((v) => v.impact === 'critical').map(shape)
      result.seriousViolations = axe.violations.filter((v) => v.impact === 'serious').map(shape)
    } catch (err: any) {
      result.reason = `axe_failed: ${String(err?.message || err).slice(0, 200)}`
    }
  }

  page.off('pageerror', onPageError)
  page.off('console', onConsole)
  return result
}

function relLum(rgb: number[]): number {
  const [r, g, b] = rgb.map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(fg: number[], bg: number[]): number {
  const a = relLum(fg)
  const b = relLum(bg)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
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
    const noNotice = results.filter((r) => r.ok && !r.devNotice)

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
        dev_notice_missing: noNotice.length,
      },
    }
    fs.writeFileSync(
      path.join(EVIDENCE, `ux_scorecard_${project}_${journey.name}.json`),
      JSON.stringify(payload, null, 2),
    )

    expect(failures, `pages that did not render: ${JSON.stringify(failures)}`).toHaveLength(0)
    expect(critical, `critical a11y violations: ${JSON.stringify(results.flatMap((r) => r.criticalViolations))}`).toBe(0)
    // The page heading must be the page's own heading, not the app name.
    const namedApp = results.filter((r) => /^northstar\s*os$/i.test(r.heading))
    expect(namedApp, `pages whose only heading is the app name: ${JSON.stringify(namedApp.map((r) => r.url))}`).toHaveLength(0)
    // The dev notice is a standing rule: it must be on every route of every journey.
    expect(noNotice, `routes without the dev notice: ${JSON.stringify(noNotice.map((r) => r.url))}`).toHaveLength(0)
  })
}

test('ux: service coverage', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  const rows: any[] = []
  for (const route of SERVICES) {
    const r = await measurePage(page, route)
    rows.push({ route, ok: r.ok, ms: r.ms, heading: r.heading,
                devNotice: r.devNotice, reason: r.reason ?? null,
                pageErrors: r.pageErrors.length, consoleErrors: r.consoleErrors.length,
                consoleSamples: r.consoleErrors.slice(0, 3) })
  }
  const ok = rows.filter((r) => r.ok).length
  const coverage = rows.length ? (ok / rows.length) * 100 : 0
  const withNotice = rows.filter((r) => r.devNotice).length
  const payload = {
    project, dimension: 'service_coverage', at: new Date().toISOString(),
    services: rows.length, rendered: ok, coverage_pct: Math.round(coverage * 10) / 10,
    dev_notice_pct: Math.round((withNotice / Math.max(1, rows.length)) * 1000) / 10,
    rows,
  }
  fs.writeFileSync(path.join(EVIDENCE, `ux_coverage_${project}.json`), JSON.stringify(payload, null, 2))
  expect(rows.filter((r) => !r.ok), JSON.stringify(rows.filter((r) => !r.ok))).toHaveLength(0)
  expect(withNotice, `routes without the dev notice: ${JSON.stringify(rows.filter((r) => !r.devNotice))}`).toBe(rows.length)
})

test('ux: tab state', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  // Explicit expectation, not a silent skip: the workbench tab bar is a queued
  // unit, and this constant is the switch that turns the canary on when it ships.
  const TABS_EXPECTED = false
  const out: any = { project, dimension: 'tab_state', at: new Date().toISOString(),
                     tabs_expected: TABS_EXPECTED }
  await page.goto('/ui/workbench')
  const bar = page.getByTestId('wb-tabbar')
  const present = await bar.isVisible({ timeout: 30000 }).catch(() => false)
  out.tabbar_present = present
  if (present) {
    const tabs = page.getByTestId('wb-tabs').locator('button')
    out.tabs_before = await tabs.count()
    if (out.tabs_before >= 1) {
      await tabs.nth(0).click()
      await page.waitForTimeout(300)
    }
    if (out.tabs_before >= 2) {
      await tabs.nth(1).click()
      await page.waitForTimeout(300)
      await tabs.nth(0).click()
      await page.waitForTimeout(300)
    }
    out.tabs_after = await tabs.count()
    out.still_present = await bar.isVisible().catch(() => false)
    out.url = page.url()
    out.passed = out.still_present && out.tabs_after === out.tabs_before
  } else {
    out.passed = false
    out.note = 'wb-tabbar not found on /ui/workbench'
  }
  fs.writeFileSync(path.join(EVIDENCE, `ux_tabs_${project}.json`), JSON.stringify(out, null, 2))
  // The gate is "the measured state matches the declared expectation", so a
  // missing tab bar fails the day someone flips TABS_EXPECTED to true.
  expect(out.tabbar_present, JSON.stringify(out)).toBe(TABS_EXPECTED)
})

test('ux: scene readability', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  await page.goto('/ui/home')
  await page.locator('main').waitFor({ state: 'visible', timeout: 45000 })
  // The empty state mounts after the session list resolves; measuring before
  // that made this test flaky in a full run (h3 absent at 600 ms).
  await page.locator('.chat-empty h3').first()
    .waitFor({ state: 'visible', timeout: 20000 }).catch(() => undefined)
  await page.waitForTimeout(600)

  const measured = await page.evaluate(() => {
    const parse = (value: string): { rgb: number[]; alpha: number } | null => {
      const m = value.match(/rgba?\(([^)]+)\)/)
      if (!m) return null
      const parts = m[1].split(',').map((v) => parseFloat(v.trim()))
      return { rgb: parts.slice(0, 3), alpha: parts.length > 3 ? parts[3] : 1 }
    }
    const effectiveBg = (el: Element): { rgb: number[]; alpha: number } => {
      // Collect the alpha layers nearest-first, then composite them back down
      // onto the first opaque ancestor. Returning a raw rgba() was wrong: a 5%
      // white card over a dark scene read as near-white and reported a 1.45:1
      // contrast for text that actually sits on near-black.
      const layers: { rgb: number[]; alpha: number }[] = []
      let node: Element | null = el
      let base: number[] | null = null
      while (node) {
        const cs = getComputedStyle(node)
        const bg = parse(cs.backgroundColor)
        if (bg && bg.alpha > 0.001) {
          layers.push(bg)
          if (bg.alpha >= 0.999) { base = bg.rgb; break }
        }
        node = node.parentElement
      }
      if (!base) base = [12, 16, 20]   // the scene behind everything
      let out = base.slice()
      for (let i = layers.length - 1; i >= 0; i -= 1) {
        const layer = layers[i]
        if (layer.alpha >= 0.999) { out = layer.rgb.slice(); continue }
        out = out.map((c, idx) => layer.alpha * layer.rgb[idx] + (1 - layer.alpha) * c)
      }
      const alpha = layers.length ? Math.max(...layers.map((l) => l.alpha)) : 1
      return { rgb: out.map((c) => Math.round(c)), alpha }
    }
    const samples: any[] = []
    const nodes = Array.from(document.querySelectorAll('.chat-bubble, .chat-empty p, .chat-empty h3, .chat-suggestion, .mb-chip')).slice(0, 24)
    for (const el of nodes) {
      const cs = getComputedStyle(el)
      const fg = parse(cs.color)
      if (!fg) continue
      const bg = effectiveBg(el)
      const rect = el.getBoundingClientRect()
      if (rect.width < 8 || rect.height < 8) continue
      samples.push({
        cls: String(el.className).slice(0, 40),
        fg: fg.rgb,
        bg: bg.rgb,
        bg_alpha: bg.alpha,
        // Translucency is what couples text to the moving scene behind it.
        translucent: bg.alpha < 0.999,
        fontSize: parseFloat(cs.fontSize),
      })
    }
    return samples
  })

  const scored = measured.map((s: any) => ({
    ...s,
    contrast: Math.round(contrast(s.fg, s.bg) * 100) / 100,
  }))
  const worst = scored.reduce((min: any, s: any) => (s.contrast < (min?.contrast ?? 99) ? s : min), null as any)
  const translucent = scored.filter((s: any) => s.translucent).length
  const failing = scored.filter((s: any) => s.contrast < 4.5)
  const payload = {
    project, dimension: 'scene_readability', at: new Date().toISOString(),
    sampled: scored.length,
    translucent_panels: translucent,
    worst,
    below_aa: failing.length,
    rows: scored,
  }
  fs.writeFileSync(path.join(EVIDENCE, `ux_readability_${project}.json`), JSON.stringify(payload, null, 2))
  // The gate: no sampled text may fall below AA on its own panel.
  expect(failing, `text below 4.5:1: ${JSON.stringify(failing.slice(0, 4))}`).toHaveLength(0)

  // Layout integrity, measured on the same page: the empty state must fit the
  // stream (it was cut off by 28px) and no status chip may be clipped by its
  // own row (the last theme name used to be sliced).
  const layout = await page.evaluate(() => {
    const stream = document.querySelector('[data-testid="chat-stream"]') as HTMLElement | null
    const h3 = document.querySelector('.chat-empty h3') as HTMLElement | null
    const chips = Array.from(document.querySelectorAll('.mb-status > *')) as HTMLElement[]
    const clipped = chips.filter((c) => {
      const r = c.getBoundingClientRect()
      const p = c.parentElement!.getBoundingClientRect()
      return r.right > p.right + 1 || r.left < p.left - 1
    }).map((c) => (c.textContent || '').trim().slice(0, 30))
    const sr = stream?.getBoundingClientRect()
    const hr = h3?.getBoundingClientRect()
    return {
      stream_height: stream?.clientHeight ?? null,
      stream_scroll_height: stream?.scrollHeight ?? null,
      stream_scroll_top: stream?.scrollTop ?? null,
      // The real defect was the greeting being scrolled out of view, not the
      // cards being taller than a phone screen (scrolling is fine there).
      greeting_visible: !!(sr && hr && hr.top >= sr.top - 1 && hr.bottom <= sr.bottom + 1),
      chips: chips.length,
      clipped,
    }
  })
  fs.writeFileSync(path.join(EVIDENCE, `ux_layout_${project}.json`), JSON.stringify(layout, null, 2))
  // Font loading: the serif must actually be available, not silently falling
  // back. WebKit refused the font stylesheet for months while nobody noticed.
  const fonts = await page.evaluate(async () => {
    const wanted = ['Libre Baskerville', 'DM Sans']
    const state: Record<string, boolean> = {}
    for (const family of wanted) {
      // `check()` reports false for a face that is declared but not yet fetched
      // (font-display: swap). `load()` requests it and waits, which is what
      // "the font is available" actually means. Measured flake 2026-11-06:
      // desktop said false and mobile true for the same build.
      try {
        await document.fonts.load(`16px "${family}"`)
      } catch { /* recorded below as false */ }
      state[family] = document.fonts.check(`16px "${family}"`)
    }
    await document.fonts.ready
    const h1 = document.querySelector('h1, h2')
    return { checked: state, headingFamily: h1 ? getComputedStyle(h1).fontFamily : null }
  })
  fs.writeFileSync(path.join(EVIDENCE, `ux_fonts_${project}.json`), JSON.stringify(fonts, null, 2))
  expect(fonts.checked['Libre Baskerville'], `serif not loaded: ${JSON.stringify(fonts)}`).toBe(true)
  expect(layout.clipped, `clipped status chips: ${JSON.stringify(layout.clipped)}`).toHaveLength(0)
  expect(layout.stream_scroll_top, 'the empty state must not be scrolled away on load').toBe(0)
  expect(layout.greeting_visible, 'the greeting heading must be inside the stream viewport').toBe(true)
  // A message area smaller than a couple of lines is not a message area.
  expect(layout.stream_height ?? 0, 'the chat stream must have usable height').toBeGreaterThanOrEqual(200)
})
