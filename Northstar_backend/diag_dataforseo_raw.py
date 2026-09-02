"""Diagnostic: inspect RAW DataForSEO asin+sellers response shape for ONE ASIN.

Approved follow-up to the last run. Makes exactly 1 ASIN's two tasks (asin +
sellers), prints the raw structure (keys + truncated values) so we can see
whether price_from / Best Sellers Rank / buybox keys exist under different
names. Never prints credentials. Cost accounted separately from the 20-ASIN
enrichment cap (this is a diagnostic probe, not the enrichment batch).
"""

import json
import time

import requests
from dotenv import load_dotenv

from dataforseo_adapter import _auth, merchant_task_post_url, merchant_task_get_url

load_dotenv()

ASIN = "B00AQ0LMTC"  # top shortlist ASIN
TIMEOUT = 60
MAX_POLL = 120
POLL = 5


def _trunc(v, n=140):
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + "...<%d chars>" % len(v)
    if isinstance(v, (dict, list)):
        return "<%s len=%d>" % (type(v).__name__, len(v))
    return v


def post_task(family):
    url = merchant_task_post_url(family)
    payload = [{"asin": ASIN, "location_code": 2840, "language_code": "en_US"}]
    resp = requests.post(url, json=payload, auth=_auth(), timeout=TIMEOUT)
    return resp.status_code, resp.json()


def get_task(family, task_id):
    url = merchant_task_get_url(family, task_id)
    deadline = time.monotonic() + MAX_POLL
    last = None
    while time.monotonic() < deadline:
        resp = requests.get(url, auth=_auth(), timeout=TIMEOUT)
        try:
            body = resp.json()
        except ValueError:
            return last
        tasks = body.get("tasks") if isinstance(body, dict) else None
        if isinstance(tasks, list) and tasks and isinstance(tasks[0], dict):
            first = tasks[0]
            st = first.get("status_code")
            if st == 20000 and first.get("result"):
                return first
            if st in (40602, 20100):  # "Task In Queue" / "Created" -> keep polling
                last = first
                time.sleep(POLL)
                continue
            return first  # terminal (rejection or unexpected)
        time.sleep(POLL)
    return last


def show_item(item, label):
    print("\n--- RAW %s result item keys ---" % label)
    if not isinstance(item, dict):
        print("  (not a dict): %r" % _trunc(item))
        return
    for k, v in item.items():
        print("  %-28s %s" % (k, _trunc(v)))
    # product_information detail (BSR lives here per adapter assumption)
    pi = item.get("product_information")
    if isinstance(pi, list):
        print("\n  product_information[] (%d sections):" % len(pi))
        for sec in pi:
            if isinstance(sec, dict):
                print("    section keys:", list(sec.keys()))
                body = sec.get("body")
                if isinstance(body, dict):
                    for bk, bv in body.items():
                        print("      body.%s = %s" % (bk, _trunc(bv, 200)))
    elif isinstance(pi, dict):
        print("  product_information is dict; keys:", list(pi.keys()))


def main():
    print("Diagnostic ASIN: %s" % ASIN)
    for family in ("asin", "sellers"):
        print("\n===== FAMILY: %s =====" % family)
        code, body = post_task(family)
        print("POST status_code: %s" % code)
        print("POST top-level keys: %s" % (list(body.keys()) if isinstance(body, dict) else type(body)))
        tasks = body.get("tasks") if isinstance(body, dict) else None
        if not (isinstance(tasks, list) and tasks and isinstance(tasks[0], dict)):
            print("  POST did not return a task; body head: %s" % _trunc(json.dumps(body)[:400]))
            continue
        t0 = tasks[0]
        print("POST task status_code=%s msg=%s id=%s cost=%s"
              % (t0.get("status_code"), t0.get("status_message"),
                 t0.get("id"), t0.get("cost")))
        if t0.get("status_code") != 20100:
            print("  task NOT accepted; stopping this family.")
            continue
        got = get_task(family, t0["id"])
        if got is None:
            print("  GET: no result within poll window.")
            continue
        res = got.get("result")
        if isinstance(res, list) and res:
            show_item(res[0], family)
            # dig one level deeper: real data lives in items[0]
            inner = res[0].get("items") if isinstance(res[0], dict) else None
            if isinstance(inner, list) and inner:
                show_item(inner[0], "%s.inner[0]" % family)
                if family == "sellers" and len(inner) > 1:
                    print("  (sellers inner list has %d total; showing first)" % len(inner))
            elif family == "sellers" and len(res) > 1:
                print("  (sellers list has %d total; showing first)" % len(res))
        else:
            print("  GET result empty/not-list: %s" % _trunc(json.dumps(got)[:300]))


if __name__ == "__main__":
    main()
