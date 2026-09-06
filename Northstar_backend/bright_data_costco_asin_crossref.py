"""Offline cross-reference: Amazon ASIN list (Rank + BSR-proxyrank CSVs, deduped by ASIN)
<-> Costco item catalog (costco-items.csv, costco-api-catalog.json, prepared manifest)
+ live-fetch evidence (per-ID identity_match_status from costco-discovery-runs).

No live calls. Outputs:
  Northstar_backend/data/catalog/asin_costco_crossref.csv   (merged ASIN x Costco table)
  Northstar_backend/data/catalog/asin_costco_crossref.json  (same plus classifications)

Run: python bright_data_costco_asin_crossref.py
"""
import csv
import json
import os
import re
import glob

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))          # Northstar_backend/
DATA = os.path.join(os.path.dirname(REPO_ROOT), "data")         # repo-root data/
BENCH = os.path.join(REPO_ROOT, "data", "benchmarks", "raw")
CATALOG_JSON = os.path.join(DATA, "costco-api-catalog.json")
ITEMS_CSV = os.path.join(DATA, "costco-items.csv")
MANIFEST = os.path.join(REPO_ROOT, "data", "catalog", "brightdata_costco_180_prepared_manifest.json")
EVIDENCE = os.path.join(REPO_ROOT, "data", "costco-discovery-runs")
OUT_CSV = os.path.join(REPO_ROOT, "data", "catalog", "asin_costco_crossref.csv")
OUT_JSON = os.path.join(REPO_ROOT, "data", "catalog", "asin_costco_crossref.json")

RANK_CSV = os.path.join(BENCH, "Rank-Product-ASIN-Reviews-Price-BSR.csv")
PROXY_CSV = os.path.join(BENCH, "BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv")

# ---------------------------------------------------------------------------
# 1. Load & merge the two ASIN CSVs (dedupe by ASIN)
# ---------------------------------------------------------------------------
def _load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))

def _int(s):
    s = str(s or "")
    return int(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s) else None

def _price(s):
    try:
        return round(float(re.sub(r"[^\d.]", "", s or "")), 2)
    except (ValueError, TypeError):
        return None

merged = {}
for row in _load_csv(RANK_CSV):
    asin = (row.get("ASIN") or "").strip()
    if not asin:
        continue
    merged[asin] = {
        "asin": asin, "product_rank": row.get("Product") or "", "product_proxy": "",
        "rank_rank": row.get("Rank") or "", "reviews": _int(row.get("Reviews")),
        "price": _price(row.get("Price")), "bsr": (row.get("BSR") or "").strip(),
        "prime_fba": "", "sources": ["Rank"],
    }
for row in _load_csv(PROXY_CSV):
    asin = (row.get("ASIN") or "").strip()
    if not asin:
        continue
    rec = merged.get(asin)
    if rec is None:
        rec = {
            "asin": asin, "product_rank": "", "product_proxy": row.get("Product") or "",
            "rank_rank": "", "reviews": _int(row.get("Reviews")),
            "price": _price(row.get("Price")), "bsr": "", "prime_fba": "",
            "sources": ["ProxyRank"],
        }
        merged[asin] = rec
    else:
        rec["sources"].append("ProxyRank")
    rec["product_proxy"] = row.get("Product") or rec["product_proxy"] or ""
    rec["prime_fba"] = (row.get("Prime/FBA") or "").strip()
    if rec["reviews"] is None:
        rec["reviews"] = _int(row.get("Reviews"))
    if rec["price"] is None:
        rec["price"] = _price(row.get("Price"))

# ---------------------------------------------------------------------------
# 1b. (optional) merge live-discovered Kirkland ASINs from an Amazon search
#     manifest (kirkland_discovery.py output). Only ADDS ASINs absent from the
#     benchmark CSVs -- benchmark metadata is never overwritten by weaker
#     search-card fields. No-op when KIRKLAND_DISCOVERY_ASINS is unset, so the
#     existing 47-ASIN outputs are byte-for-byte unchanged with no env set.
# ---------------------------------------------------------------------------
DISCOVERY_MANIFEST = os.getenv("KIRKLAND_DISCOVERY_ASINS")
INPUT_FILES = [RANK_CSV, PROXY_CSV, ITEMS_CSV, CATALOG_JSON, MANIFEST]
discovery_added = 0
if DISCOVERY_MANIFEST and os.path.exists(DISCOVERY_MANIFEST):
    try:
        with open(DISCOVERY_MANIFEST, encoding="utf-8") as _fh:
            _dm = json.load(_fh)
        for _c in (_dm.get("candidates") or []):
            _a = (_c.get("asin") or "").strip()
            if not _a or _a in merged:
                continue
            _name = (_c.get("name") or _c.get("title") or "").strip()
            if not _name:
                continue
            merged[_a] = {
                "asin": _a,
                "product_rank": "", "product_proxy": _name, "rank_rank": "",
                "reviews": _int(_c.get("reviews_count")),
                "price": _price(_c.get("amazon_price")),
                "bsr": "", "prime_fba": "",
                "sources": ["Discovery"],
            }
            discovery_added += 1
        INPUT_FILES.append(DISCOVERY_MANIFEST)
        print("DISCOVERY manifest: %s -> new ASINs merged: %d" % (
            os.path.basename(DISCOVERY_MANIFEST), discovery_added))
    except Exception as _e:
        print("DISCOVERY manifest load failed: %s" % _e)

LOW_REVIEWS_THRESHOLD = 1000
for rec in merged.values():
    flags = []
    if rec["bsr"] and "Not listed" in rec["bsr"]:
        flags.append("BSR-not-listed")
    if rec["reviews"] is not None and rec["reviews"] < LOW_REVIEWS_THRESHOLD:
        flags.append("low-reviews(<%d)" % LOW_REVIEWS_THRESHOLD)
    pf = (rec["prime_fba"] or "").lower()
    if pf and not pf.startswith("yes"):
        flags.append("non-Prime/FBA")
    rec["dormancy_flags"] = flags
    rec["revival_candidate"] = bool(flags)
    rec["revive_signals"] = len(flags)

# ---------------------------------------------------------------------------
# 2. Costco catalog corpus (+ unresolved lane)
# ---------------------------------------------------------------------------
def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return s.split()

def stem(t):
    """singular-fold trailing 's' for len>3 (pecans->pecan, gloves->glove, wipes->wipe)."""
    return t[:-1] if (len(t) > 3 and t.endswith("s") and not t.endswith("ss")) else t

STOP_TOKENS = {
    "kirkland", "signature", "the", "and", "with", "of", "pack", "packs", "pk",
    "count", "cnt", "ct", "cts", "oz", "lbs", "lb", "fl", "g", "kg", "ml",
    "bottle", "bottles", "spray", "sprays", "tablet", "tablets", "softgel",
    "softgels", "capsule", "capsules", "month", "months", "mo", "packaging",
    "variety", "bundle", "original", "listing", "extra", "strength", "ultra",
    "premium", "size", "sizes", "avg", "wt", "item", "jar", "jars", "can",
    "cans", "fba", "prime", "men", "for", "with", "pkrt",
    "baking", "nuts", "fresh", "organic", "plus", "scented", "kitchen",
}

# family keyword found in the ASIN product name -> required Costco-item tokens (post-stem)
# NOTE: dict order = precedence; more specific keys must come first (compactor before trash).
ALIAS = {
    "compactor": {"compactor"},
    "allerflo|fluticasone": {"aller", "flo"},
    "minoxidil|regrowth": {"minoxidil"},
    "stoolsoftener|softener": {"stool", "softener"},
    "sleepaid|doxylamine": {"sleep", "doxylamine"},
    "microfiber|towel": {"microfiber", "towel"},
    "fibercapsule|fiber": {"fiber", "capsule"},
    "glucosamine|chondroitin": {"glucosamine"},
    "antacid": {"antacid"},
    "psyllium": {"psyllium"},
    "babywipe|wipes": {"baby", "wipe"},
    "trashbag|trash": {"trash", "bag"},
    "compost": {"compost"},
    "water|drinkingwater": {"water"},
    "walnut": {"walnut"},
    "golf": {"golf"},
    "vanilla": {"vanilla", "extract"},
    "dentalchew|chew": {"dental", "chew"},
    "foodwrap|stretchtite|wrap": {"plastic", "wrap"},
    "agave": {"agave"},
    "pecan|praline": {"pecan"},
    "nitrile|glove": {"nitrile", "glove"},
    "hemp": {"hemp"},
    "kcup|k-cup|coffee": {"coffee"},
    "hearingaid|hearing": {"hearing", "aid"},
    "calciumgumm|calcium": {"calcium"},
    "nutbutter|nutbutter|butter": {"nut", "butter"},
    "peanut|pretzel|nugget": {"pretzel"},
    "vitamine|vitamin": {"vitamin", "e"},
    "proteinbar|protein": {"protein"},
    "diaper": {"diaper"},
    "seasalt|salt": {"sea", "salt"},
}

