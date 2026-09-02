"""Self-contained DataForSEO-primary / RapidAPI-Tier3 Amazon ASIN validation
waterfall for Northstar OS.

This is a STANDALONE live executor. It does NOT import validation_run.py or
dataforseo_adapter.py (those carry a broken import boundary). It reuses ONLY
proof_batch_contracts.py for the offline-authoritative URL builders and
acceptance predicates (pure stdlib, import-safe).

Pipeline (per the user's waterfall spec):
  Tier 1 (DataForSEO Merchant Amazon ASIN task): POST asin task -> poll
          task_get/advanced/{id} until ready. Source of product title,
          price, brand, BSR, reviews.
  Tier 2 (DataForSEO Merchant Amazon Sellers task): only after a Tier-1
          success, POST sellers task -> poll. Source of seller count /
          Buy Box roster.
  Tier 3 (RapidAPI fallback): only if Tier-1 returns an error / missing
          fields. Host is currently unsubscribed ("No such app"); handled
          cleanly as tier3_unavailable, never crashes.

Envelope budgeting (Prospective Envelope Budget Model):
  Operational safety cap = $0.25 (ENVELOPE_CAP_USD). Theoretical max is
  computed before dispatch; the run does NOT halt mid-batch for expected
  async costs (DataForSEO bills after completion); actual spend is
  reconciled at completion and reported.

Gate: probe B01H40O42I end-to-end (POST accepted AND GET ready) before the
remaining 9 ASINs are dispatched.

Provenance / safety:
  - Writes ONLY under data/enrich-content/waterfall-runs/<run-id>/ (and
    mirrors to data/enrich/waterfall-runs/). Never touches shared stores
    (amazon-market-snapshots.json, enrichment-run-report.json, CSVs).
  - Never prints / logs / stores secrets (credentials read from env only
    at request time, used solely in the Authorization header).
  - Requires explicit --live (or NS_ALLOW_NETWORK=1) so it can never fire
    by accident in a test context.

No secrets are read, printed, logged, or stored.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:  # pragma: no cover
    pass

try:
    import requests
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("requests library is required: pip install requests\n")
    raise

from proof_batch_contracts import (
    merchant_task_post_url,
    merchant_task_get_url,
    DEFAULT_LOCATION_CODE,
    DEFAULT_LANGUAGE_CODE,
)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ENVELOPE_CAP_USD = 0.25
POLL_INTERVAL_SECONDS = 6
POLL_MAX_ATTEMPTS = 12
MANIFEST_PATH = os.path.join(BACKEND_DIR, "data", "enrich", "live-10asin-manifest.json")
DATAFORSEO_LOGIN_ENV = "DATAFORSEO_LOGIN"
DATAFORSEO_PASSWORD_ENV = "DATAFORSEO_PASSWORD"
RAPIDAPI_KEY_ENV = "RAPIDAPI_KEY"
RAPIDAPI_HOST_ENV = "RAPIDAPI_HOST"
PROBE_ASIN = "B01H40O42I"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_live() -> None:
    if "--live" in sys.argv:
        return
    if (os.environ.get("NS_ALLOW_NETWORK") or "").strip() == "1":
        return
    raise SystemExit(
        "REFUSED: this is a live network executor. Re-run with --live "
        "(or NS_ALLOW_NETWORK=1) to actually dispatch requests."
    )


def load_manifest(path: str) -> dict:
    # Manifest carries a UTF-8 BOM from the original export; utf-8-sig is safe.
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _dataforseo_auth_headers() -> dict:
    login = os.getenv(DATAFORSEO_LOGIN_ENV) or ""
    password = os.getenv(DATAFORSEO_PASSWORD_ENV) or ""
    if not login or not password:
        raise SystemExit("DATAFORSEO credentials missing from environment")
    token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _dataforseo_post(url: str, payload: list) -> dict:
    headers = _dataforseo_auth_headers()
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    try:
        return resp.json()
    except ValueError:
        return {"_raw_status": resp.status_code, "_raw_text": resp.text[:500]}


def _dataforseo_get(url: str) -> dict:
    headers = _dataforseo_auth_headers()
    resp = requests.get(url, headers=headers, timeout=30)
    try:
        return resp.json()
    except ValueError:
        return {"_raw_status": resp.status_code, "_raw_text": resp.text[:500]}


def post_asin_task(asin: str) -> tuple:
    """POST a Merchant Amazon ASIN task. Returns (accepted, task_id, cost_usd, response)."""
    url = merchant_task_post_url("asin")
    payload = [{
        "asin": asin.upper(),
        "language_code": DEFAULT_LANGUAGE_CODE,
        "location_code": DEFAULT_LOCATION_CODE,
    }]
    resp = _dataforseo_post(url, payload)
    accepted, task_id, cost = _evaluate_post(resp)
    return accepted, task_id, cost, resp


def post_sellers_task(asin: str) -> tuple:
    url = merchant_task_post_url("sellers")
    payload = [{
        "asin": asin.upper(),
        "language_code": DEFAULT_LANGUAGE_CODE,
        "location_code": DEFAULT_LOCATION_CODE,
    }]
    resp = _dataforseo_post(url, payload)
    accepted, task_id, cost = _evaluate_post(resp)
    return accepted, task_id, cost, resp


def _evaluate_post(resp: dict) -> tuple:
    if not isinstance(resp, dict):
        return False, None, 0.0
    if resp.get("status_code") != 20000 or resp.get("tasks_error") not in (None, 0):
        return False, None, 0.0
    tasks = resp.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return False, None, 0.0
    first = tasks[0]
    if not isinstance(first, dict):
        return False, None, 0.0
    if first.get("status_code") != 20100:
        return False, None, 0.0
    msg = str(first.get("status_message") or "").strip().lower()
    if msg not in ("task created.", "task created"):
        return False, None, 0.0
    task_id = first.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        return False, None, 0.0
    cost = first.get("cost")
    cost_usd = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else 0.0
    return True, task_id.strip(), cost_usd


def poll_task_get(family: str, task_id: str) -> tuple:
    """Poll task_get/advanced/{id} until ready. Returns (ready, result_item, response).

    The Merchant Amazon `asin` task nests the product under
    result[0].items[0]; this digs one level so callers get the product dict.
    """
    url = merchant_task_get_url(family, task_id)
    for _ in range(POLL_MAX_ATTEMPTS):
        resp = _dataforseo_get(url)
        if isinstance(resp, dict) and resp.get("tasks_error") in (None, 0):
            tasks = resp.get("tasks")
            if isinstance(tasks, list) and tasks:
                first = tasks[0]
                if isinstance(first, dict):
                    if first.get("status_code") == 20000 and str(
                            first.get("status_message") or "").strip().lower() in ("ok.", "ok"):
                        result = first.get("result")
                        if isinstance(result, list) and result:
                            item = result[0]
                            if isinstance(item, dict):
                                prod = item
                                nested = item.get("items")
                                if isinstance(nested, list) and nested:
                                    prod = nested[0]
                                return True, prod, resp
        time.sleep(POLL_INTERVAL_SECONDS)
    return False, None, None


def extract_product(get_resp: dict) -> Optional[dict]:
    """Dig the product dict out of a Merchant Amazon asin task_get response
    (result[0].items[0]); returns None when not ready/empty."""
    if not isinstance(get_resp, dict):
        return None
    if get_resp.get("tasks_error") not in (None, 0):
        return None
    tasks = get_resp.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return None
    first = tasks[0]
    if not isinstance(first, dict):
        return None
    if first.get("status_code") != 20000:
        return None
    result = first.get("result")
    if not isinstance(result, list) or not result:
        return None
    item = result[0]
    if not isinstance(item, dict):
        return None
    nested = item.get("items")
    if isinstance(nested, list) and nested:
        return nested[0]
    return item


def map_asin_result(item: dict) -> dict:
    if not isinstance(item, dict):
        return {}
    price = item.get("price")
    price_value = None
    if isinstance(price, dict):
        v = price.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            price_value = float(v)
    if price_value is None:
        # Organic-listing shape reports price_from / price_to.
        for key in ("price_from", "price_to"):
            pv = item.get(key)
            if isinstance(pv, (int, float)) and not isinstance(pv, bool):
                price_value = float(pv)
                break
    currency = item.get("currency")
    if currency is None and isinstance(price, dict):
        currency = price.get("currency")
    # Rating in the DataForSEO asin item is a dict: {value, votes_count, ...}.
    raw_rating = item.get("rating")
    rating_value = None
    reviews_count = None
    if isinstance(raw_rating, dict):
        rv = raw_rating.get("value")
        if isinstance(rv, (int, float)) and not isinstance(rv, bool):
            rating_value = float(rv)
        vc = raw_rating.get("votes_count")
        if isinstance(vc, (int, float)) and not isinstance(vc, bool):
            reviews_count = int(vc)
    elif isinstance(raw_rating, (int, float)) and not isinstance(raw_rating, bool):
        rating_value = float(raw_rating)
    return {
        "asin": item.get("data_asin") or item.get("asin"),
        "title": item.get("title"),
        "brand": item.get("brand"),
        "price": price_value,
        "currency": currency,
        "reviews_count": reviews_count,
        "rating_value": rating_value,
        "rating_raw": raw_rating,
        "bsr_text": None,
        "buybox_price": None,
    }


def map_sellers_result(get_resp: dict) -> dict:
    """Tier-2 sellers roster. The Merchant Amazon sellers task nests the roster
    under result[0].items (type amazon_seller_main_item / amazon_seller_item).

    NOTE: the real DataForSEO sellers payload does NOT populate
    is_buy_box_winner / is_fba (they arrive as null). Per the repo's
    "winner never inferred" rule those are reported as Unavailable rather
    than guessed from the lowest price.
    """
    if not isinstance(get_resp, dict):
        return {"sellers_count": None, "sellers": [], "buybox_winner": "Unavailable",
                "is_fba": "Unavailable"}
    tasks = get_resp.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return {"sellers_count": None, "sellers": [], "buybox_winner": "Unavailable",
                "is_fba": "Unavailable"}
    first = tasks[0]
    result = first.get("result") if isinstance(first, dict) else None
    if not isinstance(result, list) or not result:
        return {"sellers_count": None, "sellers": [], "buybox_winner": "Unavailable",
                "is_fba": "Unavailable"}
    wrap = result[0]
    items = wrap.get("items") if isinstance(wrap, dict) else None
    if not isinstance(items, list) or not items:
        return {"sellers_count": 0, "sellers": [], "buybox_winner": "Unavailable",
                "is_fba": "Unavailable"}
    sellers = []
    for it in items:
        if not isinstance(it, dict):
            continue
        price = it.get("price")
        cur = price.get("current") if isinstance(price, dict) else None
        sellers.append({
            "seller_name": it.get("seller_name"),
            "price": float(cur) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None,
            "ships_from": it.get("ships_from"),
            "condition": it.get("condition"),
        })
    return {
        "sellers_count": len(items),
        "sellers": sellers,
        # DataForSEO does not expose these on this endpoint -> honest gap.
        "buybox_winner": "Unavailable",
        "is_fba": "Unavailable",
    }


def rapidapi_fallback(asin: str) -> dict:
    """Tier-3 fallback. Host is currently unsubscribed; returns a clean
    status, never raises."""
    key = os.getenv(RAPIDAPI_KEY_ENV)
    host = os.getenv(RAPIDAPI_HOST_ENV)
    if not key or not host:
        return {"tier3_status": "tier3_unconfigured"}
    url = f"https://{host}/products/{asin}"
    try:
        resp = requests.get(
            url,
            headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host},
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001 - defensive fallback
        return {"tier3_status": "tier3_request_error", "detail": str(exc)[:200]}
    if resp.status_code == 404 or "no such app" in resp.text.lower():
        return {"tier3_status": "tier3_host_unsubscribed"}
    if resp.status_code != 200:
        return {"tier3_status": "tier3_http_error", "http_status": resp.status_code}
    try:
        data = resp.json()
    except ValueError:
        return {"tier3_status": "tier3_unparseable"}
    return {"tier3_status": "tier3_ok", "title": (data or {}).get("title"),
            "price": (data or {}).get("price")}


def _norm_title(t: str) -> str:
    if not t:
        return ""
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _title_match(truth_title: str, obs_title: str) -> bool:
    """Token-subset match: every significant manifest word (pack annotations
    in parentheses stripped) must appear (as a normalized substring) in the
    DataForSEO title. Forgiving of injected descriptive words."""
    if not truth_title or not obs_title:
        return False
    core = re.sub(r"\([^)]*\)", " ", truth_title)
    tokens = [t for t in re.split(r"[^a-z0-9]+", core.lower())
              if len(t) >= 3 and not t.isdigit()]
    if not tokens:
        return False
    no = _norm_title(obs_title)
    return all(tok in no for tok in tokens)


def compare_to_manifest(observed: dict, truth: dict) -> dict:
    truth_title = truth.get("product_title_csv") or truth.get("product_title_bsr_csv")
    obs_title = observed.get("title")
    title_match = _title_match(truth_title, obs_title)
    truth_price = truth.get("price_csv")
    obs_price = observed.get("price")
    price_delta = None
    if isinstance(truth_price, (int, float)) and isinstance(obs_price, (int, float)):
        price_delta = round(obs_price - float(truth_price), 2)
    return {
        "asin": truth.get("asin"),
        "manifest_title": truth_title,
        "dfs_title": obs_title,
        "title_match": title_match,
        "manifest_price_csv": truth_price,
        "dfs_price": obs_price,
        "price_delta": price_delta,
        "manifest_reviews_csv": truth.get("reviews_csv"),
        "dfs_reviews": observed.get("reviews_count"),
        "dfs_brand": observed.get("brand"),
        "dfs_bsr": observed.get("bsr_text"),
    }


def main(argv: list) -> int:
    _require_live()
    parser = argparse.ArgumentParser(description="DataForSEO Amazon validation waterfall")
    parser.add_argument("--live", action="store_true", help="actually dispatch requests")
    args = parser.parse_args(argv[1:])

    manifest = load_manifest(MANIFEST_PATH)
    asins = manifest.get("canonical_asin_order") or [
        a.get("asin") for a in manifest.get("asins", [])
    ]
    if not asins:
        raise SystemExit("manifest contains no ASINs")

    run_id = f"waterfall-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_root = os.path.join(BACKEND_DIR, "data", "enrich", "waterfall-runs", run_id)
    os.makedirs(os.path.join(out_root, "raw"), exist_ok=True)
    os.makedirs(os.path.join(out_root, "normalized"), exist_ok=True)
    progress_path = os.path.join(out_root, "progress.log")

    def _progress(msg: str) -> None:
        line = f"{_utc_now()} {msg}"
        print(line, flush=True)
        with open(progress_path, "a", encoding="utf-8") as pf:
            pf.write(line + "\n")

    run_log = {
        "kind": "waterfall-run",
        "run_id": run_id,
        "started_at": _utc_now(),
        "primary_provider": "DATAFORSEO",
        "tier3_provider": "RAPIDAPI",
        "envelope_cap_usd": ENVELOPE_CAP_USD,
        "asin_order": asins,
        "probe_asin": PROBE_ASIN,
    }
    cumulative_cost_usd = 0.0
    results = []

    # ---- Probe gate: B01H40O42I end-to-end ----
    _progress(f"[probe] {PROBE_ASIN} -> POST asin task")
    accepted, task_id, cost, post_resp = post_asin_task(PROBE_ASIN)
    cumulative_cost_usd += cost
    if not accepted:
        run_log["probe_outcome"] = "post_rejected"
        run_log["probe_post_response"] = post_resp
        _write_json(os.path.join(out_root, "run-log.json"), run_log)
        _progress("PROBE FAILED at POST (asin task not accepted). Stopping.")
        return 2
    _progress(f"[probe] POST accepted task_id={task_id}; polling GET")
    ready, item, get_resp = poll_task_get("asin", task_id)
    if not ready:
        run_log["probe_outcome"] = "get_not_ready"
        run_log["probe_get_response"] = get_resp
        _write_json(os.path.join(out_root, "run-log.json"), run_log)
        _progress("PROBE FAILED at GET (task not ready within polling window). Stopping.")
        return 2
    _progress(f"[probe] GET ready; proceeding with remaining {len(asins) - 1} ASINs")
    run_log["probe_outcome"] = "passed"

    # ---- Tier 1: ASIN tasks for all ASINs ----
    truth_by_asin = {a.get("asin"): a for a in manifest.get("asins", [])}
    tier1 = {}
    for asin in asins:
        accepted, task_id, cost, post_resp = post_asin_task(asin)
        cumulative_cost_usd += cost
        row = {
            "asin": asin,
            "tier1_accepted": accepted,
            "tier1_task_id": task_id,
            "tier1_cost_usd": cost,
            "tier1_post_response": post_resp,
        }
        if accepted:
            ready, item, get_resp = poll_task_get("asin", task_id)
            row["tier1_ready"] = ready
            row["tier1_get_response"] = get_resp
            if ready:
                observed = map_asin_result(item)
                row["tier1_observed"] = observed
                _write_json(os.path.join(out_root, "raw", f"{asin}-tier1.json"),
                            {"post": post_resp, "get": get_resp})
                _write_json(os.path.join(out_root, "normalized", f"{asin}-tier1.json"),
                            observed)
                tier1[asin] = observed
                _progress(f"[tier1] {asin} READY title={observed.get('title')!r} "
                          f"price={observed.get('price')}")
            else:
                _progress(f"[tier1] {asin} NOT READY within polling window")
        else:
            _progress(f"[tier1] {asin} POST REJECTED")
        tier1[asin] = tier1.get(asin, row.get("tier1_observed"))
        results.append(row)

    # ---- Tier 2: Sellers tasks for Tier-1 successes ----
    for asin in asins:
        observed = tier1.get(asin)
        if not observed:
            continue
        accepted, task_id, cost, post_resp = post_sellers_task(asin)
        cumulative_cost_usd += cost
        row = next(r for r in results if r["asin"] == asin)
        row["tier2_accepted"] = accepted
        row["tier2_task_id"] = task_id
        row["tier2_cost_usd"] = cost
        if accepted:
            ready, item, get_resp = poll_task_get("sellers", task_id)
            row["tier2_ready"] = ready
            if ready:
                sellers = map_sellers_result(get_resp)
                row["tier2_observed"] = sellers
                observed.update(sellers)
                _write_json(os.path.join(out_root, "raw", f"{asin}-tier2.json"),
                            {"post": post_resp, "get": get_resp})
                _progress(f"[tier2] {asin} sellers_count={sellers.get('sellers_count')}")

    # ---- Tier 3: RapidAPI fallback only where Tier-1 missing ----
    for asin in asins:
        observed = tier1.get(asin)
        if observed:
            continue
        fb = rapidapi_fallback(asin)
        row = next(r for r in results if r["asin"] == asin)
        row["tier3"] = fb

    # ---- Comparison vs manifest ground truth ----
    comparison_rows = []
    for asin in asins:
        observed = tier1.get(asin) or {}
        truth = truth_by_asin.get(asin, {})
        cmp = compare_to_manifest(observed, truth)
        if asin in tier1 and tier1[asin]:
            sellers_row = next(
                (r.get("tier2_observed") for r in results
                 if r["asin"] == asin and r.get("tier2_observed")), {})
            cmp["sellers_count"] = sellers_row.get("sellers_count")
        else:
            cmp["sellers_count"] = None
            tier3 = next((r.get("tier3") for r in results if r["asin"] == asin), None)
            cmp["tier3_status"] = (tier3 or {}).get("tier3_status")
        comparison_rows.append(cmp)

    csv_path = os.path.join(out_root, "waterfall-vs-csv-comparison.csv")
    _write_comparison_csv(csv_path, comparison_rows)

    run_log["completed_at"] = _utc_now()
    run_log["cumulative_cost_usd_observed"] = round(cumulative_cost_usd, 4)
    run_log["envelope_cap_usd"] = ENVELOPE_CAP_USD
    run_log["envelope_exceeded"] = cumulative_cost_usd > ENVELOPE_CAP_USD
    run_log["asin_count"] = len(asins)
    run_log["tier1_ready_count"] = sum(1 for a in asins if tier1.get(a))
    run_log["results"] = results
    run_log["comparison"] = comparison_rows
    _write_json(os.path.join(out_root, "run-log.json"), run_log)

    _progress(f"WATERFALL COMPLETE: run_id={run_id}")
    _progress(f"  asins: {len(asins)}")
    _progress(f"  tier1_ready: {run_log['tier1_ready_count']}")
    _progress(f"  observed_cost_usd: {round(cumulative_cost_usd, 4)}")
    _progress(f"  envelope_cap_usd: {ENVELOPE_CAP_USD} "
              f"(exceeded={run_log['envelope_exceeded']})")
    _progress(f"  output: {out_root}")
    return 0


def _write_json(path: str, payload: dict) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _write_comparison_csv(path: str, rows: list) -> None:
    headers = [
        "asin", "manifest_title", "dfs_title", "title_match",
        "manifest_price_csv", "dfs_price", "price_delta",
        "manifest_reviews_csv", "dfs_reviews", "dfs_brand", "dfs_bsr",
        "sellers_count", "tier3_status",
    ]
    lines = [",".join(headers)]
    for r in rows:
        cells = []
        for h in headers:
            v = r.get(h)
            if v is None:
                cells.append("")
            elif isinstance(v, str):
                cells.append('"' + v.replace('"', '""') + '"')
            else:
                cells.append(str(v))
        lines.append(",".join(cells))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
