/*
 * Mocked frontend tests for static/northstar-os/index.html (Northstar OS shell).
 *
 * Loads the shell scripts (engine + demo-data + hub + four service modules +
 * inline boot) into a sandboxed VM with a DOM stub and no network. Exercises:
 * router/drawer, bulletin board, paperclip, global search, gate banners,
 * demo-data honesty, all four service views, and the data-honesty contract.
 *
 * Run: node tests/test_shell.cjs  (from Northstar_backend/static/northstar-os/)
 * or:  node Northstar_backend/static/northstar-os/tests/test_shell.cjs
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const scriptParts = [
    'engine.js', 'demo-data.js', 'hub.js', 'sourcescout.js',
    'listingforge.js', 'adpilot.js', 'socialpulse.js', 'autothink.js',
    'account.js',
].map((f) => fs.readFileSync(path.join(ROOT, 'js', f), 'utf8'));
const boot = 'window.NS.init();';
const script = scriptParts.join('\n;\n') + '\n' + boot;

let failures = 0;
const assert = (cond, msg) => {
    if (cond) console.log('PASS:', msg);
    else { failures++; console.log('FAIL:', msg); }
};

/* ---------- stateful DOM stub: per-id element singletons ---------- */
const els = {};
const classList = (e) => {
    const state = new Set((e.className || '').split(/\s+/).filter(Boolean));
    return {
        add(c) { state.add(c); e.className = Array.from(state).join(' '); },
        remove(c) { state.delete(c); e.className = Array.from(state).join(' '); },
        toggle(c, force) {
            const on = force === undefined ? !state.has(c) : !!force;
            if (on) state.add(c); else state.delete(c);
            e.className = Array.from(state).join(' ');
            return on;
        },
        contains(c) { return state.has(c); },
    };
};
const makeElement = (id, tag) => {
    const listeners = {};
    const attrs = new Map();
    const e = {
        id, tagName: (tag || 'div').toUpperCase(),
        innerHTML: '', textContent: '', className: '', value: '', checked: false,
        hidden: false, disabled: false, style: {}, children: [], options: [],
        _listeners: listeners,
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        removeEventListener(type, fn) { listeners[type] = (listeners[type] || []).filter((f) => f !== fn); },
        setAttribute(k, v) { attrs.set(k, String(v)); },
        getAttribute(k) { return attrs.has(k) ? attrs.get(k) : null; },
        appendChild(child) { this.children.push(child); return child; },
        querySelector: () => null,
        querySelectorAll: () => [],
        closest: () => null,
        click() {},
    };
    Object.defineProperty(e, 'classList', { get: () => classList(e) });
    return e;
};
const getEl = (id) => {
    if (!els[id]) els[id] = makeElement(id);
    return els[id];
};
/* view / nav singletons created up front so classList toggles persist */
['hub', 'sourcescout', 'listingforge', 'adpilot', 'socialpulse', 'autothink', 'account'].forEach((name) => {
    getEl('view-' + name);
    getEl('nav-' + name);
});

const navItems = ['hub', 'sourcescout', 'listingforge', 'adpilot', 'socialpulse', 'autothink', 'account'].map((r) => {
    const n = getEl('nav-' + r);
    n.setAttribute('data-route', r);
    return n;
});
const gateBanners = [
    ['ss-live-banner', 'sourcescout_live_pull'],
    ['gate-adpilot_ads_read', 'adpilot_ads_read'],
    ['gate-adpilot_bulk_exec', 'adpilot_bulk_exec'],
    ['gate-socialpulse_publish', 'socialpulse_publish'],
    ['gate-socialpulse_attrib', 'socialpulse_attrib'],
].map(([id, gateName]) => {
    const g = getEl(id);
    g.setAttribute('data-gate', gateName);
    return g;
});

/* at-workspace iframe: lazy-mount seeded for the harness — no src at boot */
const atFrameHarness = getEl('at-workspace');
atFrameHarness.setAttribute('data-src', '../../autothink/ui/index.html');
assert(atFrameHarness.getAttribute('src') === null, 'perf: autothink iframe has no src at boot (lazy mount)');

const domEvents = {};
const windowStub = {
    innerWidth: 1280,
    addEventListener: (type, fn) => { (domEvents[type] = domEvents[type] || []).push(fn); },
    removeEventListener: (type, fn) => { domEvents[type] = (domEvents[type] || []).filter((f) => f !== fn); },
};
const documentStub = {
    getElementById: getEl,
    createElement: (tag) => makeElement('created-' + tag, tag),
    querySelector: () => null,
    querySelectorAll: (sel) => (sel === '.nav-item[data-route]' ? navItems : sel === '.gate-banner[data-gate]' ? gateBanners : []),
    readyState: 'loading',
    documentElement: { setAttribute() {}, getAttribute() { return 'dark'; } },
    body: { style: {} },
    addEventListener: (type, fn) => { (domEvents[type] = domEvents[type] || []).push(fn); },
    removeEventListener: (type, fn) => { domEvents[type] = (domEvents[type] || []).filter((f) => f !== fn); },
};
const locationStub = { hash: '' };
const localStorageStub = { getItem: () => null, setItem() {}, removeItem() {} };

const context = vm.createContext({
    document: documentStub,
    window: windowStub,
    location: locationStub,
    localStorage: localStorageStub,
    navigator: {},
    setTimeout,
    clearTimeout,
    console,
    Blob: function () {},
    URL: { createObjectURL: () => 'blob:mock', revokeObjectURL() {} },
});
vm.runInContext(script, context, { filename: 'northstar-os shell' });

const NS = windowStub.NS;
assert(typeof NS === 'object' && NS !== null, 'boot: NS global exposed by engine');
assert(typeof NS.DEMO === 'function', 'boot: demo-data loader wired into NS');

/* ============================================================
 * Phase 1 — Router + Drawer
 * ============================================================ */
assert(NS.currentRoute() === 'hub', 'router: default route is hub (empty hash)');
assert(els['view-hub'].classList.contains('active'), 'router: hub view is active by default');
assert(!els['view-listingforge'].classList.contains('active'), 'router: listingforge view inactive by default');

