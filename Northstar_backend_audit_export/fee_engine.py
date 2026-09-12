"""Versioned Amazon US fee engine for the Northstar Scout.

Calculations only — no network. Rules are loaded from
amazon_us_fee_rules_2026.py (data only, versioned). The engine never
invents values: when an input is missing the result field is None and
the status/confidence/note explain exactly what is missing and what to
verify.

Public API:
  calculate_referral_fee(sale_price, amazon_category=None, browse_node=None)
  calculate_fba_fulfillment_fee(package_weight_lbs, package_dimensions_in,
                                sale_price, product_category)
  calculate_unit_costs()
  calculate_unit_economics(product, costco)

Honesty rules (spec):
  - missing values stay None / JSON null, never 0 or $0.00
  - 0.00 is only ever an explicit configured value (env), never a guess
  - every result carries confidence / status / note provenance
  - no category data -> default Everything Else 15% with an explicit
    "verify in Seller Central" note (confidence=default_category)
"""

import os

from dotenv import load_dotenv

from amazon_us_fee_rules_2026 import (
    DEFAULT_PACKAGING_COST_PER_UNIT,
    DEFAULT_INBOUND_COST_PER_UNIT,
    DEFAULT_PREP_COST_PER_UNIT,
    DEFAULT_RETURN_RESERVE_RATE,
    DEFAULT_REFERRAL_CATEGORY,
    DEFAULT_REFERRAL_RATE,
    FBA_LOGISTICS_SURCHARGE_RATE,
    FBA_SMALL_OVERSIZE_MAX_WEIGHT_LBS,
    FBA_SIZE_TIER_TABLE,
    FBA_STANDARD_MAX_DIMENSIONS_IN,
    FBA_STANDARD_MAX_WEIGHT_LBS,
    REFERRAL_BROWSE_NODE_MAP,
    REFERRAL_RULES,
    RULES_VERSION,
)

load_dotenv()

# Confidence / status vocabularies (stable strings; UI renders these).
REFERRAL_CONFIDENCE_VERIFIED = "verified_category"
REFERRAL_CONFIDENCE_DEFAULT = "default_category"
REFERRAL_CONFIDENCE_UNAVAILABLE = "unavailable"

FBA_CONFIDENCE_TABLE = "table_estimate"
FBA_CONFIDENCE_LISTING = "listing_reported"
FBA_CONFIDENCE_UNAVAILABLE = "unavailable"

FBA_STATUS_AVAILABLE = "available"
FBA_STATUS_WEIGHT_UNAVAILABLE = "weight_unavailable"
FBA_STATUS_DIMENSIONS_UNAVAILABLE = "dimensions_unavailable"
FBA_STATUS_SIZE_TIER_UNAVAILABLE = "size_tier_unavailable"
FBA_STATUS_NEEDS_VERIFICATION = "needs_revenue_calculator_verification"

ECON_ESTIMATED = "estimated"
ECON_PROVISIONAL = "provisional"
ECON_UNAVAILABLE = "unavailable"

ECON_STATUS_ESTIMATED = "estimated_fee_stack"
ECON_STATUS_NEEDS_FEE_VERIFICATION = "needs_fee_verification"
ECON_STATUS_MISSING_PRICE = "missing_amazon_price"
ECON_STATUS_MISSING_COGS = "missing_costco_cogs"

COST_BASIS_INVOICE_CONFIRMED = "invoice_confirmed"
COST_BASIS_COSTCO_ONLINE = "costco_online"
COST_BASIS_ESTIMATED = "estimated"
COST_BASIS_UNAVAILABLE = "unavailable"


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_price(value):
    """Positive numeric price, else None. Never coerces strings."""
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _rule_id(category):
    return f"REF-{RULES_VERSION}-{category}"


