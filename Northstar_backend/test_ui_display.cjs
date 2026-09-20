/*
 * Mocked frontend tests for static/index.html (Northstar OS Scout).
 *
 * Loads the embedded <script> into a sandboxed VM with a DOM stub and a
 * never-resolving fetch stub (no network). Exercises the Scout data
 * contract, filters, sorts, opportunity scores, KPIs, and honest state
 * rendering.
 *
 * Run: node test_ui_display.cjs
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = path.join(__dirname, 'static', 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
    console.error('FAIL: could not find <script> block in static/index.html');
    process.exit(1);
}
const script = scriptMatch[1];

let failures = 0;
const assert = (cond, msg) => {
    if (cond) console.log('PASS:', msg);
    else { failures++; console.log('FAIL:', msg); }
};

/* ---------- stateful DOM stub: per-id element singletons with real
 * listener storage, class/attribute tracking, and event dispatch.
 * Interaction tests (tabs, close, sort, Escape) run against the real
 * event bindings in static/index.html — no jsdom, no network. ---------- */
const makeElement = (id) => {
    const listeners = {};
    const attrs = new Map();
    const classes = new Set();
    const children = [];
    const e = {
        id,
        innerHTML: '', textContent: '', className: '', value: '', checked: false,
        hidden: false, disabled: false, style: {}, children, options: [], offsetWidth: 240,
        _listeners: listeners,
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        removeEventListener(type, fn) { listeners[type] = (listeners[type] || []).filter((f) => f !== fn); },
        setAttribute(k, v) { attrs.set(k, String(v)); },
        getAttribute(k) { return attrs.has(k) ? attrs.get(k) : null; },
        removeAttribute(k) { attrs.delete(k); },
        classList: {
            add(c) { classes.add(c); },
            remove(c) { classes.delete(c); },
            toggle(c, force) { const want = force === undefined ? !classes.has(c) : !!force; if (want) classes.add(c); else classes.delete(c); return want; },
            contains(c) { return classes.has(c); },
        },
        querySelector() { return null; },
        querySelectorAll() { return []; },
        closest() { return null; },
        contains(node) { return node === e || children.indexOf(node) !== -1; },
        focus() {},
        appendChild(child) { children.push(child); return child; },
        getBoundingClientRect() { return { top: 0, bottom: 40, left: 8, width: 120, right: 128 }; },
    };
    return e;
};

const els = {};
const domEvents = {};
const getEl = (id) => (els[id] = els[id] || makeElement(id));
/* standalone element factory (legacy helper used by later phases to
 * fabricate throwaway nodes for click/delegation targets) */
const el = () => makeElement('anon');

/* dispatch a synthetic event on a named element (bubble phase, delegation
 * targets passed via `target`) */
const fireEvent = (id, type, target, extra) => {
    const node = els[id];
    if (!node) return;
    const t = target || node;
    const ev = Object.assign({ type, target: t, preventDefault() {}, stopPropagation() {} }, extra || {});
    (node._listeners[type] || []).slice().forEach((fn) => {
        try { fn(ev); } catch (err) { console.error('handler error on #' + id + ' (' + type + '):', err); }
    });
};
const click = (id, target) => fireEvent(id, 'click', target);
const change = (id, value) => { const n = els[id]; if (n) n.value = value; fireEvent(id, 'change'); };
const fireDoc = (type, target) => {
    const ev = { type, target: target || { contains() { return false; } }, preventDefault() {}, stopPropagation() {} };
    (domEvents[type] || []).slice().forEach((fn) => { try { fn(ev); } catch (err) { /* ignore */ } });
};

const documentStub = {
    getElementById: getEl,
    createElement: (tag) => makeElement(tag),
    querySelector: () => null,
    querySelectorAll: () => [],
    readyState: 'loading',
    documentElement: { setAttribute() {}, getAttribute() { return 'dark'; } },
    body: { style: {} },
    addEventListener: (type, fn) => { (domEvents[type] = domEvents[type] || []).push(fn); },
    removeEventListener: (type, fn) => { domEvents[type] = (domEvents[type] || []).filter((f) => f !== fn); },
};

/* fire a synthetic keydown through every registered handler (bubble phase) */
const fireKey = (key) => {
    (domEvents.keydown || []).forEach((fn) => {
        try { fn({ key, preventDefault() {} }); } catch (e) { /* ignore */ }
    });
};

const store = {};
const localStorageStub = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
};

const context = vm.createContext({
    document: documentStub,
    localStorage: localStorageStub,
    window: { innerWidth: 1280 },
    location: { search: '' },
    fetch: () => new Promise(() => {}),
    setTimeout,
    clearTimeout,
    console,
    assert,
});
vm.runInContext(script, context, { filename: 'index.html<script>' });

/* seed the inspection-sheet tabs and sort-select options from the real
 * markup so event delegation in the script resolves real nodes */
const seedTabs = ['overview', 'source', 'economics', 'market', 'verify'].map((seg) => {
    const t = makeElement('seg-' + seg);
    t.setAttribute('data-segment', seg);
    t.closest = (sel) => (sel === '.sheet-segment' ? t : null);
    return t;
});
els.sheetNav = getEl('sheetNav');
els.sheetNav.querySelectorAll = (sel) => (sel === '.sheet-segment' ? seedTabs : []);
els.sheetNav.querySelector = (sel) => (sel === '.sheet-segment' ? seedTabs[0] : null);
els.csSortSelect = getEl('csSortSelect');
const popoverSlice = html.slice(html.indexOf('id="sortPopover"'), html.indexOf('id="colPopover"'));
const sortOptions = [];
const optRe = /<option value="([^"]+)"[^>]*>([^<]+)<\/option>/g;
let optMatch;
while ((optMatch = optRe.exec(popoverSlice)) !== null) sortOptions.push({ value: optMatch[1], text: optMatch[2] });
els.csSortSelect.options = sortOptions;
els.csSortSelect.selectedOptions = [];
/* the real markup ships these hidden; stub defaults are visible */
els.sortPopover = getEl('sortPopover');
els.sortPopover.hidden = true;
els.sheetOverlay = getEl('sheetOverlay');
els.sheetOverlay.hidden = true;

/* -------- boot lifecycle: the real file defers init() until
 * DOMContentLoaded because the sheet/popover markup sits after the
 * script tag. Mirror that exactly: assert NO bindings exist yet, then
 * fire DOMContentLoaded and prove the bindings attach. -------- */
getEl('sheetClose');
getEl('csSortBtn');
assert(!(els.sheetNav._listeners.click || []).length, 'boot: no tab binding before DOMContentLoaded (nodes after script)');
assert(!(els.sheetOverlay._listeners.click || []).length, 'boot: no overlay binding before DOMContentLoaded');
assert(!(els.sheetClose._listeners.click || []).length, 'boot: no close binding before DOMContentLoaded');
assert(!(els.csSortBtn._listeners.click || []).length, 'boot: no sort trigger binding before DOMContentLoaded');
fireDoc('DOMContentLoaded');
assert((els.sheetNav._listeners.click || []).length === 1, 'boot: tab delegation binds once at DOMContentLoaded');
assert((els.sheetOverlay._listeners.click || []).length === 1, 'boot: overlay click binds once at DOMContentLoaded');
assert((els.sheetClose._listeners.click || []).length === 1, 'boot: X close binds once at DOMContentLoaded');
assert((els.csSortBtn._listeners.click || []).length === 1, 'boot: sort trigger binds once at DOMContentLoaded');
assert((domEvents.keydown || []).length === 1, 'boot: global Escape handler binds once at DOMContentLoaded');

/* ---------- fixtures (scanner contract shape only) ---------- */
const P = (overrides = {}) => Object.assign({
    name: 'Kirkland Test Product',
    asin: 'B0TEST0001',
    amazon_price: 48.87,
    costco_cost: 15.99,
    weight_lbs: 3.5,
    fba_fee: 7.10,
    net_profit: 17.0,
    roi_pct: 106.3,
    profit_tier: 11,
    total_sellers: 5,
    fba_sellers: 2,
    monthly_sales_estimate: 1500,
    monthly_sales_estimated: true,
    verdict: 'Pass',
}, overrides);

const setState = (products, status, costcoCatalog, costcoDiscovery) => {
    vm.runInContext(`
        scoutState = {
            status: ${JSON.stringify(status || 'ok')},
            generatedAt: '2026-01-01T00:00:00Z',
            tierFound: null,
            costcoCatalog: ${JSON.stringify(costcoCatalog === undefined ? 'ready' : costcoCatalog)},
            costcoDiscovery: ${JSON.stringify(costcoDiscovery === undefined ? null : costcoDiscovery)},
            products: ${JSON.stringify(products)},
        };
        currentFilters = NS.defaultFilters();
        currentFilters.minProfit = null;
        currentFilters.minRoi = null;
        sortKey = 'profit_desc';
        NS.renderScout();
    `, context, { filename: 'setState' });
};

/* build an explicit filter object (defaults + overrides) for pure tests */
const filtersFor = (overrides) => {
    const d = vm.runInContext('NS.defaultFilters()', context);
    return Object.assign({}, d, {
        minProfit: null, minRoi: null, minSales: null, maxFba: null,
    }, overrides);
};

/* ================================================================
 * Phase 1b — previous run auto-loads every session (no refresh)
 * ================================================================ */
/* The key product data changes rarely, so every page load must render the
 * last known scan from the local snapshot instantly — no refresh tap needed,
 * no provider round-trip. The follow-up GET is the cache-only scanner route
 * (zero provider calls); staleness is surfaced honestly, never erased. */
store['t2.kirklandScout.scan.v1'] = JSON.stringify({
    saved_at: '2026-09-03T07:00:00Z',
    payload: {
        status: 'ok',
        generated_at: '2026-09-03T07:00:00Z',
        summary: { cache_status: 'fresh_snapshot', scanner_mode: 'cache_only', enrichment_source: 'off' },
        products: [P({ name: 'Last Run Product', asin: 'B0AUTO0001' })],
    },
});
vm.runInContext('NS.loadScanner()', context);
assert(els.tableBody.innerHTML.includes('Last Run Product'), 'autoload: last run renders instantly from the local snapshot');
assert(vm.runInContext('scoutState.dataFromCache', context) === true, 'autoload: state is honestly flagged as from-cache');
assert(els.resultCount.textContent.includes('1 of 1'), 'autoload: result counter reflects the cached snapshot');
assert(!els.tableBody.innerHTML.includes('skeleton'), 'autoload: no loading skeleton when a snapshot exists');

/* ================================================================
 * Phase 2 — structure, theme shell, honest states
 * ================================================================ */
/* Brand contract updated 2026-09-04 with the Retail Arbitrage UI redesign
   (commit 016ac58): operator directed a rebrand — "Northstar OS" is the product
   brand, "Retail Arbitrage" is the service, "Amazon FBA sourcing suite" is the
   context line. This replaces the old "T2 Holdings / Kirkland Product Scout"
   chrome. Deliberate contract change, not a test relaxation. */
assert(html.includes('Northstar OS') && html.includes('Retail Arbitrage') && html.includes('Amazon FBA sourcing suite'), 'sidebar brand: Northstar OS / Retail Arbitrage / Amazon FBA sourcing suite');
['Product Scout', 'Margin Calculator', 'Risk Engine', 'Cycle Planner', 'Portfolio'].forEach((label) => {
    assert(html.includes('>' + label + '</span>'), 'nav item present: ' + label);
});

const scoutTableHtml = html.slice(html.indexOf('id="scoutTable"'), html.indexOf('</table>', html.indexOf('id="scoutTable"')) + 8);
const headers = (scoutTableHtml.match(/<th scope="col"[^>]*>([^<]+)/g) || []).map((h) => h.replace(/<[^>]+>/g, '').replace('sticky-col', '').trim());
assert(JSON.stringify(headers) === JSON.stringify(
    ['Product', 'ASIN', 'Amazon Price', 'Costco COGS', 'FBA Fee', 'Net Profit', 'ROI', 'Score', 'Competition', 'Sellers', 'Buy Box', 'Est. Monthly Sales', 'Tier', 'Status', 'Gate', 'Action']
), 'scout table headers exactly 16: Product, ASIN, Amazon Price, Costco COGS, FBA Fee, Net Profit, ROI, Score, Competition, Sellers, Buy Box, Est. Monthly Sales, Tier, Status, Gate, Action');
assert(scoutTableHtml.includes('colspan="16"'), 'scout table has colspan="16" header row');
assert(!scoutTableHtml.includes('Weight'), 'no Weight column in scout table');
assert(scoutTableHtml.includes('data-sort="name_asc"'), 'Product header is sortable asc (name_asc)');
assert(scoutTableHtml.includes('data-sort="asin_asc"'), 'ASIN header is sortable asc (asin_asc)');
assert(scoutTableHtml.includes('data-sort="cost_desc"'), 'Costco COGS header sorts by cost desc');
assert(scoutTableHtml.includes('Est. Monthly Sales is a provider estimate, not verified sales'), 'Est. Monthly Sales header carries honest estimate qualifier');
assert(html.includes('data-theme="dark"'), 'default theme is dark');
assert(html.includes('themeToggle'), 'theme toggle button present');
assert(html.includes('Refresh scan'), '"Refresh scan" button label present');
assert(html.includes('Scout Filters'), 'filter panel heading present');
assert(html.includes('Showing 0 of 0 candidates'), 'result count placeholder present');

/* ================================================================
   Phase 2c — Product Focus Mode
   ================================================================ */

assert(html.includes('id="csViewFocus"'), 'focus toggle button present in control strip');

/* Phase 2c executable Product Focus behavior tests were relocated to a
   dedicated Phase 18 section at the end of this file so they run after the
   full VM/DOM/UI initialization, with a loaded product collection and after
   the fetchCalls tracker is defined. The static structure assertion remains
   immediately above. */

const mockNames = ['K-Cups (120ct)', 'Minoxidil Foam', 'Roasted Almonds', 'Vitamin D3'];
assert(!mockNames.some((n) => html.includes(n)), 'no hardcoded mock products in static HTML');

/* loading state pill */
vm.runInContext(`scoutState = { status: 'loading', generatedAt: null, tierFound: null, products: [] }; NS.renderScout();`, context);
assert(els.statusPill.className.includes('loading') && els.statusPillText.textContent === 'Loading', 'status pill shows Loading');
assert(els.bannerTitle.textContent === 'Loading Kirkland candidates…', 'loading banner text exact');
assert(els.tableBody.innerHTML.includes('skeleton'), 'table shows skeleton while loading');

/* no_candidates state — costco catalog ready */
setState([], 'no_candidates', 'ready');
assert(els.bannerTitle.textContent === 'No matching products found.', 'no_candidates banner title exact (catalog ready)');
assert(els.bannerSub.textContent.includes('item_name,costco_cost rows to data/costco-items.csv'), 'no_candidates supporting text exact (catalog ready)');
assert(els.statusPill.className.includes('empty') && els.statusPillText.textContent === 'No candidates', 'pill shows No candidates');

/* no_candidates state — costco catalog empty/missing */
setState([], 'no_candidates', 'empty');
assert(els.bannerTitle.textContent === 'Costco cost data unavailable.', 'no_candidates banner title exact (catalog empty)');
assert(els.bannerSub.textContent.includes('item_name,costco_cost'), 'no_candidates supporting text exact (catalog empty)');
assert(els.tableBody.innerHTML.includes('Costco cost data unavailable.'), 'no_candidates table state block exact (catalog empty)');

/* no_candidates state — costco catalog ready shows matching-specific copy */
setState([], 'no_candidates', 'ready');
assert(els.tableBody.innerHTML.includes('none matched the Costco catalog'), 'no_candidates table state block exact (catalog ready)');

/* upstream_unavailable state */
setState([], 'upstream_unavailable');
assert(els.bannerTitle.textContent === 'Live product data is temporarily unavailable.', 'upstream_unavailable banner title exact');
assert(els.statusPill.className.includes('unavailable') && els.statusPillText.textContent === 'Data source unavailable', 'pill shows Data source unavailable');
assert(els.tableBody.innerHTML.includes('No sourcing recommendation is being displayed.'), 'unavailable table state text exact');

/* upstream_unavailable with Scavio 402 hint (credit exhaustion) */
vm.runInContext(`
    scoutState = {
        status: 'upstream_unavailable',
        generatedAt: null,
        tierFound: null,
        costcoCatalog: 'ready',
        costcoDiscovery: null,
        upstreamHint: 'Scavio credit balance is 0. Top up credits at https://dashboard.scavio.dev/billing and try again.',
        products: [],
    };
    currentFilters = NS.defaultFilters();
    sortKey = 'profit_desc';
    NS.renderScout();
`, context, { filename: 'setState402' });
assert(els.bannerSub.textContent.includes('Scavio credit balance is 0'), '402 hint renders in banner sub');
assert(els.tableBody.innerHTML.includes('dashboard.scavio.dev/billing'), '402 hint renders in table state block');

/* scan data cache: last good scan renders instantly and survives refresh failure */
vm.runInContext(`localStorage.removeItem('t2.kirklandScout.scan.v1');`, context);
const cachePayload = {
    status: 'ok',
    generated_at: '2026-08-14T10:00:00Z',
    summary: { candidates_returned: 2, tier_found: 11, costco_catalog: 'ready', costco_discovery: null },
    products: [P(), P({ asin: 'B0CACHED002', name: 'Cached Second Item' })],
};
vm.runInContext('NS.saveScanCache(' + JSON.stringify(cachePayload) + ')', context);
let cached = vm.runInContext('NS.loadScanCache()', context);
assert(cached && cached.payload.products.length === 2 && cached.savedAt === '2026-08-14T10:00:00Z', 'scan cache round-trips with saved_at');
vm.runInContext(`scoutState = { status: 'loading', products: [] }; scoutState.cacheSavedAt = '2026-08-14T10:00:00Z'; NS.applyScanData(${JSON.stringify(cachePayload)}, true);`, context);
assert(els.bannerTitle.textContent === 'Showing last scan data', 'cached banner title exact');
assert(els.bannerSub.textContent.includes('refreshing in the background'), 'cached banner notes background refresh');
assert(els.tableBody.innerHTML.includes('Cached Second Item'), 'cached products render immediately on load');
assert(els.resultCount.textContent === 'Showing 2 of 2 candidates', 'cached result count correct');
vm.runInContext(`scoutState.cacheStale = true; scoutState.upstreamHint = 'Amazon is temporarily blocking searches for Chocodata.'; NS.renderScout();`, context);
assert(els.bannerTitle.textContent === 'Showing last scan data', 'stale-cache banner keeps last-scan title');
assert(els.bannerSub.textContent.includes('Live refresh is temporarily unavailable'), 'stale-cache banner explains live refresh failure');
assert(els.bannerSub.textContent.includes('Chocodata'), 'stale-cache banner carries the live failure hint');
assert(els.tableBody.innerHTML.includes('Cached Second Item'), 'products stay visible when live refresh fails');
assert(els.statusPill.className.includes('live') && els.statusPillText.textContent === 'Live data ready', 'pill stays Live data ready while showing cached data');
vm.runInContext('NS.saveScanCache(null)', context);
assert(vm.runInContext('NS.loadScanCache()', context) === null, 'corrupt/empty cache returns null');

/* network error state */
setState([], 'error');
assert(els.bannerTitle.textContent === 'Unable to load the scanner.', 'error banner title exact');
assert(els.tableBody.innerHTML.includes('Retry'), 'error state has Retry action');

/* catalog freshness line (costco_discovery) */
const discoveryFresh = {
    freshness: 'fresh',
    last_run_at: '2026-08-16T03:00:00Z',
    last_fetched_count: 24,
    status: 'ok',
    stop_reason: null,
    location: { delivery_zip: '75201', business_center: 'Dallas Business Center' },
};
setState([], 'no_candidates', 'ready', discoveryFresh);
assert(els.catalogFreshness.hidden === false, 'freshness line visible when discovery data present');
assert(els.catalogFreshness.textContent.includes('Costco online discovery: fresh'), 'fresh run labeled fresh');
assert(els.catalogFreshness.textContent.includes('24 items') && els.catalogFreshness.textContent.includes('75201'), 'freshness line carries fetched count and delivery ZIP');

const discoveryBlocked = {
    freshness: 'stale',
    last_run_at: '2026-08-09T03:00:00Z',
    last_fetched_count: 0,
    status: 'failed',
    stop_reason: 'blocked',
    location: { delivery_zip: '75201', business_center: 'Dallas Business Center' },
};
setState([], 'no_candidates', 'ready', discoveryBlocked);
assert(els.catalogFreshness.textContent.includes('STALE'), 'blocked/rate-limited run labeled STALE');
assert(els.catalogFreshness.textContent.includes('stop reason blocked'), 'stale label carries the stop reason');
assert(els.catalogFreshness.textContent.includes('confirm at the Business Center'), 'stale label warns to confirm before purchase');

setState([], 'no_candidates', 'ready', null);
assert(els.catalogFreshness.hidden === true, 'freshness line hidden when no discovery data');

/* ================================================================
 * Phase 3 — live contract rendering
 * ================================================================ */
const full = [P(), P({
    asin: 'B0TEST0002', name: 'Second Product', net_profit: 9.5, roi_pct: 55.1,
    profit_tier: 9, fba_sellers: 8, monthly_sales_estimate: null,
    monthly_sales_estimated: true, verdict: null,
})];
setState(full);
assert(els.resultCount.textContent === 'Showing 2 of 2 candidates', 'result count correct');
assert(els.kpiCandidates.textContent === '2', 'KPI candidates = visible count');
assert(els.kpiQualified.textContent === '1', 'KPI qualified = verdict Pass count');
assert(els.kpiAvgProfit.textContent === '$13.25', 'KPI average net profit correct');
assert(els.kpiBest.textContent === 'Kirkland Test Product', 'KPI best candidate = top of sort');

const out = els.tableBody.innerHTML;
assert(out.includes('$48.87') && out.includes('$15.99') && out.includes('$7.10'), 'currency cells rendered');
assert(out.includes('106.3%'), 'ROI percentage rendered');
assert(out.includes('Total: 5 · FBA: 2'), 'competition cell "Total: X · FBA: Y"');
assert(out.includes('Unknown') && out.includes('Estimated'), 'unknown sales renders "Unknown" and estimated chip present');
assert(out.includes('>Pass<'), 'status badge Pass');
assert(out.includes('Unscored'), 'null verdict renders Unscored');
assert(out.includes('$11+') && out.includes('$9+'), 'tier badges render');

/* fee-less candidates stay visible with honest Unavailable labels + review status */
const noFee = [P({ asin: 'B0TEST0003', name: 'No Fee Item', fba_fee: null, net_profit: null, roi_pct: null, profit_tier: null, verdict: 'Needs Fee Verification' })];
setState(noFee, 'ok', 'ready');
const noFeeOut = els.tableBody.innerHTML;
assert(noFeeOut.includes('No Fee Item'), 'candidate without FBA fee still rendered');
assert((noFeeOut.match(/Unavailable/g) || []).length === 3, 'fee, net profit, ROI all render Unavailable (never $0/—)');
assert(noFeeOut.includes('FBA fee not yet verified'), 'Unavailable cells carry the honest fee-verification title');
assert(noFeeOut.includes('Needs Fee Verification'), 'fee-less candidate carries Needs Fee Verification status badge');
assert(!noFeeOut.includes('Unscored') && !noFeeOut.includes('>Pass<'), 'fee-less candidate is not Unscored and never labeled Pass');
assert(!noFeeOut.includes('$0.00'), 'no fabricated $0 values for unknown fee fields');
assert(els.kpiQualified.textContent === '0', 'Needs Fee Verification products never count as qualified');
setState(full);
assert(els.kpiQualified.textContent === '1', 'qualified KPI counts Pass only');

/* candidate without a Costco match stays visible: cost cell renders Unavailable */
const noCostco = [P({ asin: 'B0TEST0006', name: 'No Catalog Match Item', costco_cost: null, fba_fee: null, net_profit: null, roi_pct: null, profit_tier: null, verdict: 'Needs Fee Verification' })];
setState(noCostco, 'ok', 'ready');
const noCostcoOut = els.tableBody.innerHTML;
assert(noCostcoOut.includes('No Catalog Match Item'), 'candidate without Costco cost still rendered');
assert(noCostcoOut.includes('No Costco cost on record'), 'cost cell Unavailable carries honest title');
assert((noCostcoOut.match(/Unavailable/g) || []).length === 4, 'cost, fee, net profit, ROI all render Unavailable');
assert(!noCostcoOut.includes('$0.00'), 'no fabricated $0 for missing Costco cost');
setState(full);

/* candidate with no Amazon price: Price cell renders Unavailable (never $0.00 or a bare dash) */
const noPrice = [P({ asin: 'B0TEST0007', name: 'No Price Item', amazon_price: null })];
setState(noPrice, 'ok', 'ready');
const noPriceOut = els.tableBody.innerHTML;
assert(noPriceOut.includes('No Price Item'), 'candidate without Amazon price still rendered');
assert(noPriceOut.includes('No Amazon price on record'), 'price cell Unavailable carries honest title');
assert(!noPriceOut.includes('$0.00'), 'no fabricated $0.00 for missing Amazon price');
assert(!noPriceOut.includes('data-col="price">—'), 'price cell never renders a bare dash for missing price');
/* legacy cached scan data may carry amazon_price 0 — treated as missing, never $0.00 */
const zeroPrice = [P({ asin: 'B0TEST0008', name: 'Zero Price Item', amazon_price: 0 })];
setState(zeroPrice, 'ok', 'ready');
const zeroPriceOut = els.tableBody.innerHTML;
assert(zeroPriceOut.includes('No Amazon price on record'), 'zero price cell renders Unavailable (defensive)');
assert(!zeroPriceOut.includes('$0.00'), 'zero price never renders $0.00');
setState(full);

/* calculator-only fields must never render */
['projected_net_profit', 'projected_roi_pct', 'financial_status', 'financial_decision_status',
 'financial_data_gaps', 'amazon_fees_total', 'amazon_payout_before_inventory_costs',
 'prep_cost', 'inbound_shipping_cost', 'landed_cost', 'cogs', 'lowest_price', 'highest_price',
 'fba_seller_preference', 'source', 'invoice', 'authorization'].forEach((f) => {
    assert(!out.includes(f), 'calculator-only/internal field absent from table render: ' + f);
});

/* empty filter result state */
vm.runInContext(`currentFilters.minProfit = 999; NS.renderScout();`, context);
assert(els.tableBody.innerHTML.includes('No candidates match your filters.'), 'filtered-empty state message');
vm.runInContext(`currentFilters = NS.defaultFilters(); NS.renderScout();`, context);

/* enrichment provenance renders per product */
const provProducts = [
    P({ asin: 'B0TEST0004', name: 'Enriched Item', offer_data_provider: 'easyparser', enrichment_status: 'complete', enriched_at: '2026-08-13T10:00:00Z' }),
    P({ asin: 'B0TEST0005', name: 'Offline Item', offer_data_provider: 'offline', enrichment_status: 'offline_mode', enriched_at: null }),
];
setState(provProducts, 'ok', 'ready');
const provOut = els.tableBody.innerHTML;
assert(provOut.includes('easyparser · complete'), 'provenance chip renders provider and status');
assert(provOut.includes('Offer data source: easyparser'), 'provenance chip carries source title');
assert(!provOut.includes('offline · offline'), 'offline provider shows no provenance chip');
setState(full);

/* ================================================================
 * Phase 4 — filters and sorts (pure functions, no DOM needed)
 * ================================================================ */