NS.go('adpilot');
assert(locationStub.hash === '#/adpilot', 'router: go() sets location hash');
assert(els['view-adpilot'].classList.contains('active'), 'router: adpilot view activates');
assert(els['nav-adpilot'].classList.contains('active'), 'router: adpilot nav highlights');
assert(els['nav-adpilot'].getAttribute('aria-current') === 'page', 'router: nav aria-current set');
assert(!els['view-hub'].classList.contains('active'), 'router: hub view deactivates on navigation');
assert(els['view-hub'].getAttribute('aria-hidden') === 'true', 'router: hidden view gets aria-hidden');

/* hashchange handler re-mounts */
locationStub.hash = '#/socialpulse';
(domEvents.hashchange || []).forEach((fn) => fn());
assert(els['view-socialpulse'].classList.contains('active'), 'router: hashchange remounts socialpulse');
assert(els['nav-socialpulse'].classList.contains('active'), 'router: hashchange nav highlight');

/* invalid route falls back to hub */
locationStub.hash = '#/nonexistent';
(domEvents.hashchange || []).forEach((fn) => fn());
assert(NS.currentRoute() === 'hub', 'router: unknown route falls back to hub');

/* drawer click wiring */
const drawerListingforge = navItems.find((n) => n.id === 'nav-listingforge');
assert((drawerListingforge._listeners.click || []).length === 1, 'drawer: each nav item has exactly one click binding');
drawerListingforge._listeners.click[0]();
assert(els['view-listingforge'].classList.contains('active'), 'drawer: clicking nav-listingforge opens listingforge');

/* ============================================================
 * Phase 2 — Demo-data honesty + zero network + gates
 * ============================================================ */
const raw = fs.readFileSync(path.join(ROOT, 'js', 'demo-data.js'), 'utf8');
assert(raw.includes('demo'), 'honesty: demo-data module is explicitly labeled demo');
assert(!raw.includes('fetch(') && !raw.includes('XMLHttpRequest'), 'zero-network: demo-data has no network calls');
const allJs = scriptParts.join('\n');
assert(!allJs.includes('fetch(') && !allJs.includes('XMLHttpRequest'), 'zero-network: no shell script uses fetch or XHR');
assert(!html.includes('fetch('), 'zero-network: shell index.html has no fetch calls');
assert(html.includes('data-live-gate="off"'), 'honesty: shell markup carries data-live-gate="off" on gated controls');
assert((html.match(/Authorization required/g) || []).length === 1, 'gates: "Authorization required" appears exactly once (drawer footnote), not in static banners');
assert((html.match(/demo-badge/g) || []).length === 7, 'honesty: seven demo badges in shell markup');

/* all authorization gates start OFF */
Object.keys(NS.gates).forEach((name) => {
    assert(NS.gateState(name).off === true, 'gates: ' + name + ' starts OFF');
});
const probeGate = makeElement('probe-gate');
NS.renderGateBanner(probeGate, 'adpilot_bulk_exec');
assert(probeGate.innerHTML.includes('Authorization required'), 'gates: off-gate banner reads "Authorization required"');
assert(probeGate.className.includes('gate-banner'), 'gates: gate banner class applied');
assert(probeGate.getAttribute('data-gate') === 'adpilot_bulk_exec', 'gates: banner carries data-gate attribute');

/* boot rendered the static gate banners present in markup */
assert(getEl('ss-live-banner').innerHTML.includes('Authorization required'), 'gates: static ss-live-banner rendered by init');
assert(getEl('gate-adpilot_ads_read').innerHTML.includes('Authorization required'), 'gates: static adpilot read banner rendered by init');
assert(getEl('gate-socialpulse_publish').innerHTML.includes('Authorization required'), 'gates: static socialpulse publish banner rendered by init');

/* ============================================================
 * Phase 3 — Hub view
 * ============================================================ */
NS.go('hub');
assert(els['hub-kpis'].innerHTML.includes('Total Profit'), 'hub: KPI strip renders');
assert((els['hub-kpis'].innerHTML.match(/data-kpi=/g) || []).length === 4, 'hub: exactly 4 KPIs');
assert(els['hub-services'].innerHTML.includes('SourceScout'), 'hub: SourceScout service card');
assert((els['hub-services'].innerHTML.match(/data-service=/g) || []).length === 4, 'hub: exactly 4 service cards');

/* open-service buttons bind and navigate */
const openBtn = makeElement('openBtn', 'button');
openBtn.setAttribute('data-open-service', 'sourcescout');
els['hub-services'].querySelectorAll = () => [openBtn];
NS.hub.onMount();
assert((openBtn._listeners.click || []).length === 1, 'hub: open-service buttons bound');

/* ============================================================
 * Phase 4 — Bulletin board
 * ============================================================ */
NS.pin('Kirkland Minoxidil (B0CP6LXPLK)', 'deal');
assert(els['board-list'].innerHTML.includes('Kirkland Minoxidil'), 'board: pin renders text');
assert(els['board-list'].innerHTML.includes('data-pin-id='), 'board: pin renders id marker');
assert(els['pin-count'].textContent.includes('1'), 'board: pin count updates');
assert(NS.board.length === 1, 'board: pin stored in state');
const pinnedId = NS.board[0].id;
NS.unpin(pinnedId);
assert(NS.board.length === 0, 'board: unpin removes from state');
assert(!els['board-list'].innerHTML.includes('data-pin-id='), 'board: unpin clears rendered list');

/* ============================================================
 * Phase 5 — Paperclip assistant
 * ============================================================ */
NS.insights.length = 0;
NS.showInsight('Profit Spike', 'Portfolio KPIs are demo fixtures — no live data loaded.', true);
assert(els['pc-note'].classList.contains('show'), 'paperclip: insight note shows');
assert(els['pc-body'].textContent.includes('demo fixtures'), 'paperclip: insight body rendered');
assert(NS.insights.length === 1, 'paperclip: persisted insight recorded');
NS.showInsight('Rank Drop', 'BSR flagged — verify next scan (demo).');
assert(els['pc-kicker'].textContent === 'Rank Drop', 'paperclip: kicker updates');
NS.dismissInsight();
assert(!els['pc-note'].classList.contains('show'), 'paperclip: dismiss hides note');
assert((getEl('paperclip-figure')._listeners.click || []).length === 1, 'paperclip: figure click bound');

/* ============================================================
 * Phase 6 — Global search handoff
 * ============================================================ */
const input = getEl('global-search');
input.value = 'minoxidil';
(input._listeners.input || []).forEach((fn) => fn());
assert(NS.globalQuery === 'minoxidil', 'search: input updates NS.globalQuery');
NS.globalQuery = ''; /* reset so view filtering in source works cleanly */

