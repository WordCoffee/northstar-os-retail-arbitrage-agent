import os
import csv
import re
from difflib import SequenceMatcher
from dotenv import load_dotenv
from typing import Optional, Dict, List, Tuple

load_dotenv()

COSTCO_CSV_PATH = os.getenv("COSTCO_CSV_PATH")

if not COSTCO_CSV_PATH:
    print("[Costco] COSTCO_CSV_PATH not set; cost lookups will be skipped")

REQUIRED_COLUMNS = ("item_name", "costco_cost")
MATCH_RATIO_THRESHOLD = 0.70
HIGH_CONFIDENCE_TITLE_RATIO = 0.85
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# --- product-equivalence fingerprint -------------------------------------
# Purchase analysis requires a hard fingerprint match before estimated
# economics are allowed. Fingerprint dimensions (compared on BOTH sides):
# brand, product line/formula (core tokens), flavor (core token conflicts),
# net weight, pack/count, and UPC/EAN when the catalog row carries one.
# A fuzzy name match may still surface a research candidate, but it sets
# costco_cost_basis = "candidate_match" and blocks estimated economics.
# Tier 2 (high_confidence): strong normalized title identity
# (>= HIGH_CONFIDENCE_TITLE_RATIO) with no known fingerprint conflict —
# valid match, may expose a Costco research cost and existing ROI/profit
# calculations; it is never a purchase authorization by itself.

_BRAND_WORDS = {"kirkland", "krikland", "signature", "costco"}
_STOP_WORDS = {"and", "with", "for", "by", "of", "the", "a", "an", "plus", "feat"}
_UNIT_WORDS = {
    "lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces",
    "fl", "floz", "fluid", "kg", "gram", "grams", "g", "mg", "mcg",
    "liter", "liters", "l", "gal", "gallon", "gallons", "ml",
    "ct", "count", "pk", "pack", "packs", "each",
    "sheet", "sheets", "roll", "rolls", "bag", "bags", "bar", "bars",
    "can", "cans", "bottle", "bottles", "ea", "piece", "pieces",
    "tablet", "tablets", "capsule", "capsules", "pill", "pills", "tab", "tabs",
    "serving", "servings", "wipes", "pads", "packet", "packets",
}

_WEIGHT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(fl\s*oz|oz|lb|lbs|pounds?|kg|g|grams?|mg|mcg|liters?|l|gal|gallons?|ml)\b",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ct|count|pk|packs?|each|eaches|sheets?|rolls?|bags?|bars?|cans?|bottles?|pieces?|tablets?|capsules?|pills?|tabs?|servings?|wipes|pads|packets?)\b",
    re.IGNORECASE,
)
_PAREN_COUNT_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*(?:ct|count|pk|pack)?\s*\)", re.IGNORECASE)
# Compound packs: "5 x 120 ct", "5 Bottles x 120 Metered Sprays". The total
# (product of both numbers) is the canonical count; the parts are dropped so
# "600 ct" compares equal to "5 x 120".
_X_TOTAL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_UPC_RE = re.compile(r"(?:upc|ean)[:\s#]*([0-9]{8,14})", re.IGNORECASE)

_LB_PER_KG = 2.20462
_FLOZ_PER_LITER = 33.814
_FLOZ_PER_GALLON = 128
_LB_PER_MG = 2.20462e-6
_LB_PER_MCG = 2.20462e-9


def _tokens(text: str) -> List[str]:
    if not text:
        return []
    folded = text.casefold()
    folded = re.sub(r"&", " and ", folded)
    folded = re.sub(r"[^a-z0-9. ]+", " ", folded)
    return [t.rstrip(".") for t in folded.split() if t]


