#!/usr/bin/env python
"""
Quantity Match Validator - core validation logic for Amazon/Costco quantity matching.
"""
import json
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from quantity_parser import ParsedQuantity, parse_amazon_quantity, parse_costco_pack, quantities_match, classify_match
from costco_sku_registry import CostcoSKU, CostcoSKURegistry, load_registry


class MatchStatus(Enum):
    PASS = "PASS"           # Amazon quantity matches Costco SKU quantity
    FAIL = "FAIL"           # Quantities don't match - skip enrichment
    REVIEW = "REVIEW"       # Costco SKU not found or ambiguous - needs manual review


@dataclass
class ValidationResult:
    """Result of quantity match validation."""
    asin: str
    status: MatchStatus
    amazon_qty: 'ParsedQuantity'
    costco_qty: Optional['ParsedQuantity']
    costco_sku: Optional['CostcoSKU'] = None
    mismatch_reason: str = ""
    amazon_title: str = ""
    costco_title: str = ""
    
    def to_dict(self) -> dict:
        return {
            'asin': self.asin,
            'status': self.status.value,
            'amazon_quantity': {
                'count': self.amazon_qty.count,
                'unit': self.amazon_qty.unit,
                'unit_type': self.amazon_qty.unit_type,
                'is_multipack': self.amazon_qty.is_multipack,
            },
            'costco_quantity': {
                'count': self.costco_qty.count if self.costco_qty else None,
                'unit': self.costco_qty.unit if self.costco_qty else None,
                'unit_type': self.costco_qty.unit_type if self.costco_qty else None,
                'is_multipack': self.costco_qty.is_multipack if self.costco_qty else None,
            } if self.costco_qty else None,
            'costco_sku': self.costco_sku.to_dict() if self.costco_sku else None,
            'mismatch_reason': self.mismatch_reason,
            'amazon_title': self.amazon_title,
            'costco_title': self.costco_title,
        }


class QuantityMatchValidator:
    """
    Validates that Amazon listing quantities match Costco SKU quantities.
    """
    
    def __init__(self, registry: Optional[CostcoSKURegistry] = None, data_root: str = "data"):
        self.registry = registry or load_registry(data_root)
        self.results_cache: Dict[str, ValidationResult] = {}
    
    def validate(self, asin: str, amazon_item: dict) -> ValidationResult:
        """
        Validate a single ASIN against Costco SKU data.
        
        Args:
            asin: Amazon ASIN
            amazon_item: Dict with 'title', 'pack', 'requested_pack', etc.
            
        Returns:
            ValidationResult with PASS/FAIL/REVIEW status
        """
        # Check cache first
        if asin in self.results_cache:
            return self.results_cache[asin]
        
        # Parse Amazon quantity
        amazon_qty = parse_amazon_quantity(
            title=amazon_item.get('title', ''),
            pack_field=amazon_item.get('pack', ''),
            requested_pack=amazon_item.get('requested_pack', '')
        )
        
        # Get Costco SKU
        costco_sku = self.registry.get_by_asin(asin)
        
        # Parse Costco quantity
        costco_qty = costco_sku.quantity if costco_sku and costco_sku.quantity else None
        
        # If no Costco SKU found, try to parse from item data
        if not costco_qty and costco_sku:
            costco_qty = parse_costco_pack(
                costco_sku.requested_pack,
                costco_sku.item_id
            )
        
        # Determine match status
        if not costco_sku:
            status = MatchStatus.REVIEW
            reason = "No Costco SKU found for this ASIN"
            costco_title = ""
        elif not costco_qty:
            status = MatchStatus.REVIEW
            reason = "Costco SKU found but quantity could not be parsed"
            costco_title = costco_sku.requested_title
        else:
            matches, reason = quantities_match(amazon_qty, costco_qty)
            if matches:
                status = MatchStatus.PASS
            else:
                # Check if it's a review case (Costco data incomplete)
                if costco_qty.count == 1 and costco_qty.unit == "each" and not costco_sku.requested_pack:
                    status = MatchStatus.REVIEW
                else:
                    status = MatchStatus.FAIL
        
        result = ValidationResult(
            asin=asin,
            status=status,
            amazon_qty=amazon_qty,
            costco_qty=costco_qty,
            costco_sku=costco_sku,
            mismatch_reason=reason,
            amazon_title=amazon_item.get('title', ''),
            costco_title=costco_sku.requested_title if costco_sku else "",
        )
        
        self.results_cache[asin] = result
        return result
    
    def validate_batch(self, items: List[dict]) -> List[ValidationResult]:
        """Validate a batch of items."""
        return [self.validate(item.get('asin', ''), item) for item in items if item.get('asin')]
    
    def get_summary(self, results: List[ValidationResult]) -> dict:
        """Get summary statistics from validation results."""
        total = len(results)
        pass_count = sum(1 for r in results if r.status == MatchStatus.PASS)
        fail_count = sum(1 for r in results if r.status == MatchStatus.FAIL)
        review_count = sum(1 for r in results if r.status == MatchStatus.REVIEW)
        
        return {
            'total': total,
            'pass': pass_count,
            'fail': fail_count,
            'review': review_count,
            'pass_rate': pass_count / total if total > 0 else 0,
            'fail_rate': fail_count / total if total > 0 else 0,
            'review_rate': review_count / total if total > 0 else 0,
        }
    
    def get_failures(self, results: List[ValidationResult]) -> List[ValidationResult]:
        """Get all FAIL results."""
        return [r for r in results if r.status == MatchStatus.FAIL]
    
    def get_reviews(self, results: List[ValidationResult]) -> List[ValidationResult]:
        """Get all REVIEW results."""
        return [r for r in results if r.status == MatchStatus.REVIEW]
    
    def get_passes(self, results: List[ValidationResult]) -> List[ValidationResult]:
        """Get all PASS results."""
        return [r for r in results if r.status == MatchStatus.PASS]