def _resolve_category(amazon_category, browse_node, source_hint=None):
    """Category resolution: browse node first (most specific signal), then
    exact name/key/alias match. Never invents a category: returns
    (category, confidence, note, source).

    source_hint records where the category text came from upstream
    ("breadcrumb" from the Bright Data product-page parser,
    "structured_category" for provider-verified metadata, or None). A
    breadcrumb-derived match is verified for the RULE it maps to but
    carries the inferred caveat in the resolution metadata.
    """
    if _is_number(browse_node) and int(browse_node) in REFERRAL_BROWSE_NODE_MAP:
        category = REFERRAL_BROWSE_NODE_MAP[int(browse_node)]
        return category, REFERRAL_CONFIDENCE_VERIFIED, (
            f"Category '{category}' matched via browse node {int(browse_node)}."
        ), "browse_node"
    if amazon_category is not None and str(amazon_category).strip():
        name = str(amazon_category).strip()
        if name in REFERRAL_RULES:
            source = source_hint or "structured_category"
            note = f"Category '{name}' matched exactly."
            if source == "breadcrumb":
                note += " Resolved from Amazon page breadcrumbs; confirm the exact category in Seller Central."
            return name, REFERRAL_CONFIDENCE_VERIFIED, note, source
        folded = " ".join(name.lower().split())
        for category, rule in REFERRAL_RULES.items():
            if folded in [a for a in (rule.get("aliases") or [])] or folded == category.lower():
                source = source_hint or "structured_category"
                note = f"Category '{name}' matched rule '{category}'."
                if source == "breadcrumb":
                    note += " Resolved from Amazon page breadcrumbs; confirm the exact category in Seller Central."
                return category, REFERRAL_CONFIDENCE_VERIFIED, note, source
        return DEFAULT_REFERRAL_CATEGORY, REFERRAL_CONFIDENCE_DEFAULT, (
            f"Category '{name}' is not on the {RULES_VERSION} schedule; "
            f"default '{DEFAULT_REFERRAL_CATEGORY}' {DEFAULT_REFERRAL_RATE:.0%} "
            "applied. Verify the exact category in Seller Central."
        ), "default"
    return DEFAULT_REFERRAL_CATEGORY, REFERRAL_CONFIDENCE_DEFAULT, (
        "No Amazon category / browse node available for this listing; default "
        f"'{DEFAULT_REFERRAL_CATEGORY}' {DEFAULT_REFERRAL_RATE:.0%} applied. "
        "Verify the exact category in Seller Central."
    ), "default"


def _resolution_metadata(source, note):
    """category_resolution_* provenance for the resolved source."""
    if source in ("browse_node", "structured_category"):
        confidence = "verified"
    elif source == "breadcrumb":
        confidence = "inferred"
    elif source == "default":
        confidence = "default"
    else:
        confidence = "unavailable"
    return source, confidence, note


def _compute_rule_amount(price, rule, category):
    """Raw referral amount for a resolved rule (before min-fee floor)."""
    rule_type = rule.get("type")
    if rule_type == "two_rate":
        cap = rule["cap"]
        amount = rule["rate"] * min(price, cap) + rule["over_cap_rate"] * max(0.0, price - cap)
        return amount, f"{rule['rate']:.0%} up to ${cap:,.0f} + {rule['over_cap_rate']:.0%} above"
    if rule_type == "price_switch":
        low_max = rule["low_price_max"]
        rate = rule["low_rate"] if price <= low_max else rule["high_rate"]
        return price * rate, (
            f"{rule['low_rate']:.0%} at/below ${low_max:,.2f}, "
            f"{rule['high_rate']:.0%} above"
        )
    if rule_type == "progressive":
        amount = 0.0
        tiers = rule["tiers"]
        prev = 0.0
        for cap, rate in tiers:
            if price > prev:
                amount += rate * (min(price, cap) - prev)
            prev = cap
        if price > prev:
            amount += rule["top_rate"] * (price - prev)
        bracket = " / ".join(f"{r:.0%} up to ${c:,.2f}" for c, r in tiers)
        return amount, f"{bracket} / {rule['top_rate']:.0%} above ${prev:,.2f}"
    return price * rule.get("rate", DEFAULT_REFERRAL_RATE), (
        f"{rule.get('rate', DEFAULT_REFERRAL_RATE):.0%} of sale price"
    )


def calculate_referral_fee(sale_price, amazon_category=None, browse_node=None, category_source_hint=None):
    """Referral fee for a sale price under the versioned 2026 rules.

    Returns a dict with referral_fee, referral_fee_rate (effective
    blended rate = fee / price), referral_fee_category,
    referral_fee_confidence, referral_fee_rule, referral_fee_tier,
    referral_fee_note, browse_node_id and the category_resolution_*
    provenance (source / confidence / note). When the sale price is
    missing the referral fee is None with confidence 'unavailable' —
    never invented.
    """
    price = _as_price(sale_price)
    if price is None:
        return {
            "referral_fee": None,
            "referral_fee_rate": None,
            "referral_fee_category": None,
            "referral_fee_confidence": REFERRAL_CONFIDENCE_UNAVAILABLE,
            "referral_fee_rule": None,
            "referral_fee_tier": None,
            "referral_fee_note": "No sale price; referral fee unavailable.",
            "browse_node_id": None,
            "category_resolution_source": "unavailable",
            "category_resolution_confidence": "unavailable",
            "category_resolution_note": None,
        }

    category, confidence, note, source = _resolve_category(
        amazon_category, browse_node, source_hint=category_source_hint
    )
    rule = REFERRAL_RULES[category]
    amount, tier = _compute_rule_amount(price, rule, category)
    min_fee = rule.get("min_fee")
    fee = max(amount, min_fee) if min_fee is not None else amount

    source, res_confidence, res_note = _resolution_metadata(source, note)

    return {
        "referral_fee": round(fee, 2),
        "referral_fee_rate": round(fee / price, 4) if price > 0 else None,
        "referral_fee_category": category,
        "referral_fee_confidence": confidence,
        "referral_fee_rule": _rule_id(category),
        "referral_fee_tier": tier,
        "referral_fee_note": note,
        "browse_node_id": int(browse_node) if _is_number(browse_node) else None,
        "category_resolution_source": source,
        "category_resolution_confidence": res_confidence,
        "category_resolution_note": res_note,
    }


