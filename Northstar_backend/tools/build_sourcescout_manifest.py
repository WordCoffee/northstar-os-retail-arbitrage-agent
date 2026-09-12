#!/usr/bin/env python
"""
Build Sourcescout manifest by aggregating ALL Kirkland ASINs from every available data source.
Auto-updates when new enrichment runs complete.
Now includes automatic quantity match validation for Amazon/Costco compliance.
"""
import json, os, sys, glob
from pathlib import Path
from datetime import datetime, timezone

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p: Path, data: dict):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def merge_items(existing: dict, new_items: list, key="asin") -> dict:
    """Merge new items into existing dict, keyed by ASIN."""
    for item in new_items:
        if isinstance(item, dict) and item.get(key):
            existing[item[key]] = item
    return existing

def extract_from_list(data_list: list, key="asin") -> list:
    """Extract valid items from a list, ensuring each has the key."""
    return [item for item in data_list if isinstance(item, dict) and item.get(key)]

def expand_mapped_asins(items: list) -> list:
    """Expand items with mapped_asins lists into individual ASIN entries."""
    expanded = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # If item has mapped_asins, expand each ASIN
        mapped = item.get("mapped_asins")
        if isinstance(mapped, list) and mapped:
            for asin in mapped:
                if isinstance(asin, str) and asin.startswith("B0"):
                    new_item = item.copy()
                    new_item["asin"] = asin
                    expanded.append(new_item)
        # Also check for direct asin field
        elif item.get("asin"):
            expanded.append(item)
        # Check for item_id that looks like ASIN
        elif item.get("item_id"):
            item_id = item["item_id"]
            if isinstance(item_id, str) and item_id.startswith("B0"):
                item["asin"] = item_id
                expanded.append(item)
    return expanded


def run_quantity_validation(items_list: list, data_root: Path) -> tuple:
    """Run quantity match validation on all items and add compliance data."""
    try:
        from quantity_match_validator import QuantityMatchValidator, MatchStatus
        validator = QuantityMatchValidator(data_root=str(data_root))
        results = validator.validate_batch(items_list)
        
        # Add compliance data to each item
        for item, result in zip(items_list, results):
            item['quantity_match'] = result.to_dict()
        
        # Print summary
        summary = validator.get_summary(results)
        print(f"\n=== QUANTITY MATCH VALIDATION SUMMARY ===")
        print(f"Total: {summary['total']}")
        print(f"PASS: {summary['pass']} ({summary['pass_rate']:.1%})")
        print(f"FAIL: {summary['fail']} ({summary['fail_rate']:.1%})")
        print(f"REVIEW: {summary['review']} ({summary['review_rate']:.1%})")
        
        return items_list, summary
    except Exception as e:
        print(f"Warning: Quantity validation failed: {e}")
        return items_list, {}


