"""Production-owned manifest-selection live enrichment runner.

This runner enriches EXACTLY the ASINs listed in an approved manifest. It
never falls back to scanner-cache ordering and selects its live client via
``--provider`` (rapidapi | dataforseo; default rapidapi). Easyparser is
DEPRECATED and DISABLED and degrades to the offline placeholder.

Live controls mirror ``enrich_cached_asins``: an explicit ``--live`` flag
plus finite ``--max-requests`` / ``--max-credits`` caps checked BEFORE every
call. Automatic retry is structurally impossible: there is no ``--retries``
flag and the loop never invokes the client twice for the same ASIN.

Every run writes ONLY to a unique immutable directory under
``data/enrich/manifest-runs/<run-id>/`` and appends one audit line to
``data/enrich/manifest-runs/run-index.jsonl``. It never writes to the
shared snapshot store (``amazon-market-snapshots.json``) or the single-slot
``enrichment-run-report.json``.

Exit codes:
  0  success (including runs containing unavailable / skipped ASINs)
  2  usage / live-gate refusal
  3  run-directory collision or write failure (prior artifacts preserved)
  4  manifest rejected (before any network path is reachable)
  5  hard stop: secret-like output detected in a provider response
"""

import argparse
import csv
import hashlib
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone

import market_snapshot_store as store
import rapidapi_client
import dataforseo_adapter
from enrich_cached_asins import ESTIMATED_CREDITS_PER_ASIN


def _fetch_offers(asin, provider):
    """Dispatch the live client by provider (Easyparser disabled)."""
    if provider == "dataforseo":
        return dataforseo_adapter.get_dataforseo_offers(asin)
    if provider == "easyparser":
        # Deprecated/disabled: never call the network.
        return {
            "source": "easyparser",
            "asin": asin,
            "data_status": "unavailable",
            "offer_data_status": "provider_error",
            "offer_data_note": "Easyparser deprecated/disabled",
            "offers": [],
            "credits_used": 0,
            "credits_remaining": None,
        }
    return rapidapi_client.get_rapidapi_offers(asin)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

APPROVED_ASINS = frozenset(
    [
        "B01H40O42I",
        "B08R2SRN88",
        "B0CP6LXPLK",
        "B00BISGJXA",
        "B00BH3HPZW",
        "B00GYZWNY6",
        "B0045XGE9E",
        "B002L4M4M0",
        "B081THWMDK",
        "B085F1QCB9",
    ]
)

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
REQUIRED_FIELDS = [
    "product_title_csv",
    "price_csv",
    "reviews_csv",
    "prime_fba_flag_csv",
    "bsr_text_csv",
]

SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|authorization|bearer|password|credential|private[_-]?key)"
)
LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")

BSR_LIVE_NOTE = "provider does not supply BSR"
REVIEWS_LIVE_LABEL = "Unknown"


# --------------------------------------------------------------------------- #
# Paths / IDs / atomic IO
# --------------------------------------------------------------------------- #
def _runs_base_dir():
    return os.path.join(BACKEND_DIR, "data", "enrich", "easyparser-runs")


def make_run_id():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "manifest-%s-%s" % (ts, secrets.token_hex(2))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path, payload):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = "%s.tmp" % path
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str, indent=2)
    with open(tmp, "r", encoding="utf-8") as f:
        json.load(f)
    os.replace(tmp, path)


def _append_run_index(run_id, run_dir, status, max_requests, max_credits,
                      requests_made, credits_used):
    base = _runs_base_dir()
    if not os.path.isdir(base):
        os.makedirs(base, exist_ok=True)
    line = {
        "run_id": run_id,
        "run_dir": run_dir,
        "status": status,
        "appended_at": _now_iso(),
        "max_requests": max_requests,
        "max_credits": max_credits,
        "requests_made": requests_made,
        "credits_used": round(float(credits_used), 1),
    }
    index_path = os.path.join(base, "run-index.jsonl")
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, default=str) + "\n")