/* ============================================================
 * Phase 7 — SourceScout service view
 * ============================================================ */
/* seed a pin button inside the scout table so pinTableRows can bind it */
const rowStub = makeElement('rowStub', 'tr');
rowStub.setAttribute('data-asin', 'B0TEST0001');
rowStub.setAttribute('data-name', 'Test Row');
const pinBtn = makeElement('pinBtn', 'button');
pinBtn.closest = () => rowStub;
getEl('ss-table').querySelectorAll = (sel) => (sel === 'tbody tr.row-card .pin-btn' ? [pinBtn] : []);
getEl('facet-roi').value = '0';
getEl('facet-units').value = '0';

NS.go('sourcescout');
const ssBody = els['ss-table-body'].innerHTML;
assert((ssBody.match(/class="row-card"/g) || []).length === 5, 'sourcescout: 5 demo rows rendered');
assert(ssBody.includes('B0F87RXTVC'), 'sourcescout: Word Coffee row present');
assert(ssBody.includes('B0CP6LXPLK'), 'sourcescout: Kirkland Minoxidil row present');
assert(ssBody.includes('unk'), 'sourcescout: missing values render as "—" / unknown');
assert(els['ss-result-count'].textContent.includes('5 of 5'), 'sourcescout: result counter shows 5 of 5');
assert(els['ss-kpis'].innerHTML.includes('Qualified Deals'), 'sourcescout: KPI strip renders');
assert(els['ss-live-banner'].innerHTML.includes('Authorization required'), 'sourcescout: live-pull gate banner OFF');
assert(els['ss-live-meta'].textContent.includes('Bright Data'), 'sourcescout: live-pull provider meta shown');
assert((pinBtn._listeners.click || []).length === 1, 'sourcescout: pin buttons bound by pinTableRows');
assert((getEl('ss-export')._listeners.click || []).length === 1, 'sourcescout: export button bound');
assert((getEl('ss-open-workbench')._listeners.click || []).length === 1, 'sourcescout: open workbench bound');

/* facet filtering */
els['facet-roi'].value = '75';
(els['facet-roi']._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('1 of 5'), 'sourcescout: ROI>=75 filter yields 1 row');
els['facet-roi'].value = '0';
(els['facet-roi']._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('5 of 5'), 'sourcescout: clearing ROI facet restores 5 rows');

/* global search filters within the view */
NS.globalQuery = 'kirkland';
NS.ss.applyFilters();
assert(els['ss-result-count'].textContent.includes('3 of 5'), 'sourcescout: global search filters to "kirkland" rows');
NS.globalQuery = '';
NS.ss.applyFilters();
assert(els['ss-result-count'].textContent.includes('5 of 5'), 'sourcescout: clearing search restores 5 rows');

/* worksheet export builds CSV through stubbed Blob/URL */
NS.ss.exportWorksheet();
assert(true, 'sourcescout: worksheet export runs without network (stubbed Blob/URL)');

/* ============================================================
 * Phase 8 — ListingForge service view
 * ============================================================ */
NS.go('listingforge');
const lfSel = getEl('lf-asin-select');
assert((lfSel._listeners.change || []).length >= 1, 'listingforge: ASIN selector bound');
assert(lfSel.innerHTML.includes('option'), 'listingforge: ASIN options rendered');
const lfDetail = els['lf-detail'].innerHTML;
assert(lfDetail.includes('B0F87RXTVC'), 'listingforge: default ASIN detail renders');
assert(lfDetail.includes('SEO 30'), 'listingforge: scoring weights displayed');
assert((lfDetail.match(/data-score=/g) || []).length === 6, 'listingforge: six score dials (SEO/Conv/Compl/Visual/Rufus + Rufus readiness)');
assert(lfDetail.includes('Compliance Guardrails'), 'listingforge: compliance panel present');
assert(lfDetail.includes('absolute_superlative'), 'listingforge: default-fixture compliance flag surfaced');
const lfKpis = els['lf-kpis'].innerHTML;
assert(lfKpis.includes('Listing Score') && lfKpis.includes('79.6'), 'listingforge: KPI strip shows fixture score');
assert(els['lf-detail'].children.length >= 2, 'listingforge: gate banners appended to detail');
const gateCopy = els['lf-detail'].children.filter((c) => c.getAttribute('data-gate') === 'listingforge_copy');
assert(gateCopy.length >= 1, 'listingforge: copy gate banner created');
assert(gateCopy[0].innerHTML.includes('Authorization required'), 'listingforge: copy gate banner OFF');

/* switch to the second fixture listing via the selector */
lfSel.value = 'B0F87JDPD4';
(lfSel._listeners.change || []).forEach((fn) => fn());
const lfDetail2 = els['lf-detail'].innerHTML;
assert(lfDetail2.includes('B0F87JDPD4'), 'listingforge: selector switches to second listing');
assert(lfDetail2.includes('medical_claim'), 'listingforge: second-fixture compliance block flag surfaced');

/* ============================================================
 * Phase 9 — AdPilot service view
 * ============================================================ */
NS.go('adpilot');
const kwBody = els['ap-kw-body'].innerHTML;
assert((kwBody.match(/class="row-card"/g) || []).length === 5, 'adpilot: 5 keyword rows');
assert(kwBody.includes('affirmation cards for women'), 'adpilot: harvest row present');
assert(kwBody.includes('PROMOTED') && kwBody.includes('DEMOTED'), 'adpilot: movement pills rendered');
assert(kwBody.includes('needs approval'), 'adpilot: needs-approval zone surfaced');
assert((els['ap-tiers'].innerHTML.match(/data-tier=/g) || []).length === 4, 'adpilot: 4 campaign tiers');
assert(getEl('ap-acos-bands').innerHTML.includes('30–45%'), 'adpilot: ACoS bands include 30-45%');
assert(els['ap-placement-plot'].innerHTML.includes('ip-bar'), 'adpilot: placement ink-plot rendered');
assert((els['ap-guardrails'].innerHTML.match(/data-guard=/g) || []).length === 8, 'adpilot: 8 guardrails');
assert((els['ap-bulk-body'].innerHTML.match(/data-bulk=/g) || []).length === 3, 'adpilot: 3 bulk ops fixture rows');
assert(getEl('gate-adpilot_ads_read').innerHTML.includes('Authorization required'), 'adpilot: ads-read gate OFF');
assert(getEl('gate-adpilot_bulk_exec').innerHTML.includes('Authorization required'), 'adpilot: bulk-exec gate OFF');