const pool = [
    P({ name: 'Alpha', asin: 'B000000001', net_profit: 25, roi_pct: 140, fba_sellers: 1, weight_lbs: 1.2, monthly_sales_estimate: 3000, profit_tier: 11 }),
    P({ name: 'Beta', asin: 'B000000002', net_profit: 12, roi_pct: 90, fba_sellers: 4, weight_lbs: 8.0, monthly_sales_estimate: 800, profit_tier: 9 }),
    P({ name: 'Gamma', asin: 'B000000003', net_profit: 6, roi_pct: 40, fba_sellers: 10, weight_lbs: 2.0, monthly_sales_estimate: null, profit_tier: null, verdict: null }),
    P({ name: 'Delta', asin: 'B000000004', net_profit: 4, roi_pct: 25, fba_sellers: null, weight_lbs: 0.5, monthly_sales_estimate: 200, profit_tier: null, verdict: 'Hold' }),
];

let f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minProfit: 11 })) + ')', context);
assert(f.length === 2 && f[0].asin === 'B000000001', 'minProfit filter keeps only >= 11');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minRoi: 100 })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'minROI filter');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ maxRoi: 95 })) + ')', context);
assert(f.length === 3 && !f.some((p) => p.asin === 'B000000001'), 'maxROI filter caps high ROI, keeps the rest');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minRoi: 50, maxRoi: 100 })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000002', 'min+max ROI band filter');

assert(vm.runInContext('NS.defaultFilters().maxRoi', context) === null, 'defaultFilters: maxRoi is null (no default ROI cap)');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minSales: 1000, includeUnknownSales: true })) + ')', context);
assert(f.length === 2 && f.some((p) => p.asin === 'B000000003'), 'unknown sales included when toggle on (never treated as zero)');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minSales: 1000, includeUnknownSales: false })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'unknown sales excluded when toggle off');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ maxFba: 3, includeUnknownFba: true })) + ')', context);
assert(f.length === 2 && f.some((p) => p.asin === 'B000000004'), 'unknown FBA count included when toggle on');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ maxFba: 3, includeUnknownFba: false })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'unknown FBA count excluded when toggle off');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ tier: "9" })) + ')', context);
assert(f.length === 2 && f.every((p) => p.profit_tier !== null && p.profit_tier >= 9), 'tier $9+ includes 11 and 9, excludes below');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ tier: "11" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'tier $11+ only');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ status: "Unscored" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000003', 'status Unscored matches null verdicts');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ status: "Pass" })) + ')', context);
assert(f.length === 2 && f.every((p) => p.verdict === 'Pass'), 'status Pass matches only Pass');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ search: "b000000003" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000003', 'ASIN search works');

f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ search: "delta" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000004', 'name search works');

const before = pool.length;
vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', ' + JSON.stringify(filtersFor({ minProfit: 11 })) + ')', context);
assert(pool.length === before, 'filterProducts never mutates the source list');

let sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "profit_desc")', context);
assert(sorted.map((p) => p.net_profit).join(',') === '25,12,6,4', 'sort profit_desc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "sales_desc")', context);
assert(sorted.map((p) => p.monthly_sales_estimate).join(',') === '3000,800,200,', 'sort sales_desc with null last');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "fba_asc")', context);
assert(sorted[0].asin === 'B000000001' && sorted[sorted.length - 1].asin === 'B000000004', 'sort fba_asc nulls last');
assert(!html.includes('weight_asc'), 'no weight sort option remains');

/* new asc/desc + name/asin/cost/price sort keys (nulls always last) */
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "profit_asc")', context);
assert(sorted.map((p) => p.net_profit).join(',') === '4,6,12,25', 'sort profit_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "roi_asc")', context);
assert(sorted.map((p) => p.roi_pct).join(',') === '25,40,90,140', 'sort roi_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "sales_asc")', context);
assert(sorted.map((p) => p.monthly_sales_estimate).join(',') === '200,800,3000,', 'sort sales_asc with null last');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "fba_desc")', context);
assert(sorted[0].asin === 'B000000003' && sorted[sorted.length - 1].asin === 'B000000004', 'sort fba_desc nulls last');
const pcPool = [
    P({ name: 'Zulu', asin: 'B000000009', amazon_price: 55, costco_cost: 25 }),
    P({ name: 'Alpha', asin: 'B000000001', amazon_price: 10, costco_cost: 3 }),
    P({ name: 'Mike', asin: 'B000000005', amazon_price: 33, costco_cost: 12 }),
    P({ name: 'Beta', asin: 'B000000002', amazon_price: 22, costco_cost: 8 }),
];
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "price_asc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000001,B000000002,B000000005,B000000009', 'sort price_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "price_desc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000009,B000000005,B000000002,B000000001', 'sort price_desc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "cost_asc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000001,B000000002,B000000005,B000000009', 'sort cost_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "cost_desc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000009,B000000005,B000000002,B000000001', 'sort cost_desc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "name_asc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000001,B000000002,B000000005,B000000009', 'sort name_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "name_desc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000009,B000000005,B000000002,B000000001', 'sort name_desc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "asin_asc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000001,B000000002,B000000005,B000000009', 'sort asin_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pcPool) + ', "asin_desc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000009,B000000005,B000000002,B000000001', 'sort asin_desc');
vm.runInContext('NS.opportunityScores = new Map([["B000000001", 90], ["B000000002", 70], ["B000000003", 50], ["B000000004", 30]])', context);
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "opp_asc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000004,B000000003,B000000002,B000000001', 'sort opp_asc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "opp_desc")', context);
assert(sorted.map((p) => p.asin).join(',') === 'B000000001,B000000002,B000000003,B000000004', 'sort opp_desc');
sorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(pool) + ', "bogus_key")', context);
assert(sorted[0].net_profit === 25, 'unknown sort key falls back to profit_desc');

/* localStorage defensive restore */
vm.runInContext(`localStorage.setItem('t2.kirklandScout.filters.v2', '{not valid json'); var f1 = NS.defaultFilters(); currentFilters = loadFilters();`, context);
assert(JSON.stringify(vm.runInContext('currentFilters', context)) === JSON.stringify(vm.runInContext('NS.defaultFilters()', context)), 'corrupt localStorage filters revert to defaults');
vm.runInContext(`localStorage.setItem('t2.kirklandScout.filters.v2', '{"minProfit":"oops","minRoi":15,"maxRoi":"banana","tier":"banana","includeUnknownSales":false}'); currentFilters = loadFilters();`, context);
const restored = vm.runInContext('currentFilters', context);
assert(restored.minProfit === null && restored.minRoi === 15 && restored.maxRoi === null && restored.tier === 'all' && restored.includeUnknownSales === false, 'defensive sanitization of bad stored filter values');

/* permissive defaults: no thresholds active, everything visible */
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(pool) + ', NS.defaultFilters())', context);
assert(f.length === 4, 'default filters show every candidate (no hidden thresholds)');

/* ================================================================
 * Phase 4b — Quick filters, active-filter summary, popover exports
 * ================================================================ */

/* Quick filter: Qualified sets status=Pass, single active filter */
vm.runInContext(`scoutState = { status: 'ok', generatedAt: null, tierFound: null, costcoCatalog: 'ready', products: ${JSON.stringify(pool)} };`, context);
vm.runInContext('NS.applyQuickFilter("Pass", undefined)', context);
assert(vm.runInContext('currentFilters.status', context) === 'Pass', 'quick filter: Qualified sets status=Pass');
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 1, 'quick filter: Qualified counts as single active filter');
f = vm.runInContext('NS.visibleRows()', context);
assert(f.length === 2, 'quick filter: Qualified keeps 2 Pass-verdict products (Gamma=null, Delta=Hold excluded)');

/* Quick filter: toggling same value again resets to defaults */
vm.runInContext('NS.applyQuickFilter("Pass", undefined)', context);
assert(vm.runInContext('currentFilters.status', context) === 'all', 'quick filter: toggling Qualified again resets to all');

/* Quick filter: Invoice Confirmed sets packMatch */
vm.runInContext('NS.applyQuickFilter(undefined, "invoice_confirmed")', context);
assert(vm.runInContext('currentFilters.packMatch', context) === 'invoice_confirmed', 'quick filter: Invoice Confirmed sets packMatch');
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 1, 'quick filter: Invoice Confirmed counts as single active filter');

/* Quick filter: toggling Invoice Confirmed again resets */
vm.runInContext('NS.applyQuickFilter(undefined, "invoice_confirmed")', context);
assert(vm.runInContext('currentFilters.packMatch', context) === 'all', 'quick filter: toggling Invoice Confirmed again resets');

/* Quick filter: Needs Mapping sets status */
vm.runInContext('NS.applyQuickFilter("Needs Mapping Verification", undefined)', context);
assert(vm.runInContext('currentFilters.status', context) === 'Needs Mapping Verification', 'quick filter: Needs Mapping sets status');
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 1, 'quick filter: Needs Mapping counts as single active filter');
vm.runInContext('NS.applyQuickFilter("Needs Mapping Verification", undefined)', context);

/* Quick filter: Needs Fee Verification sets status */
vm.runInContext('NS.applyQuickFilter("Needs Fee Verification", undefined)', context);
assert(vm.runInContext('currentFilters.status', context) === 'Needs Fee Verification', 'quick filter: Needs Fee Verification sets status');
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 1, 'quick filter: Needs Fee Verification counts as single active filter');
vm.runInContext('NS.applyQuickFilter("Needs Fee Verification", undefined)', context);

/* clearSingleFilter resets one key */
vm.runInContext('currentFilters.status = "Pass"; currentFilters.minProfit = 15;', context);
vm.runInContext('NS.clearSingleFilter("status")', context);
assert(vm.runInContext('currentFilters.status', context) === 'all', 'clearSingleFilter: status reset to all');
assert(vm.runInContext('currentFilters.minProfit', context) === 15, 'clearSingleFilter: minProfit untouched');

/* clearAllFilters resets everything */
vm.runInContext('NS.clearAllFilters()', context);
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 0, 'clearAllFilters: count returns 0');
assert(vm.runInContext('currentFilters.status', context) === 'all', 'clearAllFilters: status is all');
assert(vm.runInContext('currentFilters.packMatch', context) === 'all', 'clearAllFilters: packMatch is all');
assert(vm.runInContext('currentFilters.minProfit', context) === null, 'clearAllFilters: minProfit is null');

/* resetFilters also clears quick-filter state */
vm.runInContext('NS.applyQuickFilter("Pass", undefined)', context);
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 1, 'resetFilters pre-condition: 1 active filter');
vm.runInContext('NS.resetFilters()', context);
assert(vm.runInContext('NS.filterCount(currentFilters)', context) === 0, 'resetFilters: clears quick-filter state');

/* NS exports exist */
assert(typeof vm.runInContext('NS.applyQuickFilter', context) === 'function', 'NS.applyQuickFilter is exported');
assert(typeof vm.runInContext('NS.clearAllFilters', context) === 'function', 'NS.clearAllFilters is exported');
assert(typeof vm.runInContext('NS.clearSingleFilter', context) === 'function', 'NS.clearSingleFilter is exported');
assert(typeof vm.runInContext('NS.toggleFilters', context) === 'function', 'NS.toggleFilters is exported');
assert(typeof vm.runInContext('NS.resetFilters', context) === 'function', 'NS.resetFilters is exported');

/* ================================================================
 * Phase 5 — decision signals
 * ================================================================ */
const pool2 = [
    P({ asin: 'B100000001', name: 'Top', net_profit: 30, roi_pct: 200, fba_sellers: 1, monthly_sales_estimate: 5000, profit_tier: 11 }),
    P({ asin: 'B100000002', name: 'Mid', net_profit: 15, roi_pct: 100, fba_sellers: 3, monthly_sales_estimate: 1000, profit_tier: 9 }),
    P({ asin: 'B100000003', name: 'Low', net_profit: 8, roi_pct: 50, fba_sellers: 6, monthly_sales_estimate: 400, profit_tier: null }),
    P({ asin: 'B100000004', name: 'NoFba', net_profit: 20, roi_pct: 120, fba_sellers: null, monthly_sales_estimate: 200, profit_tier: 11 }),
];

vm.runInContext(`
        scoutState = { status: 'ok', generatedAt: null, tierFound: null, products: ${JSON.stringify(pool2)} };
        currentFilters = NS.defaultFilters();
        currentFilters.minProfit = null;
        sortKey = 'profit_desc';
        NS.renderScout();
`, context);

const opp = vm.runInContext('NS.opportunityScores', context);
assert(opp.get('B100000004') === null, 'no opportunity score when FBA sellers unknown');
assert(typeof opp.get('B100000001') === 'number' && opp.get('B100000001') === 100, 'top product scores 100');
assert(opp.get('B100000003') < opp.get('B100000002') && opp.get('B100000002') < opp.get('B100000001'), 'score orders by relative strength');

const stripHtml = els.oppList.innerHTML;
assert(stripHtml.includes('Top opportunities') === false || stripHtml.includes('#1'), 'opportunity strip renders ranked cards');
assert(stripHtml.includes('Opportunity Score — directional'), 'score label exact: "Opportunity Score — directional"');
assert((stripHtml.match(/data-analyze=/g) || []).length === 3, 'strip shows at most three products');
assert(!stripHtml.includes('B100000004'), 'insufficient-data product not ranked in strip');

/* filtered population drives scores */
vm.runInContext(`currentFilters.minRoi = 60; NS.renderScout();`, context);
const oppFiltered = vm.runInContext('NS.opportunityScores', context);
assert(oppFiltered.get('B100000001') === 100, 'score population = filtered candidates only');

/* competition labels */
const cl = (n) => vm.runInContext('NS.competitionLabel(' + JSON.stringify(n) + ')', context);
assert(cl(0) === 'No FBA sellers reported', 'competition label 0');
assert(cl(2) === 'Low FBA competition', 'competition label 1-2');
assert(cl(5) === 'Moderate FBA competition', 'competition label 3-5');
assert(cl(9) === 'High FBA competition', 'competition label 6+');
assert(cl(null) === 'FBA competition unknown', 'competition label null');

/* status labels */
assert(vm.runInContext('NS.statusLabel(null)', context) === 'Unscored', 'null verdict displays Unscored, not Reject');
assert(vm.runInContext('NS.statusLabel("Reject")', context) === 'Reject', 'Reject displays as Reject');
assert(vm.runInContext('NS.statusLabel("Needs Fee Verification")', context) === 'Needs Fee Verification', 'Needs Fee Verification displays as its own status');
assert(html.includes('value="Needs Fee Verification"'), 'status filter offers Needs Fee Verification');

/* status filter matches the review state */
const reviewPool = [
    P({ asin: 'B300000001', name: 'Qualified One', fba_fee: 7, net_profit: 25, roi_pct: 120, verdict: 'Pass' }),
    P({ asin: 'B300000002', name: 'Review One', fba_fee: null, net_profit: null, roi_pct: null, verdict: 'Needs Fee Verification' }),
];
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(reviewPool) + ', ' + JSON.stringify(filtersFor({ status: "Needs Fee Verification" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B300000002', 'status Needs Fee Verification matches review-state products');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(reviewPool) + ', ' + JSON.stringify(filtersFor({ status: "Pass" })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B300000001', 'status Pass excludes review-state products');

/* ================================================================
 * Phase 5b — hover preview on .prod-name (progressive enhancement)
 * ================================================================ */
setState([P({ asin: 'B400000040', name: 'Preview Test Product', amazon_price: 42.50, costco_cost: 18.00, net_profit: 12.75, roi_pct: 70.8, verdict: 'Pass', pack_match: 'exact' })], 'ok', 'ready');
const previewHtml = els.tableBody.innerHTML;
assert(previewHtml.includes('ns-preview-card'), 'hover preview: ns-preview-card present in product cell');
assert(previewHtml.includes('Preview Test Product'), 'hover preview: full product name in preview card');
assert(previewHtml.includes('ASIN: B400000040'), 'hover preview: ASIN in preview card');
assert(previewHtml.includes('$42.50'), 'hover preview: Amazon price in preview card');
assert(previewHtml.includes('$18.00'), 'hover preview: Costco COGS in preview card');
assert(previewHtml.includes('$12.75'), 'hover preview: net profit in preview card');
assert(previewHtml.includes('70.8%'), 'hover preview: ROI in preview card');
assert(previewHtml.includes('Pass'), 'hover preview: status badge in preview card');

/* Accessibility: no contradictory role=tooltip + aria-hidden */
assert(!previewHtml.includes('role="tooltip"'), 'hover preview: no role=tooltip (plain supplemental container)');
assert(!previewHtml.includes('aria-hidden="true"'), 'hover preview: no aria-hidden (not hidden from AT)');

/* Overflow: sticky-col retains overflow:hidden globally */
assert(html.includes('.sticky-col {') && html.includes('overflow: hidden'), 'hover preview: .sticky-col retains overflow:hidden globally');
assert(html.includes('.sticky-col.preview-open'), 'hover preview: scoped .preview-open class exists');

/* Non-interactive: pointer-events none, no fetch trigger */
assert(html.includes('pointer-events: none'), 'hover preview: card is non-interactive (pointer-events none)');
assert(!previewHtml.includes('fetch'), 'hover preview: no network request in preview');

/* Touch/mobile: preview suppressed */
assert(html.includes('@media (pointer: coarse)'), 'hover preview: touch/coarse-pointer suppression rule exists');
assert(html.includes('@media (max-width: 900px)'), 'hover preview: mobile breakpoint suppression rule exists');

/* No stale state: Escape/focus-leave removes preview-open via focusout handler */
assert(html.includes('focusout'), 'hover preview: focusout handler removes preview-open class');
assert(html.includes('mouseout'), 'hover preview: mouseout handler removes preview-open class');
setState(full);

/* ================================================================
 * Phase 6 — Margin Calculator
 * ================================================================ */
assert(html.includes('Manual unit-economics calculator. Values entered here do not alter Scout source-cost data.'), 'calc callout text exact');
/* The Retail Arbitrage redesign (016ac58) added the Profit Calculator view
   between the Margin Calculator and Risk Engine views. The Profit Calculator
   legitimately has package weight/dimension inputs (pcWeight etc.), which the
   Margin Calculator does not. Scope this slice to end before the Profit
   Calculator so Phase 6 asserts the Margin Calculator contract only. */
const calcSectionHtml = html.slice(html.indexOf('id="view-calculator"'), html.indexOf('id="view-profit"'));
assert((calcSectionHtml.match(/What's this\?/g) || []).length === 7, 'tooltip ("What\'s this?") on every calc input (7 found, no weight field)');
assert(!calcSectionHtml.includes('cWeight'), 'no weight input remains in calculator (Margin Calculator contract)');
/* Positive contract for the new Profit Calculator page: weight + dimensions
   are required inputs mirroring fee_calculator.py (FBA_STANDARD_SIZE_TIER_TABLE
   and the 20 lb / 18x14x8 standard-size envelope check). */
const profitSectionHtml = html.slice(html.indexOf('id="view-profit"'));
assert(profitSectionHtml.includes('id="pcWeight"') && profitSectionHtml.includes('id="pcDimL"') && profitSectionHtml.includes('id="pcDimW"') && profitSectionHtml.includes('id="pcDimH"'), 'profit calculator has weight + dimension inputs (mirrors fee_calculator.py)');
assert(html.includes('id="cReferral"') && html.includes('value="15"'), 'referral fee defaults to 15%');

const cr = (f) => vm.runInContext('NS.calcRun(' + JSON.stringify(f) + ')', context);
let c = cr({ price: 48.87, cogs: 15.99, referralPct: 15, fbaFee: 7.10, prep: 1, inbound: 2 });
assert(Math.abs(c.referral - 7.3305) < 0.001 && Math.abs(c.totalFees - 17.4305) < 0.001, 'calcRun: referral + total fees math');
assert(Math.abs(c.grossMargin - 32.88) < 0.001, 'calcRun: gross margin math');
assert(Math.abs(c.netProfit - 15.4495) < 0.001, 'calcRun: estimated net profit math');
assert(Math.abs(c.roi - 81.36) < 0.05, 'calcRun: ROI math (81.36%)');
c = cr({ price: 48.87, cogs: null });
assert(c.grossMargin === null && c.netProfit === null && c.roi === null, 'calcRun: missing inputs produce nulls, never zeros');
c = cr({ price: 40, cogs: 30, referralPct: 15, fbaFee: 10, prep: 0, inbound: 0 });
assert(c.netProfit < 0 && isFinite(c.roi), 'calcRun: below break-even shows negative net profit');

/* Analyze prefill (limit: name, costco cost, sale price, FBA fee) */
const calcTarget = P({ asin: 'B200000001', name: 'Kirkland Breakfast Bars', amazon_price: 50, costco_cost: 20, weight_lbs: 3.2, fba_fee: 7, net_profit: 15, roi_pct: 75, profit_tier: 9 });
vm.runInContext(`scoutState = { status: 'ok', generatedAt: null, tierFound: null, costcoCatalog: 'ready', products: [${JSON.stringify(calcTarget)}] }; NS.analyzeProduct('B200000001');`, context);
assert(els['view-calculator'].hidden === false, 'Analyze opens the Margin Calculator view');
assert(els.cName.value === 'Kirkland Breakfast Bars', 'prefill: product name');
assert(els.cCogs.value === '20', 'prefill: Costco source cost');
assert(els.cPrice.value === '50', 'prefill: Amazon sale price');
assert(els.cFbaFee.value === '7', 'prefill: FBA fee');
assert(els.calcPrefillBar.hidden === false, 'prefill bar visible after Analyze');
assert(els.calcPrefillChip.textContent === 'Prefilled from Scout: Kirkland Breakfast Bars', 'prefill chip text');
assert(els.cReferral.value === '', 'prefill does NOT touch referral fee (manual field)');
assert(els.cGrossMargin.textContent === '$30.00', 'results render gross margin after prefill');
assert(els.cNetProfit.textContent === '$15.50', 'results render net profit after prefill');
assert(els.cRoi.textContent === '77.5%', 'results render ROI after prefill');

/* Analyze prefill without an FBA fee: fields still prefill, fee stays blank */
const noFeeTarget = P({ asin: 'B200000002', name: 'No Fee Bars', amazon_price: 50, costco_cost: 20, fba_fee: null, net_profit: null, roi_pct: null, profit_tier: null, verdict: null });
vm.runInContext(`scoutState = { status: 'ok', generatedAt: null, tierFound: null, costcoCatalog: 'ready', products: [${JSON.stringify(noFeeTarget)}] }; NS.analyzeProduct('B200000002');`, context);
assert(els.cName.value === 'No Fee Bars' && els.cCogs.value === '20' && els.cPrice.value === '50', 'prefill without fee: name/cogs/price filled');
assert(els.cFbaFee.value === '', 'prefill without fee: FBA fee left blank (never $0/fabricated)');

vm.runInContext('clearCalcPrefill()', context);
assert(els.cName.value === '' && els.cCogs.value === '' && els.cPrice.value === '' && els.cFbaFee.value === '', 'Clear Scout Prefill empties the four prefilled fields');
assert(els.calcPrefillBar.hidden === true, 'Clear Scout Prefill hides the prefill bar');
assert(els.cGrossMargin.textContent === '—', 'results reset after clearing prefill');
assert(els.cCalcNote.textContent.includes('Fill in sale price and source cost'), 'empty-state note exact');

/* ================================================================
 * Phase 7 — Risk Engine / Cycle Planner / Portfolio
 * ================================================================ */
assert(html.includes('Scenario input tool. Scores depend on your assumptions.'), 'risk engine callout exact');
assert(html.includes('Replenishment planning from your calculator assumptions. Estimates only.'), 'cycle planner callout exact');
assert(html.includes('Demo / scenario portfolio until connected to live scanner data.'), 'portfolio callout exact');

const riskRun = (f) => vm.runInContext('NS.riskRun(' + JSON.stringify(f) + ')', context);
let rr = riskRun({ sales: 500, fbaSellers: 1, profitPerUnit: 15 });
assert(rr.score === 'Low' && rr.points === 0, 'risk: healthy assumptions score Low');
rr = riskRun({ sales: 30, fbaSellers: 9, profitPerUnit: 3 });
assert(rr.score === 'High' && rr.points === 3, 'risk: thin demand + crowded + thin margin score High');
rr = riskRun({ sales: 100, fbaSellers: 4, profitPerUnit: 7 });
assert(rr.score === 'Moderate' && rr.points === 1.5, 'risk: mid assumptions score Moderate');
rr = riskRun({});
assert(rr.score === 'Moderate' && rr.points === 1.5 && rr.reasons.length === 3, 'risk: unknown fields each add 0.5 and are explained');
assert(riskRun({ sales: 500, fbaSellers: 1, profitPerUnit: 15 }).reasons.length === 3, 'risk: reasons list every factor');

const cycleRun = (f) => vm.runInContext('NS.cycleRun(' + JSON.stringify(f) + ')', context);
let cr2 = cycleRun({ monthlySales: 304, stock: 100, leadDays: 5, safetyStock: 10, batchSize: 60 });
assert(Math.abs(cr2.daily - 10) < 0.001 && Math.abs(cr2.cover - 10) < 0.001, 'cycle: daily rate = monthly / 30.4 and cover math');
assert(Math.abs(cr2.reorder - 60) < 0.001 && cr2.trigger === false && cr2.next === 0, 'cycle: stock above reorder point → no order');
cr2 = cycleRun({ monthlySales: 304, stock: 50, leadDays: 5, safetyStock: 10, batchSize: 60 });
assert(cr2.trigger === true && cr2.next === 60, 'cycle: at/below reorder point → trigger and batch order');
cr2 = cycleRun({});
assert(cr2.daily === null && cr2.cover === null && cr2.reorder === null && cr2.trigger === null && cr2.next === 0, 'cycle: missing sales produces nulls, never zeros');

vm.runInContext(`portfolio = []; renderPortfolio();`, context);
assert(els.portTable.hidden === true && els.portEmpty.hidden === false, 'portfolio: empty state by default');
assert(vm.runInContext('NS.addPortfolio("Kirkland Coffee", 10, 25.5)', context) === true, 'portfolio: add valid position');
assert(vm.runInContext('NS.addPortfolio("", 10, 5)', context) === false && vm.runInContext('NS.addPortfolio("Kirkland Snacks", -2, 5)', context) === false, 'portfolio: rejects blank name and negative units');
assert(els.portTable.hidden === false && els.portEmpty.hidden === true, 'portfolio: table shown after add');
assert(els.portBody.innerHTML.includes('Kirkland Coffee') && els.portBody.innerHTML.includes('$25.50'), 'portfolio: row renders name and unit cost');
assert(els.pTotalUnits.textContent === '10' && els.pTotalValue.textContent === '$255.00', 'portfolio: totals math');
vm.runInContext(`NS.addPortfolio('Kirkland Wipes', 5, 10);`, context);
assert(els.pTotalUnits.textContent === '15' && els.pTotalValue.textContent === '$305.00', 'portfolio: totals accumulate');
const uid = vm.runInContext('portfolio[0].uid', context);
vm.runInContext('NS.removePortfolio(' + JSON.stringify(uid) + ')', context);
assert(els.pTotalUnits.textContent === '5' && !els.portBody.innerHTML.includes('Kirkland Coffee'), 'portfolio: remove position');
vm.runInContext(`localStorage.setItem('t2.kirklandScout.portfolio.v1', 'not json'); portfolio = loadPortfolio();`, context);
assert(Array.isArray(vm.runInContext('portfolio', context)) && vm.runInContext('portfolio.length', context) === 0, 'portfolio: corrupt stored JSON reverts to empty');

/* view switching renders each tool */
vm.runInContext('openView("portfolio");', context);
assert(els['view-portfolio'].hidden === false && els['view-scout'].hidden === true, 'view switching opens portfolio and hides scout');
vm.runInContext('openView("risk"); openView("cycle"); openView("risk");', context);
assert(els['view-risk'].hidden === false && els['view-cycle'].hidden === true && els['view-portfolio'].hidden === true, 'view switching: only one tool view visible at a time');

/* ================================================================
 * Phase 8 — fee-engine economics contract (backend-computed fields)
 * ================================================================ */
const FE = (overrides = {}) => Object.assign({
    name: 'Fee Engine Item',
    asin: 'B400000001',
    product_url: 'https://www.amazon.com/dp/B400000001',
    amazon_price: 48.87,
    costco_cost: 15.99,
    costco_cogs: 15.99,
    costco_cost_basis: 'estimated',
    fba_fee: 8.20,
    fba_base_fee: 7.92,
    fba_fuel_logistics_surcharge: 0.28,
    fba_size_tier: 'standard',
    fba_fee_status: 'available',
    fba_fee_confidence: 'table_estimate',
    fba_fee_rule: 'FBA-2026.1',
    fba_fee_note: 'table estimate',
    fba_weight_basis_lbs: 3.5,
    referral_fee: 7.33,
    referral_fee_rate: 0.15,
    referral_fee_category: 'Home & Kitchen',
    referral_fee_confidence: 'verified_category',
    referral_fee_rule: 'REF-2026.1-Home & Kitchen',
    referral_fee_tier: '15% of sale price',
    referral_fee_note: 'Category matched exactly.',
    inbound_cost_per_unit: 0.35,
    prep_cost_per_unit: 0.25,
    packaging_cost_per_unit: 0.00,
    return_reserve_rate: 0.02,
    net_profit: 16.87,
    roi_pct: 105.5,
    economics_confidence: 'estimated',
    economics_status: 'estimated_fee_stack',
    economics_note: 'All costs included.',
    verdict: 'Pass',
}, overrides);

/* economics grouping (pure, no math) */
const grp = (p) => vm.runInContext('NS.economicsGroup(' + JSON.stringify(p) + ')', context);
assert(grp({ economics_confidence: 'estimated' }) === 0, 'economicsGroup: estimated = 0');
assert(grp({ economics_confidence: 'provisional' }) === 1, 'economicsGroup: provisional = 1');
assert(grp({ economics_confidence: 'unavailable' }) === 2, 'economicsGroup: unavailable = 2');
assert(grp({}) === 2, 'economicsGroup: missing confidence treated as unavailable');

/* default sort: Estimated first, Provisional second, Unavailable last,
   even when a provisional row has a higher profit */
const mixedPool = [
    FE({ asin: 'B400000002', name: 'Unavailable High Profit', economics_confidence: 'unavailable', economics_status: 'missing_costco_cogs', net_profit: null, roi_pct: null }),
    FE({ asin: 'B400000003', name: 'Provisional Higher Profit', economics_confidence: 'provisional', economics_status: 'needs_fee_verification', net_profit: 30, roi_pct: 180 }),
    FE({ asin: 'B400000004', name: 'Estimated Low Profit', net_profit: 5, roi_pct: 20 }),
];
let grpSorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(mixedPool) + ', "profit_desc")', context);
assert(grpSorted.map((p) => p.economics_confidence).join(',') === 'estimated,provisional,unavailable', 'default sort groups Estimated, Provisional, Unavailable');
assert(grpSorted[2].name === 'Unavailable High Profit', 'unavailable group always ranks last');

/* fee breakdown HTML: verified category, full estimated stack */
const bdEst = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE()) + ')', context);
assert(bdEst.includes('$7.33') && bdEst.includes('15.0%'), 'breakdown: referral amount and rate');
assert(bdEst.includes('Home &amp; Kitchen'), 'breakdown: referral category');
assert(bdEst.includes('Verified category'), 'breakdown: verified-category badge when category known');
assert(bdEst.includes('$8.20') && bdEst.includes('$7.92') && bdEst.includes('$0.28'), 'breakdown: FBA total, base, and 3.5% surcharge');
assert(bdEst.includes('standard') && bdEst.includes('3.50 lb'), 'breakdown: FBA size tier and weight basis');
assert(bdEst.includes('$0.35') && bdEst.includes('$0.25') && bdEst.includes('$0.00'), 'breakdown: unit costs render (0.00 packaging is an explicit configured value)');
assert(bdEst.includes('2% of sale price'), 'breakdown: return reserve rate');
assert(bdEst.includes('$16.87') && bdEst.includes('105.5%'), 'breakdown: net profit and ROI');
assert(bdEst.includes('Estimated') && bdEst.includes('All costs included.'), 'breakdown: estimated chip and note');
assert(!bdEst.includes('$0.00</b>') || bdEst.includes('Packaging'), 'breakdown: no fabricated zeros');

/* breakdown: default 15% badge when category unknown */
const bdDefault = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    referral_fee_confidence: 'default_category',
    referral_fee_category: 'Everything Else',
    referral_fee_note: 'default category applied',
})) + ')', context);
assert(bdDefault.includes('Default 15%'), 'breakdown: Default 15% badge when no category data');

