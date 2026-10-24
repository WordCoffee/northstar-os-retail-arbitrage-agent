# Costco Research Requirements Profile

- Version: costco-research-requirements-v1
- Generated: 2026-09-27T20:54:15.346808+00:00
- Defaults: offline_only=True, bright_data_enabled=False

| Rule | Value | Class |
|------|-------|-------|
| preferred_sources | ["costco", "costco_business_center"] | verified_current_rule |
| alternate_wholesale_leads_allowed | true | operator_preference |
| invoice_readiness_required_for_sourcing | true | verified_current_rule |
| non_kirkland_required | true | verified_current_rule |
| identifier_required_for_exact_match | "upc/ean/gtin OR mpn+brand" | verified_current_rule |
| costco_item_number_is_not_upc_gtin_mpn_asin | true | verified_current_rule |
| weight_max_lb | 3.0 | verified_current_rule |
| standard_size_preferred | true | operator_preference |
| unknown_source_weight_allowed | "provisional_only_no_auto_qualify" | verified_current_rule |
| split_pack_rule | "approved_split|intact_only|manual_review|prohibited|unknown" | verified_current_rule |
| amazon_retail_rule | "must_be_provider_reported_absent" | verified_current_rule |
| brand_seller_rule | "provider_reported_absent_when_available" | verified_current_rule |
| fba_sellers_max | 0 | verified_current_rule |
| mfn_sellers_min | 3 | verified_current_rule |
| demand_min_est_monthly_units | 500 | operator_preference |
| min_net_profit | 5.0 | verified_current_rule |
| min_roi_pct | 30.0 | verified_current_rule |
| preferred_net_profit | 11.0 | operator_preference |
| priority_net_profit | 20.0 | operator_preference |
| margin_min_pct | 20.0 | proposed_default |
| source_freshness_max_minutes | 60 | proposed_default |
| provider_freshness_max_minutes | 60 | proposed_default |
| purchase_authorization | "not_authorized_by_default" | verified_current_rule |
| evidence_provenance_required | true | verified_current_rule |
| cosmetics_exception | "excluded_by_default; no exception in first runs" | operator_preference |
| excluded_classes | ["food", "grocery", "beverage", "supplement", "otc_drug", "nicotine", "cosmetics", "skincare", "haircare", "fragrance", "topical_beauty", "collectible", "fine_jewelry", "gift_card", "hazardous", "meltable", "fragile", "expiry_risk", "oversized", "restricted_gated", "regulated_medical_or_drug", "alcohol", "tobacco", "weapons", "animal_or_animal_products"] | verified_current_rule |
| brightdata_field_availability | null | unknown_or_needs_operator_decision |
| brightdata_spend_cap | null | unknown_or_needs_operator_decision |
| provider_credit_cost | null | unknown_or_needs_operator_decision |