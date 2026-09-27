const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/listingforge?view=editor', '29-listingforge-editor.png'],
    ['#/listingforge?view=templates', '29b-listingforge-templates.png'],
    ['#/adpilot?view=detail', '30-adpilot-detail.png'],
    ['#/adpilot?view=planner', '30b-adpilot-planner.png'],
  ]
  for (const [hash, file] of shots) {
    await page.goto(BASE + hash)
    await page.waitForTimeout(1200)
    await page.screenshot({ path: OUT + '/' + file })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })