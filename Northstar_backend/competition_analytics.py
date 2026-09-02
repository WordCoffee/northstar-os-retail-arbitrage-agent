"""Offline seller-competition analytics over local market snapshots.

Pure, deterministic, read-only helpers that turn one Easyparser market
snapshot (as stored by market_snapshot_store) into honest competition
fields: observed vs claimed offer counts, observed Buy Box, lowest /
highest / spread over the actually-returned offer rows, prime and
fulfilled-by-Amazon counts, and an estimated units-per-observed-seller
share when an estimated monthly sales figure is available.

Rules of honesty (mirrored from the scanner contracts):
  - Zero seller counts are emitted only when the provider explicitly
    reports a complete zero-offer set. Otherwise an empty or
    unavailable roster is Unknown.
  - The explicit zero-offer proof requires ALL of: data_status
    "available", offers_complete exactly True, claimed_offer_count
    exactly 0, and offers_returned exactly 0. Every other empty,
    partial, failed, unavailable, malformed, or absent offer-list case
    leaves seller counts null and carries a roster reason
    (offer_roster_unavailable | partial_offer_roster |
    no_explicit_zero_offer_evidence).
  - When actual returned offer rows exist (data_status available or
    partial), counts are observed facts derived from those rows only;
    an observed zero (e.g. no prime offers among the returned rows) is
    real evidence, not a placeholder.
  - Only actual returned offer rows are counted. claimed_offer_count
    and offers_complete travel together: an incomplete roster is never
    labeled as the total marketplace seller set.
  - Landed prices are only derived when the local offer row supports
    them: offers carry a free-shipping flag, never a shipping amount,
    so landed price = offer price only when shipping_is_free is True.
  - estimated_units_per_observed_* requires BOTH an estimated monthly
    sales figure AND a positive observed count for that fulfillment
    type. No denominator-of-one substitution; zero or unknown keeps the
    field Unknown (never 0).
  - This module writes nothing and never calls a provider.
"""

from typing import Any, Dict, List, Optional

SHARE_DISCLAIMER = (
    "Estimated allocation only. Total sales are divided across observed "
    "seller offers. Buy Box rotation, stock levels, pricing, reviews, "
    "fulfillment, seller eligibility, and incomplete offer coverage may "
    "materially change actual share."
)

PARTIAL_SAMPLE_WARNING = "Based on partial returned offer sample."

OBSERVABLE_STATUSES = ("available", "partial")

# Roster state reasons for unknown/absent offer lists.
REASON_ROSTER_UNAVAILABLE = "offer_roster_unavailable"
REASON_PARTIAL_ROSTER = "partial_offer_roster"
REASON_NO_ZERO_EVIDENCE = "no_explicit_zero_offer_evidence"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _price_value(price: Any) -> Optional[float]:
    """Offer price may be a number or a {value: ...} dict (Easyparser
    normalizes to the dict form); mirror offer_enrichment behavior."""
    if isinstance(price, dict):
        value = price.get("value")
        if not _is_number(value):
            return None
        return float(value)
    if _is_number(price):
        return float(price)
    return None


def _positive_number(value: Any) -> Optional[float]:
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _exactly_zero(value: Any) -> bool:
    return _is_number(value) and value == 0


def _offer_landed(offer: Dict) -> Optional[float]:
    """Landed price for one offer row, or None when the row cannot
    support it (no shipping amount is ever parsed: only free-shipping
    offers have a known landed price equal to their offer price)."""
    price = _price_value(offer.get("price"))
    if price is None:
        return None
    if offer.get("shipping_is_free") is True:
        return price
    return None


def explicit_zero_offer_evidence(snapshot: Dict) -> bool:
    """True only when the provider explicitly reports a complete
    zero-offer set (available + offers_complete True + claimed 0 +
    returned 0). Nothing else authorizes a 0 seller count."""
    stored = snapshot.get("seller_counts") or {}
    return (
        snapshot.get("data_status") == "available"
        and snapshot.get("offers_complete") is True
        and _exactly_zero(stored.get("claimed_total"))
        and _exactly_zero(snapshot.get("offers_returned"))
    )