/* ============================================================
 * Phase 10 — SocialPulse service view
 * ============================================================ */
NS.go('socialpulse');
const voices = els['soc-voices'].innerHTML;
assert(voices.includes('Word Coffee') && voices.includes('NOT a beverage'), 'socialpulse: voice module enforces NOT-a-beverage rule');
const posts = els['soc-posts'].innerHTML;
assert((posts.match(/data-post=/g) || []).length === 3, 'socialpulse: 3 post drafts');
assert(posts.includes('Grab Word Coffee, not a cup'), 'socialpulse: brand-voice copy present');
assert((els['soc-creatives'].innerHTML.match(/data-creative=/g) || []).length === 3, 'socialpulse: 3 creative prompts');
assert((els['soc-outreach'].innerHTML.match(/data-outreach=/g) || []).length === 2, 'socialpulse: 2 outreach templates');
assert(getEl('soc-attribution').innerHTML.includes('blended ACoS &lt; 40%'), 'socialpulse: attribution threshold stated');
assert(getEl('gate-socialpulse_publish').innerHTML.includes('Authorization required'), 'socialpulse: publish gate OFF');
assert(getEl('gate-socialpulse_attrib').innerHTML.includes('Authorization required'), 'socialpulse: attribution gate OFF');

/* ============================================================
 * Phase 11 — AutothinK surface + shell integrity
 * ============================================================ */
NS.go('autothink');
assert(els['view-autothink'].classList.contains('active'), 'autothink: route mounts workspace view');
assert(html.includes('AutothinK'), 'autothink: brand spelled AutothinK in shell markup');
assert(html.includes('id="at-workspace"'), 'autothink: workspace iframe present in shell');
assert((html.match(/<button class="nav-item"/g) || []).length === 7, 'shell: drawer holds 7 nav items (hub + 4 services + autothink + account)');
assert(html.includes("Northstar OS — The Analyst's Desk"), 'shell: document title matches Analyst\u2019s Desk');
assert(html.includes('css/tokens.css') && html.includes('css/shell.css'), 'shell: css wired');

/* ============================================================
 * Phase 12 — Ink-plot + knob helpers (engine-level)
 * ============================================================ */
const plotHost = makeElement('plotHost');
NS.renderInkPlot(plotHost, 'Placement', [{ label: 'Top', value: 54 }, { label: 'Rest', value: 15 }]);
assert(plotHost.innerHTML.includes('ip-bar') && plotHost.innerHTML.includes('54'), 'engine: ink-plot renders bars and values');
const knobHost = makeElement('knobHost');
const knob = makeElement('knob-1');
knob.setAttribute('data-min', '0');
knob.setAttribute('data-max', '10');
knob.setAttribute('data-step', '1');
knob.setAttribute('data-value', '3');
knobHost.querySelectorAll = (sel) => (sel === '.knob[data-min][data-max]' ? [knob] : []);
NS.bindKnobs(knobHost);
assert(NS.knobValue(knob) === 3, 'engine: knobValue parses data-value');
(knob._listeners.click || [])[0]();
assert(NS.knobValue(knob) === 4, 'engine: knob click increments by step');
(knob._listeners.wheel || []).forEach((fn) => fn({ deltaY: 60, preventDefault() {} }));
assert(NS.knobValue(knob) === 2, 'engine: knob wheel-down decrements from closure base');

/* ============================================================
 * Phase 13 — Hub open-button navigation round trip
 * ============================================================ */
openBtn._listeners.click[0]();
assert(els['view-sourcescout'].classList.contains('active'), 'hub: open SourceScout navigates from hub card');

/* ============================================================
 * Phase 14 — ListingForge deep: scoring math, editors, bridge, feedback
 * ============================================================ */
/* weighted-sum scoring: fixture raws render exactly as fixture totals */
assert(NS.lf.weightedTotal({ seo: 82, conversion: 76, compliance: 73, visual: 88, rufus: 84 }) === 79.6, 'listingforge: weightedTotal matches L1 fixture total (79.6)');
assert(NS.lf.weightedTotal({ seo: 82, conversion: 78, compliance: 74, visual: 86, rufus: 84 }) === 80.1, 'listingforge: weightedTotal matches L2 fixture total (80.1)');
assert(NS.lf.byteLen('abc') === 3, 'listingforge: byteLen counts ASCII');
assert(NS.lf.byteLen('\u00e9') === 2, 'listingforge: byteLen counts 2-byte utf-8 char');
assert(NS.lf.byteLen('\u8a00\u8bed') === 6, 'listingforge: byteLen counts 3-byte utf-8 chars');

NS.go('listingforge');
const lfDeep = els['lf-detail'].innerHTML;
assert(lfDeep.includes('data-breakdown'), 'listingforge: scoring breakdown panel renders');
assert((lfDeep.match(/data-cat=/g) || []).length === 5, 'listingforge: breakdown lists five weighted categories');
assert(lfDeep.includes('data-total-badge'), 'listingforge: weighted total badge rendered');
assert(lfDeep.includes('weight 30%') && lfDeep.includes('weight 15%'), 'listingforge: category weights disclosed');

/* sub-view tabs isolate panels (stub panels) */
const panelScoring = makeElement('lf-p-scoring');
panelScoring.setAttribute('data-panel', 'scoring');
const panelStudio = makeElement('lf-p-studio');
panelStudio.setAttribute('data-panel', 'studio');
getEl('lf-detail').querySelectorAll = (sel) => (sel === '.lf-panel[data-panel]' ? [panelScoring, panelStudio] : []);
const lfTabsList = ['overview', 'studio', 'scoring', 'compliance', 'media', 'bridge', 'feedback'].map((t) => {
  const b = makeElement('lf-tab-' + t, 'button');
  b.setAttribute('data-lf-tab', t);
  return b;
});
getEl('lf-tabs').querySelectorAll = (sel) => (sel === '.lf-tab[data-lf-tab]' || sel === '.lf-tab' ? lfTabsList : []);
NS.lf.setTab('studio');
assert(panelScoring.classList.contains('hidden'), 'listingforge: setTab(studio) hides scoring panel');
assert(!panelStudio.classList.contains('hidden'), 'listingforge: setTab(studio) shows studio panel');
assert(lfTabsList[1].classList.contains('active') && !lfTabsList[0].classList.contains('active'), 'listingforge: setTab(studio) marks tab active');
NS.lf.setTab('overview');
assert(!panelScoring.classList.contains('hidden') && !panelStudio.classList.contains('hidden'), 'listingforge: setTab(overview) reveals all panels');

/* Studio title draft: char counter + save to feedback loop */
const lfDraftTitle = getEl('lf-title-edit');
lfDraftTitle.value = new Array(140 + 1).join('x'); /* 140 chars */
(lfDraftTitle._listeners.input || []).forEach((fn) => fn());
assert(getEl('lf-title-count').textContent.includes('140 / 200'), 'listingforge: title counter reflects live keystrokes');
assert(getEl('lf-title-count').className.includes('warn'), 'listingforge: title counter warns above 131-char ideal');
getEl('lf-title-save')._listeners.click.forEach((fn) => fn());
const lfAfterSave = els['lf-detail'].innerHTML;
assert(lfAfterSave.includes('data-fb-kind="title_draft"'), 'listingforge: saving a title draft seeds the feedback loop');
assert(lfAfterSave.match(/data-feedback=/g) && (lfAfterSave.match(/data-feedback=/g) || []).length >= 1, 'listingforge: feedback row keyed by asin');

/* Keyword Bridge: byte cap + duplicate detection + add */
const lfTermInput = getEl('lf-term-input');
lfTermInput.value = new Array(252 + 1).join('x'); /* 252 ASCII bytes > 250 cap */
(lfTermInput._listeners.input || []).forEach((fn) => fn());
assert(getEl('lf-term-count').textContent.includes('252 / 250 bytes'), 'listingforge: backend-term byte counter reports over-cap');
assert(getEl('lf-term-status').textContent.includes('Over the 250-byte cap'), 'listingforge: over-cap term flagged, not added');
lfTermInput.value = 'gift for mom'; /* exact fixture term in L1 bridge list */
(lfTermInput._listeners.input || []).forEach((fn) => fn());
assert(getEl('lf-term-status').textContent.includes('Duplicate'), 'listingforge: duplicate backend term detected');
lfTermInput.value = 'mom life gift cards';
getEl('lf-term-add')._listeners.click.forEach((fn) => fn());
const lfAfterTerm = els['lf-detail'].innerHTML;
assert((lfAfterTerm.match(/data-backend-term=/g) || []).length === 7, 'listingforge: new backend term appended to bridge list (6 -> 7)');
assert(lfAfterTerm.includes('mom life gift cards'), 'listingforge: added term rendered in bridge');
assert(lfAfterTerm.includes('data-fb-kind="backend_term"'), 'listingforge: term add logged as feedback signal');

/* ============================================================
 * Phase 15 — AdPilot deep: ACoS band rule engine, movement sort, CSV dock
 * ============================================================ */
/* band rule engine (pure): master-plan band table + low-data hold */
assert(NS.ap.bandFor(50, 15).action === '−10 to −30% bid' && NS.ap.bandFor(50, 15).kind === 'crimson', 'adpilot: bandFor(>45%, >=10 clicks) -> -10/-30% bid');
assert(NS.ap.bandFor(41.2, 82).action === '−5 to −10% bid' && NS.ap.bandFor(41.2, 82).band === '30–45%', 'adpilot: bandFor(41.2) -> 30-45% band -5/-10%');
assert(NS.ap.bandFor(27.1, 640).action === '+5 to +15% bid' && NS.ap.bandFor(27.1, 640).band === '15–30%', 'adpilot: bandFor(27.1) -> 15-30% band +5/+15%');
assert(NS.ap.bandFor(12.4, 118).action === '+15 to +30% bid' && NS.ap.bandFor(12.4, 118).band === '<15%', 'adpilot: bandFor(12.4) -> <15% band +15/+30%');
assert(NS.ap.bandFor(50, 3).lowData === true && NS.ap.bandFor(50, 3).action.indexOf('hold') !== -1, 'adpilot: <10 clicks -> hold, never an action');
assert(NS.ap.bandFor(null, 3).band === 'no ACoS', 'adpilot: missing ACoS reported as no-ACoS');

/* harvester table carries band-rule bid delta cells; band previews render */
NS.go('adpilot');
const apDeep = els['ap-kw-body'].innerHTML;
assert((apDeep.match(/data-bid-delta=/g) || []).length === 3, 'adpilot: bid-delta cells rendered for keywords with ACoS + data');
assert((els['ap-band-previews'].innerHTML.match(/data-band-preview=/g) || []).length === 3, 'adpilot: per-keyword band previews rendered');
assert(els['ap-band-previews'].innerHTML.includes('+30%'), 'adpilot: band preview shows +15/+30% for sub-15 ACoS keyword');
assert(els['ap-bulk-count'].textContent.includes('3 rows parsed'), 'adpilot: bulk dock reports parsed row count');

/* movement sort: asc = PROMOTED first; click desc flips DEMOTED first */
const apBody = els['ap-kw-body'];
const apK1 = 'data-kw="affirmation cards for women"';
const apK4 = 'data-kw="coffee beans"';
assert(apBody.innerHTML.indexOf(apK1) < apBody.innerHTML.indexOf(apK4), 'adpilot: movement sort defaults asc (PROMOTED first)');
getEl('ap-sort-movement')._listeners.click.forEach((fn) => fn());
assert(NS.ap.sortDir() === 'desc', 'adpilot: Movement header click toggles to desc');
assert(apBody.innerHTML.indexOf(apK1) > apBody.innerHTML.indexOf(apK4), 'adpilot: desc sort puts DEMOTED keyword row first');
assert(getEl('ap-sort-ind').textContent === '▼', 'adpilot: sort indicator reflects desc');
getEl('ap-sort-movement')._listeners.click.forEach((fn) => fn());
assert(NS.ap.sortDir() === 'asc' && apBody.innerHTML.indexOf(apK1) < apBody.innerHTML.indexOf(apK4), 'adpilot: second click restores asc');

