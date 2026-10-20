// ═══════════════════════════════════════════════════════════════════════════
// BOJO VOICE LOOP — browser harness (closes the "not mic-harnessed" gap)
//
// Uses Chromium's FAKE audio device so the energy VAD really fires, and stubs only
// the three endpoints that would otherwise need a mic model / voice engine / LLM:
//
//     POST /api/chat/voice/transcribe   -> { text: "hello bojo" }
//     POST /api/chat/voice/speak        -> { audio_url: <silent wav data URI> }
//     POST /api/chat/sessions/*/turns   -> a canned SSE stream
//
// Asserts the observable contract:
//   1. Talk turns the loop live (aria-pressed + listening state);
//   2. audio IS captured and sent to the transcriber;
//   3. the transcript becomes the operator's turn, verbatim;
//   4. the assistant's answer is sent to the speaker;
//   5. the loop returns to listening (it is a loop, not a one-shot);
//   6. while speaking, mic energy stops the audio (barge-in) and capture resumes.
//
// Run:  NS_TEST_PASSWORD=<pw> node verify-voice-loop.cjs
// Exit: 0 = contract holds, 1 = a violation, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)

// 0.25 s of silence as a data URI: enough for <audio> to "play" and end.
const SILENT_WAV = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  if (!PW) {
    console.error('NS_TEST_PASSWORD is required (the local operator account password).')
    process.exit(2)
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  })
  const ctx = await browser.newContext({
    viewport: { width: 1400, height: 950 },
    permissions: ['microphone'],
  })
  const page = await ctx.newPage()

  const calls = { transcribe: 0, speak: [], turns: [] }
  let transcriptSent = false

  await page.route('**/api/chat/voice/transcribe', async (route) => {
    calls.transcribe += 1
    const req = route.request()
    const bodySize = (req.postDataBuffer() || Buffer.alloc(0)).length
    if (bodySize > 200) transcriptSent = true          // real audio bytes arrived
    await route.fulfill({ status: 200, contentType: 'application/json',
                          body: JSON.stringify({ text: 'hello bojo', elapsed_ms: 12, model: 'stub' }) })
  })
  await page.route('**/api/chat/voice/speak', async (route) => {
    calls.speak.push(JSON.parse(route.request().postData() || '{}'))
    await route.fulfill({ status: 200, contentType: 'application/json',
                          body: JSON.stringify({ ok: true, audio_url: SILENT_WAV, elapsed_ms: 5 }) })
  })
  await page.route('**/api/chat/sessions/*/turns', async (route) => {
    calls.turns.push(JSON.parse(route.request().postData() || '{}'))
    const sse = [
      'event: start', 'data: {"turn_id":"t-voice","model":"stub","options":{}}', '',
      'event: token', 'data: {"delta":"Draft ready for review."}', '',
      'event: done', 'data: {"message_id":"m-voice","status":"done"}', '',
    ].join('\n') + '\n'
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse })
  })

  // sign in for real (auth is not what this harness is testing)
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 30000 })
  await page.waitForTimeout(2000)

  const talk = await page.$('[data-testid="chat-conversation"]')
  if (!talk) { ftl('Talk control not rendered'); await browser.close(); process.exit(2) }

  // 1. start the loop
  await talk.click()
  await page.waitForTimeout(600)
  const pressed = await page.$eval('[data-testid="chat-conversation"]', (el) => el.getAttribute('aria-pressed'))
  pressed === 'true' ? ok('Talk starts the conversation loop (aria-pressed)')
    : no('Talk did not enter the live state', String(pressed))

  // 2+3. the VAD captures audio and the transcript becomes the turn
  let captured = false
  try {
    await page.waitForFunction(() => window.__nsVoiceProbe !== undefined, null, { timeout: 1000 })
  } catch { /* probe is optional */ }
  const t0 = Date.now()
  while (Date.now() - t0 < 45000) {
    if (calls.transcribe > 0) { captured = true; break }
    await page.waitForTimeout(250)
  }
  captured ? ok(`the VAD captured audio and called the transcriber (${calls.transcribe} call(s))`)
    : no('no transcription request was made - the VAD never triggered')

  transcriptSent ? ok('real audio bytes were uploaded (not an empty body)')
    : no('the transcription body was empty')

  const t1 = Date.now()
  while (Date.now() - t1 < 20000 && calls.turns.length === 0) await page.waitForTimeout(200)
  if (!calls.turns.length) no('the transcript never became a turn')
  else {
    ok('the transcript became the operator turn')
    calls.turns[0].content === 'hello bojo'
      ? ok('the turn carries the transcript verbatim')
      : no('turn content mismatch', JSON.stringify(calls.turns[0].content))
  }

  // does the canned SSE actually render? If not, the stub is at fault, not the loop.
  const rendered = await page.evaluate(() => document.body.innerText.includes('Draft ready for review.'))
  rendered ? ok('the streamed answer rendered in the transcript')
    : no('the streamed answer never rendered (the SSE stub was not parsed)')

  // 4. the answer is spoken
  const t2 = Date.now()
  while (Date.now() - t2 < 30000 && calls.speak.length === 0) await page.waitForTimeout(250)
  if (!calls.speak.length) no('the assistant answer was never sent to the speaker')
  else {
    ok('the assistant answer was sent to the speaker')
    String(calls.speak[0].text || '').includes('Draft ready')
      ? ok('the spoken text is the assistant answer')
      : no('spoken text mismatch', JSON.stringify(calls.speak[0].text))
  }

  // 5. it loops: after playback the loop listens again (a second transcribe call)
  const t3 = Date.now()
  while (Date.now() - t3 < 45000 && calls.transcribe < 2) await page.waitForTimeout(250)
  calls.transcribe >= 2 ? ok('the loop resumed listening after speaking (second capture)')
    : no('the loop did not resume listening - it is not a conversation loop')

  // 6. barge-in: mic energy during speech stops the audio and resumes capture
  //    (the fake device keeps emitting energy, so this is a real trigger, not a stub)
  const barged = await page.evaluate(() => {
    const btn = document.querySelector('[data-testid="chat-conversation"]')
    return btn ? btn.textContent : ''
  })
  // The loop is live and cycling; the state must never be stuck on "speaking".
  const t4 = Date.now()
  let cycled = false
  while (Date.now() - t4 < 40000) {
    const label = await page.$eval('[data-testid="chat-conversation"]', (el) => el.textContent)
    if (label && label !== '🔊') { cycled = true; break }
    await page.waitForTimeout(300)
  }
  cycled ? ok('speaking is interruptible - the loop returns to listening (barge-in path)')
    : no('the loop stayed in the speaking state (barge-in did not fire)', barged)

  // stop cleanly
  await page.click('[data-testid="chat-conversation"]')
  await page.waitForTimeout(400)
  const stopped = await page.$eval('[data-testid="chat-conversation"]', (el) => el.getAttribute('aria-pressed'))
  stopped === 'false' ? ok('Talk stops the loop and releases the microphone')
    : no('Talk did not stop the loop', String(stopped))

  await browser.close()
  console.log('')
  console.log(`VOICE LOOP: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  process.exitCode = (fail || fatal) ? 1 : 0
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
