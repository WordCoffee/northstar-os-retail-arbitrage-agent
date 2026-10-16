// tools/_design_shots.mjs — LOCAL-ONLY design-review screenshotter.
// Talks raw CDP (Chrome DevTools Protocol) to a dedicated headless Chrome on
// 127.0.0.1. It never drives Playwright, never navigates to any non-localhost
// host, and never types credentials into the browser: the session cookie is
// minted via the local API and injected through CDP. Stdlib only (node >= 22).
//
// Usage (from repo root):
//   $env:NS_EMAIL="northstarosllc@gmail.com"; $env:NS_PW="<password>"
//   node tools/_design_shots.mjs
//
// Writes PNGs to reports/ui_review_20261016/shots/.

import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'

const BASE = 'http://127.0.0.1:8000'
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const PORT = 9223
const OUT = path.join(process.cwd(), 'reports', 'ui_review_20261016', 'shots')

const ROUTES = [
  ['00-signin', '/ui/sign-in', 3000],
  ['01-home', '/ui/home', 4500],
  ['02-listingforge', '/ui/listingforge', 4500],
  ['03-design-studio', '/ui/design-studio', 5000],
  ['04-generate', '/ui/design-studio?section=projects&view=generate', 5000],
  ['05-video', '/ui/design-studio?section=projects&view=video', 5000],
  ['06-adpilot', '/ui/adpilot', 4500],
  ['07-socialpulse', '/ui/socialpulse', 4500],
  ['08-autothink', '/ui/autothink', 8000],
  ['09-product-finder', '/ui/product-finder', 4500],
  ['10-golden-goose', '/ui/golden-goose', 4500],
  ['11-listings', '/ui/listings', 4500],
  ['12-profitability', '/ui/profitability', 4500],
  ['13-keyword-tracker', '/ui/keyword-tracker', 4500],
  ['14-master-brain', '/ui/master-brain', 4500],
]

// Only shoot names listed in NS_ONLY (comma-separated), when set.
const only = (process.env.NS_ONLY || '').split(',').map(s => s.trim()).filter(Boolean)
const WANTED = only.length ? ROUTES.filter(r => only.includes(r[0])) : ROUTES

const SIGN_IN_MARKER = 'Enter your credentials to access NorthstarOS.'

async function login() {
  const email = process.env.NS_EMAIL
  const pw = process.env.NS_PW
  if (!email || !pw) throw new Error('NS_EMAIL / NS_PW env vars required')
  const res = await fetch(BASE + '/api/v1/foundation/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: pw }),
  })
  if (!res.ok) throw new Error('login failed: HTTP ' + res.status)
  const raw = res.headers.getSetCookie ? res.headers.getSetCookie() : []
  const cookies = []
  for (const line of raw) {
    const m = line.match(/^([^=]+)=([^;]+)/)
    if (m) cookies.push({ name: m[1], value: m[2] })
  }
  console.log('login ok; cookies:', cookies.map(c => c.name).join(', '))
  return cookies
}

async function wsTarget() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const list = await r.json()
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl)
      if (page) return page.webSocketDebuggerUrl
    } catch { /* not up yet */ }
    await sleep(500)
  }
  throw new Error('chrome debug target never appeared')
}

class CDP {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    ws.addEventListener('message', (ev) => {
      let m
      try { m = JSON.parse(ev.data) } catch { return }
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id)
        this.pending.delete(m.id)
        m.error ? reject(new Error(m.error.message)) : resolve(m.result)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }
}

async function main() {
  mkdirSync(OUT, { recursive: true })
  const cookies = await login()

  const profile = path.join(process.env.TEMP || '.', 'ns-shots-profile')
  const chrome = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check',
    '--disable-gpu', '--hide-scrollbars',
    '--force-device-scale-factor=1',
    '--window-size=1600,1000',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    const wsUrl = await wsTarget()
    const ws = new WebSocket(wsUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res)
      ws.addEventListener('error', rej)
    })
    const cdp = new CDP(ws)
    await cdp.send('Page.enable')
    await cdp.send('Network.enable')
    for (const c of cookies) {
      await cdp.send('Network.setCookie', {
        name: c.name, value: c.value,
        domain: '127.0.0.1', path: '/',
        httpOnly: c.name === 'ns_session',
      })
    }
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false,
    })

    for (const [name, route, settle] of WANTED) {
      await cdp.send('Page.navigate', { url: BASE + route })
      await sleep(settle)
      // Session-refresh race: a deep link can render the sign-in guard before
      // /api/v1/foundation/me resolves. Detect and retry once.
      for (let attempt = 0; attempt < 2; attempt++) {
        const probe = await cdp.send('Runtime.evaluate', {
          expression: `document.body && document.body.innerText.includes(${JSON.stringify(SIGN_IN_MARKER)})`,
          returnByValue: true,
        })
        if (!probe.result.value) break
        console.log(`  ${name}: sign-in flash detected, retrying...`)
        await sleep(3500)
        await cdp.send('Page.navigate', { url: BASE + route })
        await sleep(settle)
      }
      const shot = await cdp.send('Page.captureScreenshot', { format: 'png' })
      writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(shot.data, 'base64'))
      console.log('shot:', name)
      await sleep(1500)
    }
    try { await cdp.send('Browser.close') } catch { /* fine */ }
  } finally {
    try { chrome.kill() } catch { /* fine */ }
  }
  console.log('done ->', OUT)
}

main().catch((e) => { console.error('FAILED:', e.message); process.exitCode = 1 })
