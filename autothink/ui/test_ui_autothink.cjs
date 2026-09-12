/* ==========================================================================
   NORTHSTAR OS — AUTOTHINK WORKSPACE UI CONTRACT
   VM + DOM-stub harness for autothink/ui/index.html (service-plans/05).
   Asserts the Northstar OS brand pass on the workspace page itself:
     - steel/gold tokens on #050505 space (old neon gradient removed)
     - four quick-ask service buttons that prefill the composer
       ("Ask <Service>: ... (demo prefill)" — same verbs as the shell)
     - local-brain readiness lamp rendering 'offline' (no probe performed)
       or flipping to 'detected' only on the local backend's own boot
       health check — the lamp render path itself NEVER calls fetch
     - master-brain/ docs pointer present
   No jsdom, no network: fetch is stubbed per scenario and counted.
   ========================================================================== */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const UI = path.join(__dirname, 'index.html');
const html = fs.readFileSync(UI, 'utf8');

let pass = 0;
let fail = 0;
function assert(cond, msg) {
  if (cond) { pass++; console.log('PASS: ' + msg); }
  else { fail++; console.log('FAIL: ' + msg); }
}

function makeEl() {
  return {
    value: '',
    textContent: '',
    innerHTML: '',
    title: '',
    disabled: false,
    _focused: false,
    _listeners: {},
    _cls: {},
    classList: {
      add: function (c) { this._c = this._c || {}; this._c[c] = true; return this; },
      remove: function (c) { if (this._c) delete this._c[c]; return this; },
      contains: function (c) { return !!(this._c && this._c[c]); },
      _c: {}
    },
    addEventListener: function (ev, fn) { (this._listeners[ev] = this._listeners[ev] || []).push(fn); },
    appendChild: function () {},
    focus: function () { this._focused = true; },
    click: function () {
      (this._listeners.click || []).forEach(function (fn) {
        fn({ stopPropagation: function () {}, preventDefault: function () {}, key: 'Enter' });
      });
    },
    setAttribute: function () {},
    removeAttribute: function () {},
    scrollTop: 0,
    scrollHeight: 0
  };
}

const ctxStub = {
  clearRect: function () {}, beginPath: function () {}, arc: function () {}, fill: function () {},
  fillText: function () {}, fillStyle: '', font: '', textAlign: '', textBaseline: '',
  measureText: function () { return { width: 0 }; },
  getImageData: function () { return { data: new Uint8ClampedArray(4) }; }
};

const SCRIPT = (html.match(/<script>([\s\S]*?)<\/script>/) || [])[1];
if (!SCRIPT) { console.error('FATAL: no inline <script> block found in autothink/ui/index.html'); process.exit(1); }

function boot(fetchImpl) {
  const els = {};
  let fetchCalls = 0;
  const sandbox = {
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    Promise: Promise,
    Math: Math,
    JSON: JSON,
    Date: Date,
    navigator: {},
    innerWidth: 800,
    innerHeight: 600,
    AudioContext: undefined,
    matchMedia: function () { return { matches: false }; },
    addEventListener: function () {},
    requestAnimationFrame: function () {},
    fetch: function () { fetchCalls++; return fetchImpl(); },
    localStorage: {
      getItem: function () { return null; },
      setItem: function () {}
    },
    document: {
      getElementById: function (id) {
        if (id === 'galaxy') {
          els.galaxy = els.galaxy || { getContext: function () { return ctxStub; }, width: 0, height: 0, addEventListener: function () {} };
          return els.galaxy;
        }
        if (!els[id]) els[id] = makeEl();
        return els[id];
      },
      createElement: function () { return makeEl(); },
      addEventListener: function () {},
      removeEventListener: function () {}
    }
  };
  sandbox.window = sandbox;
  vm.runInContext(SCRIPT, vm.createContext(sandbox));
  return { els: els, fetchCalls: function () { return fetchCalls; } };
}

function tick(ms) { return new Promise(function (r) { setTimeout(r, ms || 5); }); }

/* ---------------------------------------------------------------- */
/* Static HTML contract                                             */
/* ---------------------------------------------------------------- */
assert(/data-quick-ask="sourcescout"/.test(html) && /data-quick-ask="listingforge"/.test(html) &&
  /data-quick-ask="adpilot"/.test(html) && /data-quick-ask="socialpulse"/.test(html),
  'brand: four quick-ask service buttons present with data-quick-ask attrs');
