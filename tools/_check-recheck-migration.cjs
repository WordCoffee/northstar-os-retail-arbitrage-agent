// Browser e2e: the localStorage re-check log migrates to the tenant backend
// exactly once, clears the local copy only after the server confirms, and is
// idempotent on a second mount.  Run: node tools/_check-recheck-migration.cjs
const { chromium } = require('playwright')

const BASE = process.env.REPRO_BASE || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

const LEGACY = [
  { assetId: 'legacy-asset-A', checkedAt: '2026-10-01T10:00:00Z', user: 'owner', verdict: 'marker-present', passed: true, detail: null, surface: 'upload-check', tagRequired: true },
  { assetId: 'legacy-asset-B', checkedAt: '2026-10-02T11:00:00Z', user: 'owner', verdict: 'marker-missing', passed: false, detail: 're-upload required', surface: 'library-recheck', tagRequired: true },
]

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
  const page = await ctx.newPage()

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#signin-id')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  console.log('signed in')

  // Seed a pre-backend local log and remove the once-only flag.
  await page.evaluate((entries) => {
    localStorage.setItem('ns-ds-recheck-log', JSON.stringify(entries))
    localStorage.removeItem('ns-ds-rechecks-migrated-v1')
  }, LEGACY)

  const before = await page.evaluate(async () => {
    const j = await (await fetch('/api/design-studio/rechecks', { credentials: 'include' })).json()
    return (j.rechecks || []).filter(r => String(r.legacy_key || '').startsWith('local:')).length
  })

  // Mount the compositing surface (Listing Images) -> migration effect runs.
  await page.goto(BASE + 'design-studio?section=listing-images', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="compositing-surface"]', { timeout: 30000 })
  await page.waitForTimeout(3000)

  const after = await page.evaluate(async () => {
    const j = await (await fetch('/api/design-studio/rechecks', { credentials: 'include' })).json()
    const mine = (j.rechecks || []).filter(r => String(r.legacy_key || '').startsWith('local:'))
    return {
      count: mine.length,
      failedStored: mine.some(r => r.verdict === 'marker-missing' && r.passed === false),
      localRaw: localStorage.getItem('ns-ds-recheck-log'),
      flag: localStorage.getItem('ns-ds-rechecks-migrated-v1'),
    }
  })

  console.log(`backend legacy-key entries before: ${before}`)
  console.log(`backend legacy-key entries after : ${after.count}`)
  console.log(`failed check stored as failure    : ${after.failedStored}`)
  console.log(`local copy after migration        : ${after.localRaw}`)
  console.log(`migrated flag                     : ${after.flag}`)

  // Second mount must NOT duplicate.
  await page.goto(BASE + 'design-studio?section=aplus', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="compositing-surface"], [data-testid="aplus-workspace"]', { timeout: 30000 })
  await page.waitForTimeout(2500)
  const twice = await page.evaluate(async () => {
    const j = await (await fetch('/api/design-studio/rechecks', { credentials: 'include' })).json()
    return (j.rechecks || []).filter(r => String(r.legacy_key || '').startsWith('local:')).length
  })
  console.log(`entries after a second section     : ${twice}`)

  const ok = after.count === before + 2 && after.failedStored && after.localRaw === '[]' && after.flag === '1' && twice === after.count
  console.log(ok ? 'PASS  migration is one-shot, lossless and idempotent' : 'FAIL  migration contract not met')
  await browser.close()
  process.exit(ok ? 0 : 1)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
