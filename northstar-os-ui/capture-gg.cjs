const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/golden-goose', '40-gg-blueprint-queue.png'],
    ['#/golden-goose/GG-001', '40b-gg-review.png'],
    ['#/golden-goose?view=decisions', '40c-gg-decisions.png'],
    ['#/golden-goose?view=history', '40d-gg-history.png'],
  ]
  for (const [hash, file] of shots) {
    await page.goto(BASE + hash)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