/* CSV dock: parser handles quoted commas and blank bids; button flow */
const parsed = NS.ap.parseBulkCsv(getEl('ap-csv-src').value);
assert(parsed.length === 3, 'adpilot: fixture CSV parses to 3 rows');
assert(parsed[0].sku === 'WC-MOMS-V1' && parsed[0].bid === 1.05, 'adpilot: CSV row 1 sku/bid mapped');
assert(parsed[0].reason === 'ACoS 27%, orders>0', 'adpilot: quoted comma preserved in reason');
assert(parsed[1].decision === 'decrease-8pct', 'adpilot: CSV decision column mapped');
assert(parsed[2].bid === null && parsed[2].decision === 'add-negative' && parsed[2].reason === '0 orders, repeat non-converter', 'adpilot: blank bid -> null; negative row parsed');
getEl('ap-parse-csv')._listeners.click.forEach((fn) => fn());
assert((els['ap-bulk-body'].innerHTML.match(/data-bulk=/g) || []).length === 3, 'adpilot: Parse button renders annotated rows');
assert(els['ap-bulk-body'].innerHTML.includes('increase-10pct') && els['ap-bulk-body'].innerHTML.includes('add-negative'), 'adpilot: parsed decisions rendered as pills');
const twoRowCsv = 'sku,campaign,keyword or targeting,match type,bid,decision,reason\nA,B,C,exact,0.5,increase-10pct,R\n';
getEl('ap-csv-src').value = twoRowCsv;
(getEl('ap-csv-src')._listeners.input || []).forEach((fn) => fn());
assert((els['ap-bulk-body'].innerHTML.match(/data-bulk=/g) || []).length === 1, 'adpilot: CSV input edits live re-render the dock');

/* ============================================================
 * Phase 16 — SocialPulse deep: content studio, calendar scheduling
 * ============================================================ */
/* deterministic voice-tagline generator (pure) */
assert(NS.soc.generateCaption('word_coffee', 'meta').caption === 'Grab Word Coffee, not a cup.', 'socialpulse: meta channel renders exact fixture tagline');
assert(NS.soc.generateCaption('word_coffee', 'instagram').caption === 'Fuel Your Focus.', 'socialpulse: instagram channel renders exact fixture tagline');
assert(NS.soc.generateCaption('word_coffee', 'tiktok').caption === 'Find Your Calm in the Chaos.', 'socialpulse: tiktok channel renders exact fixture tagline');
assert(NS.soc.generateCaption('word_coffee', 'tiktok', 1).caption === 'Brew Your Best Self.', 'socialpulse: regeneration cycles the tagline set');
assert(NS.soc.generateCaption('nope', 'meta') === null, 'socialpulse: unknown voice fails closed');
assert(NS.soc.generateCaption('word_coffee', 'meta').hashtags.length === 3, 'socialpulse: generated caption carries channel hashtag set');

NS.go('socialpulse');
const socCal = els['soc-calendar'].innerHTML;
assert((socCal.match(/data-slot=/g) || []).length === 7, 'socialpulse: calendar hosts 7 week slots');
assert((socCal.match(/class="day-slot filled"/g) || []).length === 2, 'socialpulse: fixture saved posts fill 2 day slots');

/* content studio renders default caption + clickable hashtag chips */
const csOut0 = els['soc-cs-output'].innerHTML;
assert(csOut0.includes('Grab Word Coffee, not a cup.'), 'socialpulse: studio defaults to meta tagline');
assert((csOut0.match(/data-hashtag=/g) || []).length === 3, 'socialpulse: generated hashtag chips render');
assert(csOut0.includes('role="button"'), 'socialpulse: studio hashtag chips are clickable');

/* regenerate cycles to the next tagline */
getEl('soc-cs-generate')._listeners.click.forEach((fn) => fn());
assert(els['soc-cs-output'].innerHTML.includes('Fuel Your Focus.'), 'socialpulse: regenerate steps to next voice tagline');

/* schedule from studio: new post moves into first free slot, in-memory */
getEl('soc-cs-schedule')._listeners.click.forEach((fn) => fn());
const socCal2 = els['soc-calendar'].innerHTML;
assert((socCal2.match(/class="day-slot filled"/g) || []).length === 3, 'socialpulse: studio caption occupies a calendar slot');
assert(socCal2.includes('data-filled="cs4"'), 'socialpulse: studio-scheduled post tracked by id in calendar');
assert(socCal2.includes('data-slot="Tue 8:30 AM"') && socCal2.includes('data-filled="cs4"'), 'socialpulse: scheduling picks the first free slot (Tue)');
assert((els['soc-posts'].innerHTML.match(/data-post=/g) || []).length === 4, 'socialpulse: studio-scheduled caption appended to posts');

/* draft -> calendar: p3 moves out of drafts on click */
getEl('schedule-p3')._listeners.click.forEach((fn) => fn());
const socCal3 = els['soc-calendar'].innerHTML;
assert((socCal3.match(/class="day-slot filled"/g) || []).length === 4, 'socialpulse: p3 draft scheduled into calendar');
assert(socCal3.includes('data-filled="p3"') && socCal3.includes('data-slot="Thu 9:00 AM"'), 'socialpulse: p3 lands in next free slot (Thu)');
assert(!els['soc-posts'].innerHTML.includes('data-schedule="p3"'), 'socialpulse: scheduled draft loses its schedule button');
assert(els['soc-posts'].innerHTML.includes('scheduled'), 'socialpulse: scheduled draft badge flips to green');

/* data-honesty: publishing + attribution still gated after interactions */
assert(getEl('gate-socialpulse_publish').innerHTML.includes('Authorization required'), 'socialpulse: publish gate stays OFF after studio interactions');
assert(getEl('gate-socialpulse_attrib').innerHTML.includes('Authorization required'), 'socialpulse: attribution gate stays OFF after studio interactions');

/* ============================================================
 * Phase 17 — AutothinK surface: quick-ask prefill + backend lamp
 * ============================================================ */
NS.go('autothink');
assert(els['view-autothink'].classList.contains('active'), 'autothink: route mounts workspace view (deep surface)');
assert(html.includes('data-quick="sourcescout"') && html.includes('data-quick="socialpulse"'), 'autothink: 4 quick-ask buttons present in markup');
assert(html.includes('no probe performed — shows configured state'), 'autothink: lamp honestly labeled as non-probed');

/* local-brain lamp: configured state, no network */
assert(getEl('at-lamp-value').textContent === 'offline', 'autothink: lamp defaults to offline (no probe performed)');
assert(getEl('at-lamp-dot').classList.contains('offline'), 'autothink: lamp dot reflects offline state');
NS.config.autothinkBackend = 'detected';
NS.autothink.renderLamp();
assert(getEl('at-lamp-value').textContent === 'detected', 'autothink: lamp reflects detected state after operator flip');
assert(getEl('at-lamp-dot').classList.contains('detected') && !getEl('at-lamp-dot').classList.contains('offline'), 'autothink: lamp dot swaps to detected');

