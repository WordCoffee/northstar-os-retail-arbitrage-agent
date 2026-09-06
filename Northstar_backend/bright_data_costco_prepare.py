"""Bright Data Web Unlocker Costco — offline catalog resolver / run-manifest prep.

Reads (all local, deterministic, NO live calls):
  - data/costco-items.csv             (180 tracked Kirkland products: name, cost)
  - data/costco-api-catalog.json      (186 captured Costco catalog rows w/ ids)
  - data/costco-discovery-runs/<frozen>/costco-discovery-manifest.json
                                      (15 operator-verified item seeds)

For every 180-entry it emits a prepared run-manifest item the detail adapter
can consume via `--expected-json`, carrying:
  item_id            resolved Costco item number (null -> needs lookup)
  requested_title    the tracked product name (verbatim, typo preserved)
  requested_brand    "Kirkland Signature" / "Costco Wholesale"
  requested_pack     count-style pack extracted from the name (or null)
  costco_cost_reference  the tracked CSV cost (reference only, NOT live)
  resolution         enum: manifest_seed | catalog_exact | catalog_fuzzy
                              | catalog_alt_for_dead | unresolved_needs_lookup
  plus provenance fields (catalog title, source_url, url_derived, score).

Resolution policy (conservative, auditable):
  1. manifest_seed — operator-verified item id is used when the frozen
     discovery manifest's requested_title overlaps the product name >= 0.60.
     EXCEPTION: item 1493188 (Baby Wipes 900) is live-CONFIRMED dead
     (url_not_found, 2026-09-06); that id is NOT re-quoted; the catalog
     candidate 1493488 is marked catalog_alt_for_dead instead.
  2. catalog_exact — normalized name equality against id-bearing catalog rows.
  3. catalog_fuzzy — explicit, reviewed allowlist of fuzzy matches (each entry
     documents the catalog neighbor). Nothing else is auto-fuzzy-resolved.
  4. unresolved_needs_lookup — everything else (slug/search lookup live path).

Everything below runs offline. The live lookup for unresolved items is a
separate gated module (bright_data_costco_lookup.py).

CLI:
  python bright_data_costco_prepare.py --csv data/costco-items.csv \
      --catalog data/costco-api-catalog.json \
      --out <prepared-manifest.json> [--audit <resolution-audit.csv>]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DEFAULT_RUN_DIR = os.path.join("data", "costco-discovery-runs", "20260828T021658Z")
DEFAULT_MANIFEST = os.path.join(DEFAULT_RUN_DIR, "costco-discovery-manifest.json")
DEFAULT_CSV = os.path.join("data", "costco-items.csv")
DEFAULT_CATALOG = os.path.join("data", "costco-api-catalog.json")

# URL pattern for the flat item-number lookup the adapter uses.
COSTCO_ITEM_URL_TEMPLATE = "https://www.costco.com/.product.{item_id}.html"

# Live-confirmed dead item numbers (never re-quoted into a prepared manifest).
KNOWN_DEAD_ITEM_IDS = {"1493188"}

# Catalog candidate for Baby Wipes 900 (digit-transposed vs the dead 1493188).
BABY_WIPES_900 = {
    "item_id": "1493488",
    "catalog_title": "Kirkland Signature Baby Wipes, Fragrance Free, 900 ct",
    "source_url": "https://www.costcobusinessdelivery.com/kirkland-signature-baby-wipes,-fragrance-free,-900-ct.product.2001121923.html",
}

# Reviewed fuzzy allowlist: product name -> (item_id, catalog_title, score, note)
# These were hand-checked against the 2026-08-14 catalog capture.
FUZZY_ALLOWLIST: Dict[str, Tuple[str, str, float, str]] = {
    "Kirkland Signature AA Batteries 48 Count": (
        "2322010",
        "Kirkland Signature Alkaline AA Batteries, 48 ct",
        0.50,
        "catalog uses 'Alkaline AA Batteries, 48 ct'; same product line",
    ),
    "Kirkland Signature, Pure Sea Salt, 30 oz": (
        "384732",
        "Kirkland Signature Pure Sea Salt, Fine Grain, 30 oz",
        0.71,
        "catalog adds 'Fine Grain'; matches tracked 30 oz sea salt",
    ),
    "Kirkland Signature Elegant Plastic Plates, Variety Pack, White, 50-count": (
        "1343253",
        "Kirkland Signature Elegant Plastic Plate, White, 50 ct",
        0.40,
        "catalog row is singular 'Plate' 50 ct; flag for manual_verify on live run",
    ),
}

# Product names that MUST NOT auto-resolve (fuzzy trap that would mis-point).
REJECTED_FUZZY: Dict[str, str] = {
    "Kirkland Signature Adult Formula Lamb, Rice and Vegetable Dog Food, 25 lbs": (
        "nearest id-bearing catalog row was Cat Food 52296 — different product; "
        "dog food requires a real lookup"
    ),
}


def _norm(text: Optional[str]) -> str:
    s = (text or "").lower()
    # ascii-fold (breaks '&' and quotes cleanly)
    s = re.sub(r"&", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(kirkland|signature|co|costco|wholesale)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(text: Optional[str]) -> set:
    return set(_norm(text).split())


def _jaccard(a: Optional[str], b: Optional[str]) -> float:
    A, B = _tokens(a), _tokens(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _count_pack_from_name(name: Optional[str]) -> Optional[str]:
    """Extract a count-style pack ('48 Count', '200-count') from a product name."""
    if not name:
        return None
    m = re.search(r"(\d[\d,]*)\s*[-–—]?\s*(count|ct\.?|tablets?|softgels?|"
                  r"servings?|pills?|capsules?|bottles?|wipes?|rolls?|sheets?)\b",
                  name, re.I)
    if not m:
        return None
    return f"{m.group(1).replace(',', '')} {m.group(2).lower().rstrip('.')}"


def _brand_from_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    if re.search(r"kingland|kirkland", name, re.I):
        return "Kirkland Signature"
    if re.search(r"costco wholesale", name, re.I):
        return "Costco Wholesale"
    return None


def _load_csv(path: str) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            name = (r.get("item_name") or "").strip()
            if name:
                rows.append({"name": name, "cost": r.get("costco_cost", "").strip()})
    return rows


def _load_catalog(path: str) -> List[Dict]:
    """Id-bearing catalog rows from all pools (items / held_for_review / unmatched)."""
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    rows = []
    seen = set()
    for pool in ("items", "held_for_review", "unmatched"):
        for r in data.get(pool) or []:
            if not isinstance(r, dict):
                continue
            iid = str(r.get("costco_item_id") or "").strip()
            name = str(r.get("item_name") or "").strip()
            if not iid or not name:
                continue
            key = (_norm(name), iid)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "item_name": name,
                    "costco_item_id": iid,
                    "source_url": r.get("source_url") or "",
                    "url_derived": bool(r.get("url_derived")),
                    "regular_price": r.get("regular_price"),
                    "sale_price": r.get("sale_price"),
                    "pool": pool,
                }
            )
    return rows


def _load_manifest(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    return [
        {
            "item_id": str(it.get("item_id") or "").strip(),
            "requested_title": it.get("requested_title") or "",
            "requested_pack": it.get("requested_pack") or "",
        }
        for it in (data.get("items") or [])
        if (it.get("item_id") or "").strip()
    ]


def resolve_product(
    product: Dict,
    catalog: List[Dict],
    manifest: List[Dict],
    fuzzies: Optional[Dict[str, Tuple]] = None,
) -> Dict:
    """Resolve one product to a Costco item id (offline). Returns full item dict."""
    fuzzies = fuzzies if fuzzies is not None else FUZZY_ALLOWLIST
    name = product["name"]

    brand = _brand_from_name(name)
    pack = _count_pack_from_name(name)
    item = {
        "item_id": None,
        "requested_title": name,
        "requested_brand": brand,
        "requested_pack": pack,
        "costco_cost_reference": product.get("cost") or None,
        "resolution": "unresolved_needs_lookup",
        "resolution_notes": "",
        "catalog_title": None,
        "catalog_source_url": None,
        "url_derived": None,
        "match_score": None,
        "pool": None,
    }

    if name in REJECTED_FUZZY:
        item["resolution_notes"] = REJECTED_FUZZY[name]
        return item

    # 1) manifest seed (operator-verified ids) — but never the known-dead id.
    for m in manifest:
        if _jaccard(name, m["requested_title"]) >= 0.60:
            if m["item_id"] in KNOWN_DEAD_ITEM_IDS:
                # 1493188 live-confirmed dead; do not re-quote. Prefer catalog alt.
                if name.lower().startswith("kirkland signature baby wipes"):
                    item.update(
                        {
                            "item_id": BABY_WIPES_900["item_id"],
                            "resolution": "resolved_catalog_alt_for_dead",
                            "resolution_notes": (
                                "manifest seed 1493188 live-confirmed dead (url_not_found "
                                "2026-09-06); using catalog candidate 1493488 instead — "
                                "must be live-verified"
                            ),
                            "catalog_title": BABY_WIPES_900["catalog_title"],
                            "catalog_source_url": BABY_WIPES_900["source_url"],
                            "url_derived": False,
                            "match_score": None,
                            "pool": "held_for_review",
                        }
                    )
                return item
            item.update(
                {
                    "item_id": m["item_id"],
                    "requested_pack": m["requested_pack"] or pack,
                    "resolution": "resolved_manifest_seed",
                    "resolution_notes": f"frozen manifest seed (overlap {_jaccard(name, m['requested_title']):.2f})",
                    "match_score": round(_jaccard(name, m["requested_title"]), 2),
                    "pool": "manifest",
                }
            )
            return item

    # 2) catalog exact (normalized name equality)
    n = _norm(name)
    exact = [c for c in catalog if _norm(c["item_name"]) == n]
    if exact:
        c = exact[0]
        item.update(
            {
                "item_id": c["costco_item_id"],
                "resolution": "resolved_catalog_exact",
                "resolution_notes": "normalized-name equality vs 2026-08-14 catalog",
                "catalog_title": c["item_name"],
                "catalog_source_url": c["source_url"],
                "url_derived": c["url_derived"],
                "match_score": 1.0,
                "pool": c["pool"],
            }
        )
        return item

    # 3) reviewed fuzzy allowlist
    if name in fuzzies:
        iid, ctitle, score, note = fuzzies[name]
        src = next((c["source_url"] for c in catalog if c["costco_item_id"] == iid), "")
        item.update(
            {
                "item_id": iid,
                "resolution": "resolved_catalog_fuzzy",
                "resolution_notes": f"{note} | {'manual_verify' if score < 0.5 else 'reviewed match'}",
                "catalog_title": ctitle,
                "catalog_source_url": src,
                "url_derived": False,
                "match_score": score,
                "pool": "reviewed_fuzzy",
            }
        )
        return item

    # 4) unresolved — needs the gated slug/search lookup (or operator id)
    best = None
    best_score = 0.0
    for c in catalog:
        s = _jaccard(name, c["item_name"])
        if s > best_score:
            best_score = s
            best = c
    item["resolution_notes"] = (
        f"no catalog match; nearest id-bearing row: '{best['item_name']}' "
        f"(score {best_score:.2f}) — requires slug/search lookup or operator id"
        if best
        else "no catalog id-bearing candidate"
    )
    return item


def build_prepared_manifest(
    csv_path: str, catalog_path: str, manifest_path: str
) -> Tuple[List[Dict], Dict]:
    """Resolve the tracked product list into prepared run-manifest items."""
    products = _load_csv(csv_path)
    catalog = _load_catalog(catalog_path)
    manifest = _load_manifest(manifest_path)

    items = [resolve_product(p, catalog, manifest) for p in products]

    counts = {}
    for it in items:
        counts[it["resolution"]] = counts.get(it["resolution"], 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tracked_products": len(products),
        "resolved_total": sum(
            v for k, v in counts.items() if k.startswith("resolved")
        ),
        "unresolved_needs_lookup": counts.get("unresolved_needs_lookup", 0),
        "resolution_counts": counts,
        "notes": [
            "OFFLINE resolution only — item ids are catalog/manifest candidates, "
            "NOT live-verified flat-URL resolutions.",
            "Unknown live validity until a gated detail refresh confirms each id "
            "(url_not_found items are then typed by the adapter).",
            "Known-dead manifest id 1493188 (baby wipes) is replaced by catalog "
            "candidate 1493488 for the live run and must be verified.",
        ],
    }
    return items, summary


def _write_manifest(items: List[Dict], summary: Dict, out_path: str) -> None:
    payload = {
        "kind": "brightdata_costco_prepared_run_manifest",
        "scope": "180-product catalog test (costco-items.csv)",
        "schema_version": "1.0",
        "summary": summary,
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"wrote prepared manifest: {out_path}")


def _write_audit(items: List[Dict], out_path: str) -> None:
    fields = [
        "requested_title",
        "costco_cost_reference",
        "item_id",
        "resolution",
        "match_score",
        "requested_brand",
        "requested_pack",
        "catalog_title",
        "pool",
        "url_derived",
        "resolution_notes",
    ]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for it in items:
            w.writerow({f: it.get(f) for f in fields})
    print(f"wrote resolution audit: {out_path}")


def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="bright_data_costco_prepare.py",
        description="Offline Costco catalog resolver → prepared run manifest (no live calls).",
    )
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--out", required=True)
    parser.add_argument("--audit", default=None)
    args = parser.parse_args(argv)

    items, summary = build_prepared_manifest(args.csv, args.catalog, args.manifest)
    _write_manifest(items, summary, args.out)
    if args.audit:
        _write_audit(items, args.audit)

    print("\n=== RESOLUTION SUMMARY (offline) ===")
    print(f"tracked products      : {summary['tracked_products']}")
    print(f"resolved total        : {summary['resolved_total']}")
    print(f"unresolved needs-lookup: {summary['unresolved_needs_lookup']}")
    for k, v in sorted(summary["resolution_counts"].items()):
        print(f"  {k:<32} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())