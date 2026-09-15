#!/usr/bin/env python3
"""
Kirkland Signature Product Discovery Pipeline

Finds profitable Kirkland Signature branded products on Amazon that sell >500 units/month
using BSR-based sales estimation. Filters out food categories. Cross-references with
Costco catalog. All data persists locally and auto-loads on session start.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import demand_estimator
import costco_client
import costco_api_client
from kirkland_filter import is_genuine_kirkland_candidate

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
SCANNER_CACHE = os.path.join(CACHE_DIR, "scanner-search-cache.json")
ENRICHED_CACHE = os.path.join(CACHE_DIR, "scanner-search-cache.enriched-candidate.json")
DISCOVERY_OUTPUT = os.path.join(CACHE_DIR, "kirkland-discovery.json")
DISCOVERY_META_OUTPUT = os.path.join(CACHE_DIR, "kirkland-discovery-meta.json")

# Food categories to exclude (Amazon browse node categories)
EXCLUDED_CATEGORIES = {
    "grocery & gourmet food",
    "grocery",
    "food",
    "beverages",
    "wine",
    "beer",
    "spirits",
    "pantry",
    "snacks",
    "candy",
    "chocolate",
    "coffee",
    "tea",
    "breakfast",
    "condiments",
    "sauces",
    "spices",
    "baking",
    "canned goods",
    "packaged foods",
    "frozen foods",
    "dairy",
    "eggs",
    "meat",
    "seafood",
    "produce",
    "bakery",
    "deli",
    "prepared foods",
    "baby food",
    "pet food",
    "vitamins & supplements",
    "health & household",
}

# Keywords that indicate food/beverage in product title.
# NOTE: dietary supplements (vitamins, minerals, fiber, probiotics, fish oil)
# are explicitly NOT food — they are a target arbitrage category.
FOOD_TITLE_KEYWORDS = [
    "water", "beverage", "drink", "juice", "soda", "coffee", "tea",
    "snack", "trail mix", "peanut", "pecan", "almond", "cashew",
    "pistachio", "mixed nuts", "praline", "vanilla extract",
    "k cup", "k-cup", "k-cup pod", "k-cup pods",
    "ground coffee", "whole bean", "roast coffee", "roast",
    "dog food", "cat food", "pet food", "dog treat", "cat treat", "pet treat",
    "dental treat", "training treat",
    "popcorn", "granola", "protein bar", "protein bars", "cookie",
    "chocolate", "candy", "vinegar", "olive oil", "balsamic",
    "tuna", "macadamia", "raisin", "biscuit", "nut bar", "nut bars",
    "s'more", "smores", "caramel", "cheese", "butter", "bagel",
    "croissant", "muffin", "donut", "pasta", "noodle", "rice",
    "soup", "broth", "sauce", "spice", "seasoning", "salt",
]

# Precise multi-word phrases that can neutralize a food-keyword match
# when they appear in the SAME title (e.g. "Plastic Food Wrap" is
# cling film, not a food item). Tokens must be specific enough that they
# never appear in an actual food product.
NON_FOOD_OVERRIDES = [
    "food wrap", "plastic wrap", "stretch tite", "stretch-tite",
    "food service", "foil sheets", "trash bag", "garbage bag",
    "drawstring", "compactor kitchen", "bath tissue", "toilet paper",
]

# Kirkland-relevant Amazon categories to INCLUDE (non-food)
INCLUDED_CATEGORIES = {
    "health & household",
    "health & personal care",
    "beauty & personal care",
    "home & kitchen",
    "home improvement",
    "tools & home improvement",
    "automotive",
    "baby products",
    "pet supplies",
    "sports & outdoors",
    "office products",
    "electronics",
    "electronics accessories",
    "toys & games",
    "books",
}

# Minimum monthly sales threshold
MIN_MONTHLY_SALES = 500

# ---------------------------------------------------------------------------
# Category inference from title (fallback when BSR/category not available)
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "Health & Household": [
        "minoxidil", "hair regrowth", "hair loss", "hair growth", "fiber", "fiber capsule",
        "stool softener", "laxative", "psyllium", "glucosamine", "chondroitin",
        "calcium", "vitamin d", "vitamin d3", "vitamin c", "vitamin b", "multivitamin",
        "supplement", "sleep aid", "doxylamine", "melatonin", "aller", "fluticasone",
        "allergy", "antihistamine", "nasal spray", "corticosteroid", "pain relief",
        "ibuprofen", "acetaminophen", "aspirin", "first aid", "bandage", "antiseptic",
        "thermometer", "blood pressure", "glucose", "diabetic", "compression",
        "brace", "support", "orthopedic", "joint", "muscle", "arthritis",
    ],
    "Beauty & Personal Care": [
        "shampoo", "conditioner", "body wash", "soap", "deodorant", "antiperspirant",
        "toothpaste", "toothbrush", "floss", "mouthwash", "dental", "floss",
        "razor", "shaving", "aftershave", "lotion", "moisturizer", "cream",
        "sunscreen", "sunblock", "lip balm", "hand sanitizer", "sanitizer",
        "makeup", "cosmetic", "skincare", "facial", "cleanser", "toner",
        "serum", "retinol", "hyaluronic", "collagen", "anti-aging", "anti aging",
        "hair care", "styling", "gel", "mousse", "hairspray", "brush", "comb",
    ],
    "Home & Kitchen": [
        "trash bag", "garbage bag", "trash can", "garbage can", "wastebasket",
        "food wrap", "plastic wrap", "stretch tite", "stretch-tite", "foil",
        "aluminum foil", "parchment", "parchment paper", "wax paper", "bag",
        "storage bag", "freezer bag", "ziploc", "container", "tupperware",
        "food storage", "meal prep", "lunch box", "water bottle", "thermos",
        "paper towel", "bath tissue", "toilet paper", "tissue", "napkin",
        "paper plate", "plastic plate", "cup", "bowl", "utensil", "cutlery",
        "kitchen", "cookware", "bakeware", "pan", "pot", "sheet pan",
        "cutting board", "knife", "peeler", "grater", "measuring", "timer",
        "dishwasher", "detergent", "dish soap", "sponge", "scrub", "cleaner",
        "laundry", "detergent", "fabric softener", "dryer sheet", "stain remover",
        "bleach", "disinfectant", "sanitizer", "all purpose", "multi surface",
    ],
    "Home Improvement": [
        "tool", "drill", "saw", "hammer", "screwdriver", "wrench", "pliers",
        "level", "tape measure", "stud finder", "ladder", "scaffold",
        "paint", "primer", "brush", "roller", "tray", "drop cloth",
        "caulk", "sealant", "adhesive", "glue", "epoxy", "tape", "duct tape",
        "electrical", "wire", "outlet", "switch", "breaker", "light", "bulb",
        "plumbing", "pipe", "fitting", "valve", "faucet", "drain", "trap",
        "drywall", "sandpaper", "sander", "shop vac", "vacuum", "dust",
    ],
    "Automotive": [
        "motor oil", "synthetic oil", "oil filter", "air filter", "cabin filter",
        "wiper", "wiper blade", "windshield", "washer fluid", "antifreeze",
        "coolant", "brake fluid", "power steering", "transmission fluid",
        "battery", "jumper cable", "charger", "tire", "tire gauge", "inflator",
        "jack", "stand", "socket", "ratchet", "torque wrench", "scan tool",
        "obd", "code reader", "diagnostic", "fuel", "additive", "cleaner",
        "wax", "polish", "detail", "microfiber", "towel", "applicator",
        "seat cover", "floor mat", "cargo", "organizer", "trunk", "roof rack",
    ],
    "Baby Products": [
        "diaper", "diapers", "wipe", "wipes", "baby wipe", "baby wipes",
        "formula", "baby formula", "bottle", "nipple", "pacifier", "teether",
        "blanket", "swaddle", "sleep sack", "onesie", "bodysuit", "pajamas",
        "crib", "mattress", "sheet", "bumper", "mobile", "monitor", "camera",
        "stroller", "car seat", "carrier", "high chair", "booster", "bib",
        "spoon", "bowl", "plate", "sippy cup", "training cup", "food maker",
        "diaper bag", "changing pad", "diaper pail", "diaper genie", "refill",
    ],
    "Pet Supplies": [
        "dog food", "cat food", "pet food", "kibble", "wet food", "treat",
        "dog treat", "cat treat", "dental chew", "rawhide", "bully stick",
        "toy", "ball", "rope", "squeaky", "plush", "catnip", "scratcher",
        "litter", "litter box", "scoop", "mat", "bed", "crate", "carrier",
        "leash", "collar", "harness", "tag", "grooming", "brush", "nail clipper",
        "shampoo", "conditioner", "flea", "tick", "heartworm", "medication",
        "supplement", "joint", "hip", "probiotic", "enzyme", "pumpkin",
    ],
    "Sports & Outdoors": [
        "tent", "sleeping bag", "sleeping pad", "camp", "camping", "hiking",
        "backpack", "daypack", "hydration", "water bottle", "water filter",
        "stove", "fuel", "cookset", "cooler", "ice pack", "chair", "table",
        "lantern", "headlamp", "flashlight", "battery", "solar", "power bank",
        "gps", "compass", "map", "first aid", "survival", "emergency",
        "fishing", "rod", "reel", "lure", "tackle", "line", "hook",
        "bike", "helmet", "pump", "tube", "tire", "chain", "lock",
        "running", "shoe", "sock", "short", "shirt", "legging", "jacket",
        "yoga", "mat", "block", "strap", "band", "weight", "dumbbell",
        "kettlebell", "resistance", "pull up", "dip", "bar", "rack",
    ],
    "Office Products": [
        "paper", "copy paper", "printer paper", "cardstock", "label", "sticker",
        "ink", "toner", "cartridge", "printer", "scanner", "fax", "copier",
        "pen", "pencil", "marker", "highlighter", "sharpie", "dry erase",
        "whiteboard", "board", "eraser", "magnet", "push pin", "thumbtack",
        "stapler", "staple", "staple remover", "tape", "tape dispenser",
        "scissors", "ruler", "calculator", "calendar", "planner", "notebook",
        "binder", "folder", "file", "hanging file", "divider", "sheet protector",
        "envelope", "mailer", "box", "shipping", "packing", "bubble wrap",
        "desk", "chair", "monitor", "stand", "mount", "keyboard", "mouse",
        "headset", "webcam", "microphone", "speaker", "dock", "hub", "cable",
    ],
    "Electronics": [
        "tv", "television", "monitor", "display", "projector", "screen",
        "soundbar", "speaker", "headphone", "earbud", "earphone", "headset",
        "microphone", "webcam", "camera", "drone", "gimbal", "stabilizer",
        "phone", "smartphone", "case", "screen protector", "charger", "cable",
        "power bank", "wireless charger", "car charger", "adapter", "converter",
        "laptop", "tablet", "ipad", "keyboard", "mouse", "trackpad", "stylus",
        "ssd", "hdd", "drive", "storage", "memory", "ram", "gpu", "cpu",
        "motherboard", "case", "fan", "cooler", "thermal", "paste", "psu",
        "router", "modem", "switch", "access point", "mesh", "wifi", "ethernet",
        "smart home", "alexa", "google home", "hub", "switch", "bulb", "plug",
        "lock", "doorbell", "camera", "sensor", "thermostat", "vacuum", "robot",
    ],
    "Tools & Home Improvement": [
        "tool", "drill", "driver", "impact", "hammer", "saw", "circular saw",
        "miter saw", "table saw", "jigsaw", "reciprocating", "angle grinder",
        "sander", "orbital", "belt", "detail", "polisher", "buffer", "router",
        "planer", "jointer", "lathe", "press", "clamp", "vise", "bench",
        "workbench", "sawhorse", "level", "laser", "square", "ruler", "tape",
        "chalk line", "stud finder", "multimeter", "tester", "voltage", "amp",
        "wire", "cable", "conduit", "box", "outlet", "switch", "breaker",
        "panel", "subpanel", "generator", "inverter", "solar", "panel",
        "battery", "charge", "controller", "inverter", "ups", "surge",
    ],
    "Toys & Games": [
        "toy", "game", "puzzle", "board game", "card game", "dice", "lego",
        "building", "block", "brick", "construction", "vehicle", "car", "truck",
        "train", "track", "plane", "helicopter", "drone", "robot", "rc",
        "remote control", "action figure", "doll", "plush", "stuffed", "animal",
        "arts", "craft", "paint", "marker", "crayon", "clay", "dough", "slime",
        "science", "stem", "educational", "learning", "book", "reading", "story",
        "outdoor", "swing", "slide", "sandbox", "water table", "pool", "sprinkler",
        "sports", "ball", "bat", "glove", "helmet", "pad", "net", "goal", "hoop",
    ],
    "Books": [
        "book", "novel", "fiction", "nonfiction", "biography", "memoir",
        "history", "science", "technology", "business", "finance", "investing",
        "self help", "self-help", "psychology", "philosophy", "religion",
        "spirituality", "cookbook", "recipe", "diet", "nutrition", "fitness",
        "health", "medical", "textbook", "study guide", "exam", "prep",
        "children", "kid", "picture book", "chapter book", "middle grade",
        "young adult", "ya", "graphic novel", "manga", "comic", "magazine",
    ],
}


def infer_category_from_title(title: Optional[str]) -> Optional[str]:
    """Infer category from product title keywords."""
    if not title or not isinstance(title, str):
        return None
    title_lower = title.lower()
    
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in title_lower:
                score += 1
        if score > 0:
            scores[cat] = score
    
    if not scores:
        return None
    
    # Return category with highest score
    return max(scores, key=scores.get)


def normalize_category(cat: Optional[str]) -> Optional[str]:
    """Normalize Amazon category to our taxonomy."""
    if not cat or not isinstance(cat, str):
        return None
    cat_lower = " ".join(cat.lower().split())
    # Map to our canonical categories
    for canonical in INCLUDED_CATEGORIES:
        if canonical in cat_lower or cat_lower in canonical:
            return canonical
    return None


def get_product_category(product: Dict) -> Optional[str]:
    """Get the best available category for a product."""
    # Try explicit category first
    explicit = product.get("bsr_category") or product.get("amazon_category") or product.get("category")
    normalized = normalize_category(explicit)
    if normalized:
        return normalized

    # Fallback: infer from title
    title = product.get("name") or product.get("title")
    return infer_category_from_title(title)


def is_food_category(cat: Optional[str]) -> bool:
    """Check if category is a food/grocery category we should exclude."""
    if not cat or not isinstance(cat, str):
        return False
    cat_lower = " ".join(cat.lower().split())
    for excluded in EXCLUDED_CATEGORIES:
        if excluded in cat_lower or cat_lower in excluded:
            return True
    return False


def is_food_by_title(name: Optional[str]) -> bool:
    """Check if product title indicates food/beverage."""
    if not name or not isinstance(name, str):
        return False
    name_lower = name.lower()

    # First check for food keywords
    for kw in FOOD_TITLE_KEYWORDS:
        if kw in name_lower:
            # If a food keyword matches, only override when a strong
            # non-food signal applies to the same title (e.g. "food wrap"
            # is plastic wrap, not a food item). Broad tokens like
            # "recyclable" never preempt a food match by themselves.
            for override in NON_FOOD_OVERRIDES:
                if override in name_lower:
                    return False
            return True
    return False


def is_kirkland_relevant_category(cat: Optional[str]) -> bool:
    """Check if category is relevant for Kirkland non-food products."""
    if not cat or not isinstance(cat, str):
        return False
    cat_lower = " ".join(cat.lower().split())
    # Must NOT be a food category
    if is_food_category(cat):
        return False
    # Must be in our included categories OR contain relevant keywords
    for included in INCLUDED_CATEGORIES:
        if included in cat_lower or cat_lower in included:
            return True
    # Additional keyword-based check for categories we care about
    relevant_keywords = [
        "health", "beauty", "personal care", "household", "home",
        "kitchen", "automotive", "baby", "pet", "sports", "outdoors",
        "office", "electronics", "tools", "improvement", "cleaning",
        "laundry", "paper", "tissue", "trash", "storage", "organization"
    ]
    return any(kw in cat_lower for kw in relevant_keywords)


# ---------------------------------------------------------------------------
# BSR-based sales estimation (using existing demand_estimator)
# ---------------------------------------------------------------------------

def estimate_monthly_sales(product: Dict) -> Dict:
    """
    Estimate monthly sales using multiple signals in priority order:
    1. Provider's monthly_sales_estimate (from Amazon "bought in past month" card)
    2. BSR + category model (via demand_estimator)
    
    Returns dict with estimate, method, confidence, and source.
    """
    # Priority 1: Provider's direct estimate from search card
    provider_estimate = product.get("monthly_sales_estimate")
    if provider_estimate is not None:
        try:
            val = float(provider_estimate)
            if val > 0:
                return {
                    "estimate": val,
                    "method": "provider_monthly_sales_estimate",
                    "source": "amazon_search_card",
                    "confidence": "higher",
                }
        except (ValueError, TypeError):
            pass
    
    # Priority 2: BSR + category model
    bsr = product.get("bsr") or product.get("sales_rank")
    category = product.get("bsr_category") or product.get("amazon_category") or product.get("category")
    
    if bsr:
        try:
            bsr_val = float(bsr)
        except (ValueError, TypeError):
            bsr_val = None
        
        if bsr_val:
            canonical_cat = normalize_category(category)
            result = demand_estimator.estimate_demand(
                bsr=bsr_val,
                bsr_category=canonical_cat,
                bsr_observed_at=product.get("snapshot_observed_at") or product.get("enriched_at"),
            )
            if result.get("estimated_monthly_sales"):
                return {
                    "estimate": result["estimated_monthly_sales"],
                    "method": result.get("sales_estimation_method", "bsr_category_model"),
                    "source": result.get("sales_estimation_source", "bsr_category_model"),
                    "confidence": result.get("sales_estimation_confidence", "unknown"),
                }
    
    return {
        "estimate": None,
        "method": "unknown",
        "source": "unknown",
        "confidence": "unknown",
    }


# ---------------------------------------------------------------------------
# Costco cross-reference
# ---------------------------------------------------------------------------

def cross_reference_costco(product: Dict) -> Dict:
    """
    Cross-reference product with Costco catalog.
    Returns match info including costco_cost, match_quality, etc.
    """
    name = product.get("name") or product.get("title") or ""
    asin = product.get("asin")
    upc = product.get("upc") or product.get("ean")
    brand = product.get("brand")
    
    # Try the full resolver first (invoice > detail > CSV)
    costco_result = costco_api_client.resolve_costco_cost(
        name, amazon_asin=asin, amazon_upc=upc, amazon_brand=brand
    )
    
    if not costco_result:
        # Fallback to CSV only
        costco_result = costco_client.get_costco_price(
            name, amazon_upc=upc, amazon_brand=brand
        ) or {}
    
    return costco_result


# ---------------------------------------------------------------------------
# Product qualification
# ---------------------------------------------------------------------------

def qualifies_for_analysis(product: Dict, costco_match: Dict) -> Dict:
    """
    Determine if a product qualifies for arbitrage analysis.
    Returns qualification result with reasons.
    """
    reasons = []
    qualifies = True
    
    # Must be genuine Kirkland
    if not is_genuine_kirkland_candidate(product):
        reasons.append("Not a genuine Kirkland Signature product")
        qualifies = False
    
    # Must not be food (check both category and title)
    category = product.get("bsr_category") or product.get("amazon_category") or product.get("category")
    name = product.get("name") or product.get("title") or ""
    if is_food_category(category) or is_food_by_title(name):
        reason = []
        if is_food_category(category):
            reason.append(f"Excluded food category: {category}")
        if is_food_by_title(name):
            reason.append("Excluded food/beverage by title keywords")
        reasons.append("; ".join(reason))
        qualifies = False
    
    # Estimate monthly sales
    sales_result = estimate_monthly_sales(product)
    monthly_sales = sales_result.get("estimate")
    
    # Must have monthly sales estimate > 500
    if monthly_sales is None:
        reasons.append("No sales estimate available (no provider estimate, no BSR)")
        qualifies = False
    elif monthly_sales < MIN_MONTHLY_SALES:
        reasons.append(f"Monthly sales estimate ({monthly_sales:.0f}) below threshold ({MIN_MONTHLY_SALES})")
        qualifies = False
    
    # Must have Costco cost basis
    costco_cost = costco_match.get("costco_cost")
    if costco_cost is None:
        reasons.append("No Costco cost basis found")
        qualifies = False
    else:
        quality = costco_match.get("match_quality")
        if quality not in ("exact", "high_confidence", "invoice_confirmed"):
            reasons.append("Costco match not fingerprint-confirmed (quality=%s)" % quality)
            qualifies = False
    
    return {
        "qualifies": qualifies,
        "reasons": reasons,
        "monthly_sales_estimate": monthly_sales,
        "sales_estimation_method": sales_result.get("method"),
        "sales_estimation_source": sales_result.get("source"),
        "sales_estimation_confidence": sales_result.get("confidence"),
        "costco_cost": costco_cost,
        "costco_cost_basis": costco_match.get("costco_cost_basis"),
        "match_quality": costco_match.get("match_quality"),
        "match_reason": costco_match.get("match_reason"),
    }


# ---------------------------------------------------------------------------
# Main discovery pipeline
# ---------------------------------------------------------------------------

def run_discovery(
    use_cache_only: bool = True,
    min_sales: int = MIN_MONTHLY_SALES,
    excluded_cats: Optional[List[str]] = None,
    included_cats: Optional[List[str]] = None,
) -> Dict:
    """
    Run the Kirkland product discovery pipeline.
    
    Args:
        use_cache_only: If True, only use cached scanner data (no live API calls)
        min_sales: Minimum monthly sales threshold
        excluded_cats: Additional categories to exclude
        included_cats: Additional categories to include
        
    Returns:
        Discovery results with qualified products and metadata
    """
    global MIN_MONTHLY_SALES
    MIN_MONTHLY_SALES = min_sales
    
    if excluded_cats:
        EXCLUDED_CATEGORIES.update(excluded_cats)
    if included_cats:
        INCLUDED_CATEGORIES.update(included_cats)
    
    # Load cached scanner data
    if use_cache_only:
        if not os.path.exists(SCANNER_CACHE):
            return {
                "status": "error",
                "error": f"Scanner cache not found at {SCANNER_CACHE}. Run a live search first.",
                "products": [],
                "qualified": [],
                "summary": {},
            }
        
        with open(SCANNER_CACHE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        candidates = cache_data.get("products", [])
        print(f"Loaded {len(candidates)} candidates from scanner cache")
    else:
        # Live search would go here - but we're cache-only for now
        return {
            "status": "error",
            "error": "Live search not implemented in this pipeline. Use the scanner refresh endpoint.",
            "products": [],
            "qualified": [],
            "summary": {},
        }
    
    # Also load enriched cache if available for BSR/category data
    enriched_by_asin = {}
    if os.path.exists(ENRICHED_CACHE):
        with open(ENRICHED_CACHE, "r", encoding="utf-8") as f:
            enriched_data = json.load(f)
        for p in enriched_data.get("products", []):
            asin = p.get("asin")
            if asin:
                enriched_by_asin[asin.upper()] = p
        print(f"Loaded {len(enriched_by_asin)} enriched records from cache")
    
    # Process each candidate
    all_results = []
    qualified = []
    
    for candidate in candidates:
        # Merge enriched data if available
        asin = candidate.get("asin", "").upper()
        enriched = enriched_by_asin.get(asin, {})
        
        # Merge product data (enriched takes precedence for BSR/category)
        product = {**candidate, **enriched}
        
        # Skip if not Kirkland
        if not is_genuine_kirkland_candidate(product):
            continue
        
        # Get category (explicit field or inferred from title)
        category = get_product_category(product)
        
        # Skip food categories (check both category field and title keywords)
        if is_food_category(category) or is_food_by_title(product.get("name") or product.get("title")):
            continue
        
        # Estimate monthly sales
        sales_result = estimate_monthly_sales(product)
        monthly_sales = sales_result.get("estimate")
        
        # Cross-reference with Costco
        costco_match = cross_reference_costco(product)
        
        # Qualify
        qual = qualifies_for_analysis(product, costco_match)
        
        result = {
            "asin": product.get("asin"),
            "name": product.get("name") or product.get("title"),
            "brand": product.get("brand"),
            "amazon_price": product.get("amazon_price"),
            "product_url": product.get("product_url"),
            "category": product.get("bsr_category") or product.get("amazon_category") or product.get("category"),
            "category_inferred": category if not (product.get("bsr_category") or product.get("amazon_category") or product.get("category")) else None,
            "normalized_category": category,
            "bsr": product.get("bsr") or product.get("sales_rank"),
            "bsr_category": product.get("bsr_category"),
            "monthly_sales_estimate": qual.get("monthly_sales_estimate"),
            "sales_estimation_method": qual.get("sales_estimation_method"),
            "sales_estimation_source": qual.get("sales_estimation_source"),
            "sales_estimation_confidence": qual.get("sales_estimation_confidence"),
            "costco_cost": qual.get("costco_cost"),
            "costco_cost_basis": qual.get("costco_cost_basis"),
            "match_quality": qual.get("match_quality"),
            "match_reason": qual.get("match_reason"),
            "qualifies": qual.get("qualifies"),
            "qualification_reasons": qual.get("reasons"),
            "rating": product.get("rating"),
            "review_count": product.get("review_count") or product.get("reviews_count"),
            "seller_count": product.get("seller_count") or product.get("total_sellers"),
            "fba_sellers": product.get("fba_sellers"),
            "enriched_at": product.get("enriched_at") or product.get("snapshot_fetched_at"),
        }
        
        all_results.append(result)
        
        if qual.get("qualifies"):
            qualified.append(result)
    
    # Sort qualified by monthly sales desc
    qualified.sort(key=lambda x: x.get("monthly_sales_estimate") or 0, reverse=True)
    
    # Build summary
    summary = {
        "total_candidates_scanned": len(candidates),
        "kirkland_products_found": len(all_results),
        "food_excluded": len([c for c in candidates if is_food_category(
            c.get("bsr_category") or c.get("amazon_category") or c.get("category")
        )]),
        "qualified_count": len(qualified),
        "with_bsr_estimate": len([r for r in all_results if r.get("monthly_sales_estimate")]),
        "with_costco_match": len([r for r in all_results if r.get("costco_cost")]),
        "min_sales_threshold": min_sales,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache_source": cache_data.get("source") if use_cache_only else "live",
        "cache_fetched_at": cache_data.get("fetched_at") if use_cache_only else None,
    }
    
    output = {
        "meta": summary,
        "qualified_products": qualified,
        "all_kirkland_products": all_results,
    }
    
    # Save discovery results
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(DISCOVERY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    # Save meta separately for quick loading
    with open(DISCOVERY_META_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nDiscovery complete!")
    print(f"  Total Kirkland products: {len(all_results)}")
    print(f"  Qualified (>{min_sales} sales/mo, non-food, Costco match): {len(qualified)}")
    print(f"  Results saved to: {DISCOVERY_OUTPUT}")
    
    return output


def load_discovery() -> Optional[Dict]:
    """Load the latest discovery results from cache."""
    if not os.path.exists(DISCOVERY_OUTPUT):
        return None
    with open(DISCOVERY_OUTPUT, "r", encoding="utf-8") as f:
        return json.load(f)


def load_discovery_meta() -> Optional[Dict]:
    """Load just the discovery metadata."""
    if not os.path.exists(DISCOVERY_META_OUTPUT):
        return None
    with open(DISCOVERY_META_OUTPUT, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Compatibility layer — discover() and build_manifest() used by pipeline_dry_run
# and test_pipeline_offline. These wrap the older search-based interface.
# ---------------------------------------------------------------------------

_SEARCH_QUERIES = [
    "Kirkland Signature",
    "Kirkland Signature vitamins supplements",
]


def _is_genuine_kirkland(product: Dict) -> bool:
    """Check if product is genuinely Kirkland Signature branded."""
    brand = (product.get("brand") or "").strip().lower()
    title = (product.get("title") or product.get("product_title") or "").strip().lower()
    return brand == "kirkland signature" or "kirkland signature" in title


def discover(search_fn, max_pages: int = 1) -> tuple:
    """Run discovery using a search function with pagination + dedup + brand filter.

    Args:
        search_fn: Callable(query: str, page: int) -> list of product dicts.
        max_pages: Maximum pages to fetch per query.

    Returns:
        (seen, rejected) where:
          seen     – dict of {asin: product_dict} (deduplicated, Kirkland only)
          rejected – list of dicts with {asin, reason} for filtered-out products
    """
    seen: Dict[str, Dict] = {}
    rejected: List[Dict[str, Any]] = []

    for query in _SEARCH_QUERIES:
        for page in range(1, max_pages + 1):
            try:
                products = search_fn(query, page) or []
            except Exception:
                break
            if not products:
                break
            for p in products:
                asin = (p.get("asin") or "").strip()
                if not asin:
                    continue
                if asin in seen:
                    continue  # dedup across queries and within query
                if _is_genuine_kirkland(p):
                    seen[asin] = p
                else:
                    rejected.append({"asin": asin, "reason": "brand_not_kirkland_signature"})

    return seen, rejected


def build_manifest(seen: Dict[str, Dict], rejected: List[Dict]) -> tuple:
    """Build a discovery manifest from seen/rejected.

    Returns:
        (manifest_dict, manifest_file_path)
    """
    import hashlib
    fingerprint_raw = json.dumps(
        sorted(seen.keys()), sort_keys=True
    )
    fingerprint = hashlib.sha256(fingerprint_raw.encode()).hexdigest()[:16]

    manifest = {
        "fingerprint": fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "qualified_count": len(seen),
        "rejected_count": len(rejected),
        "asins": list(seen.keys()),
    }

    manifest_path = os.path.join(CACHE_DIR, "discovery-manifest.json")
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest, manifest_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kirkland Signature Product Discovery")
    parser.add_argument("--min-sales", type=int, default=MIN_MONTHLY_SALES,
                        help=f"Minimum monthly sales threshold (default: {MIN_MONTHLY_SALES})")
    parser.add_argument("--live", action="store_true",
                        help="Run live search (not implemented - use scanner refresh)")
    parser.add_argument("--exclude-cat", action="append", default=[],
                        help="Additional category to exclude")
    parser.add_argument("--include-cat", action="append", default=[],
                        help="Additional category to include")
    parser.add_argument("--load", action="store_true",
                        help="Load and display previous discovery results")
    parser.add_argument("--summary-only", action="store_true",
                        help="Only show summary, not full product list")
    
    args = parser.parse_args()
    
    if args.load:
        result = load_discovery()
        if result:
            meta = result.get("meta", {})
            print(f"Kirkland Discovery Results (generated: {meta.get('generated_at', 'unknown')})")
            print(f"  Total Kirkland: {meta.get('kirkland_products_found', 0)}")
            print(f"  Qualified: {meta.get('qualified_count', 0)}")
            print(f"  Min sales threshold: {meta.get('min_sales_threshold', 0)}")
            if not args.summary_only:
                for i, p in enumerate(result.get("qualified_products", []), 1):
                    print(f"  {i}. {p['asin']} - {p['name'][:60]}")
                    print(f"      Sales/mo: {p['monthly_sales_estimate']:.0f} | Category: {p['category']}")
                    print(f"      Costco cost: ${p['costco_cost']:.2f} ({p['costco_cost_basis']})")
                    print(f"      Match: {p['match_quality']} - {p['match_reason']}")
        else:
            print("No discovery results found. Run without --load to generate.")
    else:
        run_discovery(
            use_cache_only=not args.live,
            min_sales=args.min_sales,
            excluded_cats=args.exclude_cat,
            included_cats=args.include_cat,
        )