def alias_tokens(product_txt):
    s = norm(product_txt)
    text = " ".join(stem(t) for t in s)
    flat = text.replace(" ", "")
    for key, toks in ALIAS.items():
        for part in key.split("|"):
            if part in flat:
                # k-cup special: require the literal 'cup' token too
                if part in ("kcup", "k-cup"):
                    if "cup" in text.split():
                        return {"coffee", "cup"}
                    return None
                # 'chew' must not fire on 'chewable' or 'chewy' (e.g. protein bars),
                # which would otherwise mis-route chew-family alias matches.
                if part == "chew" and ("chewable" in flat or "chewy" in flat):
                    continue
                return toks
    return None

def item_tok_set(item):
    toks = set()
    for n in item["names"]:
        toks.update(stem(t) for t in norm(n) if t not in STOP_TOKENS and not re.search(r"\d", t))
    return toks

costco_items = {}
name_index = set()
def add_item(name, item_id, cost):
    if not name or not str(name).strip():
        return
    name = str(name)
    nkey = " ".join(norm(name))
    item_id = str(item_id) if item_id is not None else None
    key = item_id if item_id else "NEEDSLK:" + name.strip().lower()[:80]
    if nkey in name_index and key not in costco_items:
        return  # name already tracked under an existing entry (no ghost duplicates)
    if nkey not in name_index:
        name_index.add(nkey)
    rec = costco_items.setdefault(key, {"name": name, "names": [], "cost": cost, "id": item_id})
    if name not in rec["names"]:
        rec["names"].append(name)
    if cost is not None and rec["cost"] is None:
        rec["cost"] = cost
    return rec

catalog = json.load(open(CATALOG_JSON, encoding="utf-8-sig"))
for it in catalog.get("items", []):
    add_item(it.get("item_name"), it.get("costco_item_id"), it.get("costco_cost"))

manifest = json.load(open(MANIFEST, encoding="utf-8"))
manifest_items = manifest.get("items", [])
for it in manifest_items:
    iid = it.get("item_id")
    core = it.get("requested_title") or it.get("catalog_title") or ""
    add_item(core, iid, it.get("costco_cost_reference"))
    if it.get("catalog_title") and it["catalog_title"] != core:
        add_item(it["catalog_title"], iid, it.get("costco_cost_reference"))