/* breakdown: inferred category from breadcrumbs — badge + resolution note,
   while the verified referral RATE (same rule) is still surfaced */
const bdInferred = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    referral_fee_category: 'Grocery & Gourmet Food',
    referral_fee_confidence: 'verified_category',
    browse_node_id: 16310101,
    category_resolution_source: 'breadcrumb',
    category_resolution_confidence: 'inferred',
    category_resolution_note: 'Resolved from Amazon page breadcrumbs; confirm the exact category in Seller Central.',
})) + ')', context);
assert(bdInferred.includes('Inferred category'), 'breakdown: Inferred category badge when resolution is breadcrumb-based');
assert(bdInferred.includes('Resolved from Amazon page breadcrumbs'), 'breakdown: breadcrumb resolution note renders');
assert(bdInferred.includes('Verified category') === false, 'breakdown: inferred rows never show the verified badge');

/* breakdown: verified category with a browse-node source keeps the
   verified badge (not the inferred one) */
const bdNode = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    referral_fee_category: 'Beauty',
    referral_fee_confidence: 'verified_category',
    browse_node_id: 11055981,
    category_resolution_source: 'browse_node',
    category_resolution_confidence: 'verified',
    category_resolution_note: 'Resolved from Amazon browse node 11055981.',
})) + ')', context);
assert(bdNode.includes('Verified category'), 'breakdown: browse-node resolution shows verified badge');
assert(bdNode.includes('Inferred category') === false, 'breakdown: verified rows never show the inferred badge');

/* breakdown: provisional row — FBA fee missing, never final */
const bdProv = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    fba_fee: null, fba_base_fee: null, fba_fuel_logistics_surcharge: null,
    fba_size_tier: null, fba_fee_status: 'weight_unavailable',
    economics_confidence: 'provisional',
    economics_status: 'needs_fee_verification',
    economics_note: 'FBA fee not yet verified and EXCLUDED from these numbers. Verify before purchasing.',
})) + ')', context);
assert(bdProv.includes('Provisional — FBA Fee Missing'), 'breakdown: provisional badge exact');
assert(bdProv.includes('EXCLUDED'), 'breakdown: provisional note says fee excluded');
assert((bdProv.match(/Unavailable/g) || []).length >= 3, 'breakdown: missing FBA values render Unavailable');
assert(!bdProv.includes('Total: <b>$0.00</b>'), 'breakdown: no fabricated $0 for missing FBA fee');

/* breakdown: unavailable row — missing cost basis */
const bdUnav = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    net_profit: null, roi_pct: null,
    economics_confidence: 'unavailable',
    economics_status: 'missing_costco_cogs',
})) + ')', context);
assert(bdUnav.includes('Unavailable') && bdUnav.includes('missing costco cogs'), 'breakdown: unavailable status surfaces');

/* Pack/Variant Match badge states */
const pm = (q) => vm.runInContext('NS.packMatchBadge(' + JSON.stringify({ pack_match: q }) + ')', context);
assert(pm('exact').includes('Pack/Variant: Exact'), 'pack match badge: Exact');
assert(pm('candidate').includes('Pack/Variant: Candidate only'), 'pack match badge: Candidate only');
assert(pm('candidate').includes('not confirmed'), 'pack match badge: candidate carries verify-before-purchase tooltip');
assert(pm('mismatch').includes('Pack/Variant: Mismatch'), 'pack match badge: Mismatch');
assert(pm('unknown').includes('Pack/Variant: Unknown'), 'pack match badge: Unknown');
assert(pm('invoice_confirmed').includes('Pack/Variant: Invoice confirmed'), 'pack match badge: Invoice confirmed');
assert(pm('invoice_confirmed').includes('Invoice confirmed'), 'pack match badge: invoice carries paid-COGS tooltip');
assert(pm(undefined) === '', 'pack match badge: absent field renders nothing');
const bdMap = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({
    net_profit: null, roi_pct: null,
    economics_confidence: 'unavailable',
    economics_status: 'mapping_verification_required',
    economics_note: 'COGS is a candidate match only — verify the exact item at Costco before purchase.',
})) + ')', context);
assert(bdMap.includes('mapping verification required'), 'breakdown surfaces mapping_verification_required status');
assert(bdMap.includes('candidate match only'), 'breakdown carries the mapping-verification note');

/* Phase 6b: dossier 5-group structure */
(function () {
    var run = function (expr) { return vm.runInContext(expr, context); };

    /* Full dossier product */
    var fullProd = {
        asin: 'B600000001', name: 'Dossier Test Product', pack_match: 'exact',
        amazon_price: 29.99, costco_cost: 14.99, costco_cost_basis: 'costco_online',
        referral_fee: 4.50, referral_fee_rate: 0.15, referral_fee_category: 'Everything Else',
        referral_fee_confidence: 'verified_category', category_resolution_confidence: 'verified',
        referral_fee_tier: 'standard', referral_fee_rule: 'ref-15', referral_fee_note: '',
        fba_fee: 5.30, fba_base_fee: 4.75, fba_fuel_logistics_surcharge: 0.55,
        fba_size_tier: 'Standard', fba_weight_basis_lbs: 1.25, fba_fee_status: 'reported',
        fba_fee_confidence: 'reported', fba_fee_rule: 'std-1lb', fba_fee_note: '',
        inbound_cost_per_unit: 0.30, prep_cost_per_unit: 0.20, packaging_cost_per_unit: 0.00,
        return_reserve_rate: 0.05, net_profit: 14.44, roi_pct: 0.96,
        economics_confidence: 'estimated', economics_status: 'estimated_fee_stack',
        economics_note: 'All fees included', verdict: 'Pass', profit_tier: 11,
        total_sellers: 8, fba_sellers: 5, monthly_sales_estimate: 1200,
        monthly_sales_estimated: false, sales_rank: 4500, rating: 4.6, review_count: 820,
        product_url: 'https://www.amazon.com/dp/B600000001'
    };
    var html = run('NS.feeBreakdownHtml(' + JSON.stringify(fullProd) + ')');
    assert(html.includes('ns-dossier-grid'), 'dossier: renders ns-dossier-grid');
    assert(html.includes('ns-dossier-group'), 'dossier: renders ns-dossier-group');
    assert((html.match(/ns-dossier-title/g) || []).length === 5, 'dossier: exactly 5 group titles');
    assert(html.includes('Opportunity Snapshot'), 'dossier: group 1 title = Opportunity Snapshot');
    assert(html.includes('Costco Match &amp; Source Evidence'), 'dossier: group 2 title = Costco Match & Source Evidence');
    assert(html.includes('Amazon Fee Stack'), 'dossier: group 3 title = Amazon Fee Stack');
    assert(html.includes('Market &amp; Seller Intelligence'), 'dossier: group 4 title = Market & Seller Intelligence');
    assert(html.includes('Actions &amp; Next Step'), 'dossier: group 5 title = Actions & Next Step');

    /* Group 1: Opportunity Snapshot */
    assert(html.includes('B600000001'), 'dossier: g1 ASIN value');
    assert(html.includes('$29.99'), 'dossier: g1 Amazon price');
    assert(html.includes('$14.99'), 'dossier: g1 Costco COGS');
    assert(html.includes('costco online'), 'dossier: g1 cost provenance');
    assert(html.includes('Estimated'), 'dossier: g1 estimated confidence chip');
    assert(html.includes('$11+'), 'dossier: g1 profit tier');
    assert(html.includes('All fees included'), 'dossier: g1 economics note');

    /* Group 3: Amazon Fee Stack */
    assert(html.includes('Referral'), 'dossier: g3 Referral sub-heading');
    assert(html.includes('$4.50'), 'dossier: g3 referral fee amount');
    assert(html.includes('15.0%'), 'dossier: g3 referral rate');
    assert(html.includes('Verified category'), 'dossier: g3 verified badge');
    assert(html.includes('Fulfillment'), 'dossier: g3 Fulfillment sub-heading');
    assert(html.includes('$5.30'), 'dossier: g3 FBA total');
    assert(html.includes('$4.75'), 'dossier: g3 FBA base');
    assert(html.includes('$0.55'), 'dossier: g3 fuel surcharge');
    assert(html.includes('1.25 lb'), 'dossier: g3 weight basis');
    assert(html.includes('Unit costs'), 'dossier: g3 Unit costs sub-heading');
    assert(html.includes('$0.30'), 'dossier: g3 inbound cost');
    assert(html.includes('$0.20'), 'dossier: g3 prep cost');
    assert(html.includes('$0.00'), 'dossier: g3 packaging cost (explicit zero)');
    assert(html.includes('5% of sale price'), 'dossier: g3 return reserve');

    /* Group 4: Market & Seller Intelligence (with seller panel inside) */
    assert(html.includes('8'), 'dossier: g4 total sellers');
    assert(html.includes('5'), 'dossier: g4 FBA sellers');
    assert(html.includes('Not loaded'), 'dossier: g4 FBM sellers shows Not loaded');
    assert(html.includes('Not loaded'), 'dossier: g4 Amazon Retail shows Not loaded');
    assert(html.includes('Not loaded'), 'dossier: g4 Buy Box shows Not loaded');
    assert(html.includes('1.2K') || html.includes('1200'), 'dossier: g4 monthly sales formatted compact (1.2K)');
    assert(!html.includes('est-chip" title="Estimate, not verified sales"'), 'dossier: no Estimated chip when monthly_sales_estimated is false');
    var estTrueProd = Object.assign({}, fullProd, { monthly_sales_estimated: true });
    var estTrueHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(estTrueProd) + ')');
    assert(estTrueHtml.includes('est-chip" title="Estimate, not verified sales"'), 'dossier: Estimated chip present only when monthly_sales_estimated is true');
    assert(html.includes('4,500') || html.includes('4500'), 'dossier: g4 sales rank');
    assert(html.includes('4.6'), 'dossier: g4 rating');
    assert(html.includes('820'), 'dossier: g4 review count');
    assert(html.includes('Load seller details'), 'dossier: g4 seller panel inside Group 4');
    assert(html.includes('data-seller-asin'), 'dossier: g4 seller load button inside Group 4');
    assert(html.includes('Seller details not loaded'), 'dossier: g4 seller initial state');

    /* Group 5: Actions */
    assert(html.includes('data-analyze'), 'dossier: g5 Analyze button');
    assert(html.includes('amazon.com/dp/B600000001'), 'dossier: g5 Amazon listing link');
    assert(html.includes('Pass'), 'dossier: g5 pass callout');

    /* Group 2: exact match — no callout */
    assert(!html.includes('dossier-callout neg'), 'dossier: exact match no negative callout');
    assert(!html.includes('dossier-callout warn'), 'dossier: exact match no warning callout');

    /* Seller provenance with offer_data_provider */
    var provProd2 = Object.assign({}, fullProd, { offer_data_provider: 'easyparser', enrichment_status: 'complete', enriched_at: '2026-08-14T10:00:00Z' });
    var provHtml2 = run('NS.feeBreakdownHtml(' + JSON.stringify(provProd2) + ')');
    assert(provHtml2.includes('easyparser'), 'dossier: seller provenance shows provider name');
    assert(provHtml2.includes('complete'), 'dossier: seller provenance shows enrichment status');
    assert(provHtml2.includes('2026-08-14'), 'dossier: seller provenance shows fetched timestamp');
    assert(provHtml2.includes('dossier-note'), 'dossier: seller provenance uses dossier-note class');

    /* Seller provenance absent when provider is offline */
    var offlineProd = Object.assign({}, fullProd, { offer_data_provider: 'offline' });
    var offlineHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(offlineProd) + ')');
    assert(!offlineHtml.includes('dossier-note'), 'dossier: no provenance for offline provider');

    /* Provisional confidence */
    var provProd = {
        asin: 'B600000002', name: 'Provisional Dossier', pack_match: 'exact',
        amazon_price: 19.99, costco_cost: 9.99, costco_cost_basis: 'estimated',
        economics_confidence: 'provisional', economics_status: 'needs_fee_verification',
        verdict: 'Pass', profit_tier: '$5+', total_sellers: 3, fba_sellers: 2,
        product_url: 'https://www.amazon.com/dp/B600000002'
    };
    var provHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(provProd) + ')');
    assert(provHtml.includes('Provisional'), 'dossier: provisional chip');
    assert(provHtml.includes('FBA Fee Missing'), 'dossier: provisional chip mentions fee missing');
    assert(provHtml.includes('FBA fee not yet verified'), 'dossier: provisional next-step callout');

    /* Candidate pack match */
    var candProd = {
        asin: 'B600000003', name: 'Candidate Dossier', pack_match: 'candidate',
        economics_confidence: 'unavailable', economics_status: 'mapping_verification_required',
        verdict: null, product_url: ''
    };
    var candHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(candProd) + ')');
    assert(candHtml.includes('dossier-callout warn'), 'dossier: candidate match warning callout');
    assert(candHtml.includes('Candidate only'), 'dossier: candidate callout text');
    assert(candHtml.includes('verify the exact Costco item before purchasing'), 'dossier: candidate next-step');
    assert(candHtml.includes('dossier-callout warn'), 'dossier: candidate match warning callout');

    /* High-confidence pack match: visible, scoreable, labeled verify-before-buy */
    var hcProd = {
        asin: 'B600000005', name: 'High Confidence Dossier', pack_match: 'high_confidence',
        amazon_price: 24.99, costco_cost: 12.49, costco_cost_basis: 'estimated',
        economics_confidence: 'estimated', economics_status: 'estimated_fee_stack',
        net_profit: 6.0, roi_pct: 48.0, verdict: 'Pass', product_url: ''
    };
    var hcHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(hcProd) + ')');
    assert(hcHtml.includes('High confidence match'), 'dossier: high_confidence pack callout');
    assert(hcHtml.includes('verify UPC, pack size, and variant before buying'), 'dossier: high_confidence g2 verify-before-buy text');
    assert(hcHtml.includes('Likely match'), 'dossier: high_confidence next-step = Likely match');
    assert(!hcHtml.includes('economics verified, candidate eligible'), 'dossier: high_confidence never shows Pass next-step');

    /* Mismatch pack match */
    var misProd = {
        asin: 'B600000004', name: 'Mismatch Dossier', pack_match: 'mismatch',
        economics_confidence: 'unavailable', economics_status: 'mapping_verification_required',
        verdict: null, product_url: ''
    };
    var misHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(misProd) + ')');
    assert(misHtml.includes('dossier-callout neg'), 'dossier: mismatch negative callout');
    assert(misHtml.includes('Mismatch'), 'dossier: mismatch callout text');
    assert(misHtml.includes('do not purchase'), 'dossier: mismatch next-step');

    /* URL-only row (no ASIN) */
    var urlProd = {
        asin: '', name: 'URL Only Dossier', product_url: 'https://www.amazon.com/some-url',
        economics_confidence: 'unavailable', economics_status: 'missing_amazon_price',
        verdict: null
    };
    var urlHtml = run('NS.feeBreakdownHtml(' + JSON.stringify(urlProd) + ')');
    assert(!urlHtml.includes('data-analyze'), 'dossier: URL-only no Analyze button');
    assert(!urlHtml.includes('data-load-seller'), 'dossier: URL-only no seller load button');
    assert(urlHtml.includes('no ASIN, so the seller roster cannot be requested'), 'dossier: URL-only seller section shows no-ASIN reason');

    /* Buy Box content does not appear until seller detail data provides it */
    assert(!html.includes('is_buy_box_winner'), 'dossier: Buy Box winner not shown before load');
    assert(!html.includes('bb-row'), 'dossier: Buy Box detail row not shown before load');

    setState(full);
})();
const pmState = [
    FE({ asin: 'B400000020', name: 'Exact Match Row', pack_match: 'exact' }),
    FE({ asin: 'B400000021', name: 'Mismatch Row', pack_match: 'mismatch', net_profit: null, roi_pct: null, economics_confidence: 'unavailable', economics_status: 'mapping_verification_required', verdict: null }),
    FE({ asin: 'B400000022', name: 'Candidate Row', pack_match: 'candidate', net_profit: null, roi_pct: null, economics_confidence: 'unavailable', economics_status: 'mapping_verification_required', verdict: null }),
    FE({ asin: 'B400000023', name: 'Invoice Row', pack_match: 'invoice_confirmed', costco_cost_basis: 'invoice_confirmed' }),
];
setState(pmState, 'ok', 'ready');
const pmOut = els.tableBody.innerHTML;
assert(pmOut.includes('Pack/Variant: Exact'), 'table renders Exact pack badge');
assert(pmOut.includes('Pack/Variant: Mismatch'), 'table renders Mismatch pack badge');
assert(pmOut.includes('Pack/Variant: Candidate only'), 'table renders Candidate-only pack badge');
assert(pmOut.includes('Pack/Variant: Invoice confirmed'), 'table renders Invoice-confirmed pack badge');
assert((pmOut.match(/>Pass</g) || []).length === 2, 'exact + invoice-confirmed rows render Pass (blocked rows never do)');
assert(pmOut.includes('$11+') === false, 'blocked rows get no Tier badge');
assert((pmOut.match(/Pack\/Variant: Exact/g) || []).length === 1, 'only the exact row shows the Exact badge');
setState(full);

/* economics unavailable reasons: tooltip text per economics_status */
const er = (s) => vm.runInContext('NS.econUnavailableReason(' + JSON.stringify({ economics_status: s }) + ')', context);
assert(er('missing_amazon_price').includes('No sale price'), 'reason: missing_amazon_price');
assert(er('missing_costco_cogs').includes('No Costco cost'), 'reason: missing_costco_cogs');
assert(er('mapping_verification_required').includes('candidate match'), 'reason: mapping_verification_required');
assert(er('needs_fee_verification').includes('FBA fee'), 'reason: needs_fee_verification');
assert(er(undefined).includes('Unit economics unavailable'), 'reason: unknown status fallback');

/* ASIN/listing links: ASIN rows link to amazon.com/dp, URL-only rows link
   the listing, Analyze is disabled without an ASIN, and unavailable rows
   carry an inline economics reason so no cell is a bare "Unavailable" */