def _standard_band_fee(weight_lbs):
    """All-in standard-size fee from the versioned table (None if the
    weight exceeds the standard-size limit)."""
    for max_weight, fee in FBA_SIZE_TIER_TABLE:
        if weight_lbs <= max_weight:
            return fee
    return None


def _split_fba_components(total):
    """Split an all-in FBA total into base + 3.5% fuel/logistics surcharge.
    base + surcharge == total after rounding."""
    base = round(total / (1.0 + FBA_LOGISTICS_SURCHARGE_RATE), 2)
    surcharge = round(total - base, 2)
    return base, surcharge


def _normalize_dimensions(package_dimensions_in):
    """Accepts a 3-tuple of numeric inches (or None). Returns a sorted
    tuple or None. Never parses strings."""
    if package_dimensions_in is None:
        return None
    try:
        dims = tuple(float(d) for d in package_dimensions_in)
    except (TypeError, ValueError):
        return None
    if len(dims) != 3 or any(d <= 0 for d in dims):
        return None
    return tuple(sorted(dims))


def calculate_fba_fulfillment_fee(
    package_weight_lbs,
    package_dimensions_in,
    sale_price,
    product_category=None,
):
    """FBA fulfillment fee estimate from the versioned 2026 standard-size
    table (all-in published rates; base + 3.5% fuel/logistics surcharge
    reported separately).

    Prefers package/shipping weight; dimensions are used only to detect
    oversize packages. Missing weight -> weight_unavailable. Oversize
    packages are outside the table -> needs_revenue_calculator_verification
    (fee None, never guessed). sale_price is accepted for interface
    stability and used only in notes (no value-based component in the
    standard-size table).
    """
    price = _as_price(sale_price)
    weight = _as_price(package_weight_lbs)
    dims = _normalize_dimensions(package_dimensions_in)
    category = str(product_category or "").strip() or None

    def unavailable(status, note, weight_basis=None, size_tier=None):
        return {
            "fba_fee": None,
            "fba_base_fee": None,
            "fba_fuel_logistics_surcharge": None,
            "fba_size_tier": size_tier,
            "fba_weight_basis_lbs": weight_basis,
            "fba_fee_status": status,
            "fba_fee_confidence": FBA_CONFIDENCE_UNAVAILABLE,
            "fba_fee_rule": f"FBA-{RULES_VERSION}",
            "fba_fee_note": note,
        }

    if weight is None:
        return unavailable(
            FBA_STATUS_WEIGHT_UNAVAILABLE,
            "No package/shipping weight available; FBA fulfillment fee "
            "cannot be estimated. Verify in the Amazon Revenue Calculator.",
        )

    if dims is None:
        if weight > FBA_STANDARD_MAX_WEIGHT_LBS:
            return unavailable(
                FBA_STATUS_SIZE_TIER_UNAVAILABLE,
                f"Weight {weight:.2f} lb exceeds the standard-size limit "
                f"({FBA_STANDARD_MAX_WEIGHT_LBS:.0f} lb); fee outside the "
                "versioned table. Verify in the Amazon Revenue Calculator.",
                weight_basis=round(weight, 2),
            )
        total = _standard_band_fee(weight)
        if total is None:
            return unavailable(
                FBA_STATUS_SIZE_TIER_UNAVAILABLE,
                "No fee band for this weight in the versioned table; verify "
                "in the Amazon Revenue Calculator.",
                weight_basis=round(weight, 2),
            )
        base, surcharge = _split_fba_components(total)
        note = (
            f"Package dimensions not provided; assumed standard-size "
            f"(within {FBA_STANDARD_MAX_DIMENSIONS_IN[0]:.0f} x "
            f"{FBA_STANDARD_MAX_DIMENSIONS_IN[1]:.0f} x "
            f"{FBA_STANDARD_MAX_DIMENSIONS_IN[2]:.0f} in) at "
            f"{weight:.2f} lb. All-in published rate incl. "
            f"{FBA_LOGISTICS_SURCHARGE_RATE:.1%} fuel/logistics surcharge."
        )
        if category:
            note += f" Category '{category}' uses the standard-size table."
        return {
            "fba_fee": total,
            "fba_base_fee": base,
            "fba_fuel_logistics_surcharge": surcharge,
            "fba_size_tier": "standard",
            "fba_weight_basis_lbs": round(weight, 2),
            "fba_fee_status": FBA_STATUS_AVAILABLE,
            "fba_fee_confidence": FBA_CONFIDENCE_TABLE,
            "fba_fee_rule": f"FBA-{RULES_VERSION}",
            "fba_fee_note": note,
        }

    if any(d > m for d, m in zip(dims, tuple(sorted(FBA_STANDARD_MAX_DIMENSIONS_IN)))):
        tier = "small_oversize" if weight <= FBA_SMALL_OVERSIZE_MAX_WEIGHT_LBS else "large_oversize"
        return unavailable(
            FBA_STATUS_NEEDS_VERIFICATION,
            f"Package {dims[2]:.1f} x {dims[1]:.1f} x {dims[0]:.1f} in "
            f"({weight:.2f} lb) is {tier}; outside the versioned "
            "standard-size table. Verify in the Amazon Revenue Calculator.",
            weight_basis=round(weight, 2),
            size_tier=tier,
        )

    total = _standard_band_fee(weight)
    if total is None:
        return unavailable(
            FBA_STATUS_SIZE_TIER_UNAVAILABLE,
            "No fee band for this weight in the versioned table; verify in "
            "the Amazon Revenue Calculator.",
            weight_basis=round(weight, 2),
            size_tier="standard",
        )
    base, surcharge = _split_fba_components(total)
    return {
        "fba_fee": total,
        "fba_base_fee": base,
        "fba_fuel_logistics_surcharge": surcharge,
        "fba_size_tier": "standard",
        "fba_weight_basis_lbs": round(weight, 2),
        "fba_fee_status": FBA_STATUS_AVAILABLE,
        "fba_fee_confidence": FBA_CONFIDENCE_TABLE,
        "fba_fee_rule": f"FBA-{RULES_VERSION}",
        "fba_fee_note": (
            f"Standard-size {weight:.2f} lb, package within "
            f"{FBA_STANDARD_MAX_DIMENSIONS_IN[0]:.0f} x "
            f"{FBA_STANDARD_MAX_DIMENSIONS_IN[1]:.0f} x "
            f"{FBA_STANDARD_MAX_DIMENSIONS_IN[2]:.0f} in. All-in published "
            f"rate incl. {FBA_LOGISTICS_SURCHARGE_RATE:.1%} fuel/logistics "
            "surcharge."
        ),
    }