# --------------------------------------------------------------------------- #
# Manifest validation (runs BEFORE any client call)
# --------------------------------------------------------------------------- #
def load_and_validate_manifest(path):
    """Return (manifest_dict, None) or (None, error_string)."""
    if not os.path.exists(path):
        return None, "manifest file not found: %s" % path
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            m = json.load(f)
    except Exception as e:  # surface any parse failure verbatim
        return None, "malformed JSON: %s" % e
    if not isinstance(m, dict):
        return None, "manifest must be a JSON object"
    if m.get("kind") != "live-10asin-manifest":
        return None, "manifest kind mismatch (expected 'live-10asin-manifest', got %r)" % (
            m.get("kind"),)
    order = m.get("canonical_asin_order")
    if not isinstance(order, list) or not order:
        return None, "missing or invalid canonical_asin_order"
    asins = m.get("asins")
    if not isinstance(asins, list) or not asins:
        return None, "missing or invalid asins array"

    if len(order) != 10:
        return None, "ASIN count violates the 10-ASIN hard limit (got %d)" % len(order)
    seen = set()
    for a in order:
        if not isinstance(a, str) or not ASIN_PATTERN.fullmatch(a):
            return None, "invalid ASIN in canonical_asin_order: %r" % (a,)
        if a not in APPROVED_ASINS:
            return None, (
                "ASIN %s in canonical_asin_order is outside the "
                "approved 10-ASIN set" % a
            )
        if a in seen:
            return None, "duplicate ASIN in canonical_asin_order: %s" % a
        seen.add(a)

    records = {}
    for rec in asins:
        if not isinstance(rec, dict):
            return None, "asins entry must be an object"
        a = rec.get("asin")
        if not isinstance(a, str) or not ASIN_PATTERN.fullmatch(a):
            return None, "invalid ASIN in asins array: %r" % (a,)
        if a in records:
            return None, "duplicate ASIN in asins array: %s" % a
        for field in REQUIRED_FIELDS:
            if field not in rec:
                return None, "ASIN %s missing required field: %s" % (a, field)
        records[a] = rec

    for a in order:
        if a not in records:
            return None, "canonical_asin_order ASIN has no record: %s" % a
    for a in records:
        if a not in APPROVED_ASINS:
            return None, "ASIN outside the approved 10-ASIN set: %s" % a
        if a not in seen:
            return None, "asins-array ASIN missing from canonical_asin_order: %s" % a
    return m, None


