# Performance baseline — 2026-11-06

Read-only measurement lane. Nothing was fixed, refactored or "improved". Every number below came
from the command printed next to it. The backend was started only through `scripts/dev-start.ps1`
(as authorised for this lane) and stopped again at the end; the autonomous loop was not started.

**Disclosure — `STOP` was present and I honoured its scope.** `STOP` exists at the repo root
(`stopped by operator at 2026-11-06T14:33:51+00:00`). Per `reports/ty/SESSION_RESUME_20261106.md`
that file exists to halt the *autonomy loop* (the launcher was reverting committed work), and
`python tools\tys_runner.py status` still reports `"stop": true` — I left it that way and touched
nothing. This lane ran four processes total: the dev stack the task authorised, and read-only
probes. No loop cycle, no queue item, no write to any tracked file except this report.

## Environment

| | |
|---|---|
| Python | 3.14.5 |
| Backend | `uvicorn main:app --host 127.0.0.1 --port 8000`, single worker, `ENVIRONMENT=development` |
| Auth | **dev shim** — no header sent; `/api/v1/foundation/environment` reports `auth_method: dev_shim`, `auth_posture: dev_shim_local_only`, `real_authentication_active: false` |
| Box | otherwise idle. A pre-existing FLUX 3 gateway (PID 23512, started 2026-11-05) was already listening on :8190 and was **not** started or stopped by this lane; it is reachable, which matters for route 2 below |
| Git HEAD | `0c98921d` |

---

## 1. Cold import time

```
cd Northstar_backend
python -c "import time;t=time.time();import main;print(round(time.time()-t,2))"
```

Three consecutive runs (first is cold page cache, the rest warm):

| run | seconds |
|---|---|
| 1 | **2.86** |
| 2 | **1.31** |
| 3 | **1.32** |

Steady-state import of `main` is **~1.31 s**; the first run after boot pays ~1.55 s of disk.

Side effects at import time (not startup): `design_studio_api.py:1395` emits a pydantic
`UserWarning` (`Field name "copy" ... shadows an attribute`), and the log line
`northstar.main: shell hardware daemon started` fires on import.

### `-X importtime` — top 15 by cumulative (self in brackets)

```
python -X importtime -c "import main"
```

910 import rows. Times in ms:

| cumulative | self | module |
|---:|---:|---|
| 1505.7 | 322.6 | `main` |
| 346.5 | 0.0 | `foundation.api.state` |
| 346.5 | 0.9 | `foundation.api` |
| 280.7 | **279.6** | `foundation.api.router` |
| 259.0 | 0.6 | `fastapi` |
| 253.4 | 0.9 | `fastapi.applications` |
| 237.1 | 3.5 | `fastapi.routing` |
| 126.6 | 1.5 | `fastapi.params` |
| 104.5 | 2.7 | `design_studio_compose` |
| 101.8 | 1.1 | `mockup_compositor` |
| 99.3 | 2.3 | `product_analysis` |
| 78.1 | 15.1 | `fastapi.exceptions` |
| 75.3 | 14.6 | `tys_api` |
| 72.3 | 2.2 | `numpy` |
| 66.8 | 0.7 | `amazon_search` |

The five slowest by **self** time — i.e. the five places where the interpreter actually burns
time, not just waits on children:

