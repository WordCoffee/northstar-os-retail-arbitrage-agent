const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
let pass = 0
let fail = 0

function ok(ctx) { pass++; console.log('PASS  ' + ctx) }
function no(ctx, detail) { fail++; console.log('FAIL  ' + ctx + (detail ? ' :: ' + detail : '')) }

async function expectMarker(page, marker, ctx) {
  try {
    await page.waitForFunction(m => document.body.innerText.includes(m), marker, { timeout: 7000 })
    ok(ctx + ' [marker: "' + marker + '"]')
  } catch {
    no(ctx, 'marker "' + marker + '" not found, url=' + page.url() + ' hash=' + await page.evaluate(() => location.hash))
  }
}

async function expectHash(page, hash, ctx) {
  try {
    await page.waitForFunction(h => location.hash === h, hash, { timeout: 5000 })
    ok(ctx + ' [hash: ' + hash + ']')
  } catch {
    no(ctx, 'expected ' + hash + ' got ' + await page.evaluate(() => location.hash))
  }
}

async function expectToast(page, text, ctx) {
  try {
    await page.waitForSelector('.toast-item', { timeout: 5000 })
    await page.waitForFunction(t => Array.from(document.querySelectorAll('.toast-item')).some(e => e.textContent.includes(t)), text, { timeout: 4000 })
    ok(ctx + ' [toast]')
  } catch {
    no(ctx, 'toast not found')
  }
}

async function run() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })

  // ---- deep links ----
  const deepLinks = [
    ['#/profitability?view=scenario', 'Scenario Calculator', 'deep /profitability?view=scenario'],
    ['#/autothink?view=composer', 'Research Run Composer', 'deep /autothink?view=composer'],
    ['#/customer-workspace?view=services', 'Entitled Services', 'deep /customer-workspace?view=services'],
    ['#/keyword-tracker?view=terms', 'Tracked Terms by ASIN', 'deep /keyword-tracker?view=terms'],
    ['#/commerce-ops/CO-01', 'Sourcing Validation', 'deep /commerce-ops/CO-01'],
    ['#/product-finder/B08L5VJQ7T', 'Product Set — B08L5VJQ7T', 'deep /product-finder/B08L5VJQ7T'],
    ['#/golden-goose/GG-001', 'Water Filter Pro', 'deep /golden-goose/GG-001'],
    ['#/listings?view=rules', 'Guardian Rules', 'deep /listings?view=rules'],
  ]
  for (const [href, marker, ctx] of deepLinks) {
    await page.goto(BASE + href)
    await expectMarker(page, marker, ctx)
  }

  // ---- wired action: navigation ----
  async function navAction(href, clickTarget, expectedHash, ctx) {
    await page.goto(BASE + href)
    await page.waitForSelector('.app', { timeout: 8000 })
    await page.click(clickTarget, { timeout: 6000 })
    await expectHash(page, expectedHash, ctx)
  }

  await navAction('#/listings', 'button:has-text("New Rule")', '#/listings?view=rules', 'ListingGuardian New Rule')
  await navAction('#/listingforge', 'button:has-text("Create Listing")', '#/listingforge?view=editor', 'ListingForge Create Listing')
  await navAction('#/adpilot', 'button:has-text("Create Campaign")', '#/adpilot?view=planner', 'AdPilot Create Campaign')
  await navAction('#/autothink', 'button:has-text("New Research Run")', '#/autothink?view=composer', 'AutothinK New Research Run')
  await navAction('#/product-finder', 'button:has-text("Saved Sets")', '#/product-finder?view=saved', 'ProductFinder Saved Sets')
  await navAction('#/golden-goose', 'table button:has-text("Open") >> nth=0', '#/golden-goose/GG-001', 'GoldenGoose row Open')
  await navAction('#/golden-goose/GG-001', 'button:has-text("Open SourceScout")', '#/product-finder/B08L5VJQ7T', 'GoldenGoose Open SourceScout')
  await navAction('#/commerce-ops', 'table button:has-text("Open") >> nth=0', '#/commerce-ops/CO-01', 'CommerceOps row Open')

  // ---- wired action: toast ----
  await navAction('#/commerce-ops', 'button:has-text("New Workflow")', '#/commerce-ops', 'CommerceOps New Workflow (no nav)')
  await expectToast(page, 'New workflow requires a product set and operator owner', 'CommerceOps New Workflow toast')

  await page.goto(BASE + '#/profitability')
  await page.waitForSelector('.app', { timeout: 8000 })
  await page.click('button:has-text("Export Report")', { timeout: 6000 })
  await expectToast(page, 'Export prepared from observed data', 'Profitability Export Report toast')

  await browser.close()
  console.log(`\nSMOKE RESULTS: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

run().catch(e => { console.error('FATAL', e); process.exit(2) })