const linkState = [
    FE({ asin: 'B400000030', name: 'Asin Row' }),
    FE({ asin: null, product_url: 'https://www.amazon.com/dp/B400000031', name: 'Url Only Row', net_profit: null, roi_pct: null, economics_confidence: 'unavailable', economics_status: 'missing_amazon_price', verdict: null }),
    FE({ asin: null, product_url: null, name: 'No Identifier Row' }),
];
setState(linkState, 'ok', 'ready');
const linkOut = els.tableBody.innerHTML;
assert(linkOut.includes('href="https://www.amazon.com/dp/B400000030"') && linkOut.includes('>B400000030</a>'), 'table: ASIN renders as amazon.com/dp link');
assert(linkOut.includes('href="https://www.amazon.com/dp/B400000031"') && linkOut.includes('>listing</a>'), 'table: URL-only row renders listing link');
assert(linkOut.includes('data-fees="https://www.amazon.com/dp/B400000031"'), 'table: URL-only Fees button keys on product_url');
assert((linkOut.match(/disabled title="No ASIN/g) || []).length === 2, 'table: Analyze disabled when no ASIN');
assert(linkOut.includes('class="econ-reason"') && linkOut.includes('missing amazon price'), 'table: unavailable row shows inline economics reason');
setState(full);

/* ================================================================
 * Phase 8b — match/cost/economics filter isolation
 * ================================================================ */
const filterPool = [
    FE({ asin: 'B400000050', product_url: 'https://www.amazon.com/dp/B400000050', name: 'Invoice Row', pack_match: 'invoice_confirmed', costco_cost_basis: 'invoice_confirmed', economics_confidence: 'estimated', economics_status: 'estimated_fee_stack' }),
    FE({ asin: 'B400000051', product_url: 'https://www.amazon.com/dp/B400000051', name: 'Candidate Row', pack_match: 'candidate', costco_cost_basis: 'candidate_match', economics_confidence: 'unavailable', economics_status: 'mapping_verification_required', net_profit: null, roi_pct: null, verdict: null }),
    FE({ asin: 'B400000052', product_url: 'https://www.amazon.com/dp/B400000052', name: 'Mismatch Row', pack_match: 'mismatch', costco_cost_basis: 'candidate_match', economics_confidence: 'unavailable', economics_status: 'mapping_verification_required', net_profit: null, roi_pct: null, verdict: null }),
    FE({ asin: 'B400000053', product_url: 'https://www.amazon.com/dp/B400000053', name: 'Prov Row', pack_match: 'exact', costco_cost_basis: 'estimated', economics_confidence: 'provisional', economics_status: 'needs_fee_verification', verdict: 'Needs Fee Verification' }),
    FE({ asin: 'B400000054', product_url: 'https://www.amazon.com/dp/B400000054', name: 'No Cost Row', pack_match: 'unknown', costco_cost_basis: 'unavailable', economics_confidence: 'unavailable', economics_status: 'missing_costco_cogs', net_profit: null, roi_pct: null, verdict: null }),
];
const fq = (o) => vm.runInContext(
    'NS.filterProducts(' + JSON.stringify(filterPool) + ', ' + JSON.stringify(filtersFor(o)) +
    ').map(function (p) { return p.name; }).join(",")', context);
assert(fq({}).split(',').length === 5, 'filter: blank filters stay disabled (all rows pass)');
assert(fq({ packMatch: 'invoice_confirmed' }) === 'Invoice Row', 'filter: packMatch invoice_confirmed isolates');
assert(fq({ packMatch: 'exact' }) === 'Prov Row', 'filter: packMatch exact isolates');
assert(fq({ packMatch: 'candidate' }) === 'Candidate Row', 'filter: packMatch candidate isolates');
assert(fq({ packMatch: 'mismatch' }) === 'Mismatch Row', 'filter: packMatch mismatch isolates');
assert(fq({ packMatch: 'unknown' }) === 'No Cost Row', 'filter: packMatch unknown isolates');
assert(fq({ costBasis: 'invoice_confirmed' }) === 'Invoice Row', 'filter: costBasis invoice_confirmed isolates');
assert(fq({ costBasis: 'candidate_match' }) === 'Candidate Row,Mismatch Row', 'filter: costBasis candidate_match isolates both research rows');
assert(fq({ costBasis: 'unavailable' }) === 'No Cost Row', 'filter: costBasis unavailable isolates missing-cost row');
assert(fq({ econ: 'estimated' }) === 'Invoice Row', 'filter: econ estimated isolates');
assert(fq({ econ: 'provisional' }) === 'Prov Row', 'filter: econ provisional isolates');
assert(fq({ econ: 'unavailable' }).split(',').length === 3, 'filter: econ unavailable isolates all three research rows');
assert(fq({ status: 'Needs Mapping Verification' }) === 'Candidate Row,Mismatch Row', 'filter: status needs-mapping-verification isolates research rows');
assert(fq({ status: 'Needs Fee Verification' }) === 'Prov Row', 'filter: status needs-fee-verification isolates provisional row');
assert(fq({ status: 'Pass' }) === 'Invoice Row', 'filter: Pass isolates the qualified row only');
assert(fq({ search: 'B400000051' }) === 'Candidate Row', 'filter: search matches ASIN');
assert(fq({ search: '/dp/B400000050' }) === 'Invoice Row', 'filter: search matches product_url');
assert(vm.runInContext('NS.filterCount(' + JSON.stringify(filtersFor({ packMatch: 'exact', econ: 'provisional' })) + ')', context) === 2, 'filter: filterCount counts match and econ filters');

/* ================================================================
 * Phase 4c — column visibility (separate from widths)
 * ================================================================ */

/* Defaults: only Product, Price, COGS, Net, ROI visible (5 resizable).
 * ASIN, FBA Fee, Competition, Monthly Sales, Tier hidden (Advanced). */
const CVD = vm.runInContext('JSON.parse(JSON.stringify(NS.loadColVisibility()))', context);
assert(CVD.product === true && CVD.price === true && CVD.cost === true && CVD.net === true && CVD.roi === true, 'col-vis: 5 core columns default visible');
assert(CVD.asin === false && CVD.fba === false && CVD.competition === false && CVD.sales === false && CVD.tier === false, 'col-vis: 5 advanced columns default hidden');

/* loadColVisibility: nothing stored returns defaults */
delete store['t2.kirklandScout.columns.v1.visible'];
const freshVis = vm.runInContext('NS.loadColVisibility()', context);
assert(freshVis.asin === false && freshVis.product === true, 'col-vis: no stored data returns defaults');

/* Migration: old stored widths untouched by visibility system */
store['t2.kirklandScout.columns.v1'] = JSON.stringify({ product: 500, asin: 200 });
const widths = vm.runInContext('NS.loadColWidths()', context);
assert(widths.product === 500 && widths.asin === 200, 'col-vis: existing width data untouched by visibility migration');

/* setColVisible toggles and persists */
vm.runInContext('NS.setColVisible("asin", true)', context);
assert(vm.runInContext('NS.loadColVisibility().asin', context) === true, 'col-vis: setColVisible asin=true persists');
assert(vm.runInContext('NS.loadColVisibility().sales', context) === false, 'col-vis: setColVisible only changes target key');

vm.runInContext('NS.setColVisible("sales", true)', context);
assert(vm.runInContext('NS.loadColVisibility().sales', context) === true, 'col-vis: setColVisible sales=true persists');

vm.runInContext('NS.setColVisible("asin", false)', context);
assert(vm.runInContext('NS.loadColVisibility().asin', context) === false, 'col-vis: setColVisible asin=false persists');

/* getVisibleColCount: 2 fixed (Status, Action) + visible from COLUMN_VISIBLE_DEFAULTS.
   With Score/Sellers/Buy Box columns: 14 data columns + 2 fixed = 16 total when all visible. */
vm.runInContext('NS.resetColVisibility()', context);
vm.runInContext('NS.setColVisible("asin", true); NS.setColVisible("fba", true); NS.setColVisible("competition", true); NS.setColVisible("sales", true); NS.setColVisible("tier", true)', context);
assert(vm.runInContext('NS.getVisibleColCount()', context) === 16, 'col-vis: getVisibleColCount=16 when all 14 visible + 2 fixed');
vm.runInContext('NS.setColVisible("asin", false)', context);
assert(vm.runInContext('NS.getVisibleColCount()', context) === 15, 'col-vis: getVisibleColCount=15 with ASIN hidden');
vm.runInContext('NS.setColVisible("sales", false)', context);
assert(vm.runInContext('NS.getVisibleColCount()', context) === 14, 'col-vis: getVisibleColCount=14 with ASIN+sales hidden');

/* resetColVisibility restores defaults */
vm.runInContext('NS.resetColVisibility()', context);
assert(vm.runInContext('NS.loadColVisibility().asin', context) === false, 'col-vis: resetColVisibility restores asin=false');
assert(vm.runInContext('NS.loadColVisibility().product', context) === true, 'col-vis: resetColVisibility restores product=true');

/* Corrupt stored visibility falls back to defaults */
store['t2.kirklandScout.columns.v1.visible'] = 'not json';
assert(vm.runInContext('NS.loadColVisibility().product', context) === true, 'col-vis: corrupt visibility falls back to defaults');

/* Partial stored data merges with defaults */
store['t2.kirklandScout.columns.v1.visible'] = JSON.stringify({ asin: true });
const partialVis = vm.runInContext('NS.loadColVisibility()', context);
assert(partialVis.asin === true && partialVis.product === true && partialVis.sales === false, 'col-vis: partial stored data merges with defaults');

/* NS exports exist */
assert(typeof vm.runInContext('NS.setColVisible', context) === 'function', 'col-vis: NS.setColVisible exported');
assert(typeof vm.runInContext('NS.resetColVisibility', context) === 'function', 'col-vis: NS.resetColVisibility exported');
assert(typeof vm.runInContext('NS.loadColVisibility', context) === 'function', 'col-vis: NS.loadColVisibility exported');
assert(typeof vm.runInContext('NS.getVisibleColCount', context) === 'function', 'col-vis: NS.getVisibleColCount exported');

/* Panel labels carry the honest Est. qualifier (checkbox + width input) */
assert(html.includes('data-col-vis="sales"> Est. Monthly Sales'), 'col-vis: panel checkbox label is Est. Monthly Sales');
assert(html.includes('for="colInput-sales">Est. Monthly Sales (px)'), 'col-vis: width input label is Est. Monthly Sales (px)');

/* ASIN remains in product cell even when ASIN column hidden */
setState([FE({ asin: 'B400000040', name: 'ASIN Test', pack_match: 'exact' })], 'ok', 'ready');
vm.runInContext('NS.setColVisible("asin", false)', context);
vm.runInContext('NS.applyColVisibility()', context);
const rowHtml4c = els.tableBody.innerHTML;
assert(rowHtml4c.includes('prod-asin') && rowHtml4c.includes('B400000040'), 'col-vis: ASIN visible under product name even when ASIN column hidden');
vm.runInContext('NS.resetColVisibility()', context);
setState(full);

/* ================================================================
 * Scout triage columns: Score, Sellers, Buy Box
 * ================================================================ */
const scoreInfoOpp = vm.runInContext('NS.scoutScore({ opportunity_score: 75.4, data_completeness_score: 60, opportunity_score_reasons: ["economics (roi 214%, net $43.85)"] })', context);
assert(scoreInfoOpp.value === 75 && scoreInfoOpp.kind === 'opportunity', 'score: opportunity score wins when present');
const scoreInfoComp = vm.runInContext('NS.scoutScore({ amazon_price: null, data_completeness_score: 40 })', context);
assert(scoreInfoComp.value === 40 && scoreInfoComp.kind === 'completeness', 'score: falls back to completeness when price missing');
assert(vm.runInContext('NS.scoutScore({})', context) === null, 'score: null when no score computable');
assert(vm.runInContext('NS.sellersCell({ total_sellers: 12, fba_sellers: 3 })', context) === '12 total · 3 FBA', 'sellers: total + FBA counts');
assert(vm.runInContext('NS.sellersCell({ total_sellers: 5 })', context) === '5 total', 'sellers: total only');
assert(vm.runInContext('NS.sellersCell({ fba_sellers: 0 })', context) === '0 FBA', 'sellers: FBA only');
assert(vm.runInContext('NS.sellersCell({})', context) === null, 'sellers: null without counts');
const bbFba = vm.runInContext('NS.buyBoxCell({ buy_box_seller: "Amazon.com", buy_box_fulfillment: "FBA", buy_box_source: "observed" })', context);
assert(bbFba.includes('Amazon.com') && bbFba.includes('>FBA<') && bbFba.includes('badge pos'), 'buybox: FBA winner renders FBA badge');
const bbFbm = vm.runInContext('NS.buyBoxCell({ buy_box_seller: "M&D Wholesalers", buy_box_fulfillment: "fbm" })', context);
assert(bbFbm.includes('M&amp;D Wholesalers') && bbFbm.includes('>FBM<'), 'buybox: FBM winner renders FBM badge + escaped name');
assert(vm.runInContext('NS.buyBoxCell({})', context) === null, 'buybox: null without winner');
setState([FE({ asin: 'B500000001', name: 'Triage Row', opportunity_score: 68, data_completeness_score: 90, total_sellers: 9, fba_sellers: 2, buy_box_seller: 'Amazon.com', buy_box_fulfillment: 'FBA', buy_box_source: 'observed' })], 'ok', 'ready');
const triageHtml = els.tableBody.innerHTML;
assert(triageHtml.includes('data-col="score"') && triageHtml.includes('>68</b>'), 'score column renders opportunity score value');
assert(triageHtml.includes('9 total · 2 FBA'), 'sellers column renders total + FBA counts');
assert(triageHtml.includes('buybox-seller') && triageHtml.includes('>FBA<'), 'buybox column renders winner + FBA badge');
setState(full);

/* ================================================================
 * Phase 8c — resizable table columns (no external libraries)
 * ================================================================ */
const CD = vm.runInContext('NS.colWidthDefaults()', context);
assert(CD.product === 280 && CD.net === 110, 'columns: default Product width 280px and numeric defaults present');
vm.runInContext('NS.setColWidth("product", 380)', context);
assert(els['colHead-product'].style.width === '380px', 'columns: setColWidth applies th width');
assert(JSON.parse(store['t2.kirklandScout.columns.v1']).product === 380, 'columns: setColWidth persists to localStorage');
vm.runInContext('NS.setColWidth("product", 99999)', context);
assert(els['colHead-product'].style.width === '640px', 'columns: width clamped to max bound');
vm.runInContext('NS.setColWidth("product", 10)', context);
assert(els['colHead-product'].style.width === '160px', 'columns: width clamped to min bound');
const san = vm.runInContext('NS.sanitizeColWidths({ product: "x", asin: null, net: 55, price: 900 })', context);
assert(san.product === 280 && san.asin === 110 && san.net === 80 && san.price === 240, 'columns: invalid and out-of-range values sanitized to bounds');
store['t2.kirklandScout.columns.v1'] = '{not json';
assert(vm.runInContext('NS.loadColWidths()', context).product === 280, 'columns: corrupt stored JSON falls back to defaults');
store['t2.kirklandScout.columns.v1'] = JSON.stringify({ product: 420 });
vm.runInContext('NS.applyColWidths(NS.loadColWidths())', context);
assert(els['colHead-product'].style.width === '420px', 'columns: stored widths restore on load');
vm.runInContext('NS.setColWidth("product", 500)', context);
vm.runInContext('NS.resetColWidths()', context);
assert(els['colHead-product'].style.width === '280px', 'columns: reset restores default width');
assert(JSON.parse(store['t2.kirklandScout.columns.v1']).product === 280, 'columns: reset restores stored defaults');
assert(html.includes('class="col-resize"') && html.includes('data-col="product"'), 'columns: resize handles present in header');
assert(html.includes('role="separator"') && html.includes('aria-orientation="vertical"') && html.includes('tabindex="0"'), 'columns: handles are keyboard-operable separators');
assert(html.includes('id="colToggle"') && html.includes('id="colPanel"') && html.includes('id="colReset"'), 'columns: toggle, panel, and Reset controls present');
assert(html.includes('var(--col-product, 280px)') && html.includes('--col-product-max, 640px'), 'columns: CSS uses variable-driven product width');
assert(html.includes('max-width: 100%'), 'columns: title clamp scales with column width (no fixed pixel clamp)');
assert(html.includes('overflow: auto') && html.includes('min-width: 1120px'), 'table stays horizontally scrollable');
assert(html.includes('position: sticky; top: 0'), 'table header stays sticky');
const longName = 'Kirkland Signature ' + 'Ultra Long Title '.repeat(10) + 'End';
setState([FE({ asin: 'B400000040', name: longName, pack_match: 'exact' })], 'ok', 'ready');
const longOut = els.tableBody.innerHTML;
assert(longOut.includes(longName), 'columns: full product title present in the row (tooltip + ellipsis only when clamped)');
assert(longOut.includes('title="' + longName + '"'), 'columns: full title exposed via title attribute');
vm.runInContext('NS.setColWidth("product", 640)', context);
assert(els['colHead-product'].style.width === '640px', 'columns: Product column widens for long titles');
setState(linkState, 'ok', 'ready');
const linkOut2 = els.tableBody.innerHTML;
assert(linkOut2.includes('href="https://www.amazon.com/dp/B400000030"') && linkOut2.includes('>B400000030</a>'), 'columns: ASIN links still render after width changes');
assert(linkOut2.includes('href="https://www.amazon.com/dp/B400000031"') && linkOut2.includes('>listing</a>'), 'columns: listing link still renders after width changes');
assert(linkOut2.includes('disabled title="No ASIN'), 'columns: disabled Analyze preserved after width changes');
setState(full);

/* table render: economics chips per tier */
const chipState = [
    FE({ asin: 'B400000010', name: 'Estimated Row' }),
    FE({ asin: 'B400000011', name: 'Provisional Row', fba_fee: null, net_profit: 23.97, roi_pct: 149.9, economics_confidence: 'provisional', economics_status: 'needs_fee_verification', verdict: 'Needs Fee Verification' }),
];
setState(chipState, 'ok', 'ready');
const chipOut = els.tableBody.innerHTML;
assert(chipOut.includes('>Estimated<'), 'table renders Estimated chip');
assert(chipOut.includes('>Provisional<'), 'table renders Provisional chip');
assert(chipOut.includes('data-fees='), 'table has per-row Fees toggle');
assert(chipOut.includes('Needs Fee Verification'), 'provisional row keeps Needs Fee Verification status');
setState(full);

/* ================================================================
 * Phase 9 — Sellers & Buy Box (on-demand, inside the detail row)
 * ================================================================ */
/* A synchronous thenable so the .then/.catch/.finally chain in
   NS.loadSellerDetails runs without real async (no timers in tests). */
const T = (fn) => ({
    then: (cb) => T(() => cb(fn())),
    catch: (cb) => T(() => { try { return fn(); } catch (e) { return cb(e); } }),
    finally: (cb) => { const v = fn(); cb(); return T(() => v); },
});
const fetchCalls = [];
context.fetch = (url) => { fetchCalls.push(url); return T(() => sellerRes()); };
let sellerRes = () => ({ ok: true, json: () => SELLER_FIXTURE_PARTIAL });

const SELLER_FIXTURE_PARTIAL = {
    asin: 'B0TEST0001', offer_data_status: 'partial', offer_data_source: 'easyparser',
    offer_data_fetched_at: '2026-08-14T20:19:04Z', offer_data_cached: false,
    offer_data_note: 'Provider returned 2 of 3 offers; the roster may be paginated or truncated.',
    total_sellers: 3, fba_sellers: 2, fbm_sellers: 1, amazon_sellers: 1,
    buy_box: { available: true, seller_name: 'Amazon.com', seller_id: 'A1', fulfillment: 'Amazon', price: 25.0, shipping: null, landed_price: null, condition: 'New', prime: true, note: null },
    offers: [
        { seller_name: 'Amazon.com', seller_id: 'A1', fulfillment: 'Amazon', is_buy_box_winner: true, price: 25.0, shipping: null, landed_price: null, condition: 'New', prime: true, rating: 4.9, feedback_count: 1000, availability: null },
        { seller_name: 'Some Seller', seller_id: 'A2', fulfillment: 'FBM', is_buy_box_winner: false, price: 24.0, shipping: null, landed_price: null, condition: 'New', prime: false, rating: 4.5, feedback_count: 50, availability: null },
    ],
    offers_returned: 2, offers_complete: false,
};

/* section markup inside the expanded detail row (no fetch on render) */
const bdSeller = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(P()) + ')', context);
assert(bdSeller.includes('Sellers &amp; Buy Box'), 'seller: section title inside detail row');
assert(bdSeller.includes('Total sellers: 5') && bdSeller.includes('FBA: 2'), 'seller: compact aggregate summary from scan data');
assert(bdSeller.includes('FBM: Unknown'), 'seller: FBM not in scan contract renders Unknown');
assert(bdSeller.includes('Buy Box winner: Unknown'), 'seller: buy box identity Unknown until loaded');
assert(bdSeller.includes('Load seller details'), 'seller: Load button present for valid ASIN');
assert(bdSeller.includes('not loaded'), 'seller: initial state = not loaded');
assert(bdSeller.includes('data-seller-asin="B0TEST0001"'), 'seller: Load button carries the ASIN');
assert(bdSeller.includes('aria-expanded="false"') && bdSeller.includes('aria-controls="sellerCard-B0TEST0001"'), 'seller: Load button is an ARIA disclosure control');

const bdSellerUrl = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(FE({ asin: null, product_url: 'https://www.amazon.com/dp/B400000031' })) + ')', context);
assert(bdSellerUrl.includes('no ASIN'), 'seller: URL-only row shows unavailable message');
assert(!bdSellerUrl.includes('Load seller details'), 'seller: URL-only row has NO Load button');

/* no seller clutter in the primary compact table (Task 5) */
setState(full, 'ok', 'ready');
const tableNoSeller = els.tableBody.innerHTML;
assert(!tableNoSeller.includes('Sellers &amp; Buy Box'), 'no-clutter: seller section absent from primary table');
assert(!tableNoSeller.includes('Load seller details'), 'no-clutter: no Load seller button in primary row');
assert(!tableNoSeller.includes('buy-box-card') && !tableNoSeller.includes('seller-table'), 'no-clutter: no buy box card / seller table in primary row');

/* no fetch on render or on fee-detail expansion */
fetchCalls.length = 0;
setState(full, 'ok', 'ready');
assert(fetchCalls.length === 0, 'seller: no fetch on table render / scan');
vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(P()) + ')', context);
assert(fetchCalls.length === 0, 'seller: no fetch on fee-detail expansion');

/* Load click -> one fetch, buy box card + seller table, partial disclosure */
const sellerBtn = el();
sellerBtn.__attrs = {};
sellerBtn.setAttribute = (k, v) => { sellerBtn.__attrs[k] = v; };
sellerBtn.getAttribute = (a) => (a === 'data-seller-asin' ? 'B0TEST0001' : (sellerBtn.__attrs[a] || null));
context.__sellerBtn = sellerBtn;
fetchCalls.length = 0;
vm.runInContext('NS.loadSellerDetails(__sellerBtn)', context);
delete context.__sellerBtn;
assert(fetchCalls.length === 1 && fetchCalls[0] === '/api/products/B0TEST0001/offers', 'seller: exactly one fetch to the ASIN offers endpoint on Load');
const cardOut = els['sellerCard-B0TEST0001'].innerHTML;
assert(cardOut.includes('Buy Box') && cardOut.includes('Amazon.com'), 'seller: buy box card with winner seller');
assert(cardOut.includes('$25.00'), 'seller: buy box price rendered');
assert(cardOut.includes('seller-table') && cardOut.includes('<th>Seller</th>'), 'seller: seller table rendered');
assert(cardOut.includes('>FBM<'), 'seller: fulfillment badge rendered');
assert(cardOut.includes('Seller data is partial'), 'seller: partial roster disclosure shown');
assert(cardOut.includes('$24.00'), 'seller: offer price rendered');
assert(cardOut.includes('1,000'), 'seller: feedback count rendered');
assert(els['sellerState-B0TEST0001'].textContent.includes('partial'), 'seller: status text reports partial roster');
assert(sellerBtn.getAttribute('aria-expanded') === 'true', 'seller: Load button marked expanded after successful load');

/* orbital market mapping: plots the real two-offer roster after load */
const orbitOut = els['scOrbital-B0TEST0001'].innerHTML;
assert(orbitOut.includes('orbit-node') && orbitOut.includes('orbit-sun'), 'seller: market orbit plots the real offer roster after Load');
assert(orbitOut.includes('$24.00') && orbitOut.includes('Some Seller'), 'seller: orbit nodes derive from real landed prices');
assert(orbitOut.includes('Buy Box') && orbitOut.includes('feedback count'), 'seller: orbit labels buy-box winner and the presence proxy');

/* orbital honesty when the roster cannot support an orbit */
const orbitThin = vm.runInContext('NS.scOrbitalHtml({ buy_box: { price: 20 }, offers: [{ seller_name: "Solo", price: 20 }] }, null)', context);
assert(orbitThin.includes('at least two priced offers'), 'seller: single-offer roster honestly declines to plot');
assert(!orbitThin.includes('>0<') && !orbitThin.includes('$0.00'), 'seller: thin orbit never fabricates zeros');

/* cached indicator */
sellerRes = () => ({ ok: true, json: () => Object.assign({}, SELLER_FIXTURE_PARTIAL, { offer_data_cached: true }) });
context.__sellerBtn = sellerBtn;
vm.runInContext('NS.loadSellerDetails(__sellerBtn)', context);
delete context.__sellerBtn;
assert(els['sellerCard-B0TEST0001'].innerHTML.includes('Cached'), 'seller: cached indicator shown when cached');
assert(els['sellerState-B0TEST0001'].textContent.includes('Cached'), 'seller: cached shown in status text');

/* full / available state */
const SELLER_FIXTURE_AVAILABLE = Object.assign({}, SELLER_FIXTURE_PARTIAL, {
    offer_data_status: 'available', offer_data_note: null, offers_complete: true, offers_returned: 3, total_sellers: 3,
});
sellerRes = () => ({ ok: true, json: () => SELLER_FIXTURE_AVAILABLE });
context.__sellerBtn = sellerBtn;
vm.runInContext('NS.loadSellerDetails(__sellerBtn)', context);
delete context.__sellerBtn;
const avOut = els['sellerCard-B0TEST0001'].innerHTML;
assert(!avOut.includes('Seller data is partial'), 'seller: no partial banner when roster complete');
assert(els['sellerState-B0TEST0001'].textContent.includes('loaded'), 'seller: loaded state text on available');

/* failure -> retry state, no fake table, no fake zeros */
sellerRes = () => { throw new Error('HTTP 500'); };
fetchCalls.length = 0;
context.__sellerBtn = sellerBtn;
vm.runInContext('NS.loadSellerDetails(__sellerBtn)', context);
delete context.__sellerBtn;
assert(fetchCalls.length === 1, 'seller: failure still issues one request');
const errOut = els['sellerError-B0TEST0001'].innerHTML;
assert(errOut.includes('Retry'), 'seller: retry control on failure');
assert(errOut.includes('no cached response'), 'seller: retry discloses possible provider request');
assert(errOut.includes('No fake counts'), 'seller: no fake counts on failure');
assert(els['sellerCard-B0TEST0001'].innerHTML === '', 'seller: no fake seller table on failure');
assert(!errOut.includes('$0'), 'seller: no fabricated zero prices on failure');
assert(els['sellerState-B0TEST0001'].textContent.includes('Retry'), 'seller: status announces retry availability');

/* provider-error / unavailable detail state text */
const provErr = vm.runInContext('NS.sellerStateText(' + JSON.stringify({ offer_data_status: 'provider_error', offer_data_note: 'Easyparser request timed out.' }) + ')', context);
assert(provErr.includes('provider error') && provErr.includes('timed out'), 'seller: provider-error status surfaced');
const unavText = vm.runInContext('NS.sellerStateText(' + JSON.stringify({ offer_data_status: 'unavailable' }) + ')', context);
assert(unavText.includes('no seller data'), 'seller: unavailable status surfaced');

/* ---- Step 7: Seller & Buy Box visual refinement ---- */

/* 1. Unloaded state: aggregate metrics + not-loaded + valid load action */
assert(bdSeller.includes('Total sellers: 5'), 's7: unloaded state shows total sellers aggregate');
assert(bdSeller.includes('FBA: 2'), 's7: unloaded state shows FBA aggregate');
assert(bdSeller.includes('Seller details not loaded'), 's7: unloaded state shows not-loaded message');
assert(bdSeller.includes('Load seller details'), 's7: unloaded state has load action');
assert(bdSeller.includes('data-seller-asin'), 's7: load action carries ASIN');

/* 2. URL-only/no-ASIN: no enabled seller-load action */
assert(!bdSellerUrl.includes('Load seller details'), 's7: URL-only row has no enabled load action');
assert(bdSellerUrl.includes('no ASIN'), 's7: URL-only row explains why seller lookup unavailable');

/* 3. Buy Box spotlight only when response provides winner data */
var bbWithWinner = vm.runInContext('NS.sellerDetailHtml(' + JSON.stringify({
    offer_data_status: 'available', offer_data_source: 'easyparser', offer_data_fetched_at: '2026-08-14T20:00:00Z',
    buy_box: { available: true, seller_name: 'TestSeller', seller_id: 'S1', fulfillment: 'FBA', price: 29.99, shipping: null, landed_price: null, condition: 'New', prime: true },
    offers: [{ seller_name: 'TestSeller', seller_id: 'S1', fulfillment: 'FBA', is_buy_box_winner: true, price: 29.99 }]
}) + ')', context);
assert(bbWithWinner.includes('Buy Box'), 's7: Buy Box spotlight renders with winner');
assert(bbWithWinner.includes('TestSeller'), 's7: Buy Box spotlight shows seller name');
assert(bbWithWinner.includes('>FBA<'), 's7: Buy Box spotlight has fulfillment badge');
assert(bbWithWinner.includes('$29.99'), 's7: Buy Box spotlight shows price');
assert(bbWithWinner.includes('New'), 's7: Buy Box spotlight shows condition');
assert(bbWithWinner.includes('Yes'), 's7: Buy Box spotlight shows Prime');
assert(bbWithWinner.includes('easyparser'), 's7: Buy Box spotlight shows source');

/* 4. No Buy Box winner when buy_box.available is false */
var bbNoWinner = vm.runInContext('NS.sellerDetailHtml(' + JSON.stringify({
    offer_data_status: 'available', buy_box: { available: false },
    offers: [{ seller_name: 'Seller1', fulfillment: 'FBA', price: 20.0 }]
}) + ')', context);
assert(bbNoWinner.includes('Winner not confirmed'), 's7: no winner shows Winner not confirmed');
assert(bbNoWinner.includes('Buy Box winner unavailable from returned seller data'), 's7: no winner shows explanatory note');

/* 5. Lowest price alone does NOT produce a Buy Box winner */
var bbLowestOnly = vm.runInContext('NS.sellerDetailHtml(' + JSON.stringify({
    offer_data_status: 'available', buy_box: {},
    offers: [{ seller_name: 'Cheapest', fulfillment: 'FBM', price: 10.0, is_buy_box_winner: false }]
}) + ')', context);
assert(!bbLowestOnly.includes('Buy Box</b>') || bbLowestOnly.includes('Winner not confirmed'), 's7: lowest price alone does not produce Buy Box winner');

/* 6. Partial roster disclosure */
assert(cardOut.includes('Seller data is partial'), 's7: partial roster disclosure appears');
assert(cardOut.includes('2 of'), 's7: partial roster shows returned count');

/* 7. Cached state and timestamp */
var cachedHtml = vm.runInContext('NS.sellerDetailHtml(' + JSON.stringify({
    offer_data_status: 'available', offer_data_cached: true, offer_data_fetched_at: '2026-08-14T12:00:00Z',
    buy_box: { available: true, seller_name: 'CachedSeller', fulfillment: 'FBM', price: 15.0 },
    offers: [{ seller_name: 'CachedSeller', fulfillment: 'FBM', price: 15.0 }]
}) + ')', context);
assert(cachedHtml.includes('Cached'), 's7: cached indicator present in Buy Box card');
assert(cachedHtml.includes('2026-08-14'), 's7: cached timestamp shown');

/* 8. Null seller values render Unavailable, not zero */
var bbNulls = vm.runInContext('NS.sellerDetailHtml(' + JSON.stringify({
    offer_data_status: 'available', buy_box: { available: true, seller_name: null, fulfillment: null, price: null },
    offers: [{ seller_name: null, fulfillment: null, price: null, feedback_count: null, rating: null }]
}) + ')', context);
assert(bbNulls.includes('Unavailable'), 's7: null seller values render Unavailable');
assert(!bbNulls.includes('>0<') && !bbNulls.includes('$0.00'), 's7: null values do not render as zero');

/* 9. Seller table is scoped to seller-detail (CSS does not affect Scout/Portfolio/Cycle) */
var scopedRules = fs.readFileSync(path.join(__dirname, 'static', 'index.html'), 'utf8');
assert(scopedRules.includes('.seller-detail .seller-table'), 's7: seller table CSS is scoped to .seller-detail');
assert(scopedRules.includes('.seller-detail .buy-box-card'), 's7: buy-box-card CSS is scoped to .seller-detail');
assert(scopedRules.includes('.seller-detail .seller-table-wrap'), 's7: seller-table-wrap CSS is scoped');
assert(scopedRules.includes('min-width: 900px'), 's7: seller table has min-width for horizontal scroll');

