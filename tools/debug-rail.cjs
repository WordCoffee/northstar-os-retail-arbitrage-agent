const { chromium } = require('playwright')
const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  await page.waitForTimeout(1500)

  const rail = await page.$('.suite-rail')
  console.log('--- .suite-rail outerHTML (first 1800 chars) ---')
  console.log(rail ? (await rail.evaluate((e) => e.outerHTML)).slice(0, 1800) : 'NO .suite-rail ELEMENT')
  console.log('')
  console.log('--- .suite-rail-signin present? ---', !!(await page.$('.suite-rail-signin')))
  console.log('--- .suite-rail-item count ---', (await page.$$('.suite-rail-item')).length)
  console.log('--- .suite-rail-group count ---', (await page.$$('.suite-rail-group')).length)
  console.log('--- role context text ---', await page.$eval('.suite-rail-context', (e) => e.textContent).catch(() => 'none'))
  await browser.close()
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
