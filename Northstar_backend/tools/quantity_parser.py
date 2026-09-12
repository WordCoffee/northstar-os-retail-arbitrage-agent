#!/usr/bin/env python
"""
Quantity Parser for Amazon and Costco product listings.
Normalizes pack/quantity strings into structured data.
"""
import re
from typing import Optional
from dataclasses import dataclass
from typing import Optional as Opt

@dataclass
class ParsedQuantity:
    """Normalized quantity information."""
    count: int = 1                    # Number of units in the pack
    unit: str = "each"                # "pack", "bottle", "box", "each", "tablet", etc.
    unit_type: str = "item"           # "tablet", "capsule", "sheet", "roll", "bottle", etc.
    is_multipack: bool = False        # True if count > 1
    raw_text: str = ""                # Original text for debugging
    
    def __eq__(self, other):
        if not isinstance(other, ParsedQuantity):
            return False
        return (self.count == other.count and 
                self.unit == other.unit and 
                self.unit_type == other.unit_type)
    
    def __hash__(self):
        return hash((self.count, self.unit, self.unit_type))
    
    def __str__(self):
        if self.is_multipack:
            return f"{self.count} {self.unit} of {self.unit_type}"
        return f"{self.count} {self.unit_type}"


# ============================================================
# AMAZON QUANTITY PARSER
# ============================================================

# Common unit type mappings
UNIT_TYPE_ALIASES = {
    'tablet': ['tablet', 'tablets', 'tab', 'tabs'],
    'capsule': ['capsule', 'capsules', 'cap', 'caps', 'softgel', 'softgels', 'softgel', 'sg'],
    'softgel': ['softgel', 'softgels', 'sg'],
    'tablet': ['tablet', 'tablets', 'tab'],
    'capsule': ['capsule', 'capsules', 'cap'],
    'sheet': ['sheet', 'sheets', 'sht'],
    'roll': ['roll', 'rolls', 'rl'],
    'bottle': ['bottle', 'bottles', 'btl', 'btls'],
    'box': ['box', 'boxes', 'bx'],
    'pack': ['pack', 'packs', 'pk', 'pks'],
    'count': ['count', 'ct', 'cts'],
    'tablet': ['tablet', 'tablets', 'tab'],
    'capsule': ['capsule', 'capsules', 'cap', 'softgel', 'softgels'],
    'strip': ['strip', 'strips'],
    'pouch': ['pouch', 'pouches'],
    'bag': ['bag', 'bags'],
    'container': ['container', 'containers', 'cont'],
    'jar': ['jar', 'jars'],
    'tube': ['tube', 'tubes'],
    'can': ['can', 'cans'],
    'packet': ['packet', 'packets', 'pkt'],
    'sachet': ['sachet', 'sachets'],
    'roll': ['roll', 'rolls'],
    'sheet': ['sheet', 'sheets'],
    'wipe': ['wipe', 'wipes'],
    'diaper': ['diaper', 'diapers'],
    'bag': ['bag', 'bags'],
}

# Reverse mapping: alias -> canonical unit_type
ALIAS_TO_UNIT = {}
for canonical, aliases in UNIT_TYPE_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_UNIT[alias.lower()] = canonical


# Regex patterns for Amazon quantity parsing
AMAZON_PATTERNS = [
    # "N pack", "N pk", "N-pack", "N pk of"
    (re.compile(r'(\d+)\s*(?:pack|pk|packs|pks)\b', re.IGNORECASE), 'pack'),
    # "pack of N", "pk of N"
    (re.compile(r'pack\s+of\s+(\d+)', re.IGNORECASE), 'pack'),
    # "N x M" or "NxM" (e.g., "2 x 96", "2x96")
    (re.compile(r'(\d+)\s*[x×]\s*(\d+)'), 'multiplier'),
    # "N count", "N ct", "N cts", "N-count"
    (re.compile(r'(\d+)\s*(?:count|ct|cts)\b', re.IGNORECASE), 'count'),
    # "N-count" as in "192-count"
    (re.compile(r'(\d+)-count\b', re.IGNORECASE), 'count'),
    # "Npk" as in "2pk"
    (re.compile(r'(\d+)pk\b', re.IGNORECASE), 'pack'),
]