def _weight_fingerprint(text: str) -> List[Tuple[str, float]]:
    """All net-weight/volume dimensions as (family, canonical value)."""
    found = []
    for raw in re.findall(r"(\d+(?:\.\d+)?)\s*(fl\s*oz|oz|lb|lbs|pounds?|kg|g|grams?|mg|mcg|liters?|l|gal|gallons?|ml)\b", text.casefold()):
        value = float(raw[0])
        unit = raw[1].replace("fl oz", "floz").strip()
        if unit in ("lb", "lbs", "pound", "pounds"):
            found.append(("weight", round(value, 2)))
        elif unit in ("oz", "ounce", "ounces"):
            found.append(("weight", round(value / 16, 2)))
        elif unit in ("kg",):
            found.append(("weight", round(value * _LB_PER_KG, 2)))
        elif unit in ("g", "grams", "gram"):
            found.append(("weight", round(value * _LB_PER_KG / 1000, 4)))
        elif unit in ("mg",):
            found.append(("weight", round(value * _LB_PER_MG, 6)))
        elif unit in ("mcg",):
            found.append(("weight", round(value * _LB_PER_MCG, 8)))
        elif unit in ("floz",):
            found.append(("volume", round(value, 2)))
        elif unit in ("l", "liter", "liters"):
            found.append(("volume", round(value * _FLOZ_PER_LITER, 2)))
        elif unit in ("gal", "gallon", "gallons"):
            found.append(("volume", round(value * _FLOZ_PER_GALLON, 2)))
        elif unit in ("ml",):
            found.append(("volume", round(value * 0.033814, 2)))
    return sorted(found)


def _count_fingerprint(text: str) -> List[Tuple[float, str]]:
    """All pack/count dimensions canonicalized to (value, "count").

    Compound packs ("5 x 120 ct", "5 Bottles x 120") collapse to their
    TOTAL count so "600 ct" compares equal to "5 x 120". The raw parts are
    intentionally dropped: comparing totals is the equivalence that matters
    for unit economics.
    """
    found = []
    for raw in _COUNT_RE.findall(text.casefold()):
        found.append((float(raw[0]), "count"))
    for raw in _PAREN_COUNT_RE.findall(text):
        found.append((float(raw), "count"))
    for left, right in _X_TOTAL_RE.findall(text.casefold()):
        total = float(left) * float(right)
        if total.is_integer():
            found.append((float(total), "count"))
    return sorted(found)


def _upc_fingerprint(text: str) -> Optional[str]:
    if not text:
        return None
    m = _UPC_RE.search(text)
    return m.group(1) if m else None


def _core_tokens(text: str) -> set:
    """Flavor / product-line tokens: brand, units, numbers, and generic
    connectives removed. A differing core on either side means the
    formula/flavor is known to differ (mismatch), not just unknown."""
    core = set()
    for t in _tokens(text):
        if t in _BRAND_WORDS or t in _STOP_WORDS or t in _UNIT_WORDS:
            continue
        if re.search(r"\d", t):
            continue
        if len(t) == 1:
            continue
        core.add(t)
    return core


def _brand_words(text: str) -> set:
    """Brand tokens present in a title (generic names excluded)."""
    words = set()
    for t in _tokens(text or ""):
        if t in _BRAND_WORDS:
            words.add(t)
    return words


def _normalize_brand(brand: Optional[str]) -> Optional[str]:
    """Normalized brand string from a structured brand field, or None when
    empty/generic. Generic words are removed so "Kirkland Signature" and
    "Signature" both collapse to "kirkland"."""
    if not brand or not isinstance(brand, str):
        return None
    tokens = [t for t in _tokens(brand) if t not in _BRAND_WORDS or t in ("kirkland", "krikland", "costco")]
    text = " ".join(tokens).strip()
    if not text or text in ("kirkland", "krikland", "costco"):
        return None  # generic Kirkland-family brand carries no conflict signal
    return text


def _dice_similarity(amazon_name: str, costco_item_name: str) -> float:
    """Token-set Dice coefficient over normalized tokens. Order-insensitive
    complement to SequenceMatcher (which is letter/subsequence based)."""
    a = set(_tokens(amazon_name or ""))
    c = set(_tokens(costco_item_name or ""))
    if not a or not c:
        return 0.0
    return 2.0 * len(a & c) / (len(a) + len(c))


