const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // Command Center (signed-out / invitee view, matching review conditions)
  await page.goto(BASE + '#/home')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: OUT + '/25-command-center-truth-pills.png' })
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(400)
  await page.screenshot({ path: OUT + '/25b-command-center-below-fold.png' })

  // Golden Goose queue
  await page.goto(BASE + '#/golden-goose')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: OUT + '/26-golden-goose-truth-pills.png' })

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