/* quick-ask buttons prefill the composer for the Master Brain router */
getEl('at-quick-sourcescout')._listeners.click.forEach((fn) => fn());
assert(getEl('at-composer').value === 'Ask SourceScout: find sourcing candidates (demo prefill)', 'autothink: Ask SourceScout prefills verb + domain');
getEl('at-quick-adpilot')._listeners.click.forEach((fn) => fn());
assert(NS.autothink.prefill('adpilot') === 'Ask AdPilot: optimize campaign bids by band (demo prefill)', 'autothink: Ask AdPilot prefill returns deterministic copy');
assert(getEl('at-composer').value.indexOf('Ask AdPilot:') === 0, 'autothink: composer shows the AdPilot ask');
assert(NS.autothink.prefill('nope') === null, 'autothink: unknown service fails closed');

/* copy affordance is demo-only (no live clipboard side effects asserted) */
getEl('at-copy')._listeners.click.forEach((fn) => fn());
assert(getEl('at-copy-note').textContent === 'Copied (demo)', 'autothink: copy button records the demo action');

/* reset the non-secret lamp config back to the shipped default */
NS.config.autothinkBackend = 'offline';
NS.autothink.renderLamp();
assert(getEl('at-lamp-value').textContent === 'offline', 'autothink: lamp config reset to honest offline default');

/* ============================================================
 * Phase 18 — SourceScout deep: portfolio pass-through, typed
 *             live-pull taxonomy, richer sourcing facets
 * ============================================================ */
NS.go('sourcescout');

/* hub global-KPI pass-through (spec extension 4) */
const ssPortfolio = els['ss-portfolio'].innerHTML;
assert(ssPortfolio.includes('Total Profit') && ssPortfolio.includes('$11,483.22'), 'sourcescout: portfolio overview carries hub global KPIs');

/* typed live-pull failure taxonomy from the evidence manifest */
const ssLive = els['ss-live-status'].innerHTML;
assert(ssLive.includes('partial'), 'sourcescout: live-pull banner surfaces partial status');
assert(ssLive.includes('resolved 24 / requested 53'), 'sourcescout: live-pull banner reports resolved/requested counts');
assert((ssLive.match(/data-live-failure=/g) || []).length === 3, 'sourcescout: three typed failures in taxonomy');
assert(ssLive.includes('url_not_found') && ssLive.includes('no_data_found') && ssLive.includes('transport_error'), 'sourcescout: failure taxonomy rendered');
assert(!ssLive.includes('success'), 'sourcescout: partial manifest never marks success');
assert(els['ss-live-meta'].textContent.includes('Bright Data'), 'sourcescout: provider meta preserved');

/* sourcing facets */
assert(els['ss-result-count'].textContent.includes('5 of 5'), 'sourcescout: all rows present with facets neutral');
getEl('facet-margin').value = '20';
(getEl('facet-margin')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('4 of 5'), 'sourcescout: margin>=20% excludes unscored detergent');
getEl('facet-margin').value = '0';
(getEl('facet-margin')._listeners.change || []).forEach((fn) => fn());

getEl('facet-buybox').checked = true;
(getEl('facet-buybox')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('4 of 5'), 'sourcescout: buy-box-stable-only excludes towelettes');
getEl('facet-buybox').checked = false;
(getEl('facet-buybox')._listeners.change || []).forEach((fn) => fn());

getEl('facet-invoice').checked = true;
(getEl('facet-invoice')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('4 of 5'), 'sourcescout: clean-invoice-only excludes unverified towelettes');
getEl('facet-invoice').checked = false;
(getEl('facet-invoice')._listeners.change || []).forEach((fn) => fn());

getEl('facet-risk').checked = true;
(getEl('facet-risk')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('3 of 5'), 'sourcescout: risk-clean-only excludes Minoxidil + towelettes');
getEl('facet-risk').checked = false;
(getEl('facet-risk')._listeners.change || []).forEach((fn) => fn());

/* combined facets compose */
getEl('facet-margin').value = '20';
getEl('facet-buybox').checked = true;
(getEl('facet-margin')._listeners.change || []).forEach((fn) => fn());
(getEl('facet-buybox')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('3 of 5'), 'sourcescout: margin+buy-box compose (drops detergent + towelettes)');
getEl('facet-margin').value = '0';
getEl('facet-buybox').checked = false;
(getEl('facet-margin')._listeners.change || []).forEach((fn) => fn());
(getEl('facet-buybox')._listeners.change || []).forEach((fn) => fn());

/* consumables-first is a sort preference — all rows stay */
getEl('facet-consumable').checked = true;
(getEl('facet-consumable')._listeners.change || []).forEach((fn) => fn());
const ssCons = els['ss-table-body'].innerHTML;
assert((ssCons.match(/class="row-card"/g) || []).length === 5, 'sourcescout: consumables-first keeps all 5 rows');
assert(ssCons.indexOf('Facial Towelettes') > ssCons.indexOf('Word Coffee'), 'sourcescout: non-consumable sorts below consumables');
getEl('facet-consumable').checked = false;
(getEl('facet-consumable')._listeners.change || []).forEach((fn) => fn());
assert(els['ss-result-count'].textContent.includes('5 of 5'), 'sourcescout: clearing all facets restores 5 rows');

/* pure predicates exported; missing data never fakes a zero */
assert(NS.ss.marginPct({ amazonPrice: 42, cost: 17.99 }) === 57.2, 'sourcescout: marginPct math exact (42/17.99 -> 57.2)');
assert(NS.ss.marginPct({ amazonPrice: 21.19, cost: null }) === null, 'sourcescout: marginPct null cost -> null, never 0');
assert(NS.ss.matchesFilters({ name: 'x', asin: 'y', roi: 80, estMonthly: 300, buyBox: true, invoice: 'clean', riskClean: true }) === true, 'sourcescout: matchesFilters passes a fully-clean row');

/* ============================================================
 * Phase 19 — Account view: subscriber identity, plan catalog,
 *             entitlements matrix, honesty, lazy workspace
 * ============================================================ */