# --------------------------------------------------------------------------- #
# Secret-like detection
# --------------------------------------------------------------------------- #
def _contains_secret(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and SECRET_KEY_RE.search(k):
                return True
            if _contains_secret(v):
                return True
    elif isinstance(obj, list):
        for v in obj:
            if _contains_secret(v):
                return True
    elif isinstance(obj, str):
        if len(obj) >= 32 and LONG_TOKEN_RE.fullmatch(obj):
            return True
    return False


# --------------------------------------------------------------------------- #
# Comparison helpers
# --------------------------------------------------------------------------- #
def _norm_title(t):
    if not isinstance(t, str):
        return set()
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return set(w for w in t.split() if w)


def _title_similarity(csv_t, live_t):
    if not isinstance(live_t, str) or not live_t.strip():
        return "Unrelated"
    a = _norm_title(csv_t)
    b = _norm_title(live_t)
    if not b:
        return "Unrelated"
    if a == b:
        return "Exact/near-exact"
    union = len(a | b)
    if union == 0:
        return "Unrelated"
    j = float(len(a & b)) / union
    if j >= 0.9:
        return "Exact/near-exact"
    if j >= 0.6:
        return "Minor cosmetic difference"
    if j >= 0.3:
        return "Potentially conflicting"
    return "Unrelated"


def _live_prime_flag(result):
    if not isinstance(result, dict):
        return "Unknown"
    if result.get("buy_box_is_prime") is True:
        return "Prime"
    if result.get("buy_box_is_fba") is True:
        return "FBA"
    if result.get("buy_box_is_fbm") is True:
        return "FBM"
    for o in (result.get("offers") or []):
        if not isinstance(o, dict):
            continue
        if o.get("is_prime") is True:
            return "Prime"
        if o.get("is_fba") is True:
            return "FBA"
        if o.get("is_fbm") is True:
            return "FBM"
    return "Unknown"


def _row_prime_match(row):
    csv_prime = str(row.get("prime_fba_flag_csv") or "").strip().lower().startswith("yes")
    live_prime = row.get("prime_fba_flag_live") == "Prime"
    return csv_prime == live_prime


def _classify_outcome(snap):
    status = snap.get("data_status") if isinstance(snap, dict) else None
    if status == store.DATA_STATUS_AVAILABLE:
        return "available"
    if status == store.DATA_STATUS_PARTIAL:
        return "partial"
    return "unavailable"


def _build_comparison_rows(manifest, live_results, outcomes):
    """One row per manifest ASIN, including skipped_cap rows. Never drops a row."""
    records = {r["asin"]: r for r in manifest["asins"]}
    rows = []
    for asin in manifest["canonical_asin_order"]:
        rec = records[asin]
        result = live_results.get(asin)
        outcome = outcomes.get(asin, "skipped_cap")
        csv_title = rec.get("product_title_csv")
        live_title = result.get("title") if isinstance(result, dict) else None
        price_csv = rec.get("price_csv")
        price_live = result.get("buy_box_price") if isinstance(result, dict) else None
        price_delta_abs = None
        price_delta_pct = None
        if (isinstance(price_csv, (int, float)) and not isinstance(price_csv, bool)
                and isinstance(price_live, (int, float)) and not isinstance(price_live, bool)
                and price_csv != 0):
            price_delta_abs = round(price_live - price_csv, 4)
            price_delta_pct = round((price_live - price_csv) / price_csv, 4)
        live_flag = _live_prime_flag(result)
        sim = _title_similarity(csv_title, live_title)
        notes = "BSR not observed live; provider does not supply BSR."
        if outcome == "skipped_cap":
            notes = "No provider call made (request/credit cap reached); nothing compared."
        elif not _row_prime_match({
            "prime_fba_flag_csv": rec.get("prime_fba_flag_csv"),
            "prime_fba_flag_live": live_flag,
        }):
            notes += " Prime/FBA flag mismatch vs CSV."
        rows.append({
            "asin": asin,
            "product_title_csv": csv_title,
            "product_title_live": live_title,
            "price_csv": price_csv,
            "price_live": price_live,
            "price_delta_abs": price_delta_abs,
            "price_delta_pct": price_delta_pct,
            "reviews_csv": rec.get("reviews_csv"),
            "reviews_live": REVIEWS_LIVE_LABEL,
            "prime_fba_flag_csv": rec.get("prime_fba_flag_csv"),
            "prime_fba_flag_live": live_flag,
            "bsr_text_csv": rec.get("bsr_text_csv"),
            "bsr_live_note": BSR_LIVE_NOTE,
            "title_similarity": sim,
            "outcome": outcome,
            "notes": notes,
        })
    return rows


COMPARISON_COLUMNS = [
    "asin", "product_title_csv", "product_title_live", "price_csv", "price_live",
    "price_delta_abs", "price_delta_pct", "reviews_csv", "reviews_live",
    "prime_fba_flag_csv", "prime_fba_flag_live", "bsr_text_csv", "bsr_live_note",
    "title_similarity", "outcome", "notes",
]


def _write_comparison_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COMPARISON_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COMPARISON_COLUMNS})


def _judgment(row):
    if row["outcome"] == "skipped_cap":
        return "Skipped - request/credit cap reached before this ASIN; no comparison possible."
    if row["outcome"] == "unavailable":
        return "Suspect mapping / provider limitation - needs manual review"
    dp = row["price_delta_pct"]
    sim = row["title_similarity"]
    if sim in ("Potentially conflicting", "Unrelated"):
        return "Suspect mapping / provider limitation - needs manual review"
    if not isinstance(dp, (int, float)):
        return "Suspect mapping / provider limitation - needs manual review"
    adp = abs(dp)
    if adp > 0.10:
        return "Suspect mapping / provider limitation - needs manual review"
    if adp <= 0.05 and sim == "Exact/near-exact" and _row_prime_match(row):
        return "Good match"
    return "Drift only - normal variability"