with open(ITEMS_CSV, encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        nm = row.get("item_name") or ""
        add_item(nm, None, row.get("costco_cost"))

# manifest-index: item_id -> live (discovery) status
def manifest_status():
    """Live-fetch status per item_id from evidence (latest record wins)."""
    byid = {}
    http200_ids = set()
    for rd in sorted(glob.glob(os.path.join(EVIDENCE, "*"))):
        if not os.path.isdir(rd):
            continue
        for f in glob.glob(os.path.join(rd, "normalized", "*.json")):
            try:
                r = json.load(open(f, encoding="utf-8-sig"))
            except Exception:
                continue
            it = r.get("item") or {}
            iid = it.get("requested_item_id") or r.get("attempt", "").rsplit("_", 1)[-1]
            if not iid or not re.fullmatch(r"\d+", iid):
                continue
            if r.get("http_status") == 200:
                http200_ids.add(iid)
            rows = byid.setdefault(str(iid), [])
            rows.append((r.get("requested_at") or "", r.get("http_status"),
                         it.get("identity_match_status")))
    statuses = {}
    for iid, rows in byid.items():
        rows.sort(key=lambda x: x[0])
        latest = rows[-1]
        if latest[2] in ("probable_match", "url_not_found", "no_data_found", "unverified"):
            statuses[iid] = latest[2]
        elif latest[1] == 200:
            statuses[iid] = "fetched_no_status"
        else:
            statuses[iid] = "transport_error"
    return statuses, http200_ids

live, http200_ids = manifest_status()

# ---------------------------------------------------------------------------
# 3. Match ASIN -> best Costco item (alias-gated, recall-scored, rivals kept)
# ---------------------------------------------------------------------------
index = [(key, rec, item_tok_set(rec)) for key, rec in costco_items.items()]

def match_asin(rec):
    product_txt = rec["product_proxy"] or rec["product_rank"]
    ptoks = {stem(t) for t in norm(product_txt) if t not in STOP_TOKENS and not re.search(r"\d", t)}
    alias = alias_tokens(product_txt)
    cands = []
    for key, item, itoks in index:
        if alias is not None:
            if not (alias <= itoks):
                continue
        inter = ptoks & itoks
        recall = len(inter) / len(ptoks) if ptoks else 0.0
        cands.append({"score": round(recall, 2), "recall": round(recall, 2),
                      "key": key, "item": item})
    if not cands:
        return None, []
    if alias is not None:
        # alias-gated: single obvious family candidate accepted outright;
        # multiple candidates require strong secondary evidence (recall >= 0.6)
        if len(cands) > 1:
            accepted = [c for c in cands if c["recall"] >= 0.6]
        else:
            accepted = cands
    else:
        accepted = [c for c in cands if c["recall"] >= 0.5]
    if not accepted:
        return None, cands
    accepted.sort(key=lambda c: (-c["recall"]))
    return accepted[0], accepted

MATCH_OK = 0.5
rows = []
unique_ids = {}
for rec in merged.values():
    best, rivals = match_asin(rec)
    if best is None:
        rec["match"] = None
        rec["category"] = "c_needs_name_lookup"
        rec["rivals"] = []
    else:
        item = best["item"]
        cid = item["id"]
        st = live.get(cid) if cid else None
        rec["match"] = {
            "costco_id": cid, "costco_name": item["name"], "cost": item["cost"],
            "score": best["score"], "recall": best["recall"], "live_status": st,
        }
        rec["rivals"] = [{"costco_id": c["item"]["id"], "costco_name": c["item"]["name"][:70],
                          "score": c["score"]} for c in rivals[:4]]
        if cid is None:
            rec["category"] = "c_needs_name_lookup"
        elif st == "probable_match":
            rec["category"] = "a_live_confirmed_match"
        elif st == "url_not_found":
            rec["category"] = "matched_dead_item"
        elif st in ("no_data_found", "unverified", "fetched_no_status"):
            rec["category"] = "matched_unresolved"
        elif st == "transport_error":
            rec["category"] = "matched_failed_fetch"
        else:
            rec["category"] = "catalog_resolved_not_fetched"
        if cid:
            unique_ids.setdefault(cid, []).append(rec["asin"])
    if rec.get("match"):
        pass
    rows.append(rec)

# every id that is a primary OR rival candidate for any ASIN is "matched"
matched_ids = set(unique_ids)
for rec in rows:
    for r in rec.get("rivals", []):
        if r.get("costco_id"):
            matched_ids.add(r["costco_id"])
manifest_ids = {str(it.get("item_id")) for it in manifest_items
                if it.get("item_id") and str(it.get("item_id")) in live}
USABLE = {"probable_match", "url_not_found", "no_data_found", "unverified", "fetched_no_status"}
usable_fetched = {iid for iid in manifest_ids if live.get(iid) in USABLE}
failed_fetched = {iid for iid in manifest_ids if live.get(iid) == "transport_error"}
fetched_without_asin = sorted(usable_fetched - matched_ids,
                              key=lambda x: int(x) if x.isdigit() else 1 << 60)
failed_without_asin = sorted(failed_fetched - matched_ids,
                             key=lambda x: int(x) if x.isdigit() else 1 << 60)
name_of = {}
for it in manifest_items:
    iid = str(it.get("item_id")) if it.get("item_id") else None
    if iid:
        name_of[iid] = it.get("catalog_title") or it.get("requested_title")

# ---------------------------------------------------------------------------
# 4. Emit CSV + JSON
# ---------------------------------------------------------------------------
status_lbl = {
    "probable_match": "LIVE-CONFIRMED", "url_not_found": "DEAD", "no_data_found": "EMPTY",
    "unverified": "UNVERIFIED", "transport_error": "TRANSPORT-ERROR",
    "fetched_no_status": "FETCHED-NO-STATUS", None: "not-fetched",
}
out_rows = []
for rec in sorted(rows, key=lambda r: (-r["revive_signals"], r["asin"])):
    m = rec.get("match") or {}
    out_rows.append({
        "ASIN": rec["asin"],
        "Product": rec["product_proxy"] or rec["product_rank"],
        "Rank": rec["rank_rank"],
        "Reviews": rec["reviews"],
        "PriceUSD": rec["price"],
        "BSR": rec["bsr"],
        "PrimeOrFBA": rec["prime_fba"],
        "Sources": "+".join(rec["sources"]),
        "DormancyFlags": "; ".join(rec["dormancy_flags"]),
        "RevivalCandidate": rec["revival_candidate"],
        "ReviveSignals": rec["revive_signals"],
        "CostcoID": m.get("costco_id") or "",
        "CostcoName": m.get("costco_name") or "",
        "MatchScore": m.get("score") or "",
        "CostcoCostRef": m.get("cost") or "",
        "LiveStatus": status_lbl.get(m.get("live_status")),
        "Category": rec["category"],
        "RivalIDs": "; ".join(r["costco_id"] for r in rec["rivals"] if r["costco_id"]) or "",
    })

with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)