def _classify_equivalence(
    amazon_name: str,
    costco_item_name: str,
    amazon_upc: Optional[str] = None,
    costco_upc: Optional[str] = None,
    amazon_brand: Optional[str] = None,
) -> Dict:
    """Shared equivalence classification (used by product_equivalence and
    equivalence_evidence). Returns match_quality + match_reason."""
    if amazon_upc and costco_upc:
        amazon_upc = str(amazon_upc).strip()
        costco_upc = str(costco_upc).strip()
        if amazon_upc == costco_upc:
            return {"match_quality": "exact", "match_reason": None}
        return {"match_quality": "mismatch", "match_reason": "UPC/EAN differs (%s vs %s)" % (amazon_upc, costco_upc)}

    a_w = _weight_fingerprint(amazon_name)
    c_w = _weight_fingerprint(costco_item_name)
    a_c = _count_fingerprint(amazon_name)
    c_c = _count_fingerprint(costco_item_name)
    a_u = _upc_fingerprint(amazon_name)
    c_u = _upc_fingerprint(costco_item_name)
    a_core = _core_tokens(amazon_name)
    c_core = _core_tokens(costco_item_name)

    problems = []

    if a_w and c_w and a_w != c_w:
        problems.append("Net weight differs (Amazon %s vs Costco %s)" % (a_w, c_w))
    if a_c and c_c and a_c != c_c:
        problems.append("Pack/count differs (Amazon %s vs Costco %s)" % (a_c, c_c))
    if a_u and c_u and a_u != c_u:
        problems.append("UPC/EAN differs (%s vs %s)" % (a_u, c_u))
    if a_core and c_core and a_core != c_core:
        problems.append("Formula/flavor differs: %s vs %s" % (
            ", ".join(sorted(a_core)), ", ".join(sorted(c_core))
        ))

    # Brand conflict: a specific non-Kirkland Amazon brand paired with a
    # Kirkland-branded Costco row is a known identity difference. Generic
    # names collapse away in _normalize_brand, so only real brand claims
    # conflict — never "kirkland"/"costco" family words.
    amazon_brand_norm = _normalize_brand(amazon_brand)
    costco_brand_words = _brand_words(costco_item_name)
    if amazon_brand_norm and ("kirkland" in costco_brand_words or "krikland" in costco_brand_words or "costco" in costco_brand_words):
        problems.append(
            "Brand differs (Amazon brand %r vs Kirkland-family Costco row)" % amazon_brand_norm
        )

    # Cross-dimension guard: weight/volume evidence on one side with only
    # count/pack evidence on the other is a known incompatible dimension,
    # not a title-similarity nuance. A "40 lb" item and a "72 ct" item
    # cannot be compared through unit evidence, so the pair can never be
    # high_confidence or exact on title strength alone.
    a_dim = "weight" if a_w and not a_c else ("count" if a_c and not a_w else "both" if (a_w and a_c) else None)
    c_dim = "weight" if c_w and not c_c else ("count" if c_c and not c_w else "both" if (c_w and c_c) else None)
    if a_dim and c_dim and a_dim != c_dim and a_dim != "both" and c_dim != "both":
        problems.append("Unit dimension differs (Amazon %s vs Costco %s)" % (
            "weight/volume" if a_dim == "weight" else "count",
            "weight/volume" if c_dim == "weight" else "count",
        ))

    if problems:
        return {"match_quality": "mismatch", "match_reason": "; ".join(problems)}

    has_evidence_a = bool(a_w or a_c or a_u)
    has_evidence_c = bool(c_w or c_c or c_u)
    similarity = _title_similarity(amazon_name, costco_item_name)
    if not has_evidence_a and not has_evidence_c:
        if similarity >= HIGH_CONFIDENCE_TITLE_RATIO:
            return {
                "match_quality": "high_confidence",
                "match_reason": "Strong normalized title identity (%d%%); no weight/pack/UPC evidence on either side — equivalence is highly likely but not fingerprint-confirmed." % round(similarity * 100),
            }
        return {"match_quality": "unknown", "match_reason": "No weight/pack/UPC evidence in either title."}
    if not has_evidence_a or not has_evidence_c:
        if similarity >= HIGH_CONFIDENCE_TITLE_RATIO:
            # High-confidence tier: strong normalized title identity with
            # no known conflict. Weight/pack/UPC evidence may be one-sided
            # or absent — the title is the equivalence evidence and the
            # fingerprint dimensions only guard against known conflicts.
            return {
                "match_quality": "high_confidence",
                "match_reason": "Strong normalized title identity (%d%%); %s carries no weight/pack/UPC evidence and none conflicts." % (
                    round(similarity * 100),
                    "Amazon" if not has_evidence_a else "Costco",
                ),
            }
        return {
            "match_quality": "candidate",
            "match_reason": "No conflict, but weight/pack equivalence cannot be confirmed (%s side carries no weight/pack/UPC)." % (
                "Amazon" if not has_evidence_a else "Costco"
            ),
        }
    return {"match_quality": "exact", "match_reason": None}


