const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/listings', '50-guardian-alerts.png'],
    ['#/listings?view=diffs', '50b-guardian-diffs.png'],
    ['#/listings?view=history', '50c-guardian-history.png'],
    ['#/listings?view=escalations', '50d-guardian-escalations.png'],
    ['#/keyword-tracker', '51-keyword-sets.png'],
    ['#/keyword-tracker?view=trends', '51b-keyword-trends.png'],
    ['#/keyword-tracker?view=coverage', '51c-keyword-coverage.png'],
    ['#/keyword-tracker?view=alerts', '51d-keyword-alerts.png'],
    ['#/monitoring', '52-monitoring-alerts.png'],
    ['#/monitoring?view=health', '52b-monitoring-health.png'],
    ['#/monitoring?view=sync', '52c-monitoring-sync.png'],
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