def main():
    print("=== Building Sourcescout Manifest (auto-aggregate all sources) ===")
    all_items = {}  # keyed by ASIN
    
    # 1. Tier1 normalized waterfall files (already dicts with 'asin')
    tier1_dir = DATA_ROOT / "enrich" / "waterfall-runs" / "waterfall-20260822T195147Z" / "normalized"
    if tier1_dir.exists():
        for fp in tier1_dir.glob("*-tier1.json"):
            data = load_json(fp)
            items = data if isinstance(data, list) else [data]
            merge_items(all_items, extract_from_list(items))
    print(f"After tier1: {len(all_items)} ASINs")
    
    # 2. Enrichment results v2 (has nested results array)
    for ev2 in sorted(DATA_ROOT.glob("catalog/enrichment_results_v2_*.json"), reverse=True):
        data = load_json(ev2)
        if isinstance(data, dict) and "results" in data:
            merge_items(all_items, extract_from_list(data["results"]))
    print(f"After enrichment v2: {len(all_items)} ASINs")
    
    # 3. Enrichment shortlist
    for es in sorted(DATA_ROOT.glob("catalog/enrichment_shortlist_*.json"), reverse=True):
        data = load_json(es)
        if isinstance(data, dict) and "results" in data:
            merge_items(all_items, extract_from_list(data["results"]))
    print(f"After enrichment shortlist: {len(all_items)} ASINs")
    
    # 4. Kirkland catalog manifests (latest 10) - asins is a LIST with asin field
    for kf in sorted(DATA_ROOT.glob("catalog/kirkland_catalog_manifest_*.json"), reverse=True)[:10]:
        data = load_json(kf)
        if isinstance(data, dict):
            asins_list = data.get("asins", [])
            merge_items(all_items, extract_from_list(asins_list))
    print(f"After Kirkland catalogs: {len(all_items)} ASINs")
    
    # 5. BrightData Costco 180 prepared manifest - expand mapped_asins from costco_detail
    cdm = DATA_ROOT / "catalog" / "costco_detail_manifest.json"
    if cdm.exists():
        data = load_json(cdm)
        if isinstance(data, dict):
            items_list = data.get("items", [])
            expanded = expand_mapped_asins(items_list)
            merge_items(all_items, extract_from_list(expanded))
    print(f"After Costco detail (mapped_asins): {len(all_items)} ASINs")
    
    # 5b. BrightData 180 - try to extract from costco_cost_reference + resolution
    bd = DATA_ROOT / "catalog" / "brightdata_costco_180_prepared_manifest.json"
    if bd.exists():
        data = load_json(bd)
        if isinstance(data, dict):
            items_list = data.get("items", [])
            # These are mostly unresolved, but try to extract any ASIN-like IDs
            for item in items_list:
                if isinstance(item, dict):
                    # Check if item_id is an ASIN
                    item_id = item.get("item_id")
                    if isinstance(item_id, str) and item_id.startswith("B0"):
                        merge_items(all_items, [{"asin": item_id, **item}])
    print(f"After BrightData 180: {len(all_items)} ASINs")
    
    # 6. Layer1 discovery manifest - asins is a LIST with asin field
    for f in sorted(DATA_ROOT.glob("catalog/layer1_discovery_manifest_*.json"), reverse=True)[:3]:
        data = load_json(f)
        if isinstance(data, dict):
            asins_list = data.get("asins", [])
            merge_items(all_items, extract_from_list(asins_list))
    print(f"After Layer1 discovery: {len(all_items)} ASINs")
    
    # 7. Scanner search cache (enriched candidates)
    cache_files = list(DATA_ROOT.glob("**/scanner-search-cache*.json"))
    for cf in cache_files[:5]:
        try:
            data = load_json(cf)
            if isinstance(data, list):
                merge_items(all_items, extract_from_list(data))
        except:
            pass
    print(f"After scanner cache: {len(all_items)} ASINs")
    
    # 8. Brain runs (enriched)
    brain_files = list(DATA_ROOT.glob("**/brain-runs/**/*.json"))
    for bf in brain_files[:10]:
        try:
            data = load_json(bf)
            if isinstance(data, dict) and "items" in data:
                merge_items(all_items, extract_from_list(data["items"]))
            elif isinstance(data, list):
                merge_items(all_items, extract_from_list(data))
        except:
            pass
    print(f"After brain runs: {len(all_items)} ASINs")
    
    # 9. Also check tier1 normalized for ASINs directly (they may have different structure)
    for fp in tier1_dir.glob("*-tier1.json"):
        data = load_json(fp)
        if isinstance(data, dict) and data.get("asin"):
            all_items[data["asin"]] = data
    
    # Convert to list
    items_list = list(all_items.values())
    print(f"\n=== TOTAL UNIQUE ASINs: {len(items_list)} ===")
    
    # Run quantity match validation
    items_list, validation_summary = run_quantity_validation(items_list, DATA_ROOT)
    
    # Build manifest
    manifest = {
        "kind": "sourcescout_manifest",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items_list),
        "quantity_match_summary": validation_summary,
        "items": items_list
    }
    
    out_path = DATA_ROOT / "catalog" / "sourcescout_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written: {out_path}")
    
    # Also write a simple list for quick scanning
    asin_list = sorted(all_items.keys())
    asin_path = DATA_ROOT / "catalog" / "sourcescout_asins.json"
    save_json(asin_path, {"asins": asin_list, "count": len(asin_list), "generated_at": manifest["generated_at"]})
    print(f"ASIN list: {asin_path}")
    
    # Print ASINs for verification
    print(f"\nASINs found: {asin_list}")

if __name__ == "__main__":
    main()