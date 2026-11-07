import json
from datetime import datetime, timezone
import data_layer
data_layer._SQLITE_PATH = data_layer._SQLITE_PATH
from costco_non_kirkland.store import PipelineStore
from costco_non_kirkland.audit import parse_weight_lb

s = PipelineStore()
now = datetime.now(timezone.utc).isoformat()

criteria = {
    "run_name": "seller-provider-pilot-2026-09-27",
    "criteria_version": "v1",
    "confirmed_at": now,
    "economics": {"min_net_profit": 5.00, "min_roi_pct": 30.0, "preferred_net_profit": 11.00, "priority_net_profit": 20.00},
    "weight": {"max_verified_weight_lb": 3.0, "standard_size_preferred": True,
               "unknown_source_weight_allowed": "provisional_only_no_auto_qualify"},
    "competition": {"amazon_retail": "provider_reported_absent",
                    "brand_seller": "provider_reported_absent_when_available",
                    "fba_sellers_required": 0, "mfn_sellers_min": 3,
                    "unknown": "needs_enrichment_or_manual_review"},
    "demand": {"min_est_monthly_units": 500,
               "fallback": "provider_supported_strong_bsr_signal_manual_review",
               "no_direct_amazon": True},
    "sources": {"preferred": ["costco", "costco_business_center"],
                "alternate_wholesale_leads_allowed": True, "lead_is_not_verified_source": True},
    "provider_budget": {"spend_cap_usd": 0.0, "pause_before_credit_actions": True},
    "research_scope": {"provisional_queue_allowed": True, "verification_batch": 20,
                       "split_pack_review_excluded_from_auto_qualify": True,
                       "missing_identity_pack_excluded_first_batch": True,
                       "expand_to_all_after_report": 17},
}

rows = s.list_source_products(run_id='run_637d760a53b4', eligible_only=True)
provisional = [r for r in rows if r.get('brand_normalized') and r.get('costco_price') is not None
               and (r.get('normalized_unit_count') is not None or r.get('costco_pack_raw'))]

# Batch = provisional clear-pack records (brand + usable cost + clear pack/unit).
# Split-review = normalized_unit_count > 1 (multi-unit pack) -> no auto-qualify.
batch = provisional[:20]
queue = []
for r in batch:
    uc = r.get('normalized_unit_count') or 0
    split_review = bool(uc and uc > 1)
    queue.append({
        "candidate_id": r['id'], "source_product": r.get('title_raw'), "source_name": r.get('source_name'),
        "source_sku": r.get('costco_item_number'), "source_url": r.get('source_url'),
        "source_price": r.get('costco_price'), "source_pack": r.get('costco_pack_raw'),
        "source_unit_count": uc, "source_upc": r.get('upc'), "source_mpn": r.get('manufacturer_part_number'),
        "source_weight_raw": r.get('size_or_weight_raw'), "weight_lb_parsed": parse_weight_lb(r.get('size_or_weight_raw')),
        "split_pack_review": split_review,
        "auto_qualify_eligible": (not split_review),
    })

snap = {"criteria": criteria, "batch_size": len(queue), "provisional_total": len(provisional),
        "split_review_in_batch": sum(1 for q in queue if q['split_pack_review']), "queue": queue}
with open('provider_research_criteria_snapshot.json', 'w', encoding='utf-8') as f:
    json.dump(snap, f, indent=2)
with open('provider_research_import_manifest.json', 'w', encoding='utf-8') as f:
    json.dump({"run_name": criteria["run_name"], "batch_size": len(queue), "queue": queue}, f, indent=2)

run = s.create_run("seller-provider-pilot-2026-09-27", command="research_batch_1")
for q in queue:
    s.add_evidence(run['run_id'], q['candidate_id'], {
        'source': 'pilot_batch_selection', 'field_name': 'batch1_selected',
        'field_value': 'verification batch', 'evidence_class': 'user_entered_assumption',
        'capture_status': 'captured', 'notes': f"criteria v1; split_review={q['split_pack_review']}"})

print('criteria snapshot saved')
print('provisional_total:', len(provisional), 'batch:', len(queue),
      'split_review_in_batch:', snap['split_review_in_batch'])
print('northstar_run_id:', run['run_id'])
for q in queue:
    print(q['candidate_id'][:14], '| split' if q['split_pack_review'] else '| unit ', '|',
          (q['source_product'] or '')[:46], '| $', q['source_price'])