categories = {}
for r in rows:
    categories[r["category"]] = categories.get(r["category"], 0) + 1

payload = {
    "generated_at": "2026-09-06T00:00:00Z",
    "inputs": sorted({os.path.basename(p) for p in INPUT_FILES}),
    "merge": {
        "rank_rows": len(_load_csv(RANK_CSV)),
        "proxyrank_rows": len(_load_csv(PROXY_CSV)),
        "unique_asins": len(merged),
        "asins_in_both_files": sum(1 for r in merged.values() if len(r["sources"]) > 1),
    },
    "fetch_reconciliation": {
        "unique_http200_ids_all_evidence": len(http200_ids),
        "http200_ids_not_in_manifest": sorted(
            {i for i in http200_ids if i not in manifest_ids}),
        "manifest_items_with_evidence": len(manifest_ids),
        "manifest_http200_items": len(usable_fetched),
        "manifest_failed_fetch_items": len(failed_fetched),
        "usable_manifest_ids_with_no_content": sorted(
            {i for i in usable_fetched if live.get(i) in ("no_data_found", "unverified")}),
        "live_status_counts": {},
    },
    "categories": categories,
    "fetched_without_asin_match": [
        {"costco_id": i, "name": name_of.get(i, ""), "status": live.get(i)} for i in fetched_without_asin],
    "failed_fetch_without_asin_match": [
        {"costco_id": i, "name": name_of.get(i, ""), "status": "transport_error"} for i in failed_without_asin],
    "asin_to_costco": {
        r["asin"]: (r.get("match") or {}).get("costco_id") for r in rows},
    "rows": out_rows,
}
from collections import Counter
payload["fetch_reconciliation"]["live_status_counts"] = dict(Counter(live.values()))
with open(OUT_JSON, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)

# ---------------------------------------------------------------------------
# 5. Console report
# ---------------------------------------------------------------------------
print("MERGED ASINs: %d (rank %d rows + proxy %d rows; %d in both)" % (
    len(merged), payload["merge"]["rank_rows"], payload["merge"]["proxyrank_rows"],
    payload["merge"]["asins_in_both_files"]))
print("unique HTTP-200 evidence ids: %d | manifest ids with evidence: %d | manifest http-200: %d | failed-fetch: %d" % (
    len(http200_ids), len(manifest_ids), len(usable_fetched), len(failed_fetched)))
print("non-manifest http-200 ids:", payload["fetch_reconciliation"]["http200_ids_not_in_manifest"])
print("live_status_counts:", payload["fetch_reconciliation"]["live_status_counts"])
print()
print("CATEGORY COUNTS:", categories)
print()
print("{:<13}{:>7}{:>8}  {:<8}{:<30}{:<7}{:<24} {}".format(
    "ASIN", "Rev", "Price", "Revive?", "Product", "ID", "LiveStatus", "CostcoName"))
for r in out_rows:
    print("%-13s%7s%8s  %-8s%-30s%-7s%-24s %s" % (
        r["ASIN"], r["Reviews"] if r["Reviews"] is not None else "-",
        r["PriceUSD"] if r["PriceUSD"] is not None else "-",
        "Y" if r["RevivalCandidate"] else "-",
        r["Product"][:30], r["CostcoID"] or "~", r["LiveStatus"] or "-", r["CostcoName"][:46]))
print()
print("REVIVAL CANDIDATES (%d):" % sum(1 for r in rows if r["revival_candidate"]))
for r in sorted(rows, key=lambda x: -(x["revive_signals"])):
    if r["revival_candidate"]:
        print("  %s %-36s %s" % (r["asin"], (r["product_proxy"] or r["product_rank"])[:36],
                                 "; ".join(r["dormancy_flags"])))
print()
print("FETCHED WITHOUT ASIN MATCH (%d usable fetches):" % len(fetched_without_asin))
print(", ".join(fetched_without_asin))
print()
print("FAILED FETCH (transport_error) WITHOUT ASIN MATCH (%d):" % len(failed_without_asin))
print(", ".join(failed_without_asin))