def calculate_unit_costs():
    """Unit costs / rates from env with versioned defaults. 0.00 values
    are explicit configured zeros, never guesses."""
    def env_float(key, default):
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return {
        "inbound_cost_per_unit": env_float("INBOUND_COST_PER_UNIT", DEFAULT_INBOUND_COST_PER_UNIT),
        "prep_cost_per_unit": env_float("PREP_COST_PER_UNIT", DEFAULT_PREP_COST_PER_UNIT),
        "packaging_cost_per_unit": env_float("PACKAGING_COST_PER_UNIT", DEFAULT_PACKAGING_COST_PER_UNIT),
        "return_reserve_rate": env_float("RETURN_RESERVE_RATE", DEFAULT_RETURN_RESERVE_RATE),
    }


def calculate_unit_economics(product, costco):
    """Full per-unit economics for one product against its Costco cost.

    product keys: amazon_price, amazon_category, browse_node,
                  category_source_hint, package_weight_lbs,
                  item_weight_lbs, package_dimensions_in,
                  listing_fba_fee
    costco keys:  costco_cost, costco_cost_basis

    Tiers:
      estimated  — price + COGS + full fee stack (referral, FBA incl.
                   3.5% surcharge, inbound, prep, packaging, return
                   reserve). roi = net / cogs * 100.
      provisional — price + COGS + the stack WITHOUT the FBA fee
                   (fba fee not verified yet). The note says the fee is
                   excluded and must be verified before purchasing.
      unavailable — missing sale price (missing_amazon_price) or missing
                   Costco cost (missing_costco_cogs). net_profit and
                   roi_pct stay None — never 0.
    """
    price = _as_price(product.get("amazon_price"))
    cogs = _as_price(costco.get("costco_cost"))
    basis = costco.get("costco_cost_basis") or COST_BASIS_UNAVAILABLE

    category = product.get("amazon_category")
    referral = calculate_referral_fee(
        price,
        category,
        product.get("browse_node"),
        category_source_hint=product.get("category_source_hint"),
    )

    weight = _as_price(product.get("package_weight_lbs"))
    if weight is None:
        weight = _as_price(product.get("item_weight_lbs"))
    fba = calculate_fba_fulfillment_fee(
        package_weight_lbs=weight,
        package_dimensions_in=product.get("package_dimensions_in"),
        sale_price=price,
        product_category=category,
    )

    listing_fee = _as_price(product.get("listing_fba_fee"))
    if listing_fee is not None:
        base, surcharge = _split_fba_components(listing_fee)
        fba = dict(fba)
        fba["fba_fee"] = listing_fee
        fba["fba_base_fee"] = base
        fba["fba_fuel_logistics_surcharge"] = surcharge
        fba["fba_fee_status"] = FBA_STATUS_AVAILABLE
        fba["fba_fee_confidence"] = FBA_CONFIDENCE_LISTING
        fba["fba_fee_note"] = (
            f"FBA fee {listing_fee:.2f} USD reported by the listing/offer "
            "data provider; used for unit economics. Split into base + "
            f"{FBA_LOGISTICS_SURCHARGE_RATE:.1%} fuel/logistics surcharge "
            "for display."
        )

    unit = calculate_unit_costs()
    out = {
        # The category actually used for the referral rule (resolved). When
        # no price exists the referral stays unavailable and this is None.
        "amazon_category": referral["referral_fee_category"],
        "costco_cogs": round(cogs, 2) if cogs is not None else None,
        "costco_cost_basis": basis,
        **referral,
        **fba,
        **unit,
        "net_profit": None,
        "roi_pct": None,
        "economics_confidence": ECON_UNAVAILABLE,
        "economics_status": None,
        "economics_note": None,
    }

    if price is None:
        out["economics_status"] = ECON_STATUS_MISSING_PRICE
        out["economics_note"] = (
            "No Amazon sale price available; unit economics unavailable. "
            "Net profit / ROI cannot be calculated — never estimated."
        )
        return out

    if cogs is None:
        out["economics_status"] = ECON_STATUS_MISSING_COGS
        out["economics_note"] = (
            "No Costco cost on record for this item; unit economics "
            "unavailable (ROI needs the cost basis). Add an "
            "item_name,costco_cost row to data/costco-items.csv."
        )
        return out

    return_reserve = price * unit["return_reserve_rate"]

    if fba["fba_fee"] is not None:
        net = round((
            price
            - cogs
            - referral["referral_fee"]
            - fba["fba_fee"]
            - unit["inbound_cost_per_unit"]
            - unit["prep_cost_per_unit"]
            - unit["packaging_cost_per_unit"]
            - return_reserve
        ), 2)
        out["net_profit"] = net
        out["roi_pct"] = round(net / cogs * 100.0, 2) if cogs > 0 else None
        out["economics_confidence"] = ECON_ESTIMATED
        out["economics_status"] = ECON_STATUS_ESTIMATED
        out["economics_note"] = (
            "All costs included: referral fee, FBA fulfillment (incl. "
            f"{FBA_LOGISTICS_SURCHARGE_RATE:.1%} fuel/logistics surcharge), "
            f"inbound ${unit['inbound_cost_per_unit']:.2f}, prep "
            f"${unit['prep_cost_per_unit']:.2f}, packaging "
            f"${unit['packaging_cost_per_unit']:.2f}, return reserve "
            f"{unit['return_reserve_rate']:.0%} of sale price. Estimated."
        )
        return out

    net = round((
        price
        - cogs
        - referral["referral_fee"]
        - unit["inbound_cost_per_unit"]
        - unit["prep_cost_per_unit"]
        - unit["packaging_cost_per_unit"]
        - return_reserve
    ), 2)
    out["net_profit"] = net
    out["roi_pct"] = round(net / cogs * 100.0, 2) if cogs > 0 else None
    out["economics_confidence"] = ECON_PROVISIONAL
    out["economics_status"] = ECON_STATUS_NEEDS_FEE_VERIFICATION
    out["economics_note"] = (
        "PROVISIONAL — the FBA fulfillment fee is not yet verified and is "
        "EXCLUDED from these numbers. Referral fee, inbound, prep, "
        f"packaging and {unit['return_reserve_rate']:.0%} return reserve "
        "are included. Verify the FBA fee in Seller Central / the Amazon "
        "Revenue Calculator before purchasing; do not treat this as final."
    )
    return out