# Integration with Sourcescout manifest builder
def validate_sourcescout_manifest(manifest_path: str, data_root: str = "data") -> dict:
    """
    Validate an existing Sourcescout manifest and add compliance fields.
    
    Returns updated manifest with compliance data.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    items = manifest.get('items', [])
    
    validator = QuantityMatchValidator(data_root=data_root)
    results = validator.validate_batch(items)
    summary = validator.get_summary(results)
    
    # Add compliance data to each item
    for item, result in zip(items, results):
        item['quantity_match'] = result.to_dict()
    
    manifest['items'] = items
    manifest['quantity_match_summary'] = summary
    
    return manifest


def filter_compliant_items(manifest_path: str, data_root: str = "data") -> List[dict]:
    """Return only PASS items from a manifest."""
    validator = QuantityMatchValidator(data_root=data_root)
    items = json.loads(Path(manifest_path).read_text()).get('items', [])
    results = validator.validate_batch(items)
    return [item for item, result in zip(items, results) if result.status == MatchStatus.PASS]


# Main for testing
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Load a sample of items and validate
    manifest_path = "Northstar_backend/data/catalog/sourcescout_manifest.json"
    if Path(manifest_path).exists():
        manifest = json.loads(Path(manifest_path).read_text())
        items = manifest.get('items', [])
        
        print(f"Validating {len(items)} items...")
        validator = QuantityMatchValidator()
        results = validator.validate_batch(items[:50])  # Test first 50
        summary = validator.get_summary(results)
        
        print(f"\n=== VALIDATION SUMMARY (first 50) ===")
        print(f"Total: {summary['total']}")
        print(f"PASS: {summary['pass']} ({summary['pass_rate']:.1%})")
        print(f"FAIL: {summary['fail']} ({summary['fail_rate']:.1%})")
        print(f"REVIEW: {summary['review']} ({summary['review_rate']:.1%})")
        
        # Show failures
        failures = validator.get_failures(results)
        if failures:
            print(f"\n=== FAILURES ({len(failures)}) ===")
            for r in failures[:10]:
                a = r.amazon_qty
                c = r.costco_qty
                print(f"  {r.asin}: Amazon={a.count}{a.unit} vs Costco={c.count if c else '?'}{c.unit if c else '?'}")
                print(f"    Reason: {r.mismatch_reason}")
                print(f"    Amazon: {r.amazon_title[:60]}")
                print(f"    Costco: {r.costco_title[:60]}")
        
        reviews = validator.get_reviews(results)
        if reviews:
            print(f"\n=== REVIEW ({len(reviews)}) ===")
            for r in reviews[:10]:
                print(f"  {r.asin}: {r.mismatch_reason}")
                print(f"    Amazon: {r.amazon_title[:60]}")