def _write_summary_md(path, ctx, rows):
    provider = ctx.get("provider", "rapidapi")
    L = []
    L.append("# Manifest run summary")
    L.append("")
    L.append("- run-id: %s" % ctx["run_id"])
    L.append("- generated_at_utc: %s" % ctx["generated_at"])
    L.append("- provider: %s" % provider)
    L.append("- max-requests: %d | actual requests made: %d" % (
        ctx["max_requests"], ctx["requests_made"]))
    estimated = float(ctx["credits_used"]) - float(ctx["credits_reported"])
    L.append("- max-credits: %d | credits used: %.1f (reported=%d, estimated=%.1f)" % (
        ctx["max_credits"], float(ctx["credits_used"]),
        ctx["credits_reported"], estimated))
    L.append("- stop_reason: %s" % (ctx["stop_reason"] or "none (all planned ASINs processed)"))
    L.append("- provider warnings: %s" % (
        "; ".join(ctx["provider_warnings"]) if ctx["provider_warnings"] else "none"))
    L.append("")
    L.append("Disclosure: actual credits used may exceed the stated --max-credits cap "
             "by up to one ASIN's cost, because the cap is checked before each call, "
             "not continuously during it.")
    L.append("")

    within5 = [r for r in rows if isinstance(r["price_delta_pct"], (int, float))
               and abs(r["price_delta_pct"]) <= 0.05]
    priced = [r for r in rows if isinstance(r["price_delta_pct"], (int, float))]
    prime_exact = [r for r in rows if r["outcome"] in ("available", "partial")
                   and _row_prime_match(r)]
    title_exact = [r for r in rows if r["title_similarity"] == "Exact/near-exact"]
    unavail = [r for r in rows if r["outcome"] == "unavailable"]
    skipped = [r for r in rows if r["outcome"] == "skipped_cap"]

    L.append("## Aggregate metrics")
    L.append("")
    L.append("- Price delta within +/-5%%: %d of %d rows with comparable prices" % (
        len(within5), len(priced)))
    L.append("- Prime/FBA flag exact match (invoked rows): %d" % len(prime_exact))
    L.append('- Title similarity "Exact/near-exact": %d' % len(title_exact))
    L.append("- Failed/unavailable: %d | skipped_cap: %d" % (len(unavail), len(skipped)))
    L.append("")

    L.append("## Flagged ASINs (major delta / Prime mismatch / conflicting title)")
    L.append("")
    flagged = []
    for r in rows:
        reasons = []
        dp = r["price_delta_pct"]
        if isinstance(dp, (int, float)) and abs(dp) > 0.10:
            reasons.append("major price delta (%.1f%%)" % (dp * 100))
        if r["outcome"] in ("available", "partial") and not _row_prime_match(r):
            reasons.append("Prime/FBA flag mismatch (csv=%s live=%s)" % (
                r["prime_fba_flag_csv"], r["prime_fba_flag_live"]))
        if r["outcome"] != "skipped_cap" and r["title_similarity"] in (
                "Potentially conflicting", "Unrelated"):
            reasons.append("title similarity: %s" % r["title_similarity"])
        if r["outcome"] == "unavailable":
            reasons.append("no usable provider data")
        if reasons:
            flagged.append((r["asin"], reasons))
    if flagged:
        for asin, reasons in flagged:
            L.append("- %s: %s" % (asin, "; ".join(reasons)))
    else:
        L.append("- none")
    L.append("")

    L.append("## Per-ASIN judgment")
    L.append("")
    L.append("| asin | outcome | title_similarity | price_delta_pct | prime csv/live | judgment |")
    L.append("|---|---|---|---|---|---|")
    for r in rows:
        dp = r["price_delta_pct"]
        dp_txt = ("%+.1f%%" % (dp * 100)) if isinstance(dp, (int, float)) else "n/a"
        L.append("| %s | %s | %s | %s | %s / %s | %s |" % (
            r["asin"], r["outcome"], r["title_similarity"], dp_txt,
            r["prime_fba_flag_csv"], r["prime_fba_flag_live"], _judgment(r)))
    L.append("")
    L.append("Reviews: the selected provider does not supply review counts; reviews_live is "
             "Unknown for every row. " + BSR_LIVE_NOTE.capitalize() + ".")
    L.append("")
    L.append("No ASIN in this run is purchase-authorized by this comparison alone.")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #
def _run_status(args):
    m, err = load_and_validate_manifest(args.manifest)
    if err:
        print("status: REJECTED - %s" % err)
        return 4
    order = m["canonical_asin_order"]
    print("status: ACCEPTED")
    print("manifest: %s" % args.manifest)
    print("asins (%d): %s" % (len(order), ", ".join(order)))
    key_resolves = _provider_key_resolves(args.provider)
    print("provider: %s" % args.provider)
    print("provider config resolves: %s" % ("YES" if key_resolves else "NO"))
    print("Easyparser is deprecated/disabled")
    print("network calls made by status: 0")
    return 0


def _run_dry_run(args):
    m, err = load_and_validate_manifest(args.manifest)
    if err:
        print("dry-run: REJECTED - %s" % err)
        return 4
    order = m["canonical_asin_order"]
    rid = make_run_id()
    print("dry-run: ACCEPTED (zero writes, zero network)")
    print("planned asins (%d), in execution order:" % len(order))
    for i, a in enumerate(order, 1):
        print("  %2d. %s" % (i, a))
    print("would create run-id: %s" % rid)
    print("would create dir:    %s" % os.path.join(_runs_base_dir(), rid))
    print("exact live command:")
    print("  python enrich_manifest_run.py run --live --provider %s --manifest %s "
          "--max-requests 10 --max-credits <CAP>" % (args.provider, args.manifest))
    return 0