/* 10. No provider request from dossier expansion (re-verified) */
fetchCalls.length = 0;
vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(P()) + ')', context);
assert(fetchCalls.length === 0, 's7: no provider request from dossier expansion');

/* 11. Reduced-motion rule for seller spinner */
assert(scopedRules.includes('prefers-reduced-motion'), 's7: reduced-motion media query exists');
assert(scopedRules.includes('animation: none'), 's7: reduced-motion disables spinner animation');

/* ---- Cross-view visual consistency (Step 8) ---- */

/* CSS design system tokens applied to all tool views */
assert(scopedRules.includes('.calc-group {') && scopedRules.includes('box-shadow: var(--shadow)'), 'cx: calc-group cards use shadow token');
assert(scopedRules.includes('.calc-results {') && scopedRules.includes('box-shadow: var(--shadow)'), 'cx: calc-results panel uses shadow token');
assert(scopedRules.includes('font-variant-numeric: tabular-nums'), 'cx: tabular-nums applied to monetary values');
assert(scopedRules.includes('.prefill-chip') && scopedRules.includes('var(--accent-soft)'), 'cx: prefill chip uses accent-soft background');
assert(scopedRules.includes('.tip:hover') && scopedRules.includes('var(--accent-soft)'), 'cx: tip button hover uses accent-soft');
assert(scopedRules.includes('.result-total .r-value.neg') && scopedRules.includes('var(--neg-soft)'), 'cx: negative result uses neg-soft background');
assert(scopedRules.includes('.port-empty') && scopedRules.includes('var(--bg-raised)'), 'cx: portfolio empty state uses raised background');
assert(scopedRules.includes('.btn.danger-ghost:hover') && scopedRules.includes('var(--neg-soft)'), 'cx: danger button hover uses neg-soft');
assert(scopedRules.includes('.port-table th') && scopedRules.includes('10.5px'), 'cx: portfolio table header uses compact type scale');

/* Dark and light theme CSS custom properties exist */
assert(scopedRules.includes('data-theme="light"'), 'cx: light theme override defined');
assert(scopedRules.includes('data-theme="dark"') || scopedRules.includes('data-theme="light"'), 'cx: theme switching mechanism defined');
assert(scopedRules.includes('--bg-raised:'), 'cx: --bg-raised token defined');
assert(scopedRules.includes('--accent-soft:'), 'cx: --accent-soft token defined');
assert(scopedRules.includes('--neg-soft:'), 'cx: --neg-soft token defined');

/* All five views have distinct section IDs */
assert(scopedRules.includes('view-scout'), 'cx: scout view exists');
assert(scopedRules.includes('view-calculator'), 'cx: calculator view exists');
assert(scopedRules.includes('view-risk'), 'cx: risk view exists');
assert(scopedRules.includes('view-cycle'), 'cx: cycle view exists');
assert(scopedRules.includes('view-portfolio'), 'cx: portfolio view exists');

/* No backend calls during cross-view rendering */
fetchCalls.length = 0;
vm.runInContext('NS.renderCalc && NS.renderCalc()', context);
vm.runInContext('NS.renderRisk && NS.renderRisk()', context);
vm.runInContext('NS.renderCycle && NS.renderCycle()', context);
vm.runInContext('NS.renderPortfolio && NS.renderPortfolio()', context);
assert(fetchCalls.length === 0, 'cx: zero provider requests during cross-view rendering');

/* Seller table scoped CSS does not leak to Scout/Portfolio/Cycle tables */
assert(!scopedRules.includes('.scout-table') || scopedRules.includes('.seller-detail .seller-table'), 'cx: seller table CSS scoped to seller-detail');
assert(scopedRules.includes('.port-table') && !scopedRules.includes('.seller-detail .port-table'), 'cx: port-table uses own selectors (not seller-scoped)');

/* Reduced-motion covers all animated elements */
assert(scopedRules.split('prefers-reduced-motion').length >= 2, 'cx: reduced-motion rule present for tool animations');

/* ================================================================
 * Phase 9c — Refresh = LIVE pull behind a DOUBLE confirmation
 * ================================================================ */
/* Refresh is a live data operation (POST /api/kirkland/refresh). A single
 * stray click must never trigger it: the UI requires two explicit steps and
 * the server stays fail-closed (403) until the live gate is enabled. */
const priorFetch = context.fetch;
const refreshCalls = [];
let refreshRes = () => ({ ok: true, json: () => ({ status: 'ok', candidates_returned: 5, live_allowed: true }) });
const scannerRes = () => ({ ok: true, json: () => ({ status: 'ok', generated_at: '2026-09-05T10:00:00Z', summary: { cache_status: 'snapshot', scanner_mode: 'cache_only' }, products: [P({ name: 'Refreshed Product', asin: 'B0REFRESH01' })] }) });
context.fetch = (url) => { refreshCalls.push(url); return T(() => (url === '/api/kirkland/refresh' ? refreshRes() : scannerRes())); };
assert(typeof vm.runInContext('NS.confirmRefresh', context) === 'function', 'refresh: double-confirm entry point is wired on the namespace');

setState([P()], 'ok', 'ready');
refreshCalls.length = 0;

/* ONE accidental click on the control-strip Refresh: dialog opens, no call */
click('csRefreshBtn');
assert(getEl('scConfirm').hidden === false, 'refresh: control-strip refresh opens the confirmation dialog');
assert(els.scConfirmTitle.textContent.includes('Refresh catalog with a live scan?'), 'refresh: step 1 names the live scan');
assert(els.scConfirmStep.textContent.includes('Step 1 of 2'), 'refresh: dialog shows a two-stage meter');
assert(refreshCalls.length === 0, 'refresh: no request after the first click alone');

/* step 1 -> step 2 still issues nothing */
click('scConfirmOk');
assert(refreshCalls.length === 0, 'refresh: step 2 still issues no request');
assert(els.scConfirmTitle.textContent.includes('Final confirmation'), 'refresh: step 2 is the final confirmation');
assert(els.scConfirmOk.textContent.includes('run live refresh'), 'refresh: final button explicitly says it runs a live refresh');

/* Cancel from the final stage: closed, nothing executed */
click('scConfirmCancel');
assert(getEl('scConfirm').hidden === true, 'refresh: cancel closes the dialog from the final stage');
assert(refreshCalls.length === 0, 'refresh: cancel executes nothing');

/* full double confirmation executes exactly one live pull, then reloads */
refreshCalls.length = 0;
setState([P()], 'ok', 'ready');
click('csRefreshBtn');
click('scConfirmOk');
click('scConfirmOk');
assert(refreshCalls.length === 2 && refreshCalls[0] === '/api/kirkland/refresh', 'refresh: POST /api/kirkland/refresh issued right after the second confirmation');
assert(getEl('scConfirm').hidden === true, 'refresh: dialog dismissed the moment the run begins');
assert(refreshCalls[1] === 'http://127.0.0.1:8000/api/kirkland/scanner', 'refresh: catalog reloads via the cache-only scanner endpoint');
assert(els.tableBody.innerHTML.includes('Refreshed Product'), 'refresh: fresh data renders after a successful live pull');
assert(els.scRefreshNotice.textContent.includes('Live refresh completed') && els.scRefreshNotice.textContent.includes('5 candidates'), 'refresh: completion notice carries the real candidate count');
assert(els.scRefreshNotice.className.indexOf('ok') !== -1, 'refresh: completion notice styled as ok');
assert(vm.runInContext('scoutState.dataFromCache', context) === false, 'refresh: live data replaces the cache view');

/* toolbar "Refresh scan" goes through the same double gate */
refreshCalls.length = 0;
setState([P()], 'ok', 'ready');
click('refreshBtn');
assert(getEl('scConfirm').hidden === false, 'refresh: toolbar refresh also opens the dialog');
assert(refreshCalls.length === 0, 'refresh: toolbar refresh never fires on a single click');
click('scConfirmCancel');
assert(refreshCalls.length === 0, 'refresh: toolbar refresh cancel fires nothing');

/* retry stays instant: a plain cache-only reload, never a live pull */
refreshCalls.length = 0;
setState([P()], 'error', 'ready');
click('retryBtn');
assert(getEl('scConfirm').hidden === true, 'refresh: retry never opens the confirm dialog');
assert(refreshCalls.indexOf('/api/kirkland/refresh') === -1, 'refresh: retry performs no live POST');
assert(refreshCalls.indexOf('http://127.0.0.1:8000/api/kirkland/scanner') !== -1, 'refresh: retry is a plain cache-only scanner reload');

/* server fails closed (gate off): honest refusal notice, nothing swapped */
refreshCalls.length = 0;
refreshRes = () => ({ ok: false, status: 403, json: () => ({ detail: 'Live refresh is disabled: set SCANNER_LIVE_ALLOWED and approve the live gate before running live scans.' }) });
setState([P()], 'ok', 'ready');
click('csRefreshBtn');
click('scConfirmOk');
click('scConfirmOk');
assert(refreshCalls[0] === '/api/kirkland/refresh', 'refresh: gate-refusal path still issues the POST');
assert(refreshCalls.length === 1, 'refresh: refused run performs no follow-up scanner GET');
assert(els.scRefreshNotice.textContent.includes('refused') && els.scRefreshNotice.textContent.includes('SCANNER_LIVE_ALLOWED'), 'refresh: fail-closed refusal surfaced with the exact server note');
assert(els.scRefreshNotice.className.indexOf('warn') !== -1, 'refresh: refusal styled as a warning');
assert(els.tableBody.innerHTML.includes('Kirkland Test Product'), 'refresh: cached data stays in place after a refusal');

/* network failure: warn notice, no swap, buttons restored */
refreshCalls.length = 0;
refreshRes = () => { throw new Error('network unreachable'); };
setState([P()], 'ok', 'ready');
click('csRefreshBtn');
click('scConfirmOk');
click('scConfirmOk');
assert(els.scRefreshNotice.textContent.includes('failed'), 'refresh: network failure surfaced as a warning');
assert(els.scRefreshNotice.className.indexOf('warn') !== -1, 'refresh: failure styled as a warning');
assert(els.csRefreshBtn.disabled === false && els.refreshBtn.disabled === false, 'refresh: refresh buttons restored after failure');

/* restore the earlier fetch tracker for the remainder of the suite */
refreshRes = () => ({ ok: true, json: () => SELLER_FIXTURE_PARTIAL });
context.fetch = priorFetch;

/* ================================================================
 * Phase 10 — inspection lifecycle, sales honesty, high-confidence
 * ================================================================ */

/* single global keydown handler registered exactly once at init */
assert((domEvents.keydown || []).length === 1, 'p10: exactly one global keydown handler registered');

/* Escape with nothing open: no-op, no crash */
fireKey('Escape');
assert(vm.runInContext('_drawerOpen', context) === false, 'p10: Escape with nothing open keeps drawer closed');
assert(vm.runInContext('_sheetProduct', context) === null, 'p10: Escape with nothing open keeps sheet closed');

/* drawer lifecycle: open -> Escape closes only the drawer */
setState(full);
vm.runInContext('NS.openDrawer("B0TEST0001")', context);
assert(vm.runInContext('_drawerOpen', context) === true, 'p10: openDrawer sets _drawerOpen');
assert(documentStub.body.style.overflow === 'hidden', 'p10: drawer open locks page scroll');
fireKey('Escape');
assert(vm.runInContext('_drawerOpen', context) === false, 'p10: Escape closes the drawer');
assert(documentStub.body.style.overflow === '', 'p10: drawer close restores scroll when no sheet open');
assert(vm.runInContext('_sheetProduct', context) === null, 'p10: Escape does not open/affect the sheet');

/* sheet lifecycle: open -> Escape closes only the sheet */
vm.runInContext('NS.openSheet(' + JSON.stringify(P()) + ', null)', context);
assert(vm.runInContext('_sheetProduct', context) !== null, 'p10: openSheet sets _sheetProduct');
assert(documentStub.body.style.overflow === 'hidden', 'p10: sheet open locks page scroll');
fireKey('Escape');
assert(vm.runInContext('_sheetProduct', context) === null, 'p10: Escape closes the sheet');
assert(documentStub.body.style.overflow === '', 'p10: sheet close restores scroll when no drawer open');

/* sheet + drawer both open: Escape closes the TOPMOST panel only */
vm.runInContext('NS.openDrawer("B0TEST0001")', context);
vm.runInContext('NS.openSheet(' + JSON.stringify(P()) + ', null)', context);
assert(documentStub.body.style.overflow === 'hidden', 'p10: both panels open lock scroll');
fireKey('Escape');
assert(vm.runInContext('_sheetProduct', context) === null, 'p10: Escape closes the sheet first (topmost)');
assert(vm.runInContext('_drawerOpen', context) === true, 'p10: drawer stays open after sheet closes');
assert(documentStub.body.style.overflow === 'hidden', 'p10: scroll stays locked while drawer remains open');
vm.runInContext('NS.closeDrawer()', context);
assert(documentStub.body.style.overflow === '', 'p10: closeDrawer restores scroll when no sheet open');

/* repeated drawer cycles never stack keydown listeners */
for (let i = 0; i < 3; i++) {
    vm.runInContext('NS.openDrawer("B0TEST0001")', context);
    fireKey('Escape');
}
assert(domEvents.keydown.length === 1, 'p10: drawer re-open cycles keep exactly one keydown handler');

/* high_confidence pack badge renders as positive (not candidate) */
const hcBadge = vm.runInContext('NS.packMatchBadge({ pack_match: "high_confidence" })', context);
assert(hcBadge.includes('Pack/Variant: High confidence') && hcBadge.includes('badge pos'), 'p10: high_confidence badge is positive-labeled');

/* drawer and sheet label high_confidence rows as Likely match / verify before buy */
setState([P({ pack_match: 'high_confidence', verdict: 'Pass' })]);
vm.runInContext('NS.openDrawer("B0TEST0001")', context);
const hcDrawerHtml = els.drawerScroll.innerHTML;
assert(hcDrawerHtml.includes('Likely match'), 'p10: drawer labels high_confidence as Likely match');
assert(hcDrawerHtml.includes('verify UPC, pack size, and variant before buying'), 'p10: drawer verify-before-buy text for high_confidence');
vm.runInContext('NS.closeDrawer()', context);
vm.runInContext('renderSheetContent("verify", ' + JSON.stringify(P({ pack_match: 'high_confidence', verdict: 'Pass' })) + ')', context);
const hcSheetHtml = els.sheetContent.innerHTML;
assert(hcSheetHtml.includes('High confidence match'), 'p10: sheet verify flag for high_confidence');
assert(hcSheetHtml.includes('verify UPC, pack size, and variant before buying'), 'p10: sheet verify-before-buy text for high_confidence');
setState(full);

/* pack match filter select offers high_confidence and sanitizer accepts it */
assert(html.includes('value="high_confidence"'), 'p10: pack match filter offers High confidence option');
assert(vm.runInContext('sanitizeFilters({ packMatch: "high_confidence" }).packMatch', context) === 'high_confidence', 'p10: sanitizeFilters accepts high_confidence');
assert(vm.runInContext('sanitizeFilters({ packMatch: "bogus" }).packMatch', context) === 'all', 'p10: sanitizeFilters rejects unknown packMatch');

/* NS.fmtSales: compact formatting with null passthrough */
assert(vm.runInContext('NS.fmtSales(null)', context) === null, 'p10: fmtSales(null) -> null');
assert(vm.runInContext('NS.fmtSales(999)', context) === '999', 'p10: fmtSales under 1,000 stays integer');
assert(vm.runInContext('NS.fmtSales(12400)', context) === '12.4K', 'p10: fmtSales 12,400 -> 12.4K');
assert(vm.runInContext('NS.fmtSales(1200000)', context) === '1.2M', 'p10: fmtSales 1.2M -> 1.2M');

/* sales total line aggregates visible estimates (nulls ignored) */
setState(full);
assert(els.salesTotalLine.textContent === 'Total Est. Monthly Sales: 1.5K', 'p10: total line sums known estimates only (1500 -> 1.5K)');
setState([P({ asin: 'B0TEST0009', name: 'All Null Sales', monthly_sales_estimate: null, monthly_sales_estimated: false })], 'ok', 'ready');
assert(els.salesTotalLine.textContent === 'Total Est. Monthly Sales: Unknown', 'p10: total line Unknown when no estimates present');
setState([]);
assert(els.salesTotalLine.textContent === '', 'p10: total line cleared when table empty');
setState(full);

/* sales cell renders compact formatted value with honest title */
const salesCellOut = els.tableBody.innerHTML;
assert(salesCellOut.includes('1.5K'), 'p10: sales cell renders compact 1.5K');
assert(salesCellOut.includes('Est. Monthly Sales is a provider estimate, not verified sales'), 'p10: sales cell carries estimate qualifier title');

/* sort control select wires into sortKey through readFiltersFromInputs */
vm.runInContext(`currentFilters = NS.defaultFilters(); sortKey = 'profit_desc';`, context);
els['fSort'].value = 'sales_asc';
vm.runInContext('readFiltersFromInputs()', context);
assert(vm.runInContext('sortKey', context) === 'sales_asc', 'p10: fSort select drives sortKey');
els['fSort'].value = 'bogus_key';
vm.runInContext('readFiltersFromInputs()', context);
assert(vm.runInContext('sortKey', context) === 'sales_asc', 'p10: invalid fSort value keeps previous sortKey');

/* sort select options include the new asc/name/cost keys */
assert(html.includes('value="sales_asc"'), 'p10: sort popover offers Est. Monthly Sales Low to High');
assert(html.includes('value="cost_desc"'), 'p10: sort popover offers Costco COGS High to Low');
assert(html.includes('value="name_asc"'), 'p10: sort popover offers Product A to Z');
assert(html.includes('value="asin_asc"'), 'p10: sort popover offers ASIN A to Z');

/* ================================================================
 * Phase 11 — readiness, evidence, completeness, cache-safety UI
 * ================================================================ */

/* opportunity-readiness filter select + sanitizer + filter logic */
assert(html.includes('id="fReadiness"'), 'p11: readiness filter select present');
assert(vm.runInContext('sanitizeFilters({ readiness: "complete_opportunity" }).readiness', context) === 'complete_opportunity', 'p11: sanitizeFilters accepts readiness values');
assert(vm.runInContext('sanitizeFilters({ readiness: "bogus" }).readiness', context) === 'all', 'p11: sanitizeFilters rejects unknown readiness');
const readPool = [
    P({ asin: 'B0TEST0011', name: 'Ready Row', opportunity_readiness: 'complete_opportunity' }),
    P({ asin: 'B0TEST0012', name: 'Fee Row', opportunity_readiness: 'economics_provisional' }),
    P({ asin: 'B0TEST0013', name: 'Missing Cost', opportunity_readiness: 'needs_costco_match', costco_cost: null }),
    P({ asin: 'B0TEST0014', name: 'Mismatch Row', opportunity_readiness: 'blocked_mismatch' }),
];
let readF = vm.runInContext('NS.filterProducts(' + JSON.stringify(readPool) + ', ' + JSON.stringify(filtersFor({ readiness: 'complete_opportunity' })) + ')', context);
assert(readF.length === 1 && readF[0].asin === 'B0TEST0011', 'p11: readiness filter isolates complete_opportunity');
readF = vm.runInContext('NS.filterProducts(' + JSON.stringify(readPool) + ', ' + JSON.stringify(filtersFor({ readiness: 'blocked_mismatch' })) + ')', context);
assert(readF.length === 1 && readF[0].asin === 'B0TEST0014', 'p11: readiness filter isolates blocked_mismatch');
readF = vm.runInContext('NS.filterProducts(' + JSON.stringify(readPool) + ', ' + JSON.stringify(filtersFor({ readiness: 'all' })) + ')', context);
assert(readF.length === 4, 'p11: readiness all keeps every row');
assert(vm.runInContext('filterCount(' + JSON.stringify(filtersFor({ readiness: 'blocked_mismatch' })) + ')', context) === 1, 'p11: filterCount counts readiness');

/* completeness sorts */
const compPool = [
    P({ asin: 'B0TEST0021', name: 'Low Complete', data_completeness_score: 30, net_profit: 20 }),
    P({ asin: 'B0TEST0022', name: 'High Complete', data_completeness_score: 90, net_profit: 5 }),
    P({ asin: 'B0TEST0023', name: 'No Score', net_profit: 10 }),
];
let compSorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(compPool) + ', "completeness_desc")', context);
assert(compSorted[0].asin === 'B0TEST0022' && compSorted[2].asin === 'B0TEST0023', 'p11: completeness_desc sorts high first, nulls last');
compSorted = vm.runInContext('NS.sortProducts(' + JSON.stringify(compPool) + ', "completeness_asc")', context);
assert(compSorted[0].asin === 'B0TEST0021' && compSorted[2].asin === 'B0TEST0023', 'p11: completeness_asc sorts low first, nulls last');
assert(html.includes('value="completeness_desc"') && html.includes('value="completeness_asc"'), 'p11: both completeness sort options present');

/* dossier: readiness / next step / freshness rows in g1 */
const readyProd = P({
    opportunity_readiness: 'needs_seller_data',
    recommended_next_step: 'enrich_sales_and_sellers',
    data_completeness_score: 60,
    freshness_label: 'Fresh',
    freshness_basis: 'cache_fetched_at',
});
const g1Html = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(readyProd) + ')', context);
assert(g1Html.includes('needs_seller_data') && g1Html.includes('enrich_sales_and_sellers'), 'p11: dossier g1 carries readiness and next step');
assert(g1Html.includes('60 / 100'), 'p11: dossier g1 carries completeness score');
assert(g1Html.includes('Fresh') && g1Html.includes('cache fetched at'), 'p11: dossier g1 carries freshness label and basis');
assert((g1Html.match(/ns-dossier-group/g) || []).length === 5, 'p11: evidence does not add a sixth dossier group');

/* dossier: match evidence renders in g2 */
const evidenceProd = P({
    match_evidence: {
        match_quality: 'high_confidence',
        match_reason: 'title identity; pack count matches',
        evidence: {
            title_similarity: 0.95,
            title_dice: 0.9,
            title_tokens: { amazon: 6, costco: 5, shared: 4 },
            upc: { state: 'one_sided' },
            pack_count: { state: 'match' },
            weight_volume: { state: 'conflict' },
            flavor_variant: { state: 'match' },
            known_conflicts: [],
        },
    },
});
const evHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(evidenceProd) + ')', context);
assert(evHtml.includes('evidence-list'), 'p11: evidence list renders in dossier');
assert(evHtml.includes('Title similarity') && evHtml.includes('0.95'), 'p11: evidence shows title similarity value');
assert(evHtml.includes('Pack count') && evHtml.includes('match'), 'p11: evidence shows pack count state');
assert(evHtml.includes('conflict'), 'p11: evidence surfaces weight conflict honestly');

/* dossier: FBA disclaimer and referral estimate label */
const feeProd = P({ fba_fee: null, fba_base_fee: null, fba_fuel_logistics_surcharge: null, referral_fee: 7.33, referral_fee_rate: 0.15, referral_fee_confidence: 'default_category', economics_confidence: 'provisional' });
const feeHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(feeProd) + ')', context);
assert(feeHtml.includes('Referral fee (est.)'), 'p11: referral row labeled (est.) when default category');
assert(feeHtml.includes('FBA fee: Unknown — verify before buying'), 'p11: FBA disclaimer note when fee missing');
assert(feeHtml.includes('never an FBA fee'), 'p11: disclaimer states referral is never an FBA fee');
const feeHtml2 = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(P({ referral_fee_confidence: 'verified_category' })) + ')', context);
assert(feeHtml2.includes('>Referral fee<') && !feeHtml2.includes('Referral fee (est.)'), 'p11: verified-category rows keep the plain referral label');

/* drawer fee labels stay honest when FBA missing */
const drawerFeeHtml = vm.runInContext('renderDrawerContent(' + JSON.stringify(P({ fba_fee: null, referral_fee_pct: 0.15, verdict: 'Needs Fee Verification' })) + ')', context);
assert(drawerFeeHtml.includes('Unknown — verify before buying'), 'p11: drawer FBA cell says Unknown — verify before buying');
assert(drawerFeeHtml.includes('Referral Fee (est.)') && drawerFeeHtml.includes('not FBA'), 'p11: drawer referral labeled estimate, not FBA');

/* KPI tooltip carries honest coverage denominators */
setState([P({ pack_match: 'exact' }), P({ pack_match: 'candidate' }), P({ pack_match: 'high_confidence' })]);
assert(els['tip-candidates'].textContent.includes('2/3'), 'p11: candidates tooltip shows match coverage 2/3');
assert(els['tip-candidates'].textContent.includes('economics-ready'), 'p11: candidates tooltip mentions economics-ready');
setState(full);

/* cache rail: read-only label + cache-only safety indicator from summary */
vm.runInContext(`
    scoutState = {
        status: 'ok',
        generatedAt: '2026-08-17T06:59:33Z',
        costcoCatalog: 'ready',
        dataFromCache: true,
        cacheStale: false,
        cacheMeta: {
            source: 'brightdata',
            fetchedAt: '2026-08-17T06:59:33+00:00',
            status: 'fresh',
            mode: 'cache_only',
            enrichment: 'OFF',
        },
        products: ${JSON.stringify([P()])},
    };
    currentFilters = NS.defaultFilters();
    sortKey = 'profit_desc';
    NS.renderScout();
`, context, { filename: 'setStateRail' });
assert(els.railCacheText.textContent.includes('brightdata') && els.railCacheText.textContent.includes('read-only, no live calls'), 'p11: cache rail shows source + read-only label');
assert(els.railSafety.hidden === false && els.railSafetyText.textContent.includes('Enrichment: OFF — cache-only'), 'p11: cache-safety indicator shows cache-only mode');
vm.runInContext(`
    scoutState.cacheMeta = { mode: 'live_search', enrichment: 'BRIGHTDATA' };
    scoutState.dataFromCache = false;
    renderSourceRail();
`, context);
assert(els.railSafety.hidden === true, 'p11: cache-safety indicator hidden for live data');

/* ================================================================
 * Phase 12 — Local market snapshot block (g4, read-only merge)
 * ================================================================ */
/* no snapshot_* keys on the row => no snapshot block at all */
const snapNone = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(P()) + ')', context);
assert(!snapNone.includes('Local market snapshot'), 'p12: no snapshot block when row carries no snapshot keys');

/* available snapshot: badge, provenance, observed counts, buy box */
const snapAvailable = P({
    snapshot_status: 'available',
    snapshot_source: 'easyparser',
    snapshot_observed_at: '2026-08-17T06:59:33+00:00',
    snapshot_freshness: 'fresh',
    snapshot_offers_complete: true,
    snapshot_offers_returned: 2,
    snapshot_fbm_sellers: 1,
    snapshot_amazon_sellers: 1,
    snapshot_buy_box_available: true,
    snapshot_buy_box_price: 56.66,
    snapshot_buy_box_fulfillment: 'Amazon',
    snapshot_buy_box_seller: 'Amazon.com',
});
const snapAvHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(snapAvailable) + ')', context);
assert(snapAvHtml.includes('Local market snapshot'), 'p12: available snapshot block renders in g4');
assert(snapAvHtml.includes('Offers available'), 'p12: available status badge shown');
assert(snapAvHtml.includes('easyparser'), 'p12: snapshot source shown');
assert(snapAvHtml.includes('2026-08-17T06:59:33+00:00'), 'p12: observed-at timestamp shown');
assert(snapAvHtml.includes('1 FBM') && snapAvHtml.includes('1 Amazon'), 'p12: observed seller counts shown');
assert(snapAvHtml.includes('$56.66'), 'p12: buy box price from snapshot shown');
assert(snapAvHtml.includes('Offer-level seller detail unavailable in local snapshot'), 'p12: offer-level detail disclosure present');
assert(!snapAvHtml.includes('Returned offer sample is partial'), 'p12: no partial warning for complete roster');