assert((html.match(/class="quick-ask"/g) || []).length === 4, 'brand: exactly 4 quick-ask buttons render');
assert(html.includes('>Ask SourceScout</button>') && html.includes('>Ask ListingForge</button>') &&
  html.includes('>Ask AdPilot</button>') && html.includes('>Ask SocialPulse</button>'),
  'brand: quick-ask labels match the shell convention');
assert(html.includes('id="at-lamp-dot"') && html.includes('id="at-lamp-value"') && html.includes('id="at-lamp-meta"'),
  'brand: local-brain lamp elements present (dot/value/meta)');
assert(html.includes('id="at-lamp-meta">no probe performed'), 'brand: lamp meta defaults to "no probe performed" in markup');
assert(html.includes('master-brain/northstar-os-master-plan.md') && html.includes('master-brain/service-plans/05_autothink_surface.md'),
  'brand: master-brain docs pointer present');
assert(html.includes('--ns-gold: #D4AF37') && html.includes('--ns-steel: #4682B4') && html.includes('--ns-crimson: #8B0000'),
  'brand: Northstar gold/steel/crimson tokens defined');
assert(html.includes('--bg: var(--ns-space)') && html.includes('#050505'), 'brand: space-bg token on #050505 applied');
assert(!html.includes('#ff00cc') && !html.includes('#ff9900') && !html.includes('#ffd700'),
  'brand: legacy neon/neon-gold hex removed (full brand sweep)');

/* ---------------------------------------------------------------- */
/* Scenario A — backend down: lamp stays offline, no lamp-triggered  */
/* network, quick asks prefill the composer                          */
/* ---------------------------------------------------------------- */
(async function main() {
  const a = boot(function () { return Promise.reject(new Error('backend down')); });

  assert(a.els['at-lamp-value'].textContent === 'offline', 'offline: lamp renders "offline" at boot');
  assert(a.els['at-lamp-meta'].textContent === 'no probe performed', 'offline: lamp meta says no probe performed');
  assert(a.els['at-lamp-dot'].classList.contains('offline'), 'offline: lamp dot carries offline class');

  const expects = {
    sourcescout: 'Ask SourceScout: find sourcing candidates (demo prefill)',
    listingforge: 'Ask ListingForge: rewrite this listing in Word Coffee voice (demo prefill)',
    adpilot: 'Ask AdPilot: optimize campaign bids by band (demo prefill)',
    socialpulse: 'Ask SocialPulse: draft a social post (demo prefill)'
  };
  Object.keys(expects).forEach(function (svc) {
    a.els['quickAsk-' + svc].click();
    assert(a.els['query'].value === expects[svc], 'quick-ask: "' + svc + '" prefills exact composer value');
    assert(a.els['query']._focused, 'quick-ask: "' + svc + '" focuses the composer');
  });
  assert(a.fetchCalls() === 1, 'offline: lamp + quick-ask interactions perform ZERO network calls (only the boot check ran)');

  await tick();
  assert(a.els['output'].textContent.includes('AutothinK backend not reachable'), 'offline: failed boot check surfaces honest note');
  assert(a.els['at-lamp-value'].textContent === 'offline', 'offline: failed boot check never fabricates detection');
  assert(a.els['at-lamp-meta'].textContent === 'no probe performed', 'offline: meta stays no-probe after failure');

  /* ---------------------------------------------------------------- */
  /* Scenario B — boot health check OK: lamp flips to detected        */
  /* ---------------------------------------------------------------- */
  const b = boot(function () {
    return Promise.resolve({ json: function () { return Promise.resolve({ models: [], local_available: true }); } });
  });
  assert(b.els['at-lamp-value'].textContent === 'offline', 'detected: pre-flip lamp still shows default offline (synchronous render)');
  await tick();
  assert(b.els['at-lamp-value'].textContent === 'detected', 'detected: lamp flips to "detected" only on local boot health check');
  assert(b.els['at-lamp-meta'].textContent === 'detected via local boot health check', 'detected: meta explains the probe source');
  assert(b.els['at-lamp-dot'].classList.contains('detected'), 'detected: lamp dot carries detected class');
  assert(b.els['model'].innerHTML.includes('default'), 'detected: boot check also populated the model select');
  assert(b.fetchCalls() === 1, 'detected: exactly one network call (the boot health check only)');

  console.log('\nUI display test done.');
  console.log(fail ? (fail + ' FAILURES') : ('ALL PASS — ' + pass + ' assertions'));
  process.exit(fail ? 1 : 0);
})();