def _provider_key_resolves(provider):
    if provider == "dataforseo":
        from dataforseo_adapter import DATAFORSEO_ENABLED
        return bool(DATAFORSEO_ENABLED) and bool(os.getenv("DATAFORSEO_LOGIN")) \
            and bool(os.getenv("DATAFORSEO_PASSWORD"))
    return bool(os.getenv("RAPIDAPI_API_KEY"))


def _run(args):
    if not args.live:
        print("error: --live is required for the run subcommand; refusing before any provider call")
        return 2
    if args.max_requests is None or args.max_requests < 1:
        print("error: --max-requests <positive int> is required")
        return 2
    if args.max_credits is None or args.max_credits < 1:
        print("error: --max-credits <positive int> is required")
        return 2

    m, err = load_and_validate_manifest(args.manifest)
    if err:
        print("error: manifest rejected: %s" % err)
        return 4

    with open(args.manifest, "rb") as f:
        frozen_sha = hashlib.sha256(f.read()).hexdigest()

    run_id = make_run_id()
    run_dir = os.path.join(_runs_base_dir(), run_id)
    if os.path.exists(run_dir):
        print("error: run directory already exists; refusing to overwrite: %s" % run_dir)
        return 3
    try:
        os.makedirs(os.path.join(run_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "normalized"), exist_ok=True)
    except OSError as e:
        print("error: could not create run directory: %s" % e)
        return 3

    order = m["canonical_asin_order"]
    caps = {"max_requests": args.max_requests, "max_credits": args.max_credits}
    budget = {"requests_used": 0, "credits_used": 0.0, "credits_reported": 0}
    ledger = []
    live_results = {}
    outcomes = {}
    stop_reason = None
    provider_warnings = []

    _atomic_write(os.path.join(run_dir, "manifest.json"), m)
    _atomic_write(os.path.join(run_dir, "preflight.json"), {
        "kind": "manifest-run-preflight",
        "run_id": run_id,
        "generated_at": _now_iso(),
        "manifest_path": args.manifest,
        "frozen_manifest_sha256": frozen_sha,
        "caps": caps,
        "planned_asin_order": list(order),
        "provider": args.provider,
        "retries_supported": False,
    })

    halted = False
    for i, asin in enumerate(order):
        if budget["requests_used"] >= caps["max_requests"]:
            stop_reason = "max_requests"
            break
        if budget["credits_used"] >= caps["max_credits"]:
            stop_reason = "max_credits"
            break

        started = time.monotonic()
        result = _fetch_offers(asin, args.provider)
        budget["requests_used"] += 1
        used = result.get("credits_used")
        credit_kind = "reported"
        if isinstance(used, int) and not isinstance(used, bool) and used > 0:
            budget["credits_used"] += used
            budget["credits_reported"] += used
            credits_this_call = used
        else:
            budget["credits_used"] += ESTIMATED_CREDITS_PER_ASIN
            credit_kind = "estimated"
            credits_this_call = ESTIMATED_CREDITS_PER_ASIN
        finished = time.monotonic()

        if _contains_secret(result):
            halted = True
            _atomic_write(os.path.join(run_dir, "raw", "%s.json" % asin), {
                "_redacted": True,
                "reason": "secret-like output detected",
                "asin": asin,
            })
            ledger.append({
                "seq": len(ledger) + 1, "asin": asin,
                "started_at": _now_iso(), "finished_at": _now_iso(),
                "outcome": "halted_secret", "skipped": False,
                "credit_basis": credit_kind, "credits_this_call": credits_this_call,
                "credits_remaining": result.get("credits_remaining"),
                "request_id": result.get("request_id"),
                "duration_sec": round(finished - started, 3),
                "data_status_raw": None,
            })
            _atomic_write(os.path.join(run_dir, "failure-manifest.json"), {
                "kind": "easyparser-run-failure-manifest",
                "run_id": run_id,
                "generated_at": _now_iso(),
                "stage": "response_scan(%s)" % asin,
                "stop_reason": "secret_like_output_detected",
                "requests_made": budget["requests_used"],
                "credits_used": round(budget["credits_used"], 1),
                "scrubbed": "no secrets, no raw response bodies",
                "ledger_before_halt": ledger,
            })
            _append_run_index(run_id, run_dir, "halted_secret", caps["max_requests"],
                              caps["max_credits"], budget["requests_used"],
                              budget["credits_used"])
            print("HALT: secret-like output detected in response for %s; "
                  "remaining ASINs not processed; failure-manifest.json written" % asin)
            return 5

        _atomic_write(os.path.join(run_dir, "raw", "%s.json" % asin), result)
        try:
            snap = store.build_snapshot(asin, result, prior_attempts=0)
        except Exception as e:  # normalization must never kill the run
            provider_warnings.append("normalization fallback for %s: %s" % (asin, e))
            snap = {"asin": asin, "source": result.get("source") or "unknown",
                    "data_status": "unavailable",
                    "title": result.get("title")}
        _atomic_write(os.path.join(run_dir, "normalized", "%s.json" % asin), snap)
        outcome = _classify_outcome(snap)
        ledger.append({
            "seq": len(ledger) + 1,
            "asin": asin,
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "outcome": outcome,
            "skipped": False,
            "credit_basis": credit_kind,
            "credits_this_call": credits_this_call,
            "credits_remaining": result.get("credits_remaining"),
            "request_id": result.get("request_id"),
            "duration_sec": round(finished - started, 3),
            "data_status_raw": snap.get("data_status"),
        })
        live_results[asin] = result
        outcomes[asin] = outcome

    for asin in order:
        if asin not in outcomes:
            ledger.append({
                "seq": len(ledger) + 1, "asin": asin,
                "started_at": None, "finished_at": None,
                "outcome": "skipped_cap", "skipped": True,
                "credit_basis": None, "credits_this_call": 0,
                "credits_remaining": None, "request_id": None,
                "duration_sec": None, "data_status_raw": None,
            })
            outcomes[asin] = "skipped_cap"

    rows = _build_comparison_rows(m, live_results, outcomes)
    _write_comparison_csv(os.path.join(run_dir, "live-vs-csv-comparison.csv"), rows)
    ctx = {
        "run_id": run_id,
        "generated_at": _now_iso(),
        "provider": args.provider,
        "max_requests": caps["max_requests"],
        "max_credits": caps["max_credits"],
        "requests_made": budget["requests_used"],
        "credits_used": budget["credits_used"],
        "credits_reported": budget["credits_reported"],
        "stop_reason": stop_reason,
        "provider_warnings": provider_warnings,
    }
    _write_summary_md(os.path.join(run_dir, "run-summary.md"), ctx, rows)
    _atomic_write(os.path.join(run_dir, "request-ledger.json"), {
        "kind": "easyparser-manifest-run-ledger",
        "run_id": run_id,
        "entries": ledger,
    })
    _append_run_index(run_id, run_dir, "completed" if stop_reason is None else "stopped_cap",
                      caps["max_requests"], caps["max_credits"],
                      budget["requests_used"], budget["credits_used"])

    print("run complete: run_id=%s requests=%d/%d credits_used=%.1f "
          "(reported=%d) stop_reason=%s" % (
              run_id, budget["requests_used"], caps["max_requests"],
              budget["credits_used"], budget["credits_reported"],
              stop_reason or "none"))
    print("artifacts: %s" % run_dir)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Manifest-selection live enrichment (production-owned; "
                    "finite caps; no retries; provider selectable).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="validate manifest + env only (zero network)")
    p_status.add_argument("--manifest", required=True)

    p_dry = sub.add_parser("dry-run", help="validate + print plan (zero writes, zero network)")
    p_dry.add_argument("--manifest", required=True)

    p_run = sub.add_parser("run", help="execute the live loop (requires --live + finite caps)")
    p_run.add_argument("--manifest", required=True)
    p_run.add_argument("--provider", choices=["rapidapi", "dataforseo"],
                        default="rapidapi", help="live provider (Easyparser deprecated/disabled)")
    p_run.add_argument("--live", action="store_true")
    p_run.add_argument("--max-requests", type=int, default=None)
    p_run.add_argument("--max-credits", type=int, default=None)
    # NOTE: intentionally NO --retries flag. Automatic retry is structurally impossible.

    args = parser.parse_args(argv)
    if args.cmd == "status":
        return _run_status(args)
    if args.cmd == "dry-run":
        return _run_dry_run(args)
    return _run(args)


if __name__ == "__main__":
    sys.exit(main())