| self | module |
|---:|---|
| 322.6 | `main` (the 113 KB module's own top-level route definitions) |
| 279.6 | `foundation.api.router` |
| 38.6 | `design_studio_api` |
| 38.1 | `fastapi.openapi.models` |
| 26.2 | `foundation.models` |

Read: 40 % of import is `main.py` and `foundation/api/router.py` executing top-level code;
framework import (`fastapi`, 259 ms) is the second-largest bucket and is not reducible without
changing framework.

---

## 2. Endpoint latency — 10 sequential requests per route

Primary measurement: **fresh TCP connection per request** (`urllib.request`), one warm-up request
discarded, 10 timed. p95 = linear interpolation (`(n-1)*0.95`). Full script in Appendix A.

| route | codes | p50 | p95 | max | bytes |
|---|---|---:|---:|---:|---:|
| `GET /health` | 200 ×10 | 15.8 | 16.6 | 16.7 | 63 |
| `GET /api/v1/foundation/environment` | 200 ×10 | 12.5 | 20.9 | 24.2 | 341 |
| `GET /api/v1/provider-suite` | 200 ×10 | 15.4 | 17.2 | 17.8 | 53,890 |
| `GET /api/admin/tys/state` | **403 ×10** | 14.0 | 16.7 | 16.8 | 36 |
| `GET /api/design-studio/lanes/status` | 200 ×10 | 401.5 | 418.2 | 419.1 | 1,342 |
| `GET /api/kirkland/scanner` | 200 ×10 | 6598.1 | **6623.2** | 6632.5 | 553,370 |

`tys/state` body: `{"detail":{"code":"tys_admin_only"}}` — the dev shim identity is
`demo-t2 / org-t2 / operator` (`foundation/dev_identity.py:26-27`) and `operator` is not an admin
role, so the request is refused **before the handler runs**.

### Same routes, keep-alive (one persistent connection, handshake excluded)

```
python %TEMP%\opencode\ns_perf_keepalive.py      # Appendix B
```

| route | codes | p50 | p95 | max |
|---|---|---:|---:|---:|
| `GET /health` | 200 | **1.4** | 1.6 | 1.7 |
| `GET /api/v1/foundation/environment` | 200 | **2.0** | 2.2 | 2.2 |
| `GET /api/v1/provider-suite` | 200 | **2.6** | 2.8 | 2.9 |
| `GET /api/admin/tys/state` | 403 | **1.2** | 1.4 | 1.4 |
| `GET /api/design-studio/lanes/status` | 200 | **357.5** | 377.9 | 378.9 |

**This is the most important number in the report.** Four of the six routes are 1–3 ms of real
work; the 12–16 ms p50 in the first table is a Windows-loopback **connect tax** (~13 ms) paid
because `urllib` opens a new socket per request, not backend slowness. Only
`lanes/status` (~357 ms) and `scanner` (~6.6 s) are genuinely slow handlers.

---

## 3. Frontend build size

```
cd northstar-os-ui && npm run build
```

`✓ built in 1.90s`, exit 0, 249 modules transformed.

| | |
|---|---|
| total `dist/` | **4,490,844 B = 4.28 MB**, 36 files |
| **largest JS 1** | `assets/index-CL_X1DA1.js` — **1,088.55 kB** (1,091,755 B), gzip 296.42 kB |
| **largest JS 2** | `assets/vendor-Do7LaSsY.js` — **163.69 kB**, gzip 53.39 kB |
| **largest JS 3** | `assets/studio-CMTFbN15.js` — **43.58 kB**, gzip 14.93 kB |
| largest CSS | `assets/index-BdXp1mYI.css` — 208.10 kB, gzip 37.95 kB |
| largest asset | `assets/globular-core-CgOjCHys.webp` — 540.84 kB |

Vite warns: `Some chunks are larger than 500 kB after minification` — and only the entry chunk is.

Composition of the 4.28 MB: the ten `.webp` stills total **~2.75 MB**; all JS totals **~1.30 MB**.
The bundle is dominated by imagery, not code, but the 1.09 MB entry chunk is the one thing on the
critical path for every page load.

Build warnings (not errors, not fixed): `specRegistry.js`, `fidelity.js`, `disclosure.js`,
`compliance.js` and `compose.js` are each both dynamically and statically imported, so
`dynamic import will not move module into another chunk`.

---

## 4. The five slowest endpoints by measured p95, and why

Ranked on the primary (fresh-connection) numbers, which is what a cold client actually sees.

**1. `GET /api/kirkland/scanner` — p95 6623.2 ms, 200, 553 KB.**
Cause: `product_analysis.py:233` calls `get_costco_price()` once per candidate (89 candidates
served), and `costco_client.py:487-489` **re-reads and re-parses the Costco CSV on every call**
before running `difflib.SequenceMatcher(...).ratio()` against every row
(`costco_client.py:516-518`) — 80,932 `ratio()` calls, 15.4 s of the profiled request — with no
memoisation between candidates or between requests.

<details><summary>profiler output for that claim</summary>

```
    ncalls  tottime  percall  cumtime  filename:lineno(function)
         1    0.000 18.373   18.373  product_analysis.py:196(analyze_kirkland_products)
         1    0.004 18.373   18.373  product_analysis.py:220(_analyze_candidates)
        89    0.007 18.297    0.206  product_analysis.py:73(get_costco_price)
       157    0.167 17.694    0.113  costco_client.py:470(get_costco_price)
     80932    0.102 15.412    0.000  difflib.py:597(ratio)
   1069854    9.059 13.436    0.000  difflib.py:305(find_longest_match)
```
`cProfile` inflates the wall clock ~2.8× (18.4 s vs 6.6 s unprofiled); the *proportions* are what
matter. The request made no outbound call: `live_gate.live_enabled()=False`,
`offer_enrichment._enrichment_mode()="OFF"`, so `_candidates_for_mode` returns the local cache
(`product_analysis.py:203` → `amazon_search.load_cached_candidates()`), and the egress guard
installed at startup would have refused an Amazon host anyway.
</details>

**2. `GET /api/design-studio/lanes/status` — p95 418.2 ms (377.9 ms keep-alive), 200, 1.3 KB.**
Cause: the handler answers "which lanes work right now" by *probing live, on every request, with no
cache* — `design_studio_lanes.py:79` → `studio_generation.py:171-183` (HTTP to ComfyUI
`/system_stats`), `design_studio_lanes.py:105-110` → `local_vision.py:92` (spawns `nvidia-smi`)
and `local_vision.py:250` (HTTP to Ollama `/api/tags`), and `design_studio_lanes.py:92-99` →
`local_voice.py:42-48` (spawns PowerShell to load System.Speech, the single biggest item).

<details><summary>per-component timing, same environment, best of 3</summary>

```
prepress.available_cmyk_profiles           0.7ms     0.6ms     0.6ms
studio_generation.engine_status            9.0ms    15.3ms    15.7ms
local_vision.engines                     128.5ms   127.8ms   126.0ms
local_transcribe.engines                   0.0ms     0.0ms     0.0ms
local_voice.engines                      215.2ms   216.9ms   213.4ms
local_vision.vram_free_mb (nvidia-smi)    47.6ms    47.5ms    47.0ms
```
215 + 128 + ~12 + 0.7 ≈ **356 ms**, which matches the measured 357.5 ms p50. Nothing else in the
request costs anything.
</details>

**3. `GET /api/v1/foundation/environment` — p95 20.9 ms, but 2.0 ms keep-alive.**
Cause: no app-side cause worth naming — ~18 ms of the p95 is the Windows-loopback connect tax, and
the handler (`foundation/api/router.py:466-489`) just builds a 12-key dict from the already-resolved
`get_context` dependency. The real finding here is a **discrepancy, reported not fixed**: the
payload says `"environment":"production"` while `auth_method` is `dev_shim`, because
`foundation/api/deps.py:208-210` takes the environment from the `X-Env` header and **defaults to
`production` when the header is absent**, so a headerless local request is labelled production.

**4. `GET /api/v1/provider-suite` — p95 17.2 ms, but 2.6 ms keep-alive.**
Cause: connect tax again, plus the 53,890-byte payload being serialised per request; the JSON itself
is loaded once at import (`provider_suite.py:64`, module-level `_load_json`) so there is no file I/O
per call. It is the largest fast response in the set and still only 2.6 ms of handler time.

**5. `GET /api/admin/tys/state` — p95 16.7 ms, 403 ×10, 1.2 ms keep-alive.**
Cause: it never reaches the handler. `tys_api.py:46-59` refuses the dev-shim role `operator` —
neither `PLATFORM_ROLES` nor `ADMIN_ROLES` — with `{"code":"tys_admin_only"}`. Its "latency" is a
rejected dependency, so **this route's performance is still unmeasured**; measuring it needs an
identity with an admin role (an `X-Role` header is ignored outside the dev shim, `deps.py:123`).

---

## What this baseline says

- The service is **fast on 5 of 6 measured routes**: 1.2–2.6 ms of handler time each. There is no
  general latency problem to chase.
- There are exactly **two slow handlers**, and both are the same bug shape — *recompute per request
  what could be computed once*: the scanner re-parses a CSV and fuzzy-matches 89×89 strings per
  call, and the lanes probe spawns a PowerShell process and three subprocess/HTTP probes per call.
  They account for 6623 ms and 418 ms of p95 respectively; between them they are 99.5 % of the
  measured latency in the whole set.
- **Startup is ~1.31 s steady / 2.86 s cold**, 40 % of it top-level code in `main.py` and
  `foundation/api/router.py`.
- The UI ships **4.28 MB**, of which 2.75 MB is stock imagery and 1.09 MB is a single entry chunk
  that Vite itself flags as too large.

### Measurement caveats (so the next lane doesn't over-read these)

1. Fresh-connection numbers include a ~13 ms Windows-loopback connect tax. Compare like with like:
   the keep-alive column is server cost, the primary column is cold-client cost.
2. Single uvicorn worker, no concurrent load, box otherwise idle. No queueing was exercised.
3. One warm-up request per route was discarded; on the scanner route that warm-up is itself 6.6 s
   (no cache to warm).
4. The lanes timing benefits from a *reachable* ComfyUI on :8190. On a box where it is also
   reachable the numbers hold; where the port is firewalled rather than closed, the 3 s client
   timeout would apply instead.
5. `tys/state` returned 403 in all 10 samples — a refusal, not a measurement of its work.

---

## Appendix A — primary measurement script (`%TEMP%\opencode\ns_perf.py`)

```python
import json, statistics, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8000"
ROUTES = ["/health", "/api/v1/foundation/environment", "/api/v1/provider-suite",
          "/api/admin/tys/state", "/api/design-studio/lanes/status", "/api/kirkland/scanner"]
N = 10

def pct(vals, p):
    s = sorted(vals); k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)

def one(path):
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return (time.perf_counter() - t) * 1000.0, r.status, len(r.read())
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - t) * 1000.0, e.code, len(e.read())

out = []
for path in ROUTES:
    one(path)                                    # warmup, discarded
    ms, codes = [], []
    for _ in range(N):
        m, c, _ = one(path); ms.append(m); codes.append(c)
    out.append({"route": path, "codes": codes, "p50": round(statistics.median(ms), 1),
                "p95": round(pct(ms, 95), 1), "max": round(max(ms), 1),
                "raw_ms": [round(x, 1) for x in ms]})
print(json.dumps(out, indent=2))
```

## Appendix B — keep-alive script (`%TEMP%\opencode\ns_perf_keepalive.py`)

Same shape, but a single `http.client.HTTPConnection("127.0.0.1", 8000)` per route, warm-up request
first so the socket is established, then the 10 timed requests reuse it.

## Appendix C — how the backend was run and stopped

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev-start.ps1   # background job
```

(I intended `NORTHSTAR_NO_MEDIA=1` to skip the media lane; the nested-quoting in the launch
flattened that assignment, so the media step ran and found the already-running 11/5 stack. No new
media process was created — recorded here because the intent and the executed command differed.)
`dev-start.ps1` ran `scripts\check_dev_safety.py` (result: `dev safety: OK (loopback-only,
ENVIRONMENT=development, no tunnel/funnel exposure of dev ports)`), started the backend on
127.0.0.1:8000 and Vite on 127.0.0.1:8101. Media lane PIDs listed in `dev-start.pids`
(23512, 17252, 25384) were **pre-existing since 2026-11-05** and were deliberately left running;
only the backend (17688) and UI processes this lane caused (27156, 6512, 17724, 21804) were
stopped. After the stop: `:8000` and `:8101` free, the pre-existing `:8190` gateway (PID 23512)
untouched, `tys_runner status` still `"stop": true`, `STOP` untouched.

Warning for whoever runs this next: `scripts\dev-start.ps1` appends the *contents* of a stale
`flux3.pids` to its own roster without checking that the PIDs belong to what it just started, so
`dev-start.pids` currently mixes this lane's backend/UI PIDs with yesterday's media-lane PIDs. A
blind "stop everything in dev-start.pids" would kill the 11/5 FLUX 3 stack. I left the file in
place rather than deleting a runtime artifact I did not create.