/* partial snapshot: warning label + partial disclosure, no buy box */
const snapPartial = P({
    snapshot_status: 'partial',
    snapshot_source: 'easyparser',
    snapshot_observed_at: '2026-08-17T06:59:33+00:00',
    snapshot_freshness: 'fresh',
    snapshot_offers_complete: false,
    snapshot_offers_returned: 2,
    snapshot_fbm_sellers: 2,
    snapshot_amazon_sellers: 0,
});
const snapPartHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(snapPartial) + ')', context);
assert(snapPartHtml.includes('Partial offers'), 'p12: partial status badge shown');
assert(snapPartHtml.includes('Returned offer sample is partial.'), 'p12: partial roster disclosure shown');
assert(snapPartHtml.includes('2 FBM') && snapPartHtml.includes('0 Amazon'), 'p12: observed counts honest when amazon absent (0 observed)');
assert(snapPartHtml.includes('Not loaded'), 'p12: buy box shows Not loaded when unavailable');
const snapPartBlock = snapPartHtml.slice(snapPartHtml.indexOf('Local market snapshot'), snapPartHtml.indexOf('Total sellers'));
assert(!snapPartBlock.includes('$'), 'p12: no fabricated price in snapshot block when buy box missing');

/* stale snapshot: stale warning, no fake freshness */
const snapStale = P({
    snapshot_status: 'available',
    snapshot_source: 'easyparser',
    snapshot_observed_at: '2026-08-01T06:59:33+00:00',
    snapshot_freshness: 'stale',
    snapshot_offers_complete: true,
    snapshot_offers_returned: 2,
    snapshot_fbm_sellers: 1,
    snapshot_amazon_sellers: 1,
});
const snapStaleHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(snapStale) + ')', context);
assert(snapStaleHtml.includes('Snapshot stale'), 'p12: stale warning shown');

/* failed snapshot: failure badge + note, no offers/price */
const snapFailed = P({
    snapshot_status: 'failed',
    snapshot_source: 'easyparser',
    snapshot_observed_at: '2026-08-17T06:59:33+00:00',
    snapshot_freshness: 'unknown',
    snapshot_data_gaps: ['HTTP 500.'],
});
const snapFailHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(snapFailed) + ')', context);
assert(snapFailHtml.includes('Snapshot failed'), 'p12: failed status badge shown');
assert(snapFailHtml.includes('stale or missing'), 'p12: failed note explains data state');
assert(snapFailHtml.includes('>Unknown<'), 'p12: failed snapshot shows Unknown sellers, never 0');
assert(!snapFailHtml.includes('$0'), 'p12: failed snapshot never fabricates prices');

/* no snapshot block in the primary compact table */
setState([snapAvailable], 'ok', 'ready');
assert(!els.tableBody.innerHTML.includes('Local market snapshot'), 'p12: snapshot block absent from primary table');

/* ================================================================
 * Phase 13 — Phase 3 intel: Demand/Competition/Opportunity groups,
 * Phase 3 filters and sorts, unknown-roster honesty rendering
 * ================================================================ */
const titleCount = (h) => (h.match(/ns-dossier-title/g) || []).length;

/* full intel row renders g6 + g7 + g8 (8 dossier groups) */
const intelFull = P({
    estimated_monthly_sales: 3555,
    sales_estimate_low: 2488,
    sales_estimate_high: 4622,
    sales_estimation_method: 'bsr_category_model',
    sales_estimation_source: 'bsr_category_model',
    sales_estimation_confidence: 'medium',
    calibration_model_name: 'northstar-bsr',
    calibration_model_version: '1.0',
    bsr: 500,
    bsr_category: 'Home & Kitchen',
    observed_total_sellers: 3,
    observed_fba_sellers: 2,
    observed_fbm_sellers: 1,
    observed_amazon_sellers: 0,
    claimed_offer_count: 3,
    offers_returned: 3,
    offers_complete: true,
    observed_buy_box_available: true,
    observed_buy_box_price: 56.66,
    observed_buy_box_fulfillment: 'Amazon',
    observed_buy_box_seller: 'Amazon.com',
    lowest_returned_offer_price: 49.99,
    lowest_returned_landed_price: 49.99,
    highest_returned_landed_price: 56.66,
    returned_offer_price_spread: 6.67,
    prime_offer_count: 2,
    fulfilled_by_amazon_offer_count: 2,
    estimated_units_per_observed_seller: 1185,
    seller_share_confidence: 'medium',
    seller_share_basis: 'complete returned offer set (3)',
    seller_share_note: 'Estimated allocation only.',
    portfolio_readiness: 'complete_opportunity',
    portfolio_next_step: 'review_top_opportunity',
    portfolio_category: 'core_replenishable',
    risk_flags: ['low_demand'],
    portfolio_score_reasons: ['strong margin'],
    estimated_monthly_revenue: 201425,
    monthly_revenue_basis: 'observed_buy_box_landed_price',
    monthly_revenue_confidence: 'medium',
    estimated_monthly_profit_pool: 60400,
    estimated_fba_seller_monthly_profit: 30200,
    estimated_fbm_seller_monthly_profit: 60400,
    estimated_observed_seller_monthly_profit: 20133,
    total_completeness_score: 100,
    monthly_pool_note: 'Modeled estimate - not a forecast.',
});
const intelFullHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelFull) + ')', context);
assert(titleCount(intelFullHtml) === 8, 'p13: full intel row renders 8 dossier groups');
assert(intelFullHtml.includes('Demand (est.)'), 'p13: g6 title rendered');
assert(intelFullHtml.includes('Est. monthly sales'), 'p13: g6 est monthly sales row');
assert(intelFullHtml.includes('3,555'), 'p13: demand value formatted with thousands');
assert(intelFullHtml.includes('Est.</span>'), 'p13: est-chip labels modeled demand');
assert(intelFullHtml.includes('Competition (observed)'), 'p13: g7 title rendered');
assert(intelFullHtml.includes('Est. share / seller'), 'p13: g7 share row present');
assert(intelFullHtml.includes('1,185'), 'p13: share value formatted');
assert(intelFullHtml.includes('Opportunity (est.)'), 'p13: g8 title rendered');
assert(intelFullHtml.includes('Est. monthly revenue'), 'p13: g8 revenue row');
assert(intelFullHtml.includes('Revenue basis'), 'p13: g8 revenue basis row');
assert(intelFullHtml.includes('observed buy box landed price'), 'p13: buy box landed price basis disclosed');
assert(intelFullHtml.includes('Risk flags'), 'p13: g8 risk flags row');
assert(intelFullHtml.includes('100 / 100'), 'p13: completeness score rendered');
assert(intelFullHtml.includes('core replenishable'), 'p13: category badge rendered');

/* legacy-only row (sales_rank but no intel keys) keeps the 5-group dossier */
const intelLegacy = P({ sales_rank: 2000 });
const intelLegacyHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelLegacy) + ')', context);
assert(titleCount(intelLegacyHtml) === 5, 'p13: legacy-only row keeps exactly 5 dossier groups');
assert(!intelLegacyHtml.includes('Demand (est.)'), 'p13: no g6 without intel fields');
assert(!intelLegacyHtml.includes('Competition (observed)'), 'p13: no g7 without intel fields');
assert(!intelLegacyHtml.includes('Opportunity (est.)'), 'p13: no g8 without portfolio fields');

/* unknown roster: g7 renders with Unknown counts and the never-0 warning */
const intelUnknownRoster = P({
    offer_roster_reason: 'offer_roster_unavailable',
    offers_complete: null,
    offers_returned: null,
});
const intelUnknownHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelUnknownRoster) + ')', context);
assert(intelUnknownHtml.includes('Competition (observed)'), 'p13: g7 renders for unknown roster');
assert(intelUnknownHtml.includes('seller counts are Unknown, never 0'), 'p13: unknown roster warning text');
assert(intelUnknownHtml.includes('>Unknown<'), 'p13: observed sellers render Unknown, never 0');
const unknownBlock = intelUnknownHtml.slice(intelUnknownHtml.indexOf('Competition (observed)'), intelUnknownHtml.indexOf('Actions & Next Step'));
assert(!unknownBlock.includes('Observed sellers</td><td>0'), 'p13: no zero seller count in unknown roster block');

/* partial roster with no returned offers */
const intelPartialZero = P({ offer_roster_reason: 'partial_offer_roster', observed_total_sellers: null });
const intelPartialZeroHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelPartialZero) + ')', context);
assert(intelPartialZeroHtml.includes('Partial roster with no returned offers \u2014 seller counts are Unknown.'), 'p13: partial-zero roster disclosure');

/* no explicit zero-offer evidence */
const intelNoEvidence = P({ offer_roster_reason: 'no_explicit_zero_offer_evidence' });
const intelNoEvidenceHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelNoEvidence) + ')', context);
assert(intelNoEvidenceHtml.includes('No explicit zero-offer evidence \u2014 seller counts are Unknown.'), 'p13: no-zero-evidence disclosure');

/* explicit zero-offer proof shows real zeros + proof note */
const intelZeroProof = P({
    observed_total_sellers: 0,
    observed_fba_sellers: 0,
    observed_fbm_sellers: 0,
    observed_amazon_sellers: 0,
    claimed_offer_count: 0,
    offers_returned: 0,
    offers_complete: true,
    prime_offer_count: 0,
    fulfilled_by_amazon_offer_count: 0,
});
const intelZeroHtml = vm.runInContext('NS.feeBreakdownHtml(' + JSON.stringify(intelZeroProof) + ')', context);
assert(intelZeroHtml.includes('Provider-confirmed complete zero-offer set (claimed 0, returned 0).'), 'p13: zero-proof note shown');
assert(intelZeroHtml.includes('Observed sellers</span><span class="dossier-value">0'), 'p13: explicit zero observed sellers rendered');

/* filter controls and options present */
['fHasBsr', 'fHasEstSales', 'fSalesConf', 'fOfferComplete', 'fStaleSnapshot', 'fRiskFlag', 'fPortCat', 'fPortReadiness', 'fMinEstUnits', 'fMinEstRev', 'fMinEstPool'].forEach((id) => {
    assert(html.includes('id="' + id + '"'), 'p13: filter control present: ' + id);
});
['est_rev_desc', 'est_rev_asc', 'pool_desc', 'pool_asc', 'units_desc', 'units_asc'].forEach((k) => {
    assert(html.includes('value="' + k + '"'), 'p13: sort option present: ' + k);
});
assert(vm.runInContext('typeof SORTS.est_rev_desc === "function" && typeof SORTS.units_asc === "function"', context), 'p13: SORTS registry has Phase 3 sort keys');

/* Phase 3 filters behave honestly (unknown never matches) */
const intelPool = [
    P({ name: 'Core', asin: 'B000000001', portfolio_readiness: 'complete_opportunity', portfolio_category: 'core_replenishable', risk_flags: [], offers_complete: true, sales_estimation_confidence: 'medium', estimated_monthly_revenue: 5000, estimated_monthly_profit_pool: 900, estimated_units_per_observed_seller: 120, snapshot_freshness: 'fresh' }),
    P({ name: 'Watch', asin: 'B000000002', portfolio_readiness: 'needs_seller_data', portfolio_category: 'watchlist', risk_flags: ['offer_roster_unavailable'], offers_complete: null, sales_estimation_confidence: 'unknown', estimated_monthly_revenue: null, estimated_monthly_profit_pool: null, estimated_units_per_observed_seller: null, snapshot_freshness: 'stale' }),
    P({ name: 'Legacy', asin: 'B000000003', risk_flags: ['thin_margin'], offers_complete: false, sales_estimation_confidence: 'low', estimated_monthly_revenue: 2000, estimated_monthly_profit_pool: 100, estimated_units_per_observed_seller: 10, snapshot_freshness: 'unknown' }),
];
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ portCat: 'core_replenishable' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: portfolio category filter');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ portReadiness: 'complete_opportunity' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: portfolio readiness filter');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ riskFlag: 'any' })) + ')', context);
assert(f.length === 2, 'p13: riskFlag any keeps only flagged rows');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ riskFlag: 'none' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: riskFlag none keeps unflagged rows');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ offerComplete: 'complete' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: offerComplete complete filter');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ offerComplete: 'partial' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000003', 'p13: offerComplete partial filter (unknown not matched)');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ salesConf: 'medium' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: sales confidence filter');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ staleSnapshot: 'yes' })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000002', 'p13: stale snapshot filter (unknown not stale)');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ minEstRev: 3000 })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: min est revenue filter excludes unknowns');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ minEstPool: 500 })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: min est profit pool filter');
f = vm.runInContext('NS.filterProducts(' + JSON.stringify(intelPool) + ', ' + JSON.stringify(filtersFor({ minEstUnits: 100 })) + ')', context);
assert(f.length === 1 && f[0].asin === 'B000000001', 'p13: min est units per seller filter');

/* Phase 3 sorts: revenue desc puts known first, unknown last */
const intelSortPool = [
    P({ name: 'UnknownRev', asin: 'B000000001', estimated_monthly_revenue: null, estimated_monthly_profit_pool: null }),
    P({ name: 'BigRev', asin: 'B000000002', estimated_monthly_revenue: 9000, estimated_monthly_profit_pool: 1000 }),
    P({ name: 'MidRev', asin: 'B000000003', estimated_monthly_revenue: 5000, estimated_monthly_profit_pool: 500 }),
];
f = vm.runInContext('NS.sortProducts(' + JSON.stringify(intelSortPool) + ', "est_rev_desc")', context);
assert(f[0].asin === 'B000000002' && f[1].asin === 'B000000003' && f[2].asin === 'B000000001', 'p13: est_rev_desc sorts known desc, unknown last');
f = vm.runInContext('NS.sortProducts(' + JSON.stringify(intelSortPool) + ', "pool_desc")', context);
assert(f[0].asin === 'B000000002' && f[2].asin === 'B000000001', 'p13: pool_desc sorts by profit pool desc');

/* ================================================================
 * Phase 14 — sheet + sort interactions (real event dispatch)
 * ================================================================ */
assert(html.includes('role="tablist"') && html.includes('role="tab"') && html.includes('role="tabpanel"'), 'p14: sheet nav has ARIA tablist/tab/tabpanel roles');
assert(html.includes('aria-controls="sheetContent"') && html.includes('id="sheetContent"'), 'p14: tabs wire aria-controls to the sheet panel');

const sheetProd = P({ asin: 'B5TEST0001', name: 'Interaction Item', amazon_price: 42.0, costco_cost: 18.0, net_profit: 9.9, roi_pct: 55.0, fba_fee: 6.5, total_sellers: 4, fba_sellers: 1, monthly_sales_estimate: 800, monthly_sales_estimated: true, verdict: 'Pass', pack_match: 'exact', economics_status: 'estimated_fee_stack', economics_confidence: 'estimated' });
setState([sheetProd], 'ok', 'ready');
vm.runInContext('NS.openSheet(' + JSON.stringify(sheetProd) + ', null)', context);
assert(vm.runInContext('_sheetProduct', context) !== null, 'p14: sheet opens from NS.openSheet');
assert(els.inspectionSheet.classList.contains('open'), 'p14: sheet gains .open class');
assert(els.sheetOverlay.hidden === false, 'p14: sheet open unhides the overlay');

const segPanels = {
    overview: 'Data availability',
    source: 'Costco Source',
    economics: 'Fee Breakdown',
    market: 'Market &amp; Competition',
    verify: 'Verification Flags',
};
Object.keys(segPanels).forEach((seg) => {
    const btn = seedTabs.find((t) => t.getAttribute('data-segment') === seg);
    click('sheetNav', btn);
    assert(btn.classList.contains('active'), 'p14: ' + seg + ' tab becomes active');
    assert(btn.getAttribute('aria-selected') === 'true', 'p14: ' + seg + ' tab sets aria-selected=true');
    assert(els.sheetContent.innerHTML.includes(segPanels[seg]), 'p14: ' + seg + ' tab renders its own panel content');
    const othersInactive = seedTabs.filter((t) => t !== btn).every((t) => !t.classList.contains('active') && t.getAttribute('aria-selected') === 'false');
    assert(othersInactive, 'p14: ' + seg + ' tab deactivates all other tabs');
});

/* browser-style activation sequences: pointerdown->pointerup->click and
 * focus->keydown->keyup (browsers synthesize click on Enter/Space) must
 * both change the visible active tab and the visible panel content */
vm.runInContext('NS.openSheet(' + JSON.stringify(sheetProd) + ', null)', context);
const srcBtn = seedTabs.find((t) => t.getAttribute('data-segment') === 'source');
fireEvent('sheetNav', 'pointerdown', srcBtn);
fireEvent('sheetNav', 'pointerup', srcBtn);
fireEvent('sheetNav', 'click', srcBtn);
assert(srcBtn.classList.contains('active') && els.sheetContent.innerHTML.includes('Costco Source'), 'p14: pointerdown->pointerup->click activates Source and swaps panel');
const econBtn = seedTabs.find((t) => t.getAttribute('data-segment') === 'economics');
fireEvent('sheetNav', 'keydown', econBtn, { key: 'Enter' });
fireEvent('sheetNav', 'keyup', econBtn, { key: 'Enter' });
fireEvent('sheetNav', 'click', econBtn);
assert(econBtn.classList.contains('active') && els.sheetContent.innerHTML.includes('Fee Breakdown'), 'p14: focus->Enter->click activates Economics and swaps panel');
const mktBtn = seedTabs.find((t) => t.getAttribute('data-segment') === 'market');
fireEvent('sheetNav', 'keydown', mktBtn, { key: ' ' });
fireEvent('sheetNav', 'keyup', mktBtn, { key: ' ' });
fireEvent('sheetNav', 'click', mktBtn);
assert(mktBtn.classList.contains('active') && els.sheetContent.innerHTML.includes('Market &amp; Competition'), 'p14: focus->Space->click activates Market and swaps panel');

/* close paths */
click('sheetClose');
assert(!els.inspectionSheet.classList.contains('open'), 'p14: X close button closes the sheet');
assert(els.sheetOverlay.hidden === true, 'p14: X close hides the overlay');
assert(vm.runInContext('_sheetProduct', context) === null, 'p14: X close clears _sheetProduct');
vm.runInContext('NS.openSheet(' + JSON.stringify(sheetProd) + ', null)', context);
fireKey('Escape');
assert(!els.inspectionSheet.classList.contains('open'), 'p14: Escape closes the sheet');
vm.runInContext('NS.openSheet(' + JSON.stringify(sheetProd) + ', null)', context);
click('sheetOverlay');
assert(!els.inspectionSheet.classList.contains('open'), 'p14: overlay click closes the sheet');

/* sort popover open/close + aria state */
click('csSortBtn');
assert(els.sortPopover.hidden === false, 'p14: Sort click opens the sort popover');
assert(els.csSortBtn.getAttribute('aria-expanded') === 'true', 'p14: sort button aria-expanded=true while open');
click('csSortBtn');
assert(els.sortPopover.hidden === true, 'p14: second Sort click closes the sort popover');
assert(els.csSortBtn.getAttribute('aria-expanded') === 'false', 'p14: sort button aria-expanded=false when closed');

/* at least three valid sorts apply with unknowns last */
const sortPool = [
    P({ name: 'Kirkland Alpha', asin: 'B6TEST0001', amazon_price: 10, roi_pct: 10, verdict: null }),
    P({ name: 'Kirkland Beta', asin: 'B6TEST0002', amazon_price: 5, roi_pct: 30, verdict: null }),
    P({ name: 'Kirkland Gamma', asin: 'B6TEST0003', amazon_price: null, roi_pct: null, verdict: null }),
];
setState(sortPool, 'ok', 'ready');
const streamPos = (name) => els.streamView.innerHTML.indexOf(name);
change('csSortSelect', 'price_asc');
assert(streamPos('Kirkland Beta') !== -1 && streamPos('Kirkland Beta') < streamPos('Kirkland Alpha') && streamPos('Kirkland Alpha') < streamPos('Kirkland Gamma'), 'p14: price_asc sorts known ascending, unknown last');
assert(els.sortPopover.hidden === true, 'p14: sort popover closes after selection');
assert(els.sortActiveLabel.textContent === 'Amazon Price: Low to High', 'p14: active sort label shows the applied sort');
change('csSortSelect', 'roi_desc');
assert(streamPos('Kirkland Beta') < streamPos('Kirkland Alpha') && streamPos('Kirkland Alpha') < streamPos('Kirkland Gamma'), 'p14: roi_desc sorts known descending, unknown last');
assert(els.sortActiveLabel.textContent === 'ROI: High to Low', 'p14: active sort label updates with roi_desc');
change('csSortSelect', 'name_asc');
assert(streamPos('Kirkland Alpha') < streamPos('Kirkland Beta') && streamPos('Kirkland Beta') < streamPos('Kirkland Gamma'), 'p14: name_asc sorts alphabetically, unknown name last');
assert(els.sortActiveLabel.textContent === 'Product Name: A to Z', 'p14: active sort label updates with name_asc');
fireDoc('mousedown', el());
assert(els.sortPopover.hidden === true, 'p14: outside mousedown closes an open sort popover');

/* ================================================================
 * Phase 15 — sheet data availability + reason chips (honesty)
 * ================================================================ */
const sparseProd = P({ name: 'Sparse Item', asin: 'B7TEST0001', amazon_price: null, costco_cost: null, fba_fee: null, net_profit: null, roi_pct: null, total_sellers: null, fba_sellers: null, monthly_sales_estimate: null, verdict: null, pack_match: 'unknown', economics_status: 'missing_costco_cogs', economics_confidence: 'unavailable' });
setState([sparseProd], 'ok', 'ready');
vm.runInContext('NS.openSheet(' + JSON.stringify(sparseProd) + ', null)', context);
const sparseHtml = els.sheetContent.innerHTML;
assert(sparseHtml.includes('Data availability'), 'p15: overview shows the Data availability section');
assert(sparseHtml.includes('Unavailable \u2014 no Amazon price on record'), 'p15: missing price row has the exact honest reason');
assert(sparseHtml.includes('Unknown \u2014 no invoice-confirmed Costco cost'), 'p15: missing COGS row says Unknown, never 0');
assert(sparseHtml.includes('Unavailable \u2014 monthly sales source is not connected'), 'p15: missing sales row names the missing source');
assert(sparseHtml.includes('Unavailable \u2014 offer enrichment has not been run for this ASIN'), 'p15: missing seller row names the missing enrichment');
assert(sparseHtml.includes('Unavailable \u2014 provider does not supply shipping'), 'p15: shipping row states the provider gap');
assert(sparseHtml.includes('Unavailable \u2014 not loaded (never inferred from lowest price)'), 'p15: Buy Box winner row is never inferred');
assert(sparseHtml.includes('Missing Costco COGS') && sparseHtml.includes('Pack/Variant: Unknown'), 'p15: Unscored row shows reason chips for missing inputs');
assert(sparseHtml.includes('Unscored'), 'p15: null verdict renders Unscored in the sheet');
assert(!sparseHtml.includes('$0.00') && !sparseHtml.includes('>0<'), 'p15: no fabricated 0/$0.00 anywhere in the sheet output');
assert(sparseHtml.indexOf('Pack/Variant: Unknown') < sparseHtml.indexOf('Missing Costco COGS'), 'p15: chips order lists pack variant before cost input');

const nfvProd = P({ name: 'Fee Verify Item', asin: 'B7TEST0002', amazon_price: 50.0, costco_cost: null, fba_fee: null, net_profit: 12.0, roi_pct: 60.0, total_sellers: 3, fba_sellers: 1, monthly_sales_estimate: null, verdict: 'Needs Fee Verification', pack_match: 'exact', economics_status: 'needs_fee_verification', economics_confidence: 'provisional' });
setState([nfvProd], 'ok', 'ready');
vm.runInContext('NS.openSheet(' + JSON.stringify(nfvProd) + ', null)', context);
const nfvHtml = els.sheetContent.innerHTML;
assert(nfvHtml.includes('Needs FBA fee verification'), 'p15: Needs Fee Verification row shows the FBA fee reason chip');
assert(nfvHtml.includes('Unavailable \u2014 FBA fee not yet verified (weight/fee source missing)'), 'p15: FBA fee availability row names the missing input');
assert(!nfvHtml.includes('Unscored'), 'p15: Needs Fee Verification row is not labeled Unscored');
assert(nfvHtml.includes('Unknown \u2014 no invoice-confirmed Costco cost'), 'p15: no-cost row stays Unknown even with economics present');

const invProd = P({ name: 'Invoice Item', asin: 'B7TEST0003', amazon_price: 60.0, costco_cost: 25.0, costco_cost_basis: 'invoice_confirmed', net_profit: 15.0, roi_pct: 66.0, verdict: 'Pass', pack_match: 'exact', economics_status: 'estimated_fee_stack', economics_confidence: 'estimated', monthly_sales_estimate: 1200, monthly_sales_estimated: true, total_sellers: 6, fba_sellers: 2 });
setState([invProd], 'ok', 'ready');
vm.runInContext('NS.openSheet(' + JSON.stringify(invProd) + ', null)', context);
const invHtml = els.sheetContent.innerHTML;
assert(invHtml.includes('Invoice-confirmed'), 'p15: invoice-confirmed cost row shows its basis label');
assert(invHtml.includes('Pass \u2014 economics verified'), 'p15: Pass row shows the verified chip');
assert(!invHtml.includes('Unscored'), 'p15: Pass row is not labeled Unscored');

/* ================================================================
 * Phase 16 — completeness contract rendering (null-first)
 * ================================================================ */
const COMP_PARTIAL = {
    score: 41, score_max: 85, status: 'needs_mapping',
    status_reason: 'pack/variant fingerprint must be exact or invoice-confirmed',
    category_scores: { identity_mapping: 5, source_cost: 12, market_coverage: 4, fees_economics: 18, demand: null, invoice_readiness: 2 },
    category_reasons: { identity_mapping: [], source_cost: [], market_coverage: ['no buy box price'], fees_economics: [], demand: ['no monthly sales estimate; never fabricated'], invoice_readiness: ['estimated cost; invoice required to authorize'] },
    missing_inputs: { demand: ['est_monthly_sales', 'sales_method'] },
    roi_readiness: { ready: true, reason: 'net/ROI computed on estimated fee stack' },
    next_action: 'Verify pack/variant equivalence (pack_match)',
    purchase_authorized: false,
};
const COMP_ZERO = {
    score: 0, score_max: 100, status: 'blocked',
    status_reason: 'pack_match is mismatch; product equivalence disproven',
    category_scores: { identity_mapping: 0, source_cost: 0, market_coverage: 0, fees_economics: 0, demand: 0, invoice_readiness: 0 },
    category_reasons: {},
    missing_inputs: {},
    roi_readiness: { ready: false, reason: 'economics unavailable; net/ROI null' },
    next_action: 'Skip: product equivalence disproven',
    purchase_authorized: false,
};
const COMP_NOT_COMPUTABLE = {
    score: null, score_max: 0, status: 'not_computable',
    status_reason: 'no evaluated inputs; completeness cannot be computed',
    category_scores: { identity_mapping: null, source_cost: null, market_coverage: null, fees_economics: null, demand: null, invoice_readiness: null },
    category_reasons: {},
    missing_inputs: { identity_mapping: ['name', 'pack_match'], source_cost: ['costco_cost', 'costco_cost_basis'], market_coverage: ['amazon_price', 'buy_box_available', 'buy_box_price', 'offers_present', 'coverage_full', 'seller_counts_observed'], fees_economics: ['referral_fee', 'fba_fee', 'fba_fee_status', 'economics_confidence', 'net_profit', 'roi_pct'], demand: ['est_monthly_sales', 'sales_method'], invoice_readiness: ['costco_cost_basis'] },
    roi_readiness: { ready: null, reason: null },
    next_action: 'Collect scanner market data to compute completeness',
    purchase_authorized: false,
};
const compProd = (overrides = {}) => Object.assign({}, P({ amazon_price: 24.99, costco_cost: 12.99, costco_cost_basis: 'estimated', fba_fee: 4.75, fba_fee_status: 'estimated', economics_confidence: 'estimated', net_profit: 2.54, roi_pct: 19.5, monthly_sales_estimate: null }), overrides);

