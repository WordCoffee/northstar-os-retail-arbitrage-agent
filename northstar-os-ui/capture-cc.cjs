const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/home', '38-commandcenter-blueprint.png'],
    ['#/home?view=exceptions', '38b-commandcenter-exceptions.png'],
    ['#/home?view=activity', '38c-commandcenter-activity.png'],
    ['#/home?view=exposure', '38d-commandcenter-exposure.png'],
    ['#/home?view=handoffs', '38e-commandcenter-handoffs.png'],
  ]
  for (const [hash, file] of shots) {
    await page.goto(BASE + hash)
    await page.waitForTimeout(1200)
    await page.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