# Unit type keywords in title
UNIT_KEYWORDS = {
    'tablet': ['tablet', 'tablets', 'tab'],
    'capsule': ['capsule', 'capsules', 'cap', 'softgel', 'softgels'],
    'softgel': ['softgel', 'softgels'],
    'tablet': ['tablet', 'tablets', 'tab'],
    'capsule': ['capsule', 'capsules', 'cap'],
    'sheet': ['sheet', 'sheets'],
    'roll': ['roll', 'rolls'],
    'bottle': ['bottle', 'bottles'],
    'box': ['box', 'boxes'],
    'bag': ['bag', 'bags'],
    'container': ['container', 'containers'],
    'jar': ['jar', 'jars'],
    'tube': ['tube', 'tubes'],
    'can': ['can', 'cans'],
    'roll': ['roll', 'rolls'],
    'wipe': ['wipe', 'wipes'],
    'diaper': ['diaper', 'diapers'],
    'bag': ['bag', 'bags'],
    'pouch': ['pouch', 'pouches'],
    'strip': ['strip', 'strips'],
    'packet': ['packet', 'packets'],
    'sachet': ['sachet', 'sachets'],
}


def parse_amazon_quantity(title: str, pack_field: str = "", requested_pack: str = "") -> 'ParsedQuantity':
    """
    Parse Amazon product title and pack fields to extract quantity.
    
    Args:
        title: Product title from Amazon
        pack_field: Pack field from Amazon (e.g., "2 Pack")
        requested_pack: Pack field from Costco mapping
        
    Returns:
        ParsedQuantity with normalized count, unit, unit_type
    """
    # Combine all text sources
    text_parts = []
    if title:
        text_parts.append(title)
    if pack_field:
        text_parts.append(pack_field)
    if requested_pack:
        text_parts.append(requested_pack)
    
    full_text = " ".join(filter(None, text_parts))
    full_text_lower = full_text.lower()
    
    result = ParsedQuantity(raw_text=full_text)
    
    # Try patterns in order of specificity
    count = None
    unit = "each"
    unit_type = "item"
    
    # 1. Check for "N x M" multiplier pattern (e.g., "2 x 96")
    mult_match = re.search(r'(\d+)\s*[x×]\s*(\d+)', full_text, re.IGNORECASE)
    if mult_match:
        count = int(mult_match.group(1)) * int(mult_match.group(2))
        unit = "each"
        # Try to determine unit_type from context
        unit_type = _detect_unit_type(full_text_lower)
        result.count = count
        result.unit = unit
        result.unit_type = unit_type
        result.is_multipack = count > 1
        return result
    
    # 2. Check for "N pack" patterns
    for pattern, unit_name in AMAZON_PATTERNS:
        match = pattern.search(full_text)
        if match:
            if pattern.pattern == r'(\d+)\s*[x×]\s*(\d+)':
                continue  # Already handled
            count = int(match.group(1))
            unit = unit_name
            break
    
    # 3. If no explicit pack pattern, check for "N count" or standalone number with unit
    if count is None:
        # Look for "N count" or "N ct"
        count_match = re.search(r'(\d+)\s*(?:count|ct|cts)\b', full_text_lower)
        if count_match:
            count = int(count_match.group(1))
            unit = "count"
        else:
            # Look for leading number that might be quantity (e.g., "192 Tablets")
            # But be careful - could be model number
            leading_num = re.match(r'^(\d{2,4})\s+', full_text)
            if leading_num:
                potential_count = int(leading_num.group(1))
                # Heuristic: if followed by unit keyword, it's a count
                rest = full_text[leading_num.end():].lower()
                for ut, keywords in UNIT_KEYWORDS.items():
                    if any(kw in rest[:30] for kw in keywords):
                        count = potential_count
                        unit = "count"
                        break
    
    # 4. Detect unit_type from title
    unit_type = _detect_unit_type(full_text_lower)
    
    # 5. If still no count, default to 1
    if count is None:
        count = 1
        unit = "each"
    
    result.count = count
    result.unit = unit
    result.unit_type = unit_type
    result.is_multipack = count > 1
    return result


def _detect_unit_type(text_lower: str) -> str:
    """Detect the unit type (tablet, capsule, roll, etc.) from text."""
    for unit_type, keywords in UNIT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return unit_type
    return "item"


