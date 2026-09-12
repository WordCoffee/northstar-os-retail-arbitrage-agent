#!/usr/bin/env python
"""
Re-analyze all Sourcescout items for quantity compliance.
Updates the manifest with compliance fields and generates reports.
"""
import json
from pathlib import Path
from datetime import datetime

from quantity_match_validator import (
    validate_sourcescout_manifest, 
    filter_compliant_items,
    QuantityMatchValidator,
    MatchStatus
)


def main():
    print("=== RE-ANALYZING SOURCESCOUT MANIFEST FOR QUANTITY COMPLIANCE ===\n")
    
    manifest_path = Path("Northstar_backend/data/catalog/sourcescout_manifest.json")
    data_root = Path("Northstar_backend/data")
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found at {manifest_path}")
        return 1
    
    print(f"Loading manifest from {manifest_path}...")
    
    # Run validation
    print("Running quantity match validation...")
    validated_manifest = validate_sourcescout_manifest(str(manifest_path), str(data_root))
    
    items = validated_manifest.get('items', [])
    summary = validated_manifest.get('quantity_match_summary', {})
    
    print(f"\n=== COMPLIANCE SUMMARY ===")
    print(f"Total items: {summary.get('total', 0)}")
    print(f"PASS:       {summary.get('pass', 0)} ({summary.get('pass_rate', 0):.1%})")
    print(f"FAIL:       {summary.get('fail', 0)} ({summary.get('fail_rate', 0):.1%})")
    print(f"REVIEW:     {summary.get('review', 0)} ({summary.get('review_rate', 0):.1%})")
    
    # Count by status
    status_counts = {}
    for item in validated_manifest.get('items', []):
        qm = item.get('quantity_match', {})
        status = qm.get('status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\nDetailed status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    # Save updated manifest
    output_path = Path("Northstar_backend/data/catalog/sourcescout_manifest.json")
    with open(output_path, 'w') as f:
        json.dump(validated_manifest, f, indent=2)
    print(f"\nUpdated manifest saved to {output_path}")
    
    # Generate compliant-only manifest
    compliant_items = [item for item in validated_manifest['items'] 
                       if item.get('quantity_match', {}).get('status') == 'PASS']
    
    compliant_manifest = {
        'kind': 'sourcescout_manifest',
        'schema_version': '1.0',
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'count': len(compliant_items),
        'items': compliant_items,
        'compliance_note': 'Filtered to only PASS items (Amazon quantity matches Costco SKU)'
    }
    
    compliant_path = Path("Northstar_backend/data/catalog/sourcescout_compliant_manifest.json")
    with open(compliant_path, 'w') as f:
        json.dump(compliant_manifest, f, indent=2)
    print(f"\nCompliant-only manifest saved to {compliant_path} ({len(compliant_items)} items)")
    
    # Generate FAIL report
    validator = QuantityMatchValidator(data_root=str(data_root))
    items_list = validated_manifest.get('items', [])
    # Re-validate to get detailed results
    results = validator.validate_batch(items_list)
    
    fail_report = []
    for result in filter(lambda r: r.status == MatchStatus.FAIL, results):
        fail_report.append({
            'asin': result.asin,
            'amazon_title': result.amazon_title,
            'costco_title': result.costco_title,
            'amazon_qty': f"{result.amazon_qty.count} {result.amazon_qty.unit} of {result.amazon_qty.unit_type}",
            'costco_qty': f"{result.costco_qty.count} {result.costco_qty.unit} of {result.costco_qty.unit_type}" if result.costco_qty else "UNKNOWN",
            'mismatch_reason': result.mismatch_reason,
            'costco_sku': result.costco_sku.to_dict() if result.costco_sku else None,
        })
    
    fail_path = Path("Northstar_backend/data/catalog/quantity_mismatch_report.json")
    with open(fail_path, 'w') as f:
        json.dump({
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total_failures': len(fail_report),
            'failures': fail_report
        }, f, indent=2)
    print(f"\nMismatch report saved to {fail_path} ({len(fail_report)} items)")
    
    # Review report
    review_report = []
    for result in filter(lambda r: r.status == MatchStatus.REVIEW, results):
        review_report.append({
            'asin': result.asin,
            'amazon_title': result.amazon_title,
            'costco_title': result.costco_title,
            'amazon_qty': f"{result.amazon_qty.count} {result.amazon_qty.unit} of {result.amazon_qty.unit_type}",
            'costco_qty': f"{result.costco_qty.count} {result.costco_qty.unit} of {result.costco_qty.unit_type}" if result.costco_qty else "UNKNOWN",
            'reason': result.mismatch_reason,
            'costco_sku': result.costco_sku.to_dict() if result.costco_sku else None,
        })
    
    review_path = Path("Northstar_backend/data/catalog/quantity_review_report.json")
    with open(review_path, 'w') as f:
        json.dump({
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total_reviews': len(review_report),
            'reviews': review_report
        }, f, indent=2)
    print(f"Review report saved to {review_path} ({len(review_report)} items)")
    
    # Print some examples
    print(f"\n=== FAIL EXAMPLES (first 10) ===")
    for f in fail_report[:10]:
        print(f"  {f['asin']}: Amazon={f['amazon_qty']} vs Costco={f['costco_qty']}")
        print(f"    Amazon: {f['amazon_title'][:70]}")
        print(f"    Costco: {f['costco_title'][:70]}")
        print(f"    Reason: {f['mismatch_reason']}")
    
    print(f"\n=== REVIEW EXAMPLES (first 10) ===")
    for r in review_report[:10]:
        print(f"  {r['asin']}: {r['reason']}")
        print(f"    Amazon: {r['amazon_title'][:70]}")
    
    print(f"\n=== CREDIT SAVINGS PROJECTION ===")
    total = summary.get('total', 0)
    pass_count = summary.get('pass', 0)
    fail_count = summary.get('fail', 0)
    review_count = summary.get('review', 0)
    
    enrichment_cost = 0.003  # per item estimate
    before_cost = total * enrichment_cost
    after_cost = pass_count * enrichment_cost
    saved = before_cost - after_cost
    
    print(f"Before filter: {total} items × ${enrichment_cost:.3f} = ${before_cost:.2f}/run")
    print(f"After filter:  {pass_count} items × ${enrichment_cost:.3f} = ${after_cost:.2f}/run")
    print(f"Savings:       {fail_count + review_count} items skipped = ${saved:.2f}/run")
    print(f"Monthly (30 runs): ${saved * 30:.2f}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())