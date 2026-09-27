const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/socialpulse', '48-socialpulse-calendar.png'],
    ['#/socialpulse?view=queue', '48b-socialpulse-queue.png'],
    ['#/socialpulse?view=composer', '48c-socialpulse-composer.png'],
    ['#/socialpulse?view=assets', '48d-socialpulse-assets.png'],
    ['#/socialpulse?view=presets', '48e-socialpulse-presets.png'],
    ['#/socialpulse?view=approvals', '48f-socialpulse-approvals.png'],
    ['#/socialpulse?view=analytics', '48g-socialpulse-analytics.png'],
    ['#/creative-studio', '49-creative-briefs.png'],
    ['#/creative-studio?view=variants', '49b-creative-variants.png'],
    ['#/creative-studio?view=assets', '49c-creative-assets.png'],
    ['#/creative-studio?view=exports', '49d-creative-exports.png'],
    ['#/creative-studio?view=library', '49e-creative-library.png'],
  ]
  for (const [hash, file] of shots) {
    await page.goto(BASE + hash)
    await page.waitForTimeout(900)
    await page.screenshot({ path: OUT + '/' + file, fullPage: true })
  }

  await browser.close()
  console.log('CAPTURE DONE')
}

main().catch(e => { console.error(e); process.exit(1) })
