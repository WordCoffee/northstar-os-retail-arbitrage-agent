/*
 * B5 — Cloudflare Pages Functions bff/v1 contract conformance test.
 *
 * Imports each functions/api route module and invokes it with a fake context
 * (no network, KV stubbed, crypto present in node 18+). Asserts every
 * response conforms to docs/contracts/BFF_CONTRACT_v1.md: envelope fields,
 * honest status codes, no-leak (no provider/exception text), and the honest
 * 501 not_implemented transcribe stub.
 *
 * Run: node Northstar_backend/test_functions_contract.cjs
 */

const { pathToFileURL } = require('url');
const path = require('path');

let failures = 0;
const assert = (cond, msg) => {
  if (cond) console.log('PASS:', msg);
  else { failures++; console.log('FAIL:', msg); }
};

const apiDir = path.join(__dirname, '..', 'functions', 'api');
const load = (name) => import(pathToFileURL(path.join(apiDir, name)).href);

const ENV_KEYS = ['contract', 'request_id', 'status', 'data', 'error', 'meta'];

function assertEnvelope(body, url, status) {
  let ok = true;
  if (typeof body !== 'object' || body === null) { assert(false, url + ' returns JSON object'); return; }
  for (const k of ENV_KEYS) {
    if (!(k in body)) { assert(false, url + ' envelope has ' + k); ok = false; }
  }
  if (typeof body.contract !== 'string' || body.contract !== 'bff/v1') { assert(false, url + ' contract=bff/v1'); ok = false; }
  if (typeof body.request_id !== 'string' || !body.request_id.startsWith('req_')) { assert(false, url + ' request_id opaque'); ok = false; }
  if (!['ok', 'empty', 'error'].includes(body.status)) { assert(false, url + ' status enum'); ok = false; }
  if (body.status === 'error' && (body.error === null || typeof body.error.code !== 'string')) { assert(false, url + ' error object present'); ok = false; }
  if (body.status !== 'error' && body.error !== null) { assert(false, url + ' error null on success'); ok = false; }
  if (ok) assert(true, url + ' envelope shape OK (' + body.status + ')');
}

function assertNoLeak(body, url) {
  const text = JSON.stringify(body).toLowerCase();
  const bad = ['brightdata', 'chocodata', 'easyparser', 'openwebninja', 'unwrangle',
    'dataforseo', 'firecrawl', 'scrape.do', 'rapidapi', 'stack', 'traceback',
    'report_path', 'file_path', 'api_key'.replace('_', ''), 'bearer eyj'];
  let clean = true;
  for (const t of bad) {
    if (text.includes(t)) {
      clean = false;
      assert(false, url + ' no-leak: found token ' + t);
    }
  }
  if (clean) assert(true, url + ' no-leak clean');
}

function assertStatus(body, url, status) {
  assert(body.status === status, url + ' status=' + status + ' (got ' + body.status + ')');
  if (status === 'error') {
    assert(body.error && typeof body.error.code === 'string'
      && typeof body.error.message === 'string' && body.error.message.length > 0,
      url + ' error object populated (code + non-empty message)');
  } else {
    assert(body.error === null, url + ' error null on non-error');
  }
}

(async () => {
  /* ---------- files.js ---------- */
  const files = await load('files.js');
  let ctx = { env: { DEALS_KV: { get: async () => JSON.stringify([{ name: 'scored-1.json' }]) } } };
  let r = await files.onRequestGet(ctx);
  let body = await r.json();
  assertEnvelope(body, '/api/files', r.status);
  assertNoLeak(body, '/api/files');
  assertStatus(body, '/api/files', 'ok');
  assert(Array.isArray(body.data.files) && body.data.files.length === 1, '/api/files data.files populated');

  ctx = { env: { DEALS_KV: { get: async () => null } } };
  body = await (await files.onRequestGet(ctx)).json();
  assertStatus(body, '/api/files', 'empty');
  assert(Array.isArray(body.data.files) && body.data.files.length === 0, '/api/files empty -> no fabricated rows');

  /* ---------- data/[filename].js ---------- */
  const dataRoute = await load('data/[filename].js');
  ctx = { params: { filename: 'scored-20260901.json' }, env: { DEALS_KV: { get: async () => JSON.stringify({ a: 1 }) } } };
  body = await (await dataRoute.onRequestGet(ctx)).json();
  assertEnvelope(body, '/api/data/:name', 200);
  assertStatus(body, '/api/data/:name', 'ok');
  assert(body.data.name === 'scored-20260901.json', '/api/data/:name echoes name');

  ctx = { params: { filename: 'scored-20260901.json' }, env: { DEALS_KV: { get: async () => null } } };
  body = await (await dataRoute.onRequestGet(ctx)).json();
  assertStatus(body, '/api/data/:name', 'error');
  assert(body.error.code === 'not_found', '/api/data/:name missing -> not_found');

  ctx = { params: { filename: 'evil.txt' }, env: { DEALS_KV: { get: async () => null } } };
  body = await (await dataRoute.onRequestGet(ctx)).json();
  assertStatus(body, '/api/data/:name', 'error');
  assert(body.error.code === 'invalid_request', '/api/data/:name bad name -> invalid_request');

  /* ---------- transcribe.js ---------- */
  const txr = await load('transcribe.js');
  body = await (await txr.onRequest({ request: { method: 'POST' } })).json();
  assertEnvelope(body, '/api/transcribe', 501);
  assert(body.status === 'error' && body.error.code === 'not_implemented' && body.error.message.length > 0,
    '/api/transcribe POST -> honest 501 not_implemented (never a fake success)');
  body = await (await txr.onRequest({ request: { method: 'GET' } })).json();
  assert(body.status === 'error' && body.error.code === 'invalid_request', '/api/transcribe GET -> invalid_request');

  /* ---------- latest-deals.js (imports dealsApi; empty KV => no rows) ---------- */
  const deals = await load('latest-deals.js');
  ctx = { env: { DEALS_KV: { list: async () => ({ keys: [] }), get: async () => null } } };
  body = await (await deals.onRequestGet(ctx)).json();
  assertEnvelope(body, '/api/latest-deals', 200);
  assertStatus(body, '/api/latest-deals', 'ok');
  assert(Array.isArray(body.data.rows) && body.data.rows.length === 0, '/api/latest-deals empty rows honest');

  /* ---------- aggregate ---------- */
  console.log(failures === 0 ? '\nFUNCTIONS CONTRACT OK' : '\n' + failures + ' FAILURE(S)');
  process.exitCode = failures === 0 ? 0 : 1;
})().catch((e) => { console.error('test harness error:', e); process.exitCode = 1; });