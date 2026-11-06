# Amazon egress boundary — three defects fixed, each with a pre-request refusal test (2026-11-06)

Lane: backend security (`Northstar_backend`). Gate honoured: **no request was made to any
Amazon property** at any point, including while proving the pre-fix behaviour — every
pre-fix measurement below was taken with `httpx.post` / `httpx.get` mocked to a local
`RuntimeError`/`MagicMock` and with `socket.socket` patched out where the test allowed it.

Rollback point: `autonomy-lane-amazon-pre` → `0c98921d` (tagged before the first edit).

## Commits

| # | Task | Commit | Files |
|---|---|---|---|
| 1 | T1-amazon-guard | `cf443599` | `costco_non_kirkland/amazon_guard.py`, `costco_non_kirkland/tests/test_amazon_guard_asin_refusal.py` |
| 2 | T1-amazon-auth-gate | `112fef46` | `importers/sp_api_importer.py`, `importers/ads_api_importer.py`, `tests/test_amazon_auth_gate.py` |
| 3 | T2-report-download-host | `f497bcdb` | `importers/ads_api_importer.py`, `tests/test_ads_report_download_guard.py` |

No other file was touched. (`git show --stat` for each commit lists only the rows above.)

## 1. `assert_no_amazon_direct_scan` — repaired, not deleted

**Decision: repair the guard. Do not delete it.** Reasons, from reading both callers:

* `costco_non_kirkland/pipeline.py:383` passes `asin=` for every item in an enrichment
  manifest, immediately before `adapter.fetch(asin, mock=mock)`. That adapter is an
  *approved provider* adapter (SellerAmp family), not Amazon.
* `provider_imports/selleramp_importer.py:67` passes `asin=raw_row.get("asin")` for every
  row of an *approved SellerAmp export*.
* Therefore a blanket "refuse on any `asin`" would raise on 100 % of the sanctioned
  file-only/enrichment path. That is an outage, not a control — and it contradicts the
  module's own contract (ASINs from approved snapshots/exports are the permitted input)
  and `test_signin_disallowed_guard.py::test_assert_allows_provider_deep_link`, which pins
  `asin="B0TEST"` as allowed.
* Deletion was also unavailable within this lane's write scope: the two dead call sites
  live in `pipeline.py` and `selleramp_importer.py`, which are outside the files this lane
  is allowed to touch. Deleting the function while leaving the call sites would simply
  break them.

**What was actually broken** is that a *locator* arriving through `asin=` was waved
straight through. `asin` is supplied by a provider column or a manifest item and is handed
to `adapter.fetch()`, so it is precisely the field where a URL could smuggle a direct scan.
The guard now refuses, before anything runs:

* `url=` on an Amazon marketplace host (unchanged), and
* `asin=` that is not a **bare** ASIN identity — regex `^[A-Za-z0-9]{5,20}$`. Any scheme,
  host, `/dp/` path, share link, dot, slash, space or query string is refused.

Allowed: bare ASIN (`B0TEST1234`), `None`, empty/whitespace.

Test (`tests/test_amazon_guard_asin_refusal.py`, 5 tests / 9 subtests): hostile `asin`
values (`https://www.amazon.com/dp/...`, `amazon.com`, `/dp/...`, `amzn.to`, `...?ref=`,
`https://sas.selleramp.com/...`) raise `AmazonDirectScanProhibited` while `socket.socket`
and `socket.create_connection` are patched to explode — the refusal is proven to happen
before any socket can be opened. The bare-ASIN case passes under the same socket ban.

## 2. `SPAPIAuth._refresh` / `AdsAPIAuth._refresh` — gate moved inside the auth classes

Each `_refresh` now does, before `import httpx`:

```python
from amazon_linkage_gate import linkage_enabled, linkage_refusal_reason
if not linkage_enabled():
    raise AmazonLinkageDisabled(linkage_refusal_reason())
```

`AmazonLinkageDisabled(RuntimeError)` is defined in each module. `get_access_token()`
calls `_refresh()`, so the public entry point is stopped too. `_get_headers()` calls
`get_access_token()` *before* the retry loop in `_api_get`/`_api_post`, so the refusal
propagates instead of being swallowed and no request is attempted.

