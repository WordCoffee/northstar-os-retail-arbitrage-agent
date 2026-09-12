import finance


def compute_profit(amazon_price, costco_cost, referral_rate=0.15, fba_fee=0.0, fuel_rate=0.035, inbound_cost=0.35):
    referral_fee = referral_rate * amazon_price
    fuel_surcharge = fuel_rate * fba_fee
    net_profit = amazon_price - costco_cost - referral_fee - fba_fee - fuel_surcharge - inbound_cost
    roi_pct = (net_profit / costco_cost) * 100 if costco_cost > 0 else 0.0
    return net_profit, roi_pct


def estimate_financial_profile(
    amazon_price,
    weight_lbs,
    costco_cost,
    prep_cost=None,
    inbound_shipping_cost=None,
    referral_rate=None,
    referral_fee=None,
):
    """Build a finance.project_finances record from explicitly supplied inputs.

    No value is silently defaulted into the calculation:
      - prep cost: used only when explicitly supplied (prep_cost=0.0 is a
        valid explicit zero; an omitted prep cost stays None)
      - inbound shipping cost: used only when explicitly supplied
      - referral fee: referral_fee, or referral_rate applied to the sale
        price; omitted when neither is explicitly supplied
      - FBA fulfillment fee: estimate_fba_fee(weight_lbs) as before
    Omitted inputs stay None so the finance engine reports
    need_cost_data / need_fee_data instead of a silently computed profit,
    and projected_net_profit / projected_roi_pct stay None.
    Explicitly supplied planning assumptions are documented in
    financial_data_gaps. An Amazon price that is missing or <= 0 is
    treated as unknown (never $0.00).
    """
    is_num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    sale_price = amazon_price if is_num(amazon_price) and amazon_price > 0 else None

    if is_num(referral_fee):
        referral = referral_fee
    elif is_num(referral_rate) and is_num(sale_price):
        referral = referral_rate * sale_price
    else:
        referral = None

    fba_fee = estimate_fba_fee(weight_lbs) if is_num(weight_lbs) else None

    result = finance.project_finances(
        amazon_sale_price=sale_price,
        referral_fee=referral,
        fba_fulfillment_fee=fba_fee,
        cogs=costco_cost,
        prep_cost=prep_cost,
        inbound_shipping_cost=inbound_shipping_cost,
    )

    assumption_gaps = []
    if is_num(prep_cost) and prep_cost >= 0:
        assumption_gaps.append(
            f"Prep cost uses a user-entered planning assumption: ${prep_cost:.2f}/unit."
        )
    if is_num(inbound_shipping_cost) and inbound_shipping_cost >= 0:
        assumption_gaps.append(
            f"Inbound cost uses a user-entered planning assumption: ${inbound_shipping_cost:.2f}/unit."
        )
    if is_num(referral_rate) and is_num(referral) and referral >= 0:
        assumption_gaps.append(
            f"Referral fee uses a user-entered planning assumption: {referral_rate * 100:.2f}%."
        )
    elif is_num(referral_fee) and referral_fee >= 0:
        assumption_gaps.append(
            f"Referral fee uses a user-entered planning assumption: ${referral_fee:.2f}."
        )

    if assumption_gaps:
        result["financial_data_gaps"] = result["financial_data_gaps"] + assumption_gaps

    return result


def estimate_fba_fee(weight_lbs):
    if weight_lbs <= 0.5:
        return 4.75
    if weight_lbs <= 1:
        return 5.25
    if weight_lbs <= 2:
        return 6.10
    if weight_lbs <= 3:
        return 7.10
    if weight_lbs <= 5:
        return 8.20
    if weight_lbs <= 10:
        return 9.90
    if weight_lbs <= 20:
        return 12.50
    return 15.00


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def screen_by_profit_tier(candidates, tiers=(11, 9, 7)):
    for threshold in tiers:
        matches = [
            c for c in candidates
            if _is_number(c.get("net_profit")) and c["net_profit"] >= threshold
        ]
        if matches:
            return threshold, matches
    return None, []