NS.go('account');
assert(els['view-account'].classList.contains('active'), 'account: route mounts the Account view');
assert(els['nav-account'].classList.contains('active'), 'account: Account nav highlights on route');
assert(NS.currentRoute() === 'account', 'account: currentRoute resolves the account hash');

/* active subscriber identity (demo mirror of profiles manifest) */
const acctId = els['acct-identity'].innerHTML;
assert(acctId.includes('data-acct="profile-id"') && acctId.includes('t2-holdings-tyrone-johnson'), 'account: profile id rendered');
assert(acctId.includes('data-acct="resolver"') && acctId.includes('local_default'), 'account: resolver chain shown (local_default, no live auth in beta)');
assert(acctId.includes('data-acct="plan"') && acctId.includes('AutothinK'), 'account: active plan rendered as AutothinK');
assert(acctId.includes('data-acct="status"') && acctId.includes('data-acct="status">active'), 'account: subscription status rendered active');

/* plan catalog renders all four beta tiers */
const acctPlans = els['acct-plans'].innerHTML;
assert((acctPlans.match(/class="plan-card/g) || []).length === 4, 'account: four plan cards render');
assert(acctPlans.includes('data-plan="foundation"') && acctPlans.includes('data-plan="autothink"') &&
       acctPlans.includes('data-plan="scout"') && acctPlans.includes('data-plan="mover"'), 'account: all four plan ids rendered');
assert(acctPlans.includes('$0') && acctPlans.includes('$29') && acctPlans.includes('$79') && acctPlans.includes('$149'), 'account: plan prices render (demo)');
assert(acctPlans.includes('>AutothinK<'), 'account: premium plan spelled AutothinK');
assert(acctPlans.includes('your plan'), 'account: active plan card is tagged');

/* entitlements matrix: all 8 gates, all OFF, active coverage marked */
const acctMatrix = els['acct-matrix'].innerHTML;
assert((acctMatrix.match(/data-gate="/g) || []).length === 8, 'account: entitlements matrix lists all 8 gates');
assert((acctMatrix.match(/Authorization required/g) || []).length === 8, 'account: every gate row shows OFF live status');
assert(acctMatrix.includes('sourcescout_live_pull') && acctMatrix.includes('socialpulse_publish'),
       'account: typed gate ids surfaced in the matrix');
assert((acctMatrix.match(/Entitled/g) || []).length === 8, 'account: autothink plan covers every gate as entitled');
assert(acctMatrix.includes('Plans that entitle'), 'account: matrix exposes plan coverage column');

/* honesty contract: plans never flip gates; live needs named approval */
const acctView = html;
assert(acctView.includes('never flipped'), 'account: honesty note — plans never flip gates');
assert(acctView.includes('fresh, named operator approval'), 'account: live actions still need fresh named approval');
assert(els['acct-beta-status'].innerHTML.includes('8 / 8 live gates off'), 'account: beta status reports all 8 gates off');

/* plan entitlement helpers (pure, fail closed) */
assert(NS.activePlan() && NS.activePlan().id === 'autothink', 'account: activePlan resolves to autothink');
assert(NS.planEntitles('sourcescout_live_pull').length === 3, 'account: live-pull entitled by 3 plans');
assert(NS.planEntitles('socialpulse_publish').length === 1 && NS.planEntitles('socialpulse_publish').indexOf('AutothinK') !== -1,
       'account: publish gate entitled only by AutothinK');
assert(NS.planEntitles('nope_gate').length === 0, 'account: unknown gate yields no entitlements (fail closed)');

/* ribbon plan badge reflects the active subscriber */
assert(els['ribbon-plan'].textContent.includes('AutothinK'), 'account: ribbon Plan stat shows the active plan');

/* reduced-motion guard for the view entrance animation */
const shellCss = fs.readFileSync(path.join(ROOT, 'css', 'shell.css'), 'utf8');
assert(shellCss.includes('@keyframes viewIn'), 'account: view entrance animation keyframes defined');
assert(shellCss.includes('prefers-reduced-motion'), 'account: reduced-motion rule disables the entrance animation');

/* lazy workspace iframe: mounts once on first visit, nothing at boot */
assert(html.includes('data-src="../../autothink/ui/index.html"'), 'perf: workspace URL deferred to data-src in markup');
assert(!html.includes('<iframe id="at-workspace" src='), 'perf: no static src on the workspace iframe (boot stays light)');
assert(els['at-workspace'].getAttribute('src') === '../../autothink/ui/index.html', 'perf: workspace iframe mounted once by first visit');

/* ==========================================================================
 * A3 — demo-data re-sync: the UI subscriber mirror must equal the canonical
 * catalog (shared/subscription-plans.json). Data-shape fix assertions are
 * additive; the hub stays zero-network by design.
 * ========================================================================== */
const demoPlansA3 = (typeof NS.DEMO === 'function' && NS.DEMO() && NS.DEMO().subscriber && NS.DEMO().subscriber.plans)
    ? NS.DEMO().subscriber.plans
    : [];
const dPanelA3 = demoPlansA3.find((p) => p && p.id === 'autothink');
assert(!!dPanelA3, 'a3: demo catalog has an autothink plan');
const CANON_A3 = ['sourcescout_live_pull', 'sourcescout_enrich', 'listingforge_copy', 'listingforge_media', 'adpilot_ads_read', 'adpilot_bulk_exec', 'socialpulse_attrib', 'socialpulse_publish', 'autothink_workspace'];
assert(!!dPanelA3 && JSON.stringify(dPanelA3.entitled_gates) === JSON.stringify(CANON_A3),
    'a3: demo autothink gate array matches shared/subscription-plans.json exactly (incl. autothink_workspace, order)');
assert(demoPlansA3.length === 4, 'a3: demo catalog still four plans (foundation/scout/mover/autothink)');
assert(JSON.stringify(demoPlansA3, null, 2).toLowerCase().indexOf('unlimited') === -1,
    'a3: demo catalog carries no "unlimited" language');
assert(JSON.stringify(demoPlansA3).includes('Everything + AutothinK AI workspace'),
    'a3: demo autothink blurb matches the canonical description');
assert((NS.DEMO().subscriber.gateStateNote || '').includes('shared/subscription-plans.json'),
    'a3: demo mirror cites the canonical catalog path');

console.log('\nShell contract complete.');
console.log(failures === 0 ? 'ALL GREEN' : failures + ' FAILURES');
process.exit(failures === 0 ? 0 : 1);