"""Disallowed product-class exclusion for the Costco Non-Kirkland pipeline.

PURE / OFFLINE / DETERMINISTIC. Marks (never deletes) records whose product
class is disallowed for the research workflow (hazardous, meltable, fragile,
expiry/perishable, oversized, gated/restricted, regulated, alcohol, tobacco,
weapons, animal products).

Classification is keyword/heuristic based on title + size/weight + category.
It is conservative: any positive hint excludes. Unknown is NOT a pass — records
with no clear class stay eligible (they may still be flagged later at scoring),
but records matching a disallowed class are excluded and audited.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import DisallowedClass, DISALLOWED_CLASS_EXCLUSION_REASON

# Keyword rules per disallowed class.
# Matching: case-insensitive; a keyword ending in "*" is a prefix match; otherwise
# exact word-boundary match (avoids "oil" matching "foil", "nut" matching "minute").
DISALLOWED_CLASS_RULES: Dict[str, tuple] = {
    DisallowedClass.HAZARDOUS.value: (
        "bleach", "acid", "corrosive", "flammable", "combustible", "lithium battery",
        "lithium-ion", "hazardous", "aerosol", "propane", "butane", "kerosene",
        "gasoline", "paint thinner", "pool shock", "muriatic",
    ),
    DisallowedClass.MELTABLE.value: (
        "chocolate", "candle", "wax", "meltable", "butter", "cheese", "yogurt", "gelatin",
    ),
    DisallowedClass.FRAGILE.value: (
        "glass bottle", "ceramic", "porcelain", "glassware", "crystal", "mirror",
    ),
    DisallowedClass.EXPIRY.value: (
        "expires", "best by", "use by", "perishable", "fresh", "refrigerated",
        "frozen", "dairy", "meat", "seafood", "produce", "shelf life", "expiration",
    ),
    DisallowedClass.OVERSIZED.value: (
        "200 lb", "250 lb", "300 lb", "400 lb", "500 lb", "pallet", "industrial",
        "commercial-grade", "50 lb", "60 lb", "75 lb", "100 lb",
    ),
    DisallowedClass.GATED.value: (
        "gated", "restricted", "brand registry", "category approval",
    ),
    DisallowedClass.FOOD_PERISHABLE.value: (
        "raw", "poultry", "fish", "fresh fruit", "fresh vegetable", "bakery", "deli",
    ),
    DisallowedClass.FOOD.value: (
        "cracker*", "cookie*", "chip*", "cereal", "granola", "oat*", "rice", "pasta",
        "noodle*", "ramen", "sauce", "spice*", "seasoning", "nutmeg", "pepper", "salt",
        "honey", "syrup", "jam", "jelly", "peanut butter", "snack*", "popcorn",
        "muffin*", "yogurt", "soup", "broth", "canned", "tuna", "salmon", "sardine*",
        "sausage", "bacon", "jerky", "flour", "sugar", "baking", "dressing",
        "mayonnaise", "ketchup", "mustard", "relish", "pickle*", "olive*", "raisin*",
        "almond*", "cashew*", "pistachio*", "walnut*", "pecan*", "avocado", "oil",
        "vinegar", "marinade", "mango*", "fruit", "latte", "hot cocoa", "pudding",
        "gelato", "ice cream", "cheese*", "milk", "cream", "coffee", "tea", "espresso",
        "cappuccino", "ready to eat",
        "nut*", "seed*", "berry", "berries", "tortilla*", "salsa", "hummus",
        "guacamole", "dip", "caviar*", "roe", "fillet", "frito*", "dorito*", "cheeto*", "bean*", "lentil*", "quinoa",
        "chia", "corn", "potato*", "vegetable", "smoothie", "granola bar*",
        "protein bar*", "energy concentrate", "drink mix", "powder mix",
    ),
    DisallowedClass.GROCERY.value: (
        "grocery", "pantry", "shelf-stable", "meal kit", "treat*", "candy", "gum",
        "mint*", "food storage", "seasoning*", "condiment*", "syrup*",
    ),
    DisallowedClass.BEVERAGE.value: (
        "beverage", "drink", "soda", "cola", "juice", "water", "sparkling water",
        "energy drink", "sports drink", "electrolyte", "kombucha", "seltzer",
        "coffee pod*", "k-cup*", "tea bag*", "powder mix",
    ),
    DisallowedClass.SUPPLEMENT.value: (
        "vitamin", "multivitamin", "supplement", "gumm*", "collagen", "protein",
        "pre-workout", "pre workout", "probiotic*", "omega", "fish oil",
        "softgel*", "capsule*", "melatonin", "electrolyte powder", "greens powder",
        "creatine", "amino acid",
    ),
    DisallowedClass.OTC.value: (
        "ibuprofen", "acetaminophen", "aspirin", "naproxen", "antacid", "antihistamine",
        "allergy relief", "pain reliever", "cough", "cold medicine", "nasal spray",
        "eye drop*", "first aid", "bandage*", "gauze", "hydrocortisone", "antibiotic",
        "medicine", "medication", "toothpaste", "mouthwash", "dental chew*",
        "nicotine", "lozenge", "benadryl*", "allergy", "antiseptic", "antifungal",
    ),
    DisallowedClass.NICOTINE.value: ("nicotine", "vape", "e-cigarette", "e-liquid", "juul", "cigarette*", "cigar*"),
    DisallowedClass.COSMETICS.value: (
        "makeup", "lipstick", "mascara", "foundation", "concealer", "eyeshadow",
        "eyeliner", "cosmetic*", "nail polish", "lip gloss", "blush", "bronzer",
    ),
    DisallowedClass.SKINCARE.value: (
        "skincare", "skin care", "moisturizer", "moisturizing lotion", "lotion",
        "serum", "cleanser", "sunscreen", "spf", "retinol", "face cream",
        "body cream", "body lotion", "eye cream", "toner", "exfoliant",
    ),
    DisallowedClass.HAIRCARE.value: (
        "shampoo", "conditioner", "hairspray", "hair spray", "hair gel", "hair oil",
        "styling gel", "hair mask", "leave-in",
    ),
    DisallowedClass.FRAGRANCE.value: (
        "fragrance", "perfume", "cologne", "eau de parfum", "eau de toilette",
        "parfum", "body mist", "deodorant", "antiperspirant",
    ),
    DisallowedClass.TOPICAL_BEAUTY.value: (
        "body wash", "bar soap", "hand soap", "facial wipe*", "makeup remover",
        "lip balm", "shaving cream", "aftershave", "self-tanner",
    ),
    DisallowedClass.COLLECTIBLE.value: ("collectible*", "trading card*", "action figure*", "memorabilia", "coin", "stamp collection"),
    DisallowedClass.FINE_JEWELRY.value: ("fine jewelry", "gold ring", "diamond ring", "necklace", "bracelet", "earring*"),
    DisallowedClass.GIFT_CARD.value: ("gift card", "gift certificate"),
    DisallowedClass.REGULATED.value: (
        "prescription", "medical device", "pharmaceutical", "inhaler", "needle",
        "syringe", "thermometer", "blood pressure monitor", "test kit",
    ),
    DisallowedClass.ALCOHOL.value: ("alcohol", "beer", "wine", "liquor", "vodka", "whiskey", "rum", "tequila"),
    DisallowedClass.TOBACCO.value: ("tobacco", "cigarette", "cigar", "vape", "nicotine", "e-liquid", "juul"),
    DisallowedClass.WEAPONS.value: ("firearm", "ammunition", "knife", "dagger", "pepper spray", "stun gun"),
    DisallowedClass.ANIMAL_PRODUCTS.value: ("live animal", "puppy", "kitten", "reptile", "fish tank live", "for dogs", "for cats", "dog chew*", "cat chew*", "dog food", "cat food", "pet food", "bird feed", "dog treat*", "cat treat*"),
}

# Unit/size hints that push a product into oversized (per pack).
_OVERSIZE_UNIT_HINTS = (
    ("lb", 40.0), ("lbs", 40.0), ("pound", 40.0), ("pounds", 40.0),
    ("kg", 20.0), ("gal", 5.0), ("gallon", 5.0),
)

_EXPIRY_STRONG = ("expires", "best by", "use by", "expiration", "perishable", "refrigerated", "frozen", "shelf life")


@dataclass
class DisallowedResult:
    excluded: bool
    exclusion_reason: Optional[str] = None
    disallowed_classes: List[str] = field(default_factory=list)
    manual_review_required: bool = False
    reason_code: str = "allowed"
    notes: str = ""

    def to_record(self, base: Dict[str, Any]) -> Dict[str, Any]:
        """Merge the disallowed-class decision into a record (mark, never delete)."""
        out = dict(base)
        out["disallowed_classes"] = list(self.disallowed_classes)
        if self.excluded:
            out["eligible_for_costco_non_kirkland_workflow"] = False
            out["exclusion_reason"] = DISALLOWED_CLASS_EXCLUSION_REASON
            out["manual_review_required"] = bool(self.manual_review_required or base.get("manual_review_required"))
        return out


def _title_text(record: Dict[str, Any]) -> str:
    for fld in ("title_raw", "item_name", "product_name", "name", "title_normalized"):
        if record.get(fld):
            return str(record[fld])
    return ""


def _size_text(record: Dict[str, Any]) -> str:
    for fld in ("size_or_weight_raw", "net_weight", "unit_of_measure", "costco_pack_raw", "pack_size"):
        if record.get(fld):
            return str(record[fld])
    return ""


def _category_text(record: Dict[str, Any]) -> str:
    for fld in ("category", "amazon_category", "browse_node", "category_path"):
        if record.get(fld):
            return str(record[fld])
    return ""


def _combined(record: Dict[str, Any]) -> str:
    return " | ".join(x for x in (_title_text(record), _size_text(record), _category_text(record)) if x).lower()


def _hits_oversize_size(record: Dict[str, Any]) -> bool:
    """Check numeric size/weight hints against oversized thresholds."""
    size = _size_text(record)
    if not size:
        return False
    for unit, threshold in _OVERSIZE_UNIT_HINTS:
        m = re.search(r"(\d+(?:\.\d+)?)\s*" + re.escape(unit) + r"\b", size, re.IGNORECASE)
        if m:
            try:
                if float(m.group(1)) >= threshold:
                    return True
            except ValueError:
                continue
    return False


def _kw_match(text: str, kw: str) -> bool:
    """Boundary-safe keyword match. A keyword ending in '*' is a prefix match."""
    if not kw:
        return False
    k = kw.lower()
    if k.endswith("*"):
        prefix = re.escape(k[:-1])
        return re.search(r"(?<![a-z0-9])" + prefix, text) is not None
    return re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", text) is not None


def classify_disallowed(record: Optional[Dict[str, Any]]) -> List[str]:
    """Return the list of disallowed classes detected for a record (empty = allowed)."""
    if not record or not isinstance(record, dict):
        return []
    text = _combined(record)
    found: List[str] = []
    for cls, keywords in DISALLOWED_CLASS_RULES.items():
        for kw in keywords:
            if _kw_match(text, kw):
                found.append(cls)
                break
    # Strong expiry signals anywhere in title/size.
    if any(_kw_match(text, k) for k in _EXPIRY_STRONG) and DisallowedClass.EXPIRY.value not in found:
        found.append(DisallowedClass.EXPIRY.value)
    if _hits_oversize_size(record) and DisallowedClass.OVERSIZED.value not in found:
        found.append(DisallowedClass.OVERSIZED.value)
    return found


def evaluate_disallowed(record: Optional[Dict[str, Any]]) -> DisallowedResult:
    """Evaluate ONE record against disallowed product classes."""
    if not record or not isinstance(record, dict):
        return DisallowedResult(excluded=False, reason_code="allowed",
                                manual_review_required=True, notes="Missing record; flagged for review.")
    classes = classify_disallowed(record)
    if classes:
        return DisallowedResult(
            excluded=True, exclusion_reason=DISALLOWED_CLASS_EXCLUSION_REASON,
            disallowed_classes=classes, reason_code="disallowed_class",
            notes=f"Disallowed product class(es): {', '.join(classes)}.",
        )
    return DisallowedResult(excluded=False, reason_code="allowed",
                            notes="No disallowed product class detected.")


@dataclass
class DisallowedAudit:
    total_discovered: int = 0
    excluded_disallowed: int = 0
    allowed: int = 0
    manual_review_required: int = 0
    by_class: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_discovered": self.total_discovered,
            "excluded_disallowed": self.excluded_disallowed,
            "allowed": self.allowed,
            "manual_review_required": self.manual_review_required,
            "by_class": dict(self.by_class),
        }


def audit_disallowed(records: List[Dict[str, Any]]) -> DisallowedAudit:
    """Apply disallowed-class exclusion to a list and produce an auditable summary.

    Does NOT delete or mutate inputs.
    """
    audit = DisallowedAudit()
    for rec in records:
        audit.total_discovered += 1
        res = evaluate_disallowed(rec)
        for cls in res.disallowed_classes:
            audit.by_class[cls] = audit.by_class.get(cls, 0) + 1
        if res.excluded:
            audit.excluded_disallowed += 1
        else:
            audit.allowed += 1
        if res.manual_review_required:
            audit.manual_review_required += 1
    return audit