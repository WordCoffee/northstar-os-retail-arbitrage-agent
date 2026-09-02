"""Layer 8 - Per-provider field mappers.

Each mapper returns an intel_schema facts.market dict (the normalized record).
Null-first: any field a provider does not return stays None / null.

real-time-amazon-data mapper is the verified one (imported). DataForSEO has a
dedicated mapper reflecting its actual normalized shape. The other 4 RapidAPI
apps (BDC, Axesso, Pricing, Online, Scout) use a best-effort generic mapper
that searches their (heterogeneous) payloads for the known keys; these are
stubs pending verified route discovery, but remain null-first and honest.
"""

import json

import rapidapi_router as R
from intel_schema import normalize_bsr


def _coerce_bsr(bsr_raw, source):
    if isinstance(bsr_raw, dict):
        rank = bsr_raw.get("rank") or bsr_raw.get("primary_rank") or bsr_raw.get("bsr_primary_rank")
        cat = bsr_raw.get("category") or bsr_raw.get("primary_category") or bsr_raw.get("bsr_primary_category")
        if rank is not None:
            return {
                "bsr_raw": json.dumps(bsr_raw, default=str),
                "bsr_primary_rank": rank,
                "bsr_primary_category": cat,
                "bsr_secondary_rank": bsr_raw.get("secondary_rank"),
                "bsr_secondary_category": bsr_raw.get("secondary_category"),
                "bsr_capture_status": "verified",
                "bsr_source": source,
                "bsr_captured_at": None,
            }
    if isinstance(bsr_raw, str):
        return normalize_bsr(bsr_raw, source=source)
    return normalize_bsr(None, source=source)


def _build_market(asin, *, title, price, bsr_raw, buy_box, offers, claimed_total, source):
    bb = buy_box or {}
    fba = sum(1 for o in offers if o.get("is_fba") is True)
    fbm = sum(1 for o in offers if o.get("is_fba") is False)
    # No per-offer FBA/FBM signal exposed -> report unknown (None), not 0.
    if offers and fba == 0 and fbm == 0:
        ffa = fbm = None
    else:
        ffa, fbm = fba, fbm
    amazon = sum(1 for o in offers if o.get("seller_name") == "Amazon")
    if offers:
        if claimed_total is not None and len(offers) < claimed_total:
            status = "partial"
            reason = "returned %d of %d claimed offers" % (len(offers), claimed_total)
        else:
            status = "full"
            reason = "%s product_offers roster" % source
    else:
        status = "unknown"
        reason = "no roster returned"
    return {
        "amazon_price": price,
        "bsr": _coerce_bsr(bsr_raw, source),
        "buy_box": {
            "available": bb.get("price") is not None,
            "price": bb.get("price"),
            "seller_name": bb.get("seller_name") or bb.get("seller"),
            "seller_id": bb.get("seller_id"),
            "fulfillment": bb.get("fulfillment"),
            "source": source,
            "observed_at": None,
        },
        "seller_counts": {
            "total_observed": len(offers),
            "fba_observed": ffa,
            "fbm_observed": fbm,
            "amazon_observed": amazon,
            "claimed_total": claimed_total,
        },
        "coverage": {
            "offer_list_available": len(offers) > 0,
            "offers_complete_status": status,
            "coverage_reason": reason,
        },
        "offers": offers,
    }


def normalize_dataforseo(asin, raw):
    title = raw.get("title")
    price = raw.get("buy_box_price")
    bsr_raw = raw.get("bsr")
    bb_seller = raw.get("buy_box_seller")
    buy_box = {"price": price, "seller_name": bb_seller}
    offers = []
    for o in (raw.get("offers") or []):
        if not isinstance(o, dict):
            continue
        offers.append({
            "seller_name": o.get("seller_name"),
            "seller_id": o.get("seller_id"),
            "price": o.get("price"),
            "condition": o.get("condition"),
            "is_fba": o.get("is_fba"),
            "is_fbm": o.get("is_fbm"),
            "fulfillment": o.get("fulfillment"),
            "ships_from": o.get("ships_from"),
        })
    claimed = raw.get("offer_count") or raw.get("offers_returned_count")
    return _build_market(asin, title=title, price=price, bsr_raw=bsr_raw,
                         buy_box=buy_box, offers=offers,
                         claimed_total=claimed, source="dataforseo")


def normalize_generic(asin, raw, source):
    title = R._find_any(raw, ["title", "name", "product_title", "item_name"])
    price = R._to_float(R._find_any(raw, ["price", "current_price", "buybox_price", "amount"]))
    bsr_raw = R._find_any(raw, ["bsr", "sales_rank", "salesRank", "rank", "best_sellers_rank"])
    bb = R._find_any(raw, ["buybox", "buy_box", "buyBox"])
    buy_box = None
    if isinstance(bb, dict):
        buy_box = {
            "price": R._to_float(bb.get("price") or bb.get("buybox_price")),
            "seller_name": bb.get("seller_name") or bb.get("seller"),
            "seller_id": bb.get("seller_id"),
            "fulfillment": bb.get("fulfillment"),
        }
    offers_raw = R._find_any(raw, ["offers", "sellers", "seller_list"])
    offers = []
    if isinstance(offers_raw, list):
        for o in offers_raw:
            if not isinstance(o, dict):
                continue
            ful = o.get("fulfillment")
            is_fba = o.get("is_fba")
            if is_fba is None and isinstance(ful, str):
                is_fba = True if ful.upper() == "FBA" else (False if ful.upper() == "FBM" else None)
            offers.append({
                "seller_name": o.get("seller_name") or o.get("seller"),
                "seller_id": o.get("seller_id"),
                "price": R._to_float(o.get("price") or o.get("current_price")),
                "condition": o.get("condition"),
                "is_fba": is_fba,
                "is_fbm": o.get("is_fbm"),
                "fulfillment": ful,
                "ships_from": o.get("ships_from"),
            })
    claimed = R._to_int(R._find_any(raw, ["offer_count", "number_of_offers", "total_offers"]))
    return _build_market(asin, title=title, price=price, bsr_raw=bsr_raw,
                         buy_box=buy_box, offers=offers,
                         claimed_total=claimed, source=source)


MAPPERS = {
    "RAPIDAPI_REALTIME": lambda asin, raw: R.to_intel_market_real_time(asin, raw),
    "RAPIDAPI_BDC": lambda asin, raw: normalize_generic(asin, raw, "rapidapi_bdc"),
    "RAPIDAPI_AXESSO": lambda asin, raw: normalize_generic(asin, raw, "rapidapi_axesso"),
    "RAPIDAPI_PRICING": lambda asin, raw: normalize_generic(asin, raw, "rapidapi_pricing"),
    "RAPIDAPI_ONLINE": lambda asin, raw: normalize_generic(asin, raw, "rapidapi_online"),
    "RAPIDAPI_SCOUT": lambda asin, raw: normalize_generic(asin, raw, "rapidapi_scout"),
    "DATAFORSEO": normalize_dataforseo,
}


def map_provider(app_label, asin, raw):
    mapper = MAPPERS.get(app_label)
    if mapper is None:
        return None
    return mapper(asin, raw)
