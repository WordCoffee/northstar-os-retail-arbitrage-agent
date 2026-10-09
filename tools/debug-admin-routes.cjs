const { chromium } = require('playwright')
const BASE = 'http://127.0.0.1/ui/'

async function main() {
  const b = await chromium.launch({ headless: true })
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
  await p.goto(BASE + 'sign-in')
  await p.fill('#signin-id', 't2')
  await p.fill('#signin-pw', 'T2holdings')
  await p.click('form button[type="submit"]')
  await p.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })

  for (const r of ['beta-ops', 'admin']) {
    await p.goto(BASE + r)
    await p.waitForTimeout(2200)
    const path = await p.evaluate(() => location.pathname)
    const h = await p.$eval('h1, h2', (e) => e.textContent).catch(() => '(no heading)')
    console.log(r.padEnd(10), '->', path.padEnd(16), '|', h.slice(0, 55))
  }
  await b.close()
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
