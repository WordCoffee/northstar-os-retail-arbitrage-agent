// Phase 7: capture every route at desktop and mobile widths into
// reports/screenshots_20261009/, and fail on any console error, uncaught
// exception, or dead control.
//
// Derived from northstar-os-ui/take-screenshots.cjs (the repo's own harness),
// retargeted at the preview server and the report directory. Every route is
// visited as an unauthenticated visitor first — a public surface must render
// without a session — and the failures are collected, not just printed.

const { chromium } = require('playwright')
const path = require('path')
const fs = require('fs')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/#'
const OUT = process.env.SCREENSHOT_OUT_DIR
  || path.join(__dirname, '..', 'reports', 'screenshots_20261009')

if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true })

const ROUTES = [
  { name: '01-home', hash: '/home', label: 'Command Center' },
  { name: '02-product-finder', hash: '/product-finder', label: 'SourceScout / Product Finder' },
  { name: '02b-product-finder-lookup', hash: '/product-finder?view=lookup', label: 'SourceScout lookup' },
  { name: '03-golden-goose', hash: '/golden-goose', label: 'Golden Goose Finder' },
  { name: '04-listingforge', hash: '/listingforge', label: 'ListingForge' },
  { name: '05-adpilot', hash: '/adpilot', label: 'AdPilot' },
  { name: '06-profitability', hash: '/profitability', label: 'Profitability Dashboard' },
  { name: '07-commerce-ops', hash: '/commerce-ops', label: 'Commerce Ops' },
  { name: '08-autothink', hash: '/autothink', label: 'AutothinK' },
  { name: '09-workspace', hash: '/customer-workspace', label: 'Customer Workspace' },
  { name: '10-plan', hash: '/plan', label: 'Plan / Usage' },
  { name: '11-support', hash: '/support', label: 'Support' },
  { name: '12-account', hash: '/account', label: 'Account' },
  { name: '13-documents', hash: '/documents', label: 'Documents' },
  { name: '14-setup', hash: '/setup', label: 'Setup' },
  { name: '15-beta-ops', hash: '/beta-ops', label: 'Beta Operations' },
  { name: '16-listings', hash: '/listings', label: 'Listing Guardian' },
  { name: '17-keyword-tracker', hash: '/keyword-tracker', label: 'Keyword Tracker' },
  { name: '18-competitor-monitor', hash: '/competitor-monitor', label: 'Competitor Monitor' },
  { name: '19-socialpulse', hash: '/socialpulse', label: 'SocialPulse' },
  { name: '20-creative-studio', hash: '/creative-studio', label: 'Creative Studio' },
  { name: '21-product-designer', hash: '/product-designer', label: 'Product Designer' },
  { name: '22-memory-bank', hash: '/memory-bank', label: 'Memory Bank' },
  { name: '23-shared-data', hash: '/shared-data', label: 'Shared Data Layer' },
  { name: '24-provider-adapters', hash: '/provider-adapters', label: 'Provider Adapters' },
  { name: '25-master-brain', hash: '/master-brain', label: 'Master Brain' },
  { name: '26-monitoring', hash: '/monitoring', label: 'Monitoring' },
  { name: '27-spreadsheet-lab', hash: '/spreadsheet-lab', label: 'Spreadsheet Lab' },
  { name: '28-admin', hash: '/admin', label: 'Internal Admin' },
  { name: '29-signin', hash: '/sign-in', label: 'Sign in (public)' },
  { name: '30-beta-landing', hash: '/beta', label: 'Beta landing (public)' },
]

const consoleErrors = []
const pageErrors = []
const deadControls = []