def product_equivalence(amazon_name: str, costco_item_name: str,
                        amazon_upc: Optional[str] = None,
                        costco_upc: Optional[str] = None,
                        amazon_brand: Optional[str] = None) -> Dict:
    """Classify the fingerprint match between an Amazon title and a Costco
    catalog row.

    Returns {"match_quality": exact|high_confidence|candidate|mismatch|unknown,
    "match_reason": str|None}. Exact requires: no conflicting dimension,
    equal weight/volume or count evidence on BOTH sides, and identical
    formula/flavor cores — or a shared UPC/EAN (when both sides carry
    one). High-confidence = no known fingerprint conflict and a strong
    normalized title identity (>= HIGH_CONFIDENCE_TITLE_RATIO), even when
    weight/pack/UPC evidence is one-sided or absent — the title itself is
    the equivalence evidence. Candidate = no conflict but incomplete
    evidence and no strong title identity. Mismatch = a known difference.
    Unknown = no comparable fingerprint evidence and no strong title
    identity.
    """
    return _classify_equivalence(
        amazon_name, costco_item_name,
        amazon_upc=amazon_upc, costco_upc=costco_upc, amazon_brand=amazon_brand,
    )


def equivalence_evidence(amazon_name: str, costco_item_name: Optional[str],
                         amazon_upc: Optional[str] = None,
                         costco_upc: Optional[str] = None,
                         amazon_brand: Optional[str] = None) -> Dict:
    """Structured match evidence for explainability (read-only, display
    only — never gates purchases or economics).

    Uses the SAME fingerprints and classification as product_equivalence,
    so the explanation always matches the decision. Every dimension is
    reported as present-or-not with its values; no claim is made for data
    the current matching path did not use (e.g. an Amazon UPC is only a
    "match" when it was actually supplied and compared).
    """
    base = _classify_equivalence(
        amazon_name, costco_item_name or "",
        amazon_upc=amazon_upc, costco_upc=costco_upc, amazon_brand=amazon_brand,
    )

    a_w = _weight_fingerprint(amazon_name)
    c_w = _weight_fingerprint(costco_item_name or "")
    a_c = _count_fingerprint(amazon_name)
    c_c = _count_fingerprint(costco_item_name or "")
    a_u = _upc_fingerprint(amazon_name)
    c_u = _upc_fingerprint(costco_item_name or "")
    a_core = _core_tokens(amazon_name)
    c_core = _core_tokens(costco_item_name or "")

    upc_state = None
    if amazon_upc and costco_upc:
        upc_state = "match" if str(amazon_upc).strip() == str(costco_upc).strip() else "conflict"
    elif amazon_upc or costco_upc:
        upc_state = "one_sided"

    def _pair(a, c):
        if a and c:
            return "match" if a == c else "conflict"
        if a or c:
            return "one_sided"
        return None

    return {
        "match_quality": base["match_quality"],
        "match_reason": base["match_reason"],
        "evidence": {
            "normalized_brand": {
                "amazon": _normalize_brand(amazon_brand),
                "costco": sorted(_brand_words(costco_item_name or "")),
            },
            "title_similarity": _title_similarity(amazon_name, costco_item_name or ""),
            "title_dice": _dice_similarity(amazon_name, costco_item_name or ""),
            "title_tokens": {
                "amazon": len(a_core),
                "costco": len(c_core),
                "shared": len(a_core & c_core),
            },
            "upc": {
                "amazon": bool(amazon_upc) or bool(a_u),
                "costco": bool(costco_upc) or bool(c_u),
                "state": upc_state,
            },
            "pack_count": {
                "amazon": a_c,
                "costco": c_c,
                "state": _pair(a_c, c_c),
            },
            "weight_volume": {
                "amazon": a_w,
                "costco": c_w,
                "state": _pair(a_w, c_w),
            },
            "flavor_variant": {
                "amazon": sorted(a_core - c_core),
                "costco": sorted(c_core - a_core),
                "shared": sorted(a_core & c_core),
                "state": "conflict" if (a_core and c_core and a_core != c_core) else "match",
            },
            "known_conflicts": [
                problem for problem in (base.get("match_reason") or "").split("; ") if problem
            ] if base["match_quality"] == "mismatch" else [],
        },
    }


def _resolve_csv_path() -> str:
    # Relative paths are relative to the project root (where .env lives and
    # where AGENTS.md puts the data/ directory), not the backend directory.
    if os.path.isabs(COSTCO_CSV_PATH):
        return COSTCO_CSV_PATH
    project_root = os.path.dirname(_BACKEND_DIR)
    return os.path.join(project_root, COSTCO_CSV_PATH)


