// ═══════════════════════════════════════════════════════════════════════════
// DEPLOY COMPOSE GUARD (Phase 6 item 2)
//
// Confirms the loopback API publish added for local harness runs
// (`127.0.0.1:8000:8000` in docker-compose.yml) is:
//   • present in the LOCAL composition (the Vite dev server proxies to it), and
//   • ABSENT from the DEPLOY composition (base + docker-compose.hosted.yml,
//     the hosted overlay used with deploy/hosted.env).
//
// If the docker CLI is unavailable the check reports NOT RUN with the cause and
// exits non-zero - a missing check is never a pass.
//
// Run:  node tools/check-compose-deploy.cjs
// Exit: 0 = both compositions correct, 1 = contract violated, 2 = NOT RUN.
// ═══════════════════════════════════════════════════════════════════════════

const { execFileSync } = require('child_process')
const path = require('path')

const ROOT = path.join(__dirname, '..')
let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

function composeConfig(files) {
  const args = ['compose']
  for (const f of files) args.push('-f', f)
  args.push('config', '--format', 'json')
  return JSON.parse(execFileSync('docker', args, {
    cwd: ROOT, encoding: 'utf8', timeout: 60000,
    stdio: ['ignore', 'pipe', 'ignore'],
  }))
}

function apiPublishedPorts(cfg) {
  const ports = (cfg.services && cfg.services.api && cfg.services.api.ports) || []
  return ports.map((p) => String(p.published || p.published_port || '').trim()).filter(Boolean)
}

try {
  execFileSync('docker', ['--version'], { encoding: 'utf8', timeout: 20000, stdio: ['ignore', 'pipe', 'ignore'] })
} catch {
  console.log('NOT RUN  docker CLI is unavailable - the compose contract was NOT checked.')
  console.log('         Cause: `docker --version` failed. Install/start Docker and re-run.')
  process.exit(2)
}

let local
let hosted
try {
  local = composeConfig(['docker-compose.yml'])
  hosted = composeConfig(['docker-compose.yml', 'docker-compose.hosted.yml'])
} catch (e) {
  console.log('NOT RUN  docker compose config failed: ' + String(e.message).slice(0, 160))
  process.exit(2)
}

const localPorts = apiPublishedPorts(local)
const hostedPorts = apiPublishedPorts(hosted)

// 1. Local composition: the loopback publish must exist so the Vite dev server
//    (and every browser harness) can reach the API.
if (localPorts.includes('8000')) {
  const entry = (local.services.api.ports || []).find((p) => String(p.published) === '8000')
  const hostIp = String(entry.host_ip || entry.host_ipv4 || '')
  if (hostIp === '127.0.0.1') ok('LOCAL composition publishes the API on 127.0.0.1:8000 (loopback only)')
  else no('LOCAL composition publishes 8000 on a non-loopback host IP', hostIp || '(all interfaces)')
} else {
  no('LOCAL composition does not publish 8000 - the Vite dev server proxy target is unreachable', `published: ${JSON.stringify(localPorts)}`)
}

// 2. Deploy composition (base + hosted): the API must NOT be published at all.
if (hostedPorts.includes('8000')) {
  no('DEPLOY composition still publishes the API on 8000 (must be reset in docker-compose.hosted.yml)', `published: ${JSON.stringify(hostedPorts)}`)
} else {
  ok('DEPLOY composition does NOT publish the API port (only Caddy is public)')
}

// 3. Positive control: the deploy composition must still publish Caddy, so an
//    empty/broken parse cannot pass vacuously.
const caddyPorts = ((hosted.services.caddy && hosted.services.caddy.ports) || [])
  .map((p) => String(p.published || ''))
if (caddyPorts.includes('80')) ok(`positive control: Caddy stays published in the deploy composition (${caddyPorts.join(',')})`)
else no('positive control failed: the deploy composition has no Caddy publish - the parse looks broken', JSON.stringify(caddyPorts))

// 4. The harness rate-limit opt-out must not survive into a deploy build
//    (Phase 7 item 3). The hosted overlay pins it to "0"; the API also refuses
//    to boot with it set in staging/production.
function envDict(svc) {
  const env = (svc && svc.environment) || {}
  if (Array.isArray(env)) {
    const m = {}
    for (const e of env) {
      const s = String(e)
      const i = s.indexOf('=')
      if (i > 0) m[s.slice(0, i)] = s.slice(i + 1)
    }
    return m
  }
  return env
}
const hostedEnv = envDict(hosted.services.api)
const localEnv = envDict(local.services.api)
if (hostedEnv.NORTHSTAR_DISABLE_RATE_LIMIT === '0') {
  ok('DEPLOY composition pins NORTHSTAR_DISABLE_RATE_LIMIT=0 (the opt-out cannot ship)')
} else {
  no('DEPLOY composition does not pin the rate-limit opt-out', `value=${JSON.stringify(hostedEnv.NORTHSTAR_DISABLE_RATE_LIMIT)}`)
}
if (localEnv.NORTHSTAR_DISABLE_RATE_LIMIT === '1') {
  no('LOCAL composition forces the rate-limit opt-out ON - a normal start must keep the limiter enabled')
} else {
  ok(`LOCAL composition does not force the opt-out (value=${JSON.stringify(localEnv.NORTHSTAR_DISABLE_RATE_LIMIT ?? 'unset -> compose default 0')})`)
}

// 5. No service in the deploy composition may publish ANY port besides the
//    proxy's 80/443 (hosted-readiness package, item 12). A single stray
//    `ports:` entry would expose Postgres, the API or a worker directly.
const ALLOWED_HOSTED_PUBLISH = new Set(['80', '443'])
const stray = []
for (const [name, svc] of Object.entries(hosted.services || {})) {
  for (const p of (svc.ports || [])) {
    const published = String(p.published || p.published_port || '').trim()
    if (!ALLOWED_HOSTED_PUBLISH.has(published)) stray.push(`${name}:${published}`)
  }
}
if (stray.length === 0) {
  ok('DEPLOY composition publishes NO port besides the proxy (80/443) across all services')
} else {
  no('DEPLOY composition publishes a non-proxy port', stray.join(', '))
}

// 6. Harness opt-outs must not survive into a deploy build. Any environment
//    switch whose name marks it as a test bypass must be 0/unset in the
//    hosted API environment; a "1" fails the guard.
const OPT_OUT_PATTERN = /(BYPASS|TEST_MODE|DISABLE_RATE_LIMIT|OWNER_SELF_APPROVAL)/
const optOuts = Object.entries(hostedEnv).filter(([k, v]) => OPT_OUT_PATTERN.test(k) && String(v) === '1')
if (optOuts.length === 0) {
  ok('DEPLOY composition carries no harness opt-out set to 1 (bypass / test-mode / rate-limit / self-approval)')
} else {
  no('DEPLOY composition sets a harness opt-out to 1', optOuts.map(([k]) => k).join(', '))
}
const localOptOuts = Object.entries(localEnv).filter(([k, v]) => OPT_OUT_PATTERN.test(k) && String(v) === '1')
if (localOptOuts.length === 0) {
  ok('LOCAL composition also carries no opt-out set to 1 (the limiter and throttles stay on by default)')
} else {
  no('LOCAL composition sets an opt-out to 1 - normal starts must keep them off', localOptOuts.map(([k]) => k).join(', '))
}

console.log(`\nDEPLOY COMPOSE GUARD: ${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