Test (`tests/test_amazon_auth_gate.py`, 6 tests): constructs each auth class **directly**
with placeholder credentials ("test-key-…" so the conftest does not scrub them), gate off,
and asserts `AmazonLinkageDisabled` with `httpx.post` mocked to explode and sockets banned;
`httpx.post` call count is asserted 0. A third test per class sets
`NS_AMAZON_LINKAGE_ENABLED=1` and asserts the refresh still happens (no over-blocking).

Pre-fix measurement (gate off, `httpx.post` mocked, tag `autonomy-lane-amazon-pre`):

```
PRE-FIX SPAPIAuth httpx.post calls = 1
PRE-FIX AdsAPIAuth httpx.post calls = 1
```

## 3. `ads_api_importer.py` report download — host allowlist

Added `is_allowed_report_url` / `assert_allowed_report_url` / `UnsafeReportURL`, and the
call is made on `status_data.get("url")` **before** the `httpx.get` (and before the broad
`except` around the download, so the refusal is loud rather than a logged error).

Accepted: `https`, port absent or 443, no embedded credentials, host equal to
`advertising-api.amazon.com` or ending in `.amazonaws.com`.
Refused: any other host (`storage.googleapis.com`, `evil.example.com`, `www.amazon.com`),
lookalikes (`evil-amazonaws.com`, `s3.amazonaws.com.evil.example`), userinfo tricks
(`s3.amazonaws.com@evil.example`), `http`, non-443 ports, IP literals including
`169.254.169.254` / `127.0.0.1` / `[::1]`, `ftp:`, `file:`, scheme-relative `//host`,
empty/None.

Test (`tests/test_ads_report_download_guard.py`, 4 tests / 27 subtests): the policy table,
plus `run_search_term_report()` driven end-to-end with a mocked status payload — the
hostile URL raises `UnsafeReportURL` with `httpx.get` asserted not called and sockets
banned, and an allowed S3 URL is still downloaded exactly once from the same URL.

Pre-fix measurement (tag `autonomy-lane-amazon-pre`, `httpx.get` mocked):

```
PRE-FIX httpx.get calls = 1 target = https://169.254.169.254/latest/meta-data/
```

## Verification actually run

Only targeted tests were run (no full suite — other lanes are on the box).

```
$ cd Northstar_backend
$ python -m pytest tests/test_amazon_auth_gate.py tests/test_ads_report_download_guard.py \
      costco_non_kirkland/tests/test_amazon_guard_asin_refusal.py \
      costco_non_kirkland/tests/test_signin_disallowed_guard.py \
      costco_non_kirkland/tests/test_provider_imports.py -q
51 passed, 36 subtests passed in 1.67s
```

The two pre-existing costco guard files are included deliberately: they are the regression
proof that the repair did not weaken the old `url=` check or break the sanctioned ASIN path.

```
$ python tools/test_no_amazon_linkage.py
NO-AMAZON-LINKAGE GUARD: 2365 passed, 0 failed        (exit 0)
```

That is the static scan over both edited importer modules plus the importer-refusal
assertions, so neither module now names an AWS/Amazon endpoint without being on the gated
list, and both still refuse with credentials while the gate is off.

## Incident, disclosed

While producing pre-fix evidence I ran
`git checkout autonomy-lane-amazon-pre -- <two importer paths>` while fix 2 was still
**uncommitted**, which discarded it. The fix was re-applied, re-tested and committed;
nothing else was affected because every `git checkout` was path-scoped to this lane's two
files. Cost: one re-apply. Lesson taken: commit before a `git checkout` of your own paths,
or take a file copy first (which is what fixes 2 and 3's evidence runs used).

## Not fixed here (out of this lane's scope, still open in the egress map)

The transport-level hook (`tools/egress_guard.py`), `design_studio_async` callback
validation, `dataforseo_adapter` (already fixed in `96b5d83c`), `rapidapi_router:340`,
`adapters/base.py` `follow_redirects=True`, the `amzn.eu` gap in
`bright_data_client._amazon_refusal`, and the Amazon-CDN image fetches in
`lions_mane_pull.py:495` / `run_vision_sb.py:63`.