def roster_state(snapshot: Dict, offers: List[Dict]) -> tuple:
    """(state, reason) for the offer roster.

    state: "rows" (observed offers exist), "zero" (explicit complete
    zero-offer proof), or None (unknown roster). reason is one of the
    roster reasons only when state is None; otherwise None.
    """
    status = snapshot.get("data_status")
    if status not in OBSERVABLE_STATUSES:
        return None, REASON_ROSTER_UNAVAILABLE
    if offers:
        return "rows", None
    if explicit_zero_offer_evidence(snapshot):
        return "zero", None
    if status == "partial":
        return None, REASON_PARTIAL_ROSTER
    return None, REASON_NO_ZERO_EVIDENCE


def observed_counts(snapshot: Dict, state: str, offers: List[Dict]) -> Dict:
    """Observed seller counts.

    "rows": counts derived from the actual returned offer rows (an
    observed zero among real rows is real evidence). "zero": explicit
    complete zero-offer proof — all counts are 0. None state: all
    counts null (never 0), with the roster reason surfaced.
    """
    stored = snapshot.get("seller_counts") or {}
    complete = snapshot.get("offers_complete") is True
    returned = snapshot.get("offers_returned")
    claimed = stored.get("claimed_total")

    if state == "rows":
        fba = sum(1 for o in offers if o.get("is_fba") is True)
        fbm = sum(1 for o in offers if o.get("is_fbm") is True)
        amazon = sum(
            1
            for o in offers
            if o.get("is_sba") is True
            or (o.get("seller_name") or "").strip().lower() == "amazon"
        )
        return {
            "observed_total_sellers": len(offers),
            "observed_fba_sellers": fba,
            "observed_fbm_sellers": fbm,
            "observed_amazon_sellers": amazon,
            "claimed_offer_count": claimed,
            "offers_returned": returned,
            "offers_complete": complete,
            "counts_from_observed": True,
        }
    if state == "zero":
        return {
            "observed_total_sellers": 0,
            "observed_fba_sellers": 0,
            "observed_fbm_sellers": 0,
            "observed_amazon_sellers": 0,
            "claimed_offer_count": 0,
            "offers_returned": 0,
            "offers_complete": True,
            "counts_from_observed": True,
        }
    return {
        "observed_total_sellers": None,
        "observed_fba_sellers": None,
        "observed_fbm_sellers": None,
        "observed_amazon_sellers": None,
        "claimed_offer_count": claimed,
        "offers_returned": returned,
        "offers_complete": complete,
        "counts_from_observed": True,
    }


def _buy_box_fields(snapshot: Dict) -> Dict:
    buy_box = snapshot.get("buy_box") or {}
    price = _price_value(buy_box.get("price"))
    return {
        "observed_buy_box_available": buy_box.get("available") is True,
        "observed_buy_box_price": price,
        "observed_buy_box_shipping": _price_value(buy_box.get("shipping")),
        "observed_buy_box_landed_price": _price_value(buy_box.get("landed_price")),
        "observed_buy_box_seller": buy_box.get("seller_name"),
        "observed_buy_box_fulfillment": buy_box.get("fulfillment"),
        "observed_buy_box_condition": buy_box.get("condition"),
    }


def _offer_price_fields(offers: List[Dict]) -> Dict:
    prices = [_price_value(o.get("price")) for o in offers]
    prices = [p for p in prices if p is not None]
    landed = [_offer_landed(o) for o in offers]
    landed = [p for p in landed if p is not None]
    lowest = min(prices) if prices else None
    highest = max(prices) if prices else None
    lowest_landed = min(landed) if landed else None
    highest_landed = max(landed) if landed else None
    return {
        "lowest_returned_offer_price": lowest,
        "lowest_returned_landed_price": lowest_landed,
        "highest_returned_landed_price": highest_landed,
        "returned_offer_price_spread": (
            round(highest - lowest, 2) if lowest is not None and highest is not None else None
        ),
        "returned_offer_landed_spread": (
            round(highest_landed - lowest_landed, 2)
            if lowest_landed is not None and highest_landed is not None
            else None
        ),
        "prime_offer_count": sum(1 for o in offers if o.get("is_prime") is True),
        "fulfilled_by_amazon_offer_count": sum(
            1 for o in offers if o.get("fulfilled_by_amazon") is True or o.get("is_fba") is True
        ),
    }