def _normalize_name(value) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


def _title_similarity(amazon_name: str, costco_item_name: str) -> float:
    """SequenceMatcher ratio over the normalized (casefolded, whitespace-
    collapsed) titles. Used only as the high-confidence tier gate; it never
    overrides a known fingerprint conflict (those stay mismatch).

    The token-set Dice coefficient is computed for DISPLAY only
    (equivalence_evidence.title_dice): using it as a gate lifted the locked
    no-evidence pair "Kirkland Test Item" vs "Kirkland Item Test" above the
    0.85 threshold (Dice = 1.0 on pure reorder), which the established
    contract deliberately keeps Unknown — identity cannot be established
    either way without fingerprint evidence. Preserving that contract.
    """
    a = _normalize_name(amazon_name)
    c = _normalize_name(costco_item_name)
    if not a or not c:
        return 0.0
    return SequenceMatcher(None, a, c).ratio()


def catalog_state() -> str:
    """State of the Costco cost-basis catalog, without performing lookups.

    Returns one of:
      - "missing": COSTCO_CSV_PATH unset or the file does not exist
      - "invalid": file exists but has a bad header or is unreadable
      - "empty":   file has no usable cost rows
      - "ready":   at least one usable cost row
    """
    if not COSTCO_CSV_PATH:
        return "missing"
    csv_path = _resolve_csv_path()
    if not os.path.exists(csv_path):
        return "missing"
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return "empty"
        if any(col not in (reader.fieldnames or []) for col in REQUIRED_COLUMNS):
            return "invalid"
        for row in rows:
            try:
                cost = float(row.get("costco_cost"))
            except (TypeError, ValueError):
                continue
            if cost > 0:
                return "ready"
        return "empty"
    except Exception:
        return "invalid"


def get_costco_price(item_name: str, amazon_upc: Optional[str] = None,
                     amazon_brand: Optional[str] = None) -> Optional[Dict]:
    if not COSTCO_CSV_PATH:
        print("[Costco] COSTCO_CSV_PATH not set; skipping lookup")
        return None

    try:
        csv_path = _resolve_csv_path()

        if not os.path.exists(csv_path):
            parent = os.path.dirname(csv_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(list(REQUIRED_COLUMNS))

        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return None

        if any(col not in (reader.fieldnames or []) for col in REQUIRED_COLUMNS):
            print(
                "[Costco] Invalid CSV header. Required columns: item_name,costco_cost"
            )
            return None

        target = _normalize_name(item_name)

        exact_matches = [
            row for row in rows if _normalize_name(row.get("item_name")) == target
        ]

        if len(exact_matches) == 1:
            best_match = exact_matches[0]
        elif len(exact_matches) > 1:
            print("[Costco] Ambiguous exact match for item_name")
            return None
        else:
            best_match = None
            best_ratio = 0.0

            for row in rows:
                ratio = SequenceMatcher(
                    None, item_name.lower(), row["item_name"].lower()
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = row

            if best_match is None or best_ratio < MATCH_RATIO_THRESHOLD:
                return None

        try:
            costco_cost = float(best_match["costco_cost"])
        except (TypeError, ValueError):
            print("[Costco] Invalid row: costco_cost must be numeric")
            return None

        if costco_cost <= 0:
            print("[Costco] Invalid row: costco_cost must be greater than zero")
            return None

        equivalence = product_equivalence(
            item_name,
            best_match["item_name"]
            + ((" upc " + str(best_match.get("upc"))) if best_match.get("upc") else "")
            + ((" ean " + str(best_match.get("ean"))) if best_match.get("ean") else ""),
            amazon_upc=amazon_upc,
            amazon_brand=amazon_brand,
        )
        quality = equivalence["match_quality"]

        # Fuzzy/candidate matches may still surface as research candidates,
        # but their cost basis is a candidate match only — never eligible
        # for estimated economics, tiers, or Pass verdicts.
        basis = "estimated" if quality in ("exact", "high_confidence") else "candidate_match"

        return {
            "item_name": best_match["item_name"],
            "costco_cost": costco_cost,
            # CSV rows are a local cost-basis record, not an invoice
            # confirmation and not a live online price.
            "costco_cost_basis": basis,
            "match_quality": quality,
            "match_reason": equivalence["match_reason"],
            "source": "csv",
        }

    except Exception as e:
        print(f"[Costco] Error: {e}")
        return None