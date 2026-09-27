const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8104/ui/'
const OUT = 'screenshots'

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const shots = [
    ['#/profitability', '35-profitability-blueprint.png'],
    ['#/profitability?view=scenarios', '35b-profitability-scenarios.png'],
    ['#/profitability?view=fee', '35c-profitability-fee.png'],
    ['#/profitability?view=inventory', '35d-profitability-inventory.png'],
    ['#/profitability?view=export', '35e-profitability-export.png'],
    ['#/commerce-ops', '36-commerceops-blueprint.png'],
    ['#/commerce-ops?view=tasks', '36b-commerceops-tasks.png'],
    ['#/commerce-ops?view=approvals', '36c-commerceops-approvals.png'],
    ['#/commerce-ops?view=blockers', '36d-commerceops-blockers.png'],
    ['#/commerce-ops?view=history', '36e-commerceops-history.png'],
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