def seller_share_fields(
    estimated_monthly_sales: Any,
    counts: Dict,
    state: str,
) -> Dict:
    """Estimated units per observed seller, honest share attribution.

    Requires both an estimated monthly sales figure and a positive
    observed count for the fulfillment type. Neither is ever substituted
    (no denominator-of-one); missing input -> Unknown. Incomplete
    rosters lower the confidence tier and carry the partial-sample
    warning; the share is never labeled as the total marketplace.
    Unknown rosters never produce a share, a confidence, or a basis.
    """
    est = _positive_number(estimated_monthly_sales)
    fields: Dict = {
        "estimated_units_per_observed_fba_seller": None,
        "estimated_units_per_observed_fbm_seller": None,
        "estimated_units_per_observed_seller": None,
        "seller_share_confidence": None,
        "seller_share_basis": None,
        "offer_competition_note": None,
        "seller_share_note": None,
    }
    if est is None:
        return fields

    if state == "zero":
        fields["seller_share_confidence"] = "medium"
        fields["seller_share_basis"] = "complete zero-offer set"
        fields["seller_share_note"] = SHARE_DISCLAIMER
        return fields

    if state != "rows":
        return fields

    returned = counts.get("offers_returned")
    if isinstance(returned, bool) or not isinstance(returned, (int, float)):
        returned = None
    complete = counts.get("offers_complete") is True
    if complete:
        basis = (
            "complete returned offer set (%s)" % int(returned)
            if returned is not None
            else "complete returned offer set"
        )
        confidence = "medium"
    else:
        basis = (
            "observed returned offer sample (%s of %s)"
            % (int(returned), int(counts["claimed_offer_count"]))
            if returned is not None and _is_number(counts.get("claimed_offer_count"))
            else "observed returned offer sample"
        )
        confidence = "low"

    def _per(denominator):
        denom = _positive_number(denominator)
        if denom is None:
            return None
        return round(est / denom, 1)

    fields["estimated_units_per_observed_fba_seller"] = _per(counts.get("observed_fba_sellers"))
    fields["estimated_units_per_observed_fbm_seller"] = _per(counts.get("observed_fbm_sellers"))
    fields["estimated_units_per_observed_seller"] = _per(counts.get("observed_total_sellers"))
    fields["seller_share_confidence"] = confidence
    fields["seller_share_basis"] = basis
    if not complete:
        fields["offer_competition_note"] = PARTIAL_SAMPLE_WARNING
        fields["seller_share_note"] = PARTIAL_SAMPLE_WARNING + " " + SHARE_DISCLAIMER
    else:
        fields["seller_share_note"] = SHARE_DISCLAIMER
    return fields


def competition_fields(snapshot: Dict, estimated_monthly_sales: Any = None) -> Dict:
    """Full competition field set for one snapshot.

    Roster states:
      - rows: observed facts from the actual returned offer rows.
      - zero: explicit complete zero-offer proof — all counts 0.
      - unknown (empty/partial-zero/failed/unavailable/malformed/
        absent): seller counts null (never 0), a roster reason in
        offer_roster_reason and competition_data_gaps, and null share.
    """
    offers = [o for o in (snapshot.get("offers") or []) if isinstance(o, dict)]
    state, reason = roster_state(snapshot, offers)
    counts = observed_counts(snapshot, state, offers)

    fields = {
        **counts,
        **_buy_box_fields(snapshot),
        **({"offer_roster_reason": reason} if reason else {}),
        **({"competition_data_gaps": [reason]} if reason else {}),
    }
    if state == "rows":
        fields.update(_offer_price_fields(offers))
    else:
        # Explicit complete zero-offer proof authorizes zero offer-level
        # counts; any unknown roster keeps them null (never 0).
        fields.update(
            {
                "lowest_returned_offer_price": None,
                "lowest_returned_landed_price": None,
                "highest_returned_landed_price": None,
                "returned_offer_price_spread": None,
                "returned_offer_landed_spread": None,
                "prime_offer_count": 0 if state == "zero" else None,
                "fulfilled_by_amazon_offer_count": 0 if state == "zero" else None,
            }
        )
    fields.update(seller_share_fields(estimated_monthly_sales, counts, state))
    return fields