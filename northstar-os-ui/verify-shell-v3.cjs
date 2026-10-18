// V3 shell harness — the Simple view is the main surface; Advanced is gated.
//
// Scenario A (Whetstone-like, advanced_view denied):
//   /home renders the Master Brain shell, focus chips exist, no rail, no
//   Advanced button, and ?shell=advanced still degrades to Simple.
// Scenario B (AutothinK-like, advanced_view granted):
//   the Advanced button switches to the room shell (suite rail), and the
//   mode toggle returns to Simple.
// Scenario C (mobile): the mode toggle is reachable below 900px.
//
// Run against a dev server:  set HARNESS_BASE_URL=http://127.0.0.1:8101/ui/
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

async function stub(page, { advanced, card = false }) {
  await page.addInitScript(({ advanced, card }) => {
    localStorage.setItem('ns-dev-session', JSON.stringify({
      userId: 'u-v3', orgId: 'org-v3', role: 'operator', env: 'production', previewId: '',
    }))
    localStorage.removeItem('ns-access-token')
    localStorage.removeItem('ns-shell-mode')
    window.__NORTHSTAR_LOCAL_DEV__ = true
    const FOUND = '/api/v1/foundation'
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url
      const json = (body, status = 200) => Promise.resolve(new Response(
        JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
      if (String(url).includes('/api/shell/context')) {
        return json({
          contract: 'shell/v1',
          default_mode: 'simple',
          capabilities: { advanced_view: advanced, autothink_workspace: advanced },
          focuses: [
            { id: 'auto', label: 'Auto', blurb: 'Route by intent', tools: null, suggestions: ['What should I focus on today?'] },
            { id: 'create', label: 'Create', blurb: 'Packaging + photo', tools: [], suggestions: [] },
            { id: 'grow', label: 'Grow', blurb: 'Listings + ads', tools: [], suggestions: [] },
            { id: 'research', label: 'Research', blurb: 'Sourcing', tools: [], suggestions: [] },
            { id: 'operate', label: 'Operate', blurb: 'Inventory', tools: [], suggestions: [] },
            { id: 'autothink', label: 'AutothinK', blurb: 'Workspace', tools: null, requires: 'autothink_workspace', locked: !advanced, suggestions: [] },
          ],
          identity: { source: 'stub', role: 'operator', plan: advanced ? 'autothink' : 'foundation', plan_name: advanced ? 'AutothinK' : 'Whetstone' },
        })
      }
      if (String(url).includes('/api/shell/hardware')) {
        return json({ sampled_at: '2026-10-18T00:00:00Z', gpu: { ok: false, gpus: [], reason: 'stub' }, ram: { ok: true, total_mb: 16384, used_mb: 8192, percent: 50 } })
      }
      if (String(url).includes('/api/chat/health')) return json({ ok: true, model: 'stub-model', tools: [], max_tool_steps: 4 })
      // In-flight turn (Scenario D): emit a start frame and hold the stream open.
      if (String(url).includes('/turns') && init && init.method === 'POST') {
        const enc = new TextEncoder()
        const stream = new ReadableStream({
          start(ctrl) { ctrl.enqueue(enc.encode('event: start\ndata: {"turn_id":"t1","model":"stub"}\n\n')) },
        })
        return Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
      }
      if (String(url).includes('/api/chat/sessions/s-card/messages')) {
        return json({
          session: { id: 's-card', focus_json: { mode: 'auto', label: 'Auto' } },
          messages: [{
            id: 'm1', role: 'assistant', content: 'Here are your voices.', model: 'stub',
            parts_json: [{
              type: 'card', title: 'Voice profiles', ok: true,
              rows: [{ label: 'Creator', value: 'v1' }],
              action: { label: 'Clone a voice', message: 'Clone a creator voice.' },
            }],
          }],
        })
      }
      if (String(url).includes('/api/chat/sessions')) return json({ sessions: card ? [{ id: 's-card', title: 'Voice test', focus_json: { mode: 'auto', label: 'Auto' } }] : [] })
      if (!url.includes(FOUND)) return json({ detail: { code: 'not_stubbed' } }, 404)
      const route = url.split(FOUND)[1].split('?')[0]
      if (route === '/ui-mode') return json({ ui_mode: 'full' })
      if (route === '/me') return json({ user_id: 'u-v3', organizations: [], active_organization_id: null, role: 'operator', permissions: [] })
      if (route === '/environment') return json({ environment: 'production', view_context: 'normal', ui_mode: 'full', is_preview: false })
      if (route === '/preview/active') return json({ active: false, preview: null })
      return json({ detail: { code: 'not_stubbed' } }, 404)
    }
  }, { advanced, card })
}

async function main() {
  const browser = await chromium.launch({ headless: true })

  // ── Scenario A: advanced denied (Whetstone-like) ──────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()
    await stub(page, { advanced: false })
    await page.goto(BASE + 'home')
    try {
      await page.waitForSelector('[data-testid="mb-shell"]', { timeout: 8000 })
      ok('A: Master Brain shell is the /home surface (Simple is the main view)')
    } catch { no('A: mb-shell not rendered', page.url()) }
    const railAbsent = !(await page.$('.suite-rail'))
    railAbsent ? ok('A: room rail hidden in Simple mode') : no('A: suite rail still visible')
    const focusChips = await page.$$('[data-testid^="mb-focus-"]')
    focusChips.length === 6 ? ok('A: 6 focus chips (auto/create/grow/research/operate/autothink)')
      : no('A: wrong focus chip count', focusChips.length)

    // Focus switch works and persists to localStorage
    await page.click('[data-testid="mb-focus-create"]')
    const activeId = await page.$eval('[data-testid="mb-focus-create"]', (el) => el.getAttribute('aria-selected'))
    activeId === 'true' ? ok('A: switching focus selects the Create chip') : no('A: focus chip not active', String(activeId))
    const stored = await page.evaluate(() => localStorage.getItem('ns-focus'))
    stored === 'create' ? ok('A: focus persisted (ns-focus=create)') : no('A: focus not persisted', String(stored))

    const advBtn = await page.$('[data-testid="mb-to-advanced"]')
    !advBtn ? ok('A: no Advanced button without the entitlement') : no('A: Advanced button shown without entitlement')

    await page.goto(BASE + 'home?shell=advanced')
    await page.waitForTimeout(800)
    const stillSimple = await page.$('[data-testid="mb-shell"]')
    const railNow = await page.$('.suite-rail')
    stillSimple && !railNow ? ok('A: ?shell=advanced degrades to Simple without the entitlement')
      : no('A: deep-linked advanced leaked', 'mb-shell=' + !!stillSimple + ' rail=' + !!railNow)
    await ctx.close()
  }

  // ── Scenario B: advanced granted (AutothinK-like) ─────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()
    await stub(page, { advanced: true })
    await page.goto(BASE + 'home')
    await page.waitForSelector('[data-testid="mb-to-advanced"]', { timeout: 8000 }).catch(() => {})
    const advBtn = await page.$('[data-testid="mb-to-advanced"]')
    if (advBtn) {
      ok('B: Advanced button present with the entitlement')
      await advBtn.click()
      await page.waitForSelector('.suite-rail', { timeout: 6000 }).catch(() => {})
      const rail = await page.$('.suite-rail')
      const shellGone = !(await page.$('[data-testid="mb-shell"]'))
      rail && shellGone ? ok('B: Advanced view renders the room shell (suite rail)')
        : no('B: advanced switch failed', 'rail=' + !!rail + ' shellGone=' + shellGone)
      const mode = await page.evaluate(() => localStorage.getItem('ns-shell-mode'))
      mode === 'advanced' ? ok('B: mode persisted as advanced') : no('B: mode not persisted', String(mode))
      // Back to Simple via the top-nav segmented toggle
      await page.click('[data-testid="ns-shell-mode"]')
      await page.waitForSelector('[data-testid="mb-shell"]', { timeout: 6000 }).catch(() => {})
      const back = await page.$('[data-testid="mb-shell"]')
      back ? ok('B: toggle returns to the Simple shell') : no('B: could not return to Simple')
      const toggleText = await page.$eval('[data-testid="ns-shell-mode"]', (el) => el.innerText)
      toggleText.includes('Advanced') ? ok('B: toggle offers Advanced for this tier') : no('B: toggle hides Advanced', toggleText)
    } else {
      no('B: Advanced button missing with entitlement')
    }
    await ctx.close()
  }

  // ── Scenario C: mobile reachability of the mode switch ────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 780 } })
    const page = await ctx.newPage()
    await stub(page, { advanced: true })
    await page.goto(BASE + 'home')
    await page.waitForSelector('[data-testid="mb-shell"]', { timeout: 8000 }).catch(() => {})
    const visible = await page.$eval('[data-testid="ns-shell-mode"]', (el) => {
      const s = getComputedStyle(el)
      return s.display !== 'none' && s.visibility !== 'hidden'
    }).catch(() => false)
    visible ? ok('C: mode toggle reachable at 390px') : no('C: mode toggle hidden on mobile')
    const chips = await page.$$('[data-testid^="mb-focus-"]')
    chips.length > 0 ? ok('C: focus chips render on mobile') : no('C: no focus chips on mobile')
    await ctx.close()
  }

  // ── Scenario D: AG-UI cards + human-in-the-loop handover ──────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()
    await stub(page, { advanced: false, card: true })
    await page.goto(BASE + 'home')
    await page.waitForSelector('[data-testid="mb-shell"]', { timeout: 8000 }).catch(() => {})

    const cards = await page.waitForSelector('[data-testid="chat-cards"]', { timeout: 8000 }).catch(() => null)
    cards ? ok('D: AG-UI card part renders as a component (not plain text)') : no('D: card part did not render')
    const title = cards ? await page.$eval('[data-testid="chat-cards"] .chat-card-title', (el) => el.innerText).catch(() => '') : ''
    title.includes('Voice profiles') ? ok('D: card title + rows rendered') : no('D: wrong card title', title)
    const action = await page.$('[data-testid="chat-card-action"]')
    action ? ok('D: card carries an interactive action control') : no('D: card action missing')

    // Trigger a turn via the card action, then take over (pause) mid-stream.
    if (action) {
      await action.click()
      const pause = await page.waitForSelector('[data-testid="chat-pause"]', { timeout: 8000 }).catch(() => null)
      pause ? ok('D: Pause control appears while the agent streams') : no('D: Pause control missing during a turn')
      if (pause) {
        await pause.click()
        const paused = await page.waitForSelector('[data-testid="chat-paused"]', { timeout: 5000 }).catch(() => null)
        paused ? ok('D: human handover — agent paused, operator is driving') : no('D: paused banner did not appear')
        const resume = await page.$('[data-testid="chat-resume"]')
        resume ? ok('D: Resume control offered to hand control back') : no('D: resume control missing')
      }
    }
    await ctx.close()
  }

  await browser.close()
  console.log(`\n${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}

main().catch((e) => { console.error(e); process.exit(1) })