assert(vm.runInContext('NS.completenessScoreText(null)', context) === 'Unknown', 'p16: absent completeness renders Unknown, never 0');
assert(vm.runInContext('NS.completenessScoreText(' + JSON.stringify(COMP_NOT_COMPUTABLE) + ')', context) === 'Not computable', 'p16: null score renders Not computable, never 0 / 100');
assert(vm.runInContext('NS.completenessScoreText(' + JSON.stringify(COMP_PARTIAL) + ')', context) === '41 / 85', 'p16: partial score renders its real value with computable max');
assert(vm.runInContext('NS.completenessScoreText(' + JSON.stringify(COMP_ZERO) + ')', context) === '0 / 100', 'p16: proven zero renders 0 / 100 with its max context');
assert(vm.runInContext('NS.completenessStatusLabel(' + JSON.stringify(COMP_PARTIAL) + ')', context) === 'Needs mapping', 'p16: status label maps the taxonomy');
assert(vm.runInContext('NS.completenessChip(' + JSON.stringify(compProd({ completeness: COMP_PARTIAL })) + ')', context).includes('cc-badge') && vm.runInContext('NS.completenessChip(' + JSON.stringify(compProd({ completeness: COMP_PARTIAL })) + ')', context).includes('41 / 85'), 'p16: compact chip renders inside the Status cell content');
assert(vm.runInContext('NS.completenessChip(' + JSON.stringify(compProd({})) + ')', context) === '', 'p16: absent completeness block renders no chip (no table clutter)');
const zeroChipHtml = vm.runInContext('NS.completenessChip(' + JSON.stringify(compProd({ completeness: COMP_ZERO })) + ')', context);
assert(zeroChipHtml.includes('0 / 100') && zeroChipHtml.includes('Genuine zero'), 'p16: genuine-zero chip carries the proven-zero disclosure');

/* sheet segments: each shows relevant completeness and honest states */
const sheetPart = compProd({ completeness: COMP_PARTIAL });
vm.runInContext('NS.openSheet(' + JSON.stringify(sheetPart) + ', null)', context);
const ovHtml = els.sheetContent.innerHTML;
assert(ovHtml.includes('Completeness</span>') && ovHtml.includes('41 / 85'), 'p16: Overview segment shows the completeness section with real score');
assert(ovHtml.includes('Needs mapping') && ovHtml.includes('Verify pack/variant equivalence'), 'p16: Overview shows status and next action');
vm.runInContext('renderSheetContent("source", ' + JSON.stringify(sheetPart) + ')', context);
const srcHtml = els.sheetContent.innerHTML;
assert(srcHtml.includes('Completeness \u2014 Sources') && srcHtml.includes('Computed: 18 / 20') && srcHtml.includes('Computed: 4 / 20'), 'p16: Source segment shows computed category states');
assert(srcHtml.includes('Not computable \u2014 missing: est_monthly_sales, sales_method'), 'p16: Source segment names the missing demand inputs');
vm.runInContext('renderSheetContent("economics", ' + JSON.stringify(sheetPart) + ')', context);
const ecHtml = els.sheetContent.innerHTML;
assert(ecHtml.includes('Completeness \u2014 Economics') && ecHtml.includes('ROI readiness') && ecHtml.includes('Ready'), 'p16: Economics segment shows ROI readiness');
vm.runInContext('renderSheetContent("market", ' + JSON.stringify(sheetPart) + ')', context);
const mkHtml = els.sheetContent.innerHTML;
assert(mkHtml.includes('Completeness \u2014 Market') && mkHtml.includes('Market / offer coverage'), 'p16: Market segment shows coverage state');
assert(mkHtml.includes('Market Orbit') && /scOrbital-[A-Z0-9]+/.test(mkHtml), 'p16: market segment renders the orbital mapping section');
assert(mkHtml.includes('orbit-node') && mkHtml.includes('$24.00'), 'p16: cached real offer roster shown as an orbit');
vm.runInContext('renderSheetContent("market", ' + JSON.stringify(compProd({ asin: 'B0TEST0099' })) + ')', context);
const mkHold = els.sheetContent.innerHTML;
assert(mkHold.includes('load Seller Detail to plot'), 'p16: uncached orbit panel honestly waits for a real roster');
vm.runInContext('renderSheetContent("verify", ' + JSON.stringify(sheetPart) + ')', context);
const vfHtml = els.sheetContent.innerHTML;
assert(vfHtml.includes('Missing inputs') && vfHtml.includes('Next action') && vfHtml.includes('Needs mapping: pack/variant fingerprint must be exact or invoice-confirmed'), 'p16: Verify segment shows next action and missing inputs');

/* null-score states in the sheet: Unknown / Not computable, never 0 / 100 */
vm.runInContext('NS.openSheet(' + JSON.stringify(compProd({ completeness: COMP_NOT_COMPUTABLE })) + ', null)', context);
const ncHtml = els.sheetContent.innerHTML;
assert(ncHtml.includes('Not computable') && !ncHtml.includes('0 / 100'), 'p16: not-computable sheet shows Not computable and never 0 / 100');
vm.runInContext('renderSheetContent("verify", ' + JSON.stringify(compProd({ completeness: COMP_NOT_COMPUTABLE })) + ')', context);
const ncVfHtml = els.sheetContent.innerHTML;
assert(ncVfHtml.includes('no evaluated inputs'), 'p16: not-computable sheet explains why');
vm.runInContext('NS.openSheet(' + JSON.stringify(compProd({ completeness: COMP_ZERO })) + ', null)', context);
const zrHtml = els.sheetContent.innerHTML;
assert(zrHtml.includes('0 / 100') && zrHtml.includes('proven 0'), 'p16: genuine-zero sheet shows the proven-zero badge');
vm.runInContext('renderSheetContent("verify", ' + JSON.stringify(compProd({ completeness: COMP_ZERO })) + ')', context);
const zrVfHtml = els.sheetContent.innerHTML;
assert(zrVfHtml.includes('Blocked: pack_match is mismatch; product equivalence disproven'), 'p16: genuine-zero sheet shows blocked status reason');
vm.runInContext('NS.openSheet(' + JSON.stringify(compProd({})) + ', null)', context);
const abHtml = els.sheetContent.innerHTML;
assert(abHtml.includes('Completeness score</dt><dd><span class="unknown">Unknown</span>'), 'p16: absent block renders Unknown in the overview');
vm.runInContext('renderSheetContent("verify", ' + JSON.stringify(compProd({})) + ')', context);
const abVfHtml = els.sheetContent.innerHTML;
assert(abVfHtml.includes('Completeness Unknown \u2014 no contract data in this response.'), 'p16: verify segment states the missing contract honestly');

/* table: compact chips inside Status cells only, no new columns */
setState([compProd({ completeness: COMP_PARTIAL }), compProd({ completeness: COMP_ZERO, asin: 'B0TEST0002' }), compProd({ asin: 'B0TEST0003' })], 'ok', 'ready');
const tblHtml = els.tableBody.innerHTML;
assert((tblHtml.match(/cc-badge/g) || []).length === 2, 'p16: exactly two compact chips render (absent block renders none)');
assert(tblHtml.includes('41 / 85') && tblHtml.includes('0 / 100'), 'p16: table chips show real partial score and proven zero');
assert(!tblHtml.includes('data-col="completeness"'), 'p16: no new completeness column was added to the table');

/* ================================================================
 * Phase 17 — Proof Batch (offline selection, preflight, fixture view)
 * ================================================================ */
/* offline benchmark index */
assert(vm.runInContext('NS.BENCHMARK_ASINS.length', context) === 47, 'p17: embedded benchmark ASIN index has 47 entries');
assert(vm.runInContext('NS.benchmarkMatch("B00BISGJXA")', context) === true, 'p17: benchmark match true for canonical ASIN');
assert(vm.runInContext('NS.benchmarkMatch("B0TEST0001")', context) === false, 'p17: benchmark match false for non-benchmark ASIN');
assert(vm.runInContext('NS.benchmarkMatch(null)', context) === false, 'p17: benchmark match false for null ASIN');

/* sanitization: secret-like keys dropped, invalid ASINs dropped, dedupe, cap */
const sanitized = vm.runInContext(`NS.sanitizeSelection({
    schema_version: 1,
    asins: [
        { asin: 'b0test0001', title: 'A', api_key: 'super-secret', completeness: { score: 41, score_max: 85, status: 'needs_mapping' } },
        { asin: 'NOT-VALID', title: 'bad' },
        { asin: 'B0TEST0001', title: 'A again', completeness: { score: 0, score_max: 100, status: 'blocked' } }
    ]
})`, context);
assert(sanitized.asins.length === 1, 'p17: sanitizer dedupes, drops secret-like and invalid records');
assert(sanitized.asins[0].asin === 'B0TEST0001', 'p17: sanitizer uppercases and keeps valid ASIN');
assert(sanitized.asins[0].api_key === undefined && !JSON.stringify(sanitized).includes('secret'), 'p17: secret-like key never survives sanitization');
assert(vm.runInContext(`NS.sanitizeSelection({ schema_version: 2, asins: [{ asin: 'B0TEST0001' }] })`, context).asins.length === 0, 'p17: unknown schema_version yields empty selection');

const capRecords = Array.from({ length: 25 }, (_, i) => ({ asin: 'B0TEST' + String(i + 1).padStart(4, '0'), title: 'T' + i }));
const capped = vm.runInContext('NS.sanitizeSelection(' + JSON.stringify({ schema_version: 1, asins: capRecords }) + ')', context);
assert(capped.asins.length === 20, 'p17: hard cap of 20 unique ASINs enforced on load');

/* missing enrichment fields derived from scanner row */
const missing = vm.runInContext('NS.missingEnrichmentFields(' + JSON.stringify(P()) + ')', context);
assert(missing.includes('identity_pack') && missing.includes('market_offers'), 'p17: missing enrichment fields derive from row (pack + offers absent)');
const missingFull = vm.runInContext(`NS.missingEnrichmentFields(${JSON.stringify(P({
    pack_match: 'exact', costco_cost: 15.99, fba_fee: 7.10, estimated_monthly_sales: 1500,
    snapshot_offers_complete: true,
}))})`, context);
assert(missingFull.length === 0, 'p17: complete row reports no missing enrichment fields');

/* selection record from scanner row */
const record = vm.runInContext(`NS.selectionRecordFrom(${JSON.stringify(P({ completeness: { score: 41, score_max: 85, status: 'needs_mapping' } }))})`, context);
assert(record.asin === 'B0TEST0001' && record.benchmark_match === false, 'p17: selection record built from row (non-benchmark)');
assert(record.completeness.score === 41 && record.completeness.status === 'needs_mapping', 'p17: selection record snapshots current completeness');
assert(record.amazon_price === 48.87 && record.costco_cost === 15.99 && record.roi_pct === 106.3, 'p17: selection record keeps price/cost/ROI only when present');

/* add/remove through the real UI path (global delegated handler) */
store['t2.kirklandScout.selection.v1'] = null;
delete store['t2.kirklandScout.selection.v1'];
setState([P(), P({ asin: 'B00BISGJXA', name: 'Stool Softener 100mg (400ct)', costco_cost: 5.99, amazon_price: 12.99, roi_pct: 31.4, pack_match: 'exact', completeness: { score: 82, score_max: 85, status: 'ready_for_test_buy' } })], 'ok', 'ready');
const toggleBtnFor = (asin) => {
    const b = makeElement('toggle-' + asin);
    b.getAttribute = () => asin;
    b.closest = (sel) => (sel === '[data-proof-toggle]' ? b : null);
    return b;
};
fireDoc('click', toggleBtnFor('B00BISGJXA'));
const selAfterAdd = JSON.parse(store['t2.kirklandScout.selection.v1']);
assert(selAfterAdd.asins.length === 1 && selAfterAdd.asins[0].asin === 'B00BISGJXA', 'p17: global toggle adds the ASIN to localStorage selection');
assert(selAfterAdd.asins[0].benchmark_match === true, 'p17: benchmark-match presence recorded at selection time');
assert(selAfterAdd.asins[0].completeness.score === 82, 'p17: completeness snapshotted at selection time');
vm.runInContext('NS.renderProofBatch()', context);
assert(els.proofBatchPanel.hidden === true, 'p17: selection alone does not open the panel (launcher-driven visibility)');
click('csProofBatchBtn');
assert(els.proofBatchPanel.hidden === false, 'p17: launcher opens the panel for a non-empty selection');
assert(els.proofCount.textContent === '1 / 20', 'p17: proof count shows 1 / 20');
assert(els.proofList.innerHTML.includes('Benchmark match'), 'p17: benchmark match badge rendered in panel');
assert(els.proofList.innerHTML.includes('82 / 85'), 'p17: completeness chip rendered in panel item');
fireDoc('click', toggleBtnFor('B00BISGJXA'));
assert(store['t2.kirklandScout.selection.v1'] === undefined || JSON.parse(store['t2.kirklandScout.selection.v1']).asins.length === 0, 'p17: toggling again removes the ASIN');
vm.runInContext('NS.renderProofBatch()', context);
click('csProofBatchBtn');
assert(els.proofBatchPanel.hidden === true, 'p17: panel closes via launcher after selection emptied (left clean for later phases)');
assert(els.proofList.innerHTML.includes('No ASINs selected'), 'p17: empty state message shown');

/* 20-cap through the UI path */
setState(Array.from({ length: 21 }, (_, i) => P({ asin: 'B0TEST' + String(i + 1).padStart(4, '0'), name: 'Product ' + (i + 1) })), 'ok', 'ready');
for (let i = 0; i < 21; i += 1) {
    fireDoc('click', toggleBtnFor('B0TEST' + String(i + 1).padStart(4, '0')));
}
const selFull = JSON.parse(store['t2.kirklandScout.selection.v1']);
assert(selFull.asins.length === 20, 'p17: UI toggle never exceeds 20');
const fullBtn = vm.runInContext(`NS.selectionButtonHtml(${JSON.stringify(P({ asin: 'B0TEST0021' }))})`, context);
assert(fullBtn.includes('disabled') && fullBtn.includes('20/20'), 'p17: add button disabled with full-batch title at 20/20');
for (let i = 0; i < 20; i += 1) {
    fireDoc('click', toggleBtnFor('B0TEST' + String(i + 1).padStart(4, '0')));
}

/* zero-network preflight draft */
setState([P({ asin: 'B00BISGJXA', name: 'Stool Softener 100mg (400ct)', costco_cost: 5.99, amazon_price: 12.99, pack_match: 'exact', snapshot_offers_complete: true, snapshot_status: 'ok' })], 'ok', 'ready');
fireDoc('click', toggleBtnFor('B00BISGJXA'));
const preflight = vm.runInContext('NS.preflightForSelection(NS.loadSelection())', context);
assert(preflight.count === 1 && preflight.hard_batch_cap === 20, 'p17: preflight shows count / 20');
assert(preflight.benchmark_match_count === 1, 'p17: preflight reports benchmark match count');
assert(preflight.zero_provider_calls === true && preflight.dry_run === true, 'p17: preflight is zero-network dry-run');
assert(preflight.human_confirmation === 'HUMAN CONFIRMATION REQUIRED \u2014 NO LIVE CALLS EXECUTED', 'p17: preflight carries the explicit human-confirmation line');
assert(preflight.expected_cache_skips === 1 && preflight.requests_planned === 0, 'p17: fresh snapshot is skipped at zero cost');
assert(preflight.easyparser_credit_estimate === 0, 'p17: zero requests means zero estimated credits');
assert(typeof preflight.keepa_credit_estimate === 'string' && preflight.keepa_credit_estimate.includes('requires provider plan confirmation'), 'p17: unknown provider credit is never guessed');
assert(preflight.budget_stop.includes('operator-defined per-run cap'), 'p17: budget stop policy stated as not configured');
assert(preflight.asins_selected[0].benchmark_match === true, 'p17: preflight per-ASIN benchmark match present');
assert(vm.runInContext('NS.preflightHtml(' + JSON.stringify(preflight) + ')', context).includes('HUMAN CONFIRMATION REQUIRED'), 'p17: preflight summary html shows the confirmation line');
fireDoc('click', toggleBtnFor('B00BISGJXA'));

/* preflight export carries no secret-like keys */
const exported = vm.runInContext('NS.exportPreflightJson(NS.loadSelection())', context);
const parsedExport = JSON.parse(exported);
assert(vm.runInContext('NS.secretLike(' + JSON.stringify(parsedExport) + ')', context) === false, 'p17: preflight export contains no secret-like keys');
assert(parsedExport.run_id && parsedExport.run_id.indexOf('proof-preflight-') === 0, 'p17: export carries run id');

/* row + sheet integration */
setState([P({ asin: 'B00BISGJXA', name: 'Stool Softener 100mg (400ct)' })], 'ok', 'ready');
assert(els.tableBody.innerHTML.includes('data-proof-toggle="B00BISGJXA"'), 'p17: table Action cell carries the Proof Batch toggle');
assert(els.streamView.innerHTML.includes('data-proof-toggle="B00BISGJXA"'), 'p17: stream row carries the Proof Batch toggle');
vm.runInContext(`NS.openSheet(${JSON.stringify(P({ asin: 'B00BISGJXA', name: 'Stool Softener 100mg (400ct)' }))}, null)`, context);
vm.runInContext('renderSheetContent("overview", ' + JSON.stringify(P({ asin: 'B00BISGJXA', name: 'Stool Softener 100mg (400ct)' })) + ')', context);
assert(els.sheetContent.innerHTML.includes('Proof Batch') && els.sheetContent.innerHTML.includes('Add to Proof Batch'), 'p17: product sheet overview shows Proof Batch toggle');
assert(html.includes('OFFLINE PREFLIGHT \u2014 NO LIVE REQUESTS'), 'p17: offline-preflight banner present in static markup');
assert(html.includes('Controlled live validation is not wired in this frontend.') && html.includes('No provider request can be submitted from this panel.'), 'p17: disabled live-enrichment notice states unwired dispatch and zero submit path');

/* fixture-only benchmark result view */
vm.runInContext('NS.renderProofFixture()', context);
assert(els.proofFixture.innerHTML.includes('SYNTHETIC FIXTURE'), 'p17: fixture view labeled synthetic, never live');
assert(els.proofFixture.innerHTML.includes('within_tolerance'), 'p17: fixture view renders price drift classification');
assert(els.proofFixture.innerHTML.includes('does not guarantee live market stability'), 'p17: fixture view renders benchmark limitations');
const fixtureJson = JSON.stringify(vm.runInContext('NS.FIXTURE_RESULT', context));
assert(fixtureJson.includes('capture time unknown') && fixtureJson.includes('internally validated'), 'p17: fixture result states capture-time and internal-validation limits');

/* ================================================================
 * Phase 18 — Product Focus Mode (executable behavior)
 * Runs after full VM/DOM/UI initialization, with a loaded local
 * product collection and after fetchCalls is defined.
 * ================================================================ */

/* Start from a known normal mode before exercising Focus */
vm.runInContext('NS.setViewMode("gallery")', context);

/* Load a local filtered/sorted collection for Focus to render from */
setState([
    P({ asin: 'B0FOCUS001', name: 'Focus Product Alpha' }),
    P({ asin: 'B0FOCUS002', name: 'Focus Product Beta' }),
], 'ok');

/* Focus is reached via the control-strip button (same mechanism as G/L/T) */
assert(vm.runInContext('currentViewMode', context) === 'gallery', 'phase18: default normal mode is gallery');
vm.runInContext('if (typeof closeSheet === "function") closeSheet();', context);
click('csViewFocus');
assert(vm.runInContext('currentViewMode', context) === 'focus', 'phase18: clicking Focus button enters focus mode');

/* Focus mode presentation state */
assert(getEl('focusGrid').hidden === false, 'phase18: focus grid visible in focus mode');
assert(getEl('focusBackBtn').hidden === false, 'phase18: focus back button visible in focus mode');
assert(getEl('streamView').style.display === 'none', 'phase18: stream hidden in focus mode');
assert(getEl('tableWrap').style.display === 'none', 'phase18: table hidden in focus mode');
assert(getEl('csViewFocus').classList.contains('active'), 'phase18: focus button marked active');
assert(getEl('csViewFocus').getAttribute('aria-pressed') === 'true', 'phase18: focus button aria-pressed true in focus mode');
assert(vm.runInContext('_prevNormalMode', context) === 'gallery', 'phase18: prior normal mode captured as gallery');

/* Cards reflect the current local filtered/sorted collection (no auto-select) */
var rendered = getEl('focusGridCards').innerHTML;
assert(rendered.includes('B0FOCUS001') && rendered.includes('B0FOCUS002'), 'phase18: focus cards reflect visibleRows collection');
assert(rendered.includes('focus-card'), 'phase18: focus card markup present');
assert(vm.runInContext('NS.visibleRows().length', context) === 2, 'phase18: visibleRows count unchanged (2 products)');
assert(vm.runInContext('_sheetProduct', context) === null, 'phase18: no auto-selection — sheet not opened on focus entry');

/* Honest empty state when zero products match */
setState([], 'ok');
vm.runInContext('NS.setViewMode("focus")', context);
assert(getEl('focusGridEmpty').hidden === false, 'phase18: empty state shown when no products match');
assert(getEl('focusGridCards').innerHTML === '', 'phase18: no cards rendered in empty state');

/* Card click opens the existing detail sheet (not the research drawer) */
setState([
    P({ asin: 'B0FOCUS001', name: 'Focus Product Alpha' }),
    P({ asin: 'B0FOCUS002', name: 'Focus Product Beta' }),
], 'ok');
vm.runInContext('NS.setViewMode("focus")', context);
var cardStub = makeElement('focus-card-stub');
cardStub.closest = function (sel) { return sel === '.focus-card' ? cardStub : null; };
cardStub.setAttribute('data-asin', 'B0FOCUS001');
click('focusGridCards', cardStub);
assert(vm.runInContext('_sheetProduct', context) !== null, 'phase18: card click opens existing detail sheet');
assert(vm.runInContext('_drawerOpen', context) === false, 'phase18: card click opens sheet, not research drawer');
assert(getEl('sheetOverlay').hidden === false, 'phase18: sheet overlay unhidden on card click');
assert(documentStub.body.style.overflow === 'hidden', 'phase18: page scroll locked while sheet open');
/* Close sheet — grid remains active behind it */
vm.runInContext('closeSheet()', context);
assert(vm.runInContext('_sheetProduct', context) === null, 'phase18: closeSheet clears _sheetProduct');
assert(getEl('sheetOverlay').hidden === true, 'phase18: sheet overlay hidden after close');
assert(documentStub.body.style.overflow === '', 'phase18: scroll unlocked after sheet close');
assert(vm.runInContext('currentViewMode', context) === 'focus', 'phase18: focus mode still active behind closed sheet');

/* Back button restores prior normal mode */
vm.runInContext('NS.setViewMode("gallery")', context);
vm.runInContext('NS.setViewMode("focus")', context);
assert(vm.runInContext('_prevNormalMode', context) === 'gallery', 'phase18: prior normal mode captured as gallery before Back');
click('focusBackBtn');
assert(vm.runInContext('currentViewMode', context) === 'gallery', 'phase18: Back button restores prior normal mode');
assert(getEl('focusGrid').hidden === true, 'phase18: focus grid hidden after Back');
assert(getEl('focusBackBtn').hidden === true, 'phase18: back button hidden after exit');
assert(getEl('csViewFocus').getAttribute('aria-pressed') === 'false', 'phase18: focus aria-pressed false after exit');

/* Escape priority: sheet first, then drawer, then focus exit */
/* 1) sheet open + focus -> Escape closes sheet only */
setState([ P({ asin: 'B0FOCUS001', name: 'Focus Product Alpha' }) ], 'ok');
vm.runInContext('NS.setViewMode("focus")', context);
var escCard = makeElement('esc-card');
escCard.closest = function (sel) { return sel === '.focus-card' ? escCard : null; };
escCard.setAttribute('data-asin', 'B0FOCUS001');
click('focusGridCards', escCard);
assert(vm.runInContext('_sheetProduct', context) !== null, 'phase18: sheet open before Escape priority test');
fireKey('Escape');
assert(vm.runInContext('_sheetProduct', context) === null, 'phase18: Escape closes sheet first (topmost)');
assert(vm.runInContext('currentViewMode', context) === 'focus', 'phase18: Escape does not exit focus while sheet was open');

/* 2) drawer open + focus -> Escape closes drawer only */
vm.runInContext('NS.setViewMode("focus")', context);
vm.runInContext('openDrawer("B0FOCUS001")', context);
assert(vm.runInContext('_drawerOpen', context) === true, 'phase18: drawer open before Escape priority test');
fireKey('Escape');
assert(vm.runInContext('_drawerOpen', context) === false, 'phase18: Escape closes drawer first');
assert(vm.runInContext('currentViewMode', context) === 'focus', 'phase18: Escape does not exit focus while drawer was open');

/* 3) neither open + focus -> Escape restores prior normal mode */
assert(vm.runInContext('currentViewMode', context) === 'focus', 'phase18: still in focus before final Escape');
fireKey('Escape');
assert(vm.runInContext('currentViewMode', context) === 'gallery', 'phase18: Escape with nothing open exits focus to prior mode');

/* Gallery/List/Table each exit Focus directly */
vm.runInContext('NS.setViewMode("focus")', context);
vm.runInContext('NS.setViewMode("gallery")', context);
assert(vm.runInContext('currentViewMode', context) === 'gallery', 'phase18: Gallery exits focus directly');
vm.runInContext('NS.setViewMode("focus")', context);
vm.runInContext('NS.setViewMode("list")', context);
assert(vm.runInContext('currentViewMode', context) === 'list', 'phase18: List exits focus directly');
vm.runInContext('NS.setViewMode("focus")', context);
vm.runInContext('NS.setViewMode("table")', context);
assert(vm.runInContext('currentViewMode', context) === 'table', 'phase18: Table exits focus directly');

/* State preservation: sort survives a Focus round-trip */
setState([ P({ asin: 'B0FOCUS001', name: 'Alpha' }), P({ asin: 'B0FOCUS002', name: 'Beta' }) ], 'ok');
vm.runInContext('sortKey = "name_asc"; NS.renderScout();', context);
var sortBefore = vm.runInContext('sortKey', context);
vm.runInContext('NS.setViewMode("focus")', context);
vm.runInContext('NS.setViewMode("gallery")', context);
assert(vm.runInContext('sortKey', context) === sortBefore, 'phase18: sortKey preserved across focus round-trip');