def parse_costco_pack(requested_pack: str = "", item_id: str = "") -> 'ParsedQuantity':
    """
    Parse Costco's requested_pack field and item_id.
    
    Examples:
    - "900-count (9 x 100ct)" → count=900, unit=count, unit_type=item
    - "2 pack" → count=2, unit=pack
    - "5 Bottles" → count=5, unit=bottle
    - "192 Tablets" → count=192, unit=count, unit_type=tablet
    """
    text = " ".join(filter(None, [requested_pack, item_id]))
    text_lower = text.lower()
    
    result = ParsedQuantity(raw_text=text)
    
    # Handle "N x M" patterns like "9 x 100ct"
    mult_match = re.search(r'(\d+)\s*[x×]\s*(\d+)', text, re.IGNORECASE)
    if mult_match:
        count = int(mult_match.group(1)) * int(mult_match.group(2))
        unit = "count"
        unit_type = _detect_unit_type(text_lower)
        result.count = count
        result.unit = unit
        result.unit_type = unit_type
        result.is_multipack = count > 1
        return result
    
    # Look for "N count" or "N ct" or "N-count"
    count_match = re.search(r'(\d+)\s*(?:count|ct|cts|-count)\b', text_lower)
    if count_match:
        count = int(count_match.group(1))
        unit = "count"
        unit_type = _detect_unit_type(text_lower)
        result.count = count
        result.unit = unit
        result.unit_type = unit_type
        result.is_multipack = count > 1
        return result
    
    # Look for "N pack" or "N pk"
    pack_match = re.search(r'(\d+)\s*(?:pack|pk|packs|pks)\b', text_lower)
    if pack_match:
        count = int(pack_match.group(1))
        result.count = count
        result.unit = "pack"
        result.unit_type = _detect_unit_type(text_lower)
        result.is_multipack = count > 1
        return result
    
    # Look for "N bottles", "N boxes", etc.
    for unit_type, keywords in UNIT_KEYWORDS.items():
        for kw in keywords:
            pattern = rf'(\d+)\s+{re.escape(kw)}s?\b'
            match = re.search(pattern, text_lower)
            if match:
                count = int(match.group(1))
                result.count = count
                result.unit = unit_type
                result.unit_type = unit_type
                result.is_multipack = count > 1
                return result
    
    # Try to find any leading number with unit
    leading = re.match(r'^(\d{1,4})\s+', text_lower)
    if leading:
        potential = int(leading.group(1))
        # Check if followed by known unit
        rest = text_lower[leading.end():]
        for ut, keywords in UNIT_KEYWORDS.items():
            if any(kw in rest[:30] for kw in keywords):
                result.count = potential
                result.unit = ut
                result.unit_type = ut
                result.is_multipack = potential > 1
                return result
    
    # Default
    result.count = 1
    result.unit = "each"
    result.unit_type = "item"
    return result


# ============================================================
# COMPARISON UTILITIES
# ============================================================

def quantities_match(amazon: ParsedQuantity, costco: ParsedQuantity, tolerance: float = 0.0) -> tuple:
    """
    Compare Amazon and Costco quantities.
    
    Returns:
        (matches: bool, reason: str)
    """
    # If both are single units, they match
    if amazon.count == 1 and costco.count == 1:
        return True, "Both single unit"
    
    # Exact count match
    if amazon.count == costco.count:
        return True, f"Exact match: {amazon.count} {amazon.unit}"
    
    # Allow small tolerance for rounding (e.g., 192 vs 192)
    if abs(amazon.count - costco.count) <= tolerance:
        return True, f"Within tolerance: amazon={amazon.count}, costco={costco.count}"
    
    # Different counts
    return False, f"Mismatch: Amazon={amazon.count} {amazon.unit} vs Costco={costco.count} {costco.unit}"


def classify_match(amazon_qty: 'ParsedQuantity', costco_qty: 'ParsedQuantity') -> str:
    """
    Classify the match result.
    Returns: 'PASS' | 'FAIL' | 'REVIEW'
    """
    matches, reason = quantities_match(amazon, costco)
    if matches:
        return 'PASS'
    
    # If Costco quantity unknown (1 each, no pack info), needs review
    if costco.count == 1 and costco.unit == "each" and costco.raw_text.strip() == "":
        return 'REVIEW'
    
    return 'FAIL'