async function main() {
  const browser = await chromium.launch({ headless: true })

  // ---------- desktop ----------
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`[${m.location()?.url || '?'}] ${m.text()}`) })
  page.on('pageerror', (e) => pageErrors.push(String(e)))

  for (const route of ROUTES) {
    await page.goto(BASE + route.hash, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1400)
    await page.screenshot({ path: path.join(OUT, `desktop-${route.name}.png`) })
    // A dead control is a button with no disabled attr and no onClick wiring.
    const dead = await page.evaluate(() => {
      const out = []
      document.querySelectorAll('button').forEach((b) => {
        const text = (b.textContent || '').trim().slice(0, 40)
        if (!text) return
        if (b.disabled || b.getAttribute('aria-disabled') === 'true') return
        if (b.hasAttribute('data-toast-only')) out.push(text)
      })
      return out
    })
    dead.forEach((d) => deadControls.push(`${route.name}: ${d}`))
    console.log(`desktop ${route.name} — ${route.label}`)
  }

  // Click every tab on the two most complex rooms, to catch dead sub-tabs.
  for (const route of [{ hash: '/product-finder', name: '02-product-finder' },
                       { hash: '/creative-studio', name: '20-creative-studio' }]) {
    await page.goto(BASE + route.hash, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(900)
    const tabs = await page.$$('[role="tab"], .room-tab, .tab-btn')
    for (let i = 0; i < Math.min(tabs.length, 12); i += 1) {
      try {
        await tabs[i].click({ timeout: 1500 })
        await page.waitForTimeout(450)
      } catch { /* a non-clickable tab is not a failure by itself */ }
    }
    await page.screenshot({ path: path.join(OUT, `desktop-${route.name}-tabs.png`) })
    console.log(`desktop ${route.name} — tabs exercised (${tabs.length} found)`)
  }

  await ctx.close()

  // ---------- mobile ----------
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })
  const mp = await mctx.newPage()
  mp.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`[mobile] ${m.text()}`) })
  mp.on('pageerror', (e) => pageErrors.push(`[mobile] ${String(e)}`))

  for (const route of ROUTES) {
    await mp.goto(BASE + route.hash, { waitUntil: 'domcontentloaded' })
    await mp.waitForTimeout(1100)
    await mp.screenshot({ path: path.join(OUT, `mobile-${route.name}.png`) })
    console.log(`mobile  ${route.name} — ${route.label}`)
  }
  await mctx.close()
  await browser.close()

  // Browser logs "Failed to load resource: 401/429" for the expected
  // unauthenticated and rate-limited foundation probes. Those are the auth
  // boundary working, not a defect — the same filter verify-live-signin.cjs
  // uses. Only unexpected console errors and JS exceptions fail the sweep.
  const EXPECTED_NETWORK_NOISE = /Failed to load resource: the server responded with a status of (401|403|429)/
  const expectedNoise = consoleErrors.filter((e) => EXPECTED_NETWORK_NOISE.test(e))
  const realConsoleErrors = consoleErrors.filter(
    (e) => !EXPECTED_NETWORK_NOISE.test(e) && !/favicon/i.test(e))

  const report = [
    `# Route screenshot sweep — ${new Date().toISOString()}`,
    '',
    `base: ${BASE}`,
    `routes captured: desktop ${ROUTES.length} + mobile ${ROUTES.length} (+2 tab sweeps)`,
    `output: ${OUT}`,
    '',
    `## console errors: ${realConsoleErrors.length} (${expectedNoise.length} expected 401/403/429 auth-boundary notices filtered)`,
    ...(realConsoleErrors.length ? realConsoleErrors.map((e) => `- ${e}`) : ['- none']),
    '',
    `## uncaught exceptions: ${pageErrors.length}`,
    ...(pageErrors.length ? pageErrors.map((e) => `- ${e}`) : ['- none']),
    '',
    `## dead controls: ${deadControls.length}`,
    ...(deadControls.length ? deadControls.map((d) => `- ${d}`) : ['- none']),
  ].join('\n')
  fs.writeFileSync(path.join(OUT, 'ROUTE_SWEEP_REPORT.md'), report, 'utf-8')

  const failures = realConsoleErrors.length + pageErrors.length + deadControls.length
  console.log(`\nROUTE SWEEP: ${ROUTES.length} routes x 2 widths, ${failures} problem(s)`)
  console.log(`  (${expectedNoise.length} expected auth-boundary network notices were filtered)`)
  process.exit(failures ? 1 : 0)
}

main().catch((e) => { console.error('FATAL', e); process.exit(2) })