/* no new provider/network behavior in Focus mode */
assert(fetchCalls.length === 0, 'phase18: zero fetch calls during all Focus interactions');

        /* no network was attempted by any interaction */
        assert(fetchCalls.length === 0, 'p15: zero fetch calls across all interaction tests');

        /* ================================================================
         * Phase 19 — Live Validation Proposal (guarded, single controlled run)
         * ================================================================ */
        function setLiveSelection(asins) {
            var recs = asins.map(function (a) {
                return { asin: a, title: 'Live ' + a, completeness: { score: 1, score_max: 2, status: 'x' }, benchmark_match: false, missing_enrichment_fields: [] };
            });
            vm.runInContext('NS.saveSelection(' + JSON.stringify({ schema_version: 1, asins: recs }) + ')', context);
        }
        var lpState = function () { return vm.runInContext('NS._liveProposal', context); };
        var lpReady = function () { var f = vm.runInContext('NS.liveProposalPreflight()', context); return f ? f.ready : false; };

        assert(vm.runInContext('NS._liveProposal', context) === null, 'p19: no live proposal before open');

        /* open with 0 ASINs -> BLOCKED */
        setLiveSelection([]);
        vm.runInContext('NS.openLiveProposal()', context);
        assert(vm.runInContext('NS._liveProposal', context) !== null, 'p19: proposal object created on open');
        assert(lpReady() === false, 'p19: 0 ASINs -> not ready');
        assert(els.liveProposalStatus.textContent.indexOf('BLOCKED') === 0, 'p19: status BLOCKED with no ASINs');
        assert(els.liveSubmitBtn.disabled === true, 'p19: submit disabled with no ASINs');

        /* open with 1 ASIN -> PLANNED, run ID + provider shown, not ready yet */
        setLiveSelection(['B0FOCUS001']);
        vm.runInContext('NS.openLiveProposal()', context);
        assert(lpState().asins.length === 1, 'p19: 1 ASIN selected');
        assert(lpState().run_id && lpState().run_id.indexOf('live-validation-') === 0, 'p19: fresh run ID generated');
        assert(els.liveProposalRunId.textContent.indexOf('live-validation-') === 0, 'p19: run ID rendered');
        assert(els.liveProposalProvider.textContent === 'EASYPARSER OFFER', 'p19: provider path shown');
        assert(els.liveProposalOperation.textContent.indexOf('market-offers') !== -1, 'p19: operation shown');
        assert(lpReady() === false, 'p19: not ready until cap/ack/phrase');
        assert(els.liveSubmitBtn.disabled === true, 'p19: submit still disabled before approval');
        assert(els.liveProposalNoOverwrite.textContent.indexOf('Verified') === 0, 'p19: no-overwrite verified for fresh id');

        /* budget cap boundaries */
        vm.runInContext('NS.onLiveCapInput("0")', context);
        assert(lpReady() === false, 'p19: cap 0 -> not ready');
        vm.runInContext('NS.onLiveCapInput("-1")', context);
        assert(lpReady() === false, 'p19: negative cap -> not ready');
        vm.runInContext('NS.onLiveCapInput("1.50")', context);
        assert(lpReady() === false, 'p19: cap > $1.00 -> not ready');
        vm.runInContext('NS.onLiveCapInput("0.50")', context);
        assert(lpReady() === false, 'p19: valid cap alone still not ready (ack/phrase)');
        assert(els.liveSubmitBtn.disabled === true, 'p19: submit disabled with valid cap but no ack/phrase');

        /* ack without exact phrase -> not ready */
        vm.runInContext('NS.onLiveAckChange(true)', context);
        assert(lpState().ack === true, 'p19: ack checked');
        assert(lpReady() === false, 'p19: ack without exact phrase -> not ready');

        /* wrong phrase -> not ready */
        vm.runInContext('NS.onLiveConfirmInput("APPROVE WRONG RUN")', context);
        assert(lpReady() === false, 'p19: wrong phrase -> not ready');

        /* exact phrase + ack + valid cap -> ready + enabled */
        vm.runInContext('NS.onLiveConfirmInput("APPROVE CONTROLLED LIVE RUN")', context);
        assert(lpState().confirm === 'APPROVE CONTROLLED LIVE RUN', 'p19: exact phrase recorded');
        assert(lpReady() === true, 'p19: all conditions pass -> ready');
        assert(els.liveSubmitBtn.disabled === false, 'p19: submit ENABLED only with full approval');

        /* >3 ASINs -> BLOCKED */
        setLiveSelection(['B0FOCUS001', 'B0FOCUS002', 'B0FOCUS003', 'B0FOCUS004']);
        vm.runInContext('NS.openLiveProposal()', context);
        assert(lpState().asins.length === 4, 'p19: 4 ASINs selected');
        assert(lpReady() === false, 'p19: 4 ASINs -> not ready');
        assert(els.liveProposalStatus.textContent.indexOf('BLOCKED') === 0, 'p19: 4 ASINs -> BLOCKED status');

        /* run-ID collision -> BLOCKED */
        setLiveSelection(['B0FOCUS001']);
        vm.runInContext('NS.openLiveProposal()', context);
        var collidingId = lpState().run_id;
        vm.runInContext('(function(){var r=NS.loadLiveRuns(); r.push({run_id:"' + collidingId + '", submit_state:"submitted"}); var ls=NS._ls(); if(ls) ls.setItem(NS.LIVE_RUNS_KEY, JSON.stringify(r));})()', context);
        vm.runInContext('NS.openLiveProposal()', context);
        vm.runInContext('NS._liveProposal.run_id = "' + collidingId + '"', context);
        vm.runInContext('NS.renderLiveProposal()', context);
        assert(vm.runInContext('NS.liveProposalPreflight().conditions.no_collision', context) === false, 'p19: colliding run ID flagged');
        assert(lpReady() === false, 'p19: colliding run ID -> not ready');
        assert(els.liveProposalStatus.textContent.indexOf('BLOCKED') === 0, 'p19: colliding run ID -> BLOCKED');
        vm.runInContext('(function(){var ls=NS._ls(); if(ls) ls.removeItem(NS.LIVE_RUNS_KEY);})()', context);

        /* cancel restores PLANNED, no fetch */
        setLiveSelection(['B0FOCUS001']);
        vm.runInContext('NS.openLiveProposal()', context);
        vm.runInContext('NS.onLiveCapInput("0.50"); NS.onLiveAckChange(true); NS.onLiveConfirmInput("APPROVE CONTROLLED LIVE RUN")', context);
        assert(lpReady() === true, 'p19: ready before cancel');
        vm.runInContext('NS.cancelLiveProposal()', context);
        assert(vm.runInContext('NS._liveProposal', context) === null, 'p19: cancel clears proposal');
        assert(els.liveProposalStatus.textContent === 'PLANNED — NO REQUEST SENT', 'p19: cancel restores PLANNED state');

        /* submit handler is fail-closed in this build (no network, no dispatch) */
        setLiveSelection(['B0FOCUS001']);
        vm.runInContext('NS.openLiveProposal()', context);
        vm.runInContext('NS.onLiveCapInput("0.50"); NS.onLiveAckChange(true); NS.onLiveConfirmInput("APPROVE CONTROLLED LIVE RUN")', context);
        assert(lpReady() === true, 'p19: ready for submit test');
        var submitResult = vm.runInContext('NS.submitControlledLiveRun()', context);
        assert(submitResult === 'blocked_unwired', 'p19: submit is fail-closed (backend not wired in this build)');
        assert(fetchCalls.length === 0, 'p19: submit made no network request');
        assert(fetchCalls.length === 0, 'p19: zero fetch calls across all proposal interactions');

        /* ================================================================
           Phase 20 — Proof Batch Panel (offline selection launcher + panel)
           ================================================================ */

        /* Helper to set a test selection */
        function setProofSelection(asins) {
            var recs = asins.map(function (a) {
                return { asin: a, title: 'Test ' + a, completeness: { score: 1, score_max: 2, status: 'x' }, benchmark_match: false, missing_enrichment_fields: [] };
            });
            vm.runInContext('NS.saveSelection(' + JSON.stringify({ schema_version: 1, asins: recs }) + ')', context);
        }

        /* Launcher button exists and is visible */
        assert(getEl('csProofBatchBtn') !== null, 'p20: Proof Batch launcher button exists in control strip');
        assert(getEl('csProofCount') !== null, 'p20: Proof Batch launcher count element exists');

        /* Local fetch counter: swap the VM-context fetch stub so ANY network
         * attempt during Phase 20 increments a local counter (never swallowed). */
        const proofFetchCalls = [];
        context.fetch = function (url) { proofFetchCalls.push(String(url)); return new Promise(function () {}); };
        const vmGet = (expr) => vm.runInContext(expr, context);

        /* Deterministic reset through the public local-only API — earlier
         * phases may have left selection state behind. */
        vm.runInContext('NS.clearSelection()', context);
        setState([P({ asin: 'B07H3TXVR7', name: 'Proof Batch Fixture Product' })], 'ok');
        vm.runInContext('NS.renderProofBatch()', context);

        /* Launcher count begins at zero after the reset */
        assert(String(els.csProofCount.textContent) === '0', 'p20: launcher count begins at zero');
        assert((els.csProofCount.className || '').indexOf('zero') !== -1, 'p20: launcher count carries zero class');

        /* Required copy ships in the served static HTML */
        assert(html.indexOf('OFFLINE PREFLIGHT \u2014 NO LIVE REQUESTS') !== -1, 'p20: OFFLINE PREFLIGHT banner in static HTML');
        assert(html.indexOf('Controlled live validation is not wired in this frontend.') !== -1, 'p20: disabled-live notice sentence 1 in static HTML');
        assert(html.indexOf('No provider request can be submitted from this panel.') !== -1, 'p20: disabled-live notice sentence 2 in static HTML');
        assert(html.indexOf('PREVIEW ONLY \u2014 LIVE DISPATCH NOT WIRED') !== -1, 'p20: proposal PREVIEW ONLY banner in static HTML');
        assert(html.indexOf('No provider request can be submitted from this frontend.') !== -1, 'p20: proposal no-submit sentence in static HTML');
        assert(/id="liveProposalOpenBtn"/.test(html), 'p20: local proposal preview button retained');
        const lbStart = html.indexOf('id="csProofBatchBtn"');
        assert(lbStart !== -1 && /Proof Batch/.test(html.slice(lbStart, lbStart + 300)), 'p20: launcher labelled Proof Batch in served HTML');
        assert(html.indexOf('>Remove all</button>') !== -1, 'p20: clear action labelled Remove all');

        /* Initial visibility/ARIA state */
        assert(getEl('proofBatchPanel').hidden === true, 'p20: panel starts hidden');
        assert(els.csProofBatchBtn.getAttribute('aria-expanded') !== 'true', 'p20: launcher not expanded initially');

        /* Launcher opens the panel */
        click('csProofBatchBtn');
        assert(getEl('proofBatchPanel').hidden === false, 'p20: launcher click opens panel');
        assert(els.csProofBatchBtn.getAttribute('aria-expanded') === 'true', 'p20: launcher aria-expanded=true when open');

        /* Honest empty state while open */
        var proofList = getEl('proofList');
        assert(proofList.innerHTML.indexOf('No ASINs selected') !== -1, 'p20: empty state says No ASINs selected');
        assert(proofList.innerHTML.indexOf('Add to Proof Batch') !== -1, 'p20: empty state explains Add to Proof Batch');

        /* Launcher toggle closes the panel */
        click('csProofBatchBtn');
        assert(getEl('proofBatchPanel').hidden === true, 'p20: launcher click closes panel');
        assert(els.csProofBatchBtn.getAttribute('aria-expanded') === 'false', 'p20: launcher aria-expanded=false after close');

        /* True toggle semantics: first toggle adds */
        var proofProduct = { name: 'Proof Batch Fixture Product', asin: 'B07H3TXVR7', amazon_price: 48.87, costco_cost: 15.99, fba_fee: 7.1 };
        vm.runInContext('NS.toggleSelection(' + JSON.stringify(proofProduct) + ')', context);
        vm.runInContext('NS.renderProofBatch()', context);
        var sel1 = vm.runInContext('NS.loadSelection()', context);
        assert(sel1.asins.length === 1 && sel1.asins[0].asin === 'B07H3TXVR7', 'p20: first toggle adds the product');
        assert(String(els.csProofCount.textContent) === '1', 'p20: launcher count updates to 1');
        assert((els.csProofCount.className || '').indexOf('zero') === -1, 'p20: zero class drops when batch non-empty');
        assert(proofList.innerHTML.indexOf('B07H3TXVR7') !== -1, 'p20: row shows ASIN');
        assert(proofList.innerHTML.indexOf('Proof Batch Fixture Product') !== -1, 'p20: row shows title');
        assert(proofList.innerHTML.indexOf('Benchmark match') !== -1, 'p20: row shows real benchmark state');
        assert(proofList.innerHTML.indexOf('Missing:') !== -1, 'p20: row shows real missing-field state');
        assert(proofList.innerHTML.indexOf('>Remove</button>') !== -1, 'p20: row exposes per-item Remove control');

        /* Second toggle removes — never duplicates */
        vm.runInContext('NS.toggleSelection(' + JSON.stringify(proofProduct) + ')', context);
        vm.runInContext('NS.renderProofBatch()', context);
        var sel2 = vm.runInContext('NS.loadSelection()', context);
        assert(sel2.asins.length === 0, 'p20: second toggle removes (toggle contract)');
        assert(String(els.csProofCount.textContent) === '0', 'p20: launcher count returns to 0 after toggle-off');

        /* Sanitizer refuses duplicate ASINs even if stored data is tampered */
        vm.runInContext('NS.saveSelection({ schema_version: 1, asins: [{ asin: "B0DUP00001", title: "a" }, { asin: "b0dup00001", title: "b" }] })', context);
        var selDup = vm.runInContext('NS.loadSelection()', context);
        assert(selDup.asins.length === 1 && selDup.asins[0].asin === 'B0DUP00001', 'p20: sanitizer collapses duplicate ASINs to one entry');
        vm.runInContext('NS.clearSelection()', context);

        /* Remove-one via ONE delegated panel click — no manual follow-up call */
        vm.runInContext('NS.toggleSelection(' + JSON.stringify(proofProduct) + ')', context);
        vm.runInContext('NS.renderProofBatch()', context);
        click('proofBatchPanel', {
            closest: function () { return this; },
            getAttribute: function (k) { return k === 'data-proof-toggle' ? 'B07H3TXVR7' : null; }
        });
        var sel3 = vm.runInContext('NS.loadSelection()', context);
        assert(sel3.asins.length === 0, 'p20: one delegated panel click removes exactly that ASIN');
        assert(String(els.csProofCount.textContent) === '0', 'p20: launcher count reflects the single removal');

        /* Remove all */
        setProofSelection(['B0PROF0002', 'B0PROF0003']);
        vm.runInContext('NS.renderProofBatch()', context);
        assert(String(els.csProofCount.textContent) === '2', 'p20: two items staged for remove-all');
        click('proofClearAll');
        assert(vmGet('NS.loadSelection()').asins.length === 0, 'p20: Remove all empties the batch');
        assert(String(els.csProofCount.textContent) === '0', 'p20: launcher count zero after Remove all');

        /* Dedicated close control */
        click('csProofBatchBtn');
        assert(getEl('proofBatchPanel').hidden === false, 'p20: panel reopens for close-control test');
        click('proofCloseBtn');
        assert(getEl('proofBatchPanel').hidden === true, 'p20: close button hides panel');
        assert(els.csProofBatchBtn.getAttribute('aria-expanded') === 'false', 'p20: aria-expanded=false after close button');

        /* Escape priority: detail sheet > Proof Batch panel */
        vm.runInContext('NS.openSheet(' + JSON.stringify(P({ asin: 'B07H3TXVR7', name: 'Proof Batch Fixture Product' })) + ', null)', context);
        assert(vmGet('_sheetProduct') !== null, 'p20: sheet open (chain setup)');
        click('csProofBatchBtn');
        assert(vmGet('_proofBatchOpen') === true, 'p20: Proof Batch open above sheet');
        fireKey('Escape');
        assert(vmGet('_sheetProduct') === null, 'p20: Escape closes the sheet first');
        assert(vmGet('_proofBatchOpen') === true, 'p20: Proof Batch survives the sheet Escape');
        fireKey('Escape');
        assert(vmGet('_proofBatchOpen') === false, 'p20: Escape closes Proof Batch when topmost');

        /* Escape priority: research drawer > Proof Batch panel */
        vm.runInContext('NS.openDrawer("B07H3TXVR7")', context);
        assert(vmGet('_drawerOpen') === true, 'p20: drawer open (chain setup)');
        click('csProofBatchBtn');
        assert(vmGet('_proofBatchOpen') === true, 'p20: Proof Batch open above drawer');
        fireKey('Escape');
        assert(vmGet('_drawerOpen') === false, 'p20: Escape closes the drawer first');
        assert(vmGet('_proofBatchOpen') === true, 'p20: Proof Batch survives the drawer Escape');
        fireKey('Escape');
        assert(vmGet('_proofBatchOpen') === false, 'p20: Escape closes Proof Batch after the drawer');

        /* Escape priority: Proof Batch panel > Product Focus exit */
        vm.runInContext('NS.setViewMode("focus")', context);
        assert(vmGet('currentViewMode') === 'focus', 'p20: focus mode active (chain setup)');
        click('csProofBatchBtn');
        assert(vmGet('_proofBatchOpen') === true, 'p20: Proof Batch open in focus mode');
        fireKey('Escape');
        assert(vmGet('_proofBatchOpen') === false, 'p20: Escape closes Proof Batch before Focus exit');
        assert(vmGet('currentViewMode') === 'focus', 'p20: Focus preserved while Proof Batch consumed Escape');
        fireKey('Escape');
        assert(vmGet('currentViewMode') === 'gallery', 'p20: Escape exits Focus only after Proof Batch closed');

        /* Selection survives Gallery/List/Table/Focus */
        setProofSelection(['B0PROF0002', 'B0PROF0003']);
        vm.runInContext('NS.renderProofBatch()', context);
        assert(String(els.csProofCount.textContent) === '2', 'p20: selection staged for persistence checks');
        ['list', 'table', 'focus', 'gallery'].forEach(function (m) {
            vm.runInContext('NS.setViewMode("' + m + '")', context);
            assert(String(els.csProofCount.textContent) === '2', 'p20: selection survives ' + m + ' view change');
        });

        /* Selection survives quick filters and clear-filters
         * (real signatures: applyQuickFilter(statusValue, packValue)) */
        vm.runInContext('NS.applyQuickFilter("Pass", undefined)', context);
        assert(String(els.csProofCount.textContent) === '2', 'p20: selection survives status filter');
        vm.runInContext('NS.applyQuickFilter(undefined, "invoice_confirmed")', context);
        assert(String(els.csProofCount.textContent) === '2', 'p20: selection survives pack filter');
        vm.runInContext('NS.clearAllFilters()', context);
        assert(String(els.csProofCount.textContent) === '2', 'p20: selection survives clear-all-filters');

        /* Live Validation Proposal remains a LOCAL preview: opens fail-closed,
         * states its guardrail, cancels cleanly. No submit path exercised. */
        click('liveProposalOpenBtn');
        assert(getEl('liveValidationPanel').hidden === false, 'p20: proposal preview opens locally');
        assert((els.liveProposalStatus.textContent || '').indexOf('BLOCKED') !== -1 || (els.liveProposalStatus.textContent || '').indexOf('NO REQUEST SENT') !== -1, 'p20: proposal status shows blocked/not-sent guardrail');
        assert((els.liveProposalProviderNote.textContent || '').length > 0, 'p20: proposal shows honest provider-note disclosure');
        vm.runInContext('NS.cancelLiveProposal()', context);
        assert(getEl('liveValidationPanel').hidden === true, 'p20: proposal preview cancels cleanly');

        /* Zero network across every Phase 20 interaction; one canonical keydown handler */
        assert(proofFetchCalls.length === 0, 'p20: zero fetch calls across all Proof Batch + proposal interactions');
        assert(domEvents.keydown.length === 1, 'p20: exactly one global keydown handler remains registered');

        /* ---- Authorization Gate: read-only, derived ONLY from existing payload fields (zero network) ---- */
        console.log('--- gate via authorizationGate ---');
        var gateOf = function (obj) {
            return vm.runInContext('NS.authorizationGate(' + JSON.stringify(obj) + ')', context);
        };
        var g;
        g = gateOf({ pack_match: 'mismatch' });
        assert(g && g.key === 'blocked', 'pack_match mismatch => blocked');

        g = gateOf({ portfolio_readiness: 'insufficient_data' });
        assert(g && g.key === 'blocked', 'portfolio_readiness insufficient_data => blocked');

        g = gateOf({ cost_is_purchase_authorized: true, costco_cost_basis: 'invoice_confirmed', pack_match: 'exact' });
        assert(g && g.key === 'authorized' && g.severity === 'ok', 'authorized flag + invoice_confirmed => authorized (severity ok)');

        g = gateOf({ costco_cost_basis: 'costco_online', pack_match: 'candidate' });
        assert(g && g.key === 'invoice_pending' && g.severity === 'warn', 'discovery cost + candidate pack => invoice_pending (severity warn)');

        g = gateOf({ costco_cost_basis: 'unavailable', pack_match: 'unknown' });
        assert(g && g.key === 'invoice_pending', 'unavailable basis + unknown pack => invoice_pending');

        g = gateOf({ economics_confidence: 'provisional', costco_cost_basis: 'invoice_confirmed', pack_match: 'exact' });
        assert(g && g.key === 'needs_review' && g.severity === 'review', 'provisional economics => needs_review (severity review)');

        g = gateOf({ economics_confidence: 'unavailable', costco_cost_basis: 'invoice_confirmed', pack_match: 'exact' });
        assert(g && g.key === 'needs_review', 'unavailable economics => needs_review');

        g = gateOf({ freshness_label: 'stale', costco_cost_basis: 'invoice_confirmed', pack_match: 'exact', economics_confidence: 'estimated' });
        assert(g && g.key === 'needs_review', 'stale freshness => needs_review');

        g = gateOf({ verdict: 'Pass', costco_cost_basis: 'costco_online', pack_match: 'exact', economics_confidence: 'estimated' });
        assert(g && g.key !== 'authorized', 'Pass/Qualified without invoice authorization must NOT be authorized');

        g = gateOf({ costco_cost_basis: 'invoice_confirmed', pack_match: 'exact' });
        assert(g && g.key === 'needs_review', 'invoice_confirmed + exact pack + no auth flag => needs_review');

        g = gateOf({});
        assert(g && g.key === 'needs_review', 'empty {} => needs_review (default fallback, not invoice_pending)');

        /* ==========================================================================
         * A3 — design tokens: canonical source embedded + aliased, v2-gated.
         * Default <html> keeps the OLD theme (no data-theme-v2 attr) until the
         * full contract passes on v2. Additive assertions only.
         * ========================================================================== */
        /* the default <html> tag must carry NO data-theme-v2 (old theme stays default) */
        const htmlTagA3 = html.slice(html.indexOf('<html'), html.indexOf('>', html.indexOf('<html')) + 1);
        assert(htmlTagA3.includes('data-theme="light"') && !htmlTagA3.includes('data-theme-v2'),
            'a3: default <html> has NO data-theme-v2 (old theme stays default)');
        assert(html.includes('html[data-theme-v2]'), 'a3: token layer gated behind html[data-theme-v2]');
        assert(html.includes('--ns-color-bg-app: #0a0f1f'), 'a3: canonical dark token present (color/bg-app)');
        assert(html.includes('--ns-color-bg-app: #f2f3f9'), 'a3: canonical light token present (color/bg-app)');
        assert(html.includes('--bg-app: var(--ns-color-bg-app)'), 'a3: existing var --bg-app aliased to token');
        assert(html.includes('--card-r: var(--ns-radius-lg)'), 'a3: radius alias covers --card-r');
        assert(html.includes('--dur: var(--ns-motion-dur)'), 'a3: motion dur aliased (--dur -> --ns-motion-dur)');
        assert(html.includes('--ease: var(--ns-motion-ease)'), 'a3: motion ease aliased (--ease -> --ns-motion-ease)');
        /* sync guard: the embedded token CSS must match shared/design-tokens.css verbatim (CRLF-normalized) */
        const tokBegin = 'A3 DESIGN-TOKENS: BEGIN';
        const tokEnd = 'A3 DESIGN-TOKENS: END';
        const tokIdxB = html.indexOf(tokBegin);
        const tokIdxE = html.lastIndexOf(tokEnd);
        const embeddedOk = tokIdxB !== -1 && tokIdxE !== -1 && tokIdxE > tokIdxB;
        const contentStart = embeddedOk ? html.indexOf('\n', tokIdxB) + 1 : -1;
        const contentEnd = embeddedOk ? html.lastIndexOf('\n', tokIdxE) : -1;
        const embeddedCss = (contentStart !== -1 && contentEnd > contentStart)
            ? html.slice(contentStart, contentEnd).replace(/\r/g, '').trim()
            : '';
        const tokCssFile = fs.readFileSync(path.join(__dirname, '..', 'shared', 'design-tokens.css'), 'utf8').replace(/\r/g, '').trim();
        assert(embeddedCss === tokCssFile, 'a3: embedded token CSS matches shared/design-tokens.css verbatim (sync guard)');

        /* ==========================================================================
         * A4 — SPA v2 redesign: presentation layer behind html[data-theme-v2].
         * Additive assertions: v2 CSS block present + token-driven, dev toggle
         * wiring present, and the toggle provably DOES NOT activate by default.
         * ========================================================================== */
        assert(html.includes('A4 SPA V2 REDESIGN: BEGIN') && html.includes('A4 SPA V2 REDESIGN: END'),
            'a4: v2 redesign CSS block present between A4 markers');
        assert(html.includes('html[data-theme-v2] #mainContent { max-width:') || html.includes('html[data-theme-v2] .app-shell'),
            'a4: v2 layout rules scoped behind data-theme-v2');
        assert(html.includes('html[data-theme-v2] .intel-metric') && html.includes('var(--ns-space-'),
            'a4: v2 spacing rhythm uses --ns-space tokens');
        assert(html.includes('html[data-theme-v2] #scoutTable') && html.includes('font-variant-numeric: tabular-nums'),
            'a4: v2 typography applied to table with tabular numerals');
        assert(html.includes('html[data-theme-v2] .btn.primary') && html.includes('var(--ns-color-accent)'),
            'a4: v2 button surface uses accent tokens');
        assert(html.includes(':focus-visible') && html.includes('var(--ns-color-accent-hi)'),
            'a4: v2 focus-visible outline (accessibility)');
        assert(html.includes('prefers-reduced-motion') && html.includes('html[data-theme-v2] .stream-row'),
            'a4: v2 respects prefers-reduced-motion');
        assert(html.indexOf('THEME_V2_KEY') !== -1 && html.includes('NS.applyThemeV2') && html.includes('initThemeV2'),
            'a4: dev toggle JS present (localStorage flag + apply + boot)');
        assert(/[?&]v2=1/.test(html) && html.includes("'t2.kirklandScout.themeV2.v1'"),
            'a4: ?v2=1 query param + localStorage key wired');
        assert(/id="devV2Btn"[^>]*aria-label="Toggle v2 theme \(dev-only\)"/.test(html),
            'a4: dev V2 chip carries an aria-label (accessibility)');
        /* functional: default boot must NOT activate v2 (old theme stays default) */
        const v2HtmlRec = { attrs: new Map(), setAttribute(k, v) { this.attrs.set(k, String(v)); }, removeAttribute(k) { this.attrs.delete(k); }, getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; } };
        documentStub.documentElement = v2HtmlRec;
        vm.runInContext(`localStorage.removeItem('t2.kirklandScout.themeV2.v1'); initThemeV2();`, context);
        assert(!v2HtmlRec.attrs.has('data-theme-v2') && vm.runInContext(`localStorage.getItem('t2.kirklandScout.themeV2.v1')`, context) === '0',
            'a4: default boot leaves data-theme-v2 OFF and persists 0');
        /* functional: flag/param path activates the attribute */
        vm.runInContext(`localStorage.setItem('t2.kirklandScout.themeV2.v1', '1'); initThemeV2();`, context);
        assert(v2HtmlRec.attrs.get('data-theme-v2') === '' && vm.runInContext(`localStorage.getItem('t2.kirklandScout.themeV2.v1')`, context) === '1',
            'a4: localStorage flag activates data-theme-v2');
        vm.runInContext(`NS.applyThemeV2(false);`, context);
        assert(!v2HtmlRec.attrs.has('data-theme-v2'), 'a4: applyThemeV2(false) removes the attribute');

        if (failures === 0) {
    console.log('ALL UI DISPLAY TESTS PASSED');
} else {
    console.log(failures + ' FAILURE(S)');
    process.exitCode = 1;
}
