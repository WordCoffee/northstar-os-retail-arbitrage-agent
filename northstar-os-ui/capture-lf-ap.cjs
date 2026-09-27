const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  await page.goto(BASE + '#/listingforge')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: OUT + '/27-listingforge.png' })
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(400)
  await page.screenshot({ path: OUT + '/27b-listingforge-below-fold.png' })

  await page.goto(BASE + '#/adpilot')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: OUT + '/28-adpilot.png' })
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(400)
  await page.screenshot({ path: OUT + '/28b-adpilot-below-fold.png' })

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })