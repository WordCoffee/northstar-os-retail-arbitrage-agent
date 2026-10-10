#!/usr/bin/env python3
"""
Rebuild: Organic Lion's Mane Mushroom Powder, Amazon US — widened 1.0–32.0 oz rule.
Cache-first: reads existing collected evidence only. No paid/provider API calls.
Raw files are READ-ONLY; all derived outputs go to out_sb/rebuild_1to32oz/.

Lenses (kept strictly separate):
  market  — customer-visible competitive market: 1–32 oz organic LM powder,
            includes flagged records (extract / full-spectrum / mycelium wording /
            value claims / multipack ambiguity / composition ambiguity).
  clean   — launch-lens comparables: market rows with no unresolved weight conflict,
            no extract/mycelium/blend concern, no organic contradiction, verified form.
Classification vocabulary: qualified market listing / clean comparable /
review required / excluded.
"""
import csv, json, math, re, hashlib
import importlib
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

L = importlib.import_module("lions_mane_sb")
L.MIN_OZ = 1.0  # widened lower bound ONLY for this rebuild; original script untouched

OUT = Path("out_sb")
RB = OUT / "rebuild_1to32oz"
RB.mkdir(exist_ok=True)

PROVIDER = "ScrapingBee (amazon/search + amazon/product); local Qwen2.5-VL vision (Ollama)"
OBS_WINDOW = "2026-10-10 16:53–17:38 UTC (discovery → details → vision)"
BSR_FORMULAS = {
    "health & household": "units/month = 10^(5.50 - 0.70*log10(BSR))",
    "grocery & gourmet food": "units/month = 10^(5.45 - 0.69*log10(BSR))",
    "health & personal care": "units/month = 10^(5.50 - 0.70*log10(BSR))",
    "default": "units/month = 10^(5.47 - 0.70*log10(BSR))",
}
CAT_WARN = "BSR is category-specific; do not compare ranks across categories."

# extra title-level patterns for the rebuild
PET_RE = re.compile(r"\b(pets?|dogs?|cats?|pupp(?:y|ies)|kittens?|horses?|animals?)\b", re.I)
POWDER_TITLE_RE = re.compile(r"\b(powder|pwdr|ground|milled)\b", re.I)
VALUE_CLAIM_RE = re.compile(r"\b(nootropic|memory|focus|brain|cognitive|nerve\s+growth|ngf|immune|energy|mood|sleep|gut|digest|clarity|concentration)\w*\b", re.I)

# ---------------------------------------------------------------- load raw
def load(name, base=OUT):
    p = base / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

disc = load("discovery.json")["records"]
details = load("details.json") or {}
verdicts = load("vision_verdicts.json") or {}
topup = load("vision_verdicts_topup_1to32oz.json", RB) or {}
verdicts = {**verdicts, **topup}
ledger = load("credit_ledger.json") or {}

old = {}
for r in read_csv(OUT / "pass.csv"):
    old[r["asin"]] = ("PASS", str(r.get("reasons") or r.get("text_review") or ""))
for r in read_csv(OUT / "review.csv"):
    old[r["asin"]] = ("REVIEW", str(r.get("reasons") or r.get("visual_reasons") or r.get("text_review") or ""))
for r in read_csv(OUT / "rejected.csv"):
    old.setdefault(r["asin"], ("REJECTED", str(r.get("reasons") or "")))

detail_ts = {}
disc_ts = {}
for req in ledger.get("requests", []):
    p = req.get("purpose", "")
    if p.startswith("detail:"):
        detail_ts.setdefault(p.split(":", 1)[1], req["ts"])
    elif p.startswith("discover:"):
        disc_ts.setdefault(p.split(":", 1)[1].rsplit(":p", 1)[0], req["ts"])

# ---------------------------------------------------------------- helpers
PACK_RE = L.PACK_RE

def _imp(rec):
    return L._imp_sections(rec)

def _ov(rec):
    return L._overview(rec)

def mult_pack_info(title):
    """-> (is_multipack, unit_count or None)"""
    m = PACK_RE.search(title or "")
    if not m:
        # also treat 'X - 5.5oz bags' style counts only when explicit
        return False, None
    n = int(m.group(1) or m.group(2))
    if n > 1:
        return True, n
    return False, None

def normalize_ts(asin, rec):
    ts = detail_ts.get(asin) or disc_ts.get(rec.get("keyword") or "") or None
    return ts or "2026-10-10 (study window)"

def freshness(ts):
    return "observed 2026-10-10 (same day as report)" if ts.startswith("2026-10-10") else "unknown"

def oz_from_text(s):
    vals, fluid = L.sizes_oz(str(s or ""))
    return (vals[0] if vals else None), fluid

# ---------------------------------------------------------------- classify one ASIN
def classify(rec):
    asin = rec["asin"]
    prod = details.get(asin)
    v = verdicts.get(asin) or {}
    title = rec.get("title") or (prod or {}).get("title") or ""
    tl = title.lower()
    reasons = []          # exclusion (hard) reasons
    rev_notes = []        # review-required notes
    flags = {"extract": False, "extract_exception": False, "mycelium": False,
             "blend": False, "value_claims": bool(VALUE_CLAIM_RE.search(title)),
             "blend_unresolved": False}

    # ---- identity / form / organic / size evidence ----
    lm_title = bool(L.LM_RE.search(L.clean(tl))) or "hericium" in tl
    if not lm_title:
        reasons.append("not lion's mane (title)")
        return finish(rec, None, v, reasons, rev_notes, flags, in_range_size=None)

    m = L.HARD_FORM.search(L.clean(tl))
    if m:
        reasons.append(f"non-powder form in title ('{m.group(0)}')")
    m = L.BAD_PHRASE.search(L.clean(tl))
    if m:
        reasons.append(f"wrong product type ('{m.group(0)}')")
    if PET_RE.search(tl):
        reasons.append("pet product")
    m = L.OTHER_SHROOMS.search(L.clean(tl))
    if m:
        reasons.append(f"named multi-ingredient blend in title ('{m.group(0)}')")
    m = L.NOISE_BLEND_RE.search(L.clean(tl))
    if m:
        reasons.append(f"blend pattern in title ('{m.group(0)}')")

    # ---- title-only evidence ----
    title_only_note = "title-only evidence (no details/vision in cache); needs enrichment before clean-lens inclusion"
    if not prod:
        # ---------- title-only evidence ----------
        if not re.search(r"\borganic\b", tl):
            reasons.append("no organic evidence (title-only record)")
        if not POWDER_TITLE_RE.search(tl):
            reasons.append("form not evidenced as powder (title-only record)")
        if re.search(r"\b(whole|sliced|pieces|chunks)\b", tl) and not POWDER_TITLE_RE.search(tl):
            reasons.append("whole/sliced mushroom form (not powder)")
        sizes, fluid = L.sizes_oz(title)
        if fluid:
            reasons.append("fluid ounces (title)")
        unit_count = None
        mp, mc = mult_pack_info(title)
        if mp:
            unit_count = mc
        size = sizes[0] if len(sizes) == 1 else None
        if len(sizes) > 1:
            rev_notes.append(f"multiple sizes in title {sizes}")
        in_range = size is not None and L.MIN_OZ <= size <= L.MAX_OZ
        if size is not None and not in_range:
            reasons.append(f"size {size}oz outside {L.MIN_OZ}-{L.MAX_OZ}")
        if size is None and not reasons:
            rev_notes.append("no parseable size (title-only)")
        # flags from title text
        if re.search(r"\bextracts?\b", L.clean(tl)):
            flags["extract"] = True
        if re.search(r"\bmyceli\w*\b", L.clean(tl)):
            flags["mycelium"] = True
        if L.SOFT_PHRASE.search(L.clean(tl)):
            rev_notes.append("coffee substitute/alternative wording")
        tot = size
        if mp and unit_count and size:
            tot = round(size * unit_count, 2)
            rev_notes.append("title-only multipack: per-unit/total unverified")
        if not reasons:
            rev_notes.insert(0, title_only_note)
        return finish(rec, None, v, reasons, rev_notes, flags,
                      in_range_size=(size if in_range else None),
                      size=size, per_unit=size, total=tot,
                      method=("title size (title-only)" if not mp else "title size × count (title-only)"),
                      is_multipack=mp, unit_count=unit_count,
                      title_only=True)

    # ---------- enriched evidence ----------
    why, review, size = L.text_gate({**prod, "asin": asin})
    # re-map hard reasons per the NEW policy (mycelium is a market flag, not exclusion)
    for r in why:
        if "mycelium" in r:
            flags["mycelium"] = True
        elif "other mushroom/ingredient in ingredients list" in r or "other ingredient in Ingredients section" in r:
            reasons.append("verified multi-ingredient (Ingredients section)")
        elif "blend product pattern" in r:
            reasons.append(r)
        else:
            reasons.append(r)
    # text review flags -> evidence notes / flags
    for r in review:
        if "extract wording in title but '100% fruiting body'" in r:
            flags["extract"] = True
            flags["extract_exception"] = True
            rev_notes.append(r)
        elif "extract wording" in r:
            flags["extract"] = True
            rev_notes.append(r)
        elif "title says 'extract'" in r:
            flags["extract"] = True
            rev_notes.append(r)
        elif "organic only in details" in r:
            rev_notes.append(r)
        elif "other mushroom mentioned in bullets" in r:
            flags["blend_unresolved"] = True
            rev_notes.append(r)
        elif "full spectrum" in r:
            rev_notes.append(r)
        elif "coffee substitute" in r:
            rev_notes.append(r)
        elif "multiple sizes" in r or "no parseable size" in r:
            rev_notes.append(r)
        elif "multi-pack" in r:
            rev_notes.append(r)
        elif "mycelium" in r:
            flags["mycelium"] = True
            rev_notes.append(r)
        else:
            rev_notes.append(r)

    ov = _ov(prod); imp = _imp(prod)
    ing_txt = imp.get("ingredients") or ""
    item_form = (ov.get("item form") or "").lower()

    # vision-derived evidence
    vform = (v.get("form") or "").lower()
    other_lab = L._badge_noise(v.get("other_ingredients_on_label"))
    if other_lab:
        flags["blend"] = True
        reasons.append(f"additional ingredients on label ({'; '.join(other_lab)[:90]})")
    if v.get("mentions_extract_or_mycelium"):
        ev = str(v.get("evidence") or "").lower()
        if re.search(r"\bmyceli", ev):
            flags["mycelium"] = True
        else:
            flags["extract"] = True
        rev_notes.append("label mentions extract/mycelium (see vision evidence)")

    # organic evidence
    organic_text = bool(re.search(r"\borganic\b", L.clean(tl) + " " + L.clean(str(prod.get("bullet_points") or ""))))
    organic_details_only = (not organic_text) and bool(re.search(r"\borganic\b", ing_txt.lower() + " " + str(imp).lower()))
    organic_label = bool(v.get("label_says_organic") or v.get("usda_organic_seal_visible"))
    organic_evidence = []
    if re.search(r"\borganic\b", L.clean(tl)):
        organic_evidence.append("title")
    if re.search(r"\borganic\b", L.clean(str(prod.get("bullet_points") or ""))):
        organic_evidence.append("bullets")
    if organic_details_only:
        organic_evidence.append("details/ingredients")
    if organic_label:
        organic_evidence.append("label image")
    if not organic_evidence:
        reasons.append("no organic evidence anywhere (text/label)")

    # form evidence
    form_ok = ("powder" in item_form) or ("powder" in L.clean(tl)) or ("powder" in L.clean(str(prod.get("bullet_points") or "")))
    if vform and not any(x in vform for x in ("powder",)):
        if any(x in vform for x in ("capsule", "tablet", "liquid", "gummy", "softgel", "cosmetic")):
            reasons.append(f"non-powder form (vision: {vform})")
        else:
            form_ok = form_ok or vform in ("powder_bag", "powder_jar", "powder_pouch", "powder_bottle")
    if not form_ok and not any("non-powder" in r for r in reasons):
        reasons.append("form not evidenced as powder")

    # label weight / multipack resolution
    vision_nw = v.get("net_weight_oz")
    sizes_t, _ = L.sizes_oz(title)
    w_sizes_t, _ = L.sizes_oz(_ov(prod).get("item weight") or "")
    mp, unit_count = mult_pack_info(title)
    is_multipack = mp
    per_unit = None; total = None; method = None
    if mp and unit_count and vision_nw:
        per_unit = vision_nw
        total = round(vision_nw * unit_count, 2)
        method = f"label per-unit weight × {unit_count} (multipack)"
        expected_total = max(sizes_t) if sizes_t else None
        if expected_total and abs(total - expected_total) / expected_total <= 0.12:
            set_size = total
        elif expected_total and abs(per_unit - expected_total) / expected_total <= 0.12:
            set_size = per_unit  # title shows per-unit content
        else:
            set_size = total
            if expected_total:
                rev_notes.append(f"multipack total {total}oz vs listing size {expected_total}oz unresolved")
    elif vision_nw:
        per_unit = vision_nw; total = vision_nw
        method = "label net weight (vision)"
        set_size = vision_nw
    elif len(sizes_t) == 1:
        per_unit = sizes_t[0]; total = sizes_t[0]
        method = "title/size text (no label weight)"
        set_size = sizes_t[0]
    elif len(w_sizes_t) == 1:
        per_unit = w_sizes_t[0]; total = w_sizes_t[0]
        method = "item weight field (no label weight)"
        set_size = w_sizes_t[0]
    else:
        set_size = None
        method = "unresolved"
        if not reasons:
            rev_notes.append("no resolvable net weight")

    # weight conflict check + serving-size protection
    label_txt = str(v.get("net_weight_on_label") or "")
    serving_like = bool(re.search(r"\b(tbsp|tsp|tablespoon|teaspoon|scoop|servings?|packet)\b", label_txt, re.I))
    conflict = False
    listing_size = sizes_t[0] if len(sizes_t) == 1 else None
    if vision_nw and listing_size and not is_multipack:
        if abs(vision_nw - listing_size) / listing_size > 0.12:
            conflict = True
            rev_notes.append(f"label weight {vision_nw}oz vs listing {listing_size}oz conflict")
    if set_size is not None and not (L.MIN_OZ <= set_size <= L.MAX_OZ):
        if set_size < 1.0 and serving_like:
            rev_notes.append(f"label weight reading '{label_txt[:40]}' looks like a serving size; net weight unresolved")
            set_size = None; total = None; per_unit = None
            method = "unresolved (serving-size reading)"
        else:
            reasons.append(f"net weight {set_size}oz outside {L.MIN_OZ}-{L.MAX_OZ}")
    in_range = set_size is not None and L.MIN_OZ <= set_size <= L.MAX_OZ
    # drop evidence notes that the (label) weight evidence resolved
    if set_size is not None:
        for drop in ("no parseable size", "multiple sizes in title", "multi-pack: confirm per-unit size"):
            rev_notes = [x for x in rev_notes if drop not in x]
        if vision_nw and listing_size and abs(vision_nw - listing_size) / listing_size <= 0.12:
            rev_notes = [x for x in rev_notes if "item weight" not in x]
        if is_multipack and unit_count and per_unit:
            rev_notes.append(f"multipack resolved: {unit_count} x {per_unit}oz = {total}oz (label per-unit weight)")

    return finish(rec, prod, v, reasons, rev_notes, flags,
                  in_range_size=(set_size if in_range else None),
                  size=set_size, per_unit=per_unit, total=total, method=method,
                  is_multipack=is_multipack, unit_count=unit_count, conflict=conflict,
                  organic_evidence=organic_evidence, form_ok=form_ok, item_form=item_form,
                  ing_txt=ing_txt, vform=vform)

# ---------------------------------------------------------------- finish/status
def finish(rec, prod, v, reasons, rev_notes, flags, in_range_size=None,
           size=None, per_unit=None, total=None, method=None, is_multipack=False,
           unit_count=None, conflict=False, organic_evidence=None, form_ok=False,
           item_form="", ing_txt="", vform="", title_only=False):
    asin = rec["asin"]
    title = rec.get("title") or ""
    o = old.get(asin, ("UNKNOWN", ""))

    excluded = bool(reasons)
    if excluded:
        market_status = "excluded"; clean_status = "excluded"
    else:
        if size is None:
            market_status = "review_required"; clean_status = "review_required"
        else:
            categorical = (flags["extract"] or flags["mycelium"] or flags["blend"])
            blocking_notes = [x for x in rev_notes if not x.startswith("multipack resolved:")]
            if title_only:
                market_status = "review_required"; clean_status = "review_required"
            elif categorical:
                market_status = "qualified_flagged"; clean_status = "excluded"
            else:
                market_status = "review_required"; clean_status = "review_required" if (blocking_notes or conflict) else "clean_comparable"
                if clean_status == "clean_comparable":
                    market_status = "qualified_clean"

    row = {
        "asin": asin,
        "parent_asin": (prod or {}).get("parent_asin") or None,
        "title": title,
        "brand": (prod or {}).get("brand") or rec.get("brand") or "",
        "url": f"https://www.amazon.com/dp/{asin}",
        "source_provider": PROVIDER,
        "observation_ts": normalize_ts(asin, rec),
        "freshness": freshness(normalize_ts(asin, rec)),
        "product_form": (item_form or vform or ("powder (title-only)" if title_only and in_range_size else "") or "UNKNOWN"),
        "organic_evidence": "; ".join(organic_evidence or []) or ("none" if not title_only else ("title" if re.search(r"organic", (title or "").lower()) else "none")),
        "lions_mane_evidence": "title" + ("; label" if v.get("label_says_lions_mane") else ""),
        "ingredients_text": (ing_txt or str(_imp(prod or {}).get("ingredients") or ""))[:300],
        "extract_flag": flags["extract"],
        "extract_exception_100fb": flags["extract_exception"],
        "mycelium_flag": flags["mycelium"],
        "blend_flag": flags["blend"] or flags["blend_unresolved"],
        "value_add_claims_flag": flags["value_claims"],
        "market_lens_status": market_status,
        "clean_comparable_status": clean_status,
        "status_reasons": "; ".join((reasons if excluded else (rev_notes or [])))[:400],
        "evidence_confidence": ("title_only" if title_only else ("full (details + vision)" if v else "details (no vision)")),
        "visual_review_notes": str(v.get("evidence") or "")[:220],
        "label_net_weight_text": str(v.get("net_weight_on_label") or ""),
        "listed_size_text": title if size is None else f"{size} oz normalized",
        "normalized_unit_weight_oz": per_unit if per_unit is not None else size,
        "unit_count": unit_count if is_multipack else 1,
        "total_sellable_net_weight_oz": total if total is not None else size,
        "is_multipack": is_multipack,
        "container_form": (vform or "UNKNOWN"),
        "weight_ambiguity_flag": size is None,
        "weight_normalization_method": method or "UNKNOWN",
        "current_observed_price": (prod or {}).get("price") or rec.get("price"),
        "currency": "USD",
        "total_price": (prod or {}).get("price") or rec.get("price"),
        "rating": (prod or {}).get("rating") or rec.get("rating"),
        "review_count": (prod or {}).get("reviews_count") or rec.get("reviews"),
        "bought_past_month_text": rec.get("sales_volume") or "",
        "bsr_primary": None, "bsr_category": None,
        "bsr_est_monthly_sales": None, "bsr_est_formula": None,
        "bsr_est_caveat": "ESTIMATE — not observed sales" if v else None,
        "category_comparability_warning": CAT_WARN,
        "old_verdict": o[0], "old_reasons": o[1][:200],
        "reclassified_by_size_rule": False,
    }
    # BSR from details
    sr = (prod or {}).get("sales_rank") or []
    if sr:
        rank = sr[0].get("rank")
        cat = ((sr[0].get("ladder") or [{}])[0].get("name") or "UNKNOWN")
        row["bsr_primary"] = rank
        row["bsr_category"] = cat
        if rank and cat:
            est, _ = L.bsr_monthly_sales(rank, cat)
            row["bsr_est_monthly_sales"] = est
            row["bsr_est_formula"] = BSR_FORMULAS.get(cat.lower(), BSR_FORMULAS["default"])
            row["bsr_est_caveat"] = "ESTIMATE — not observed sales (category-specific BSR model)"
    # price per oz
    price = row["total_price"]
    tot = row["total_sellable_net_weight_oz"]
    if price and tot:
        row["price_per_oz"] = round(float(price) / float(tot), 3)
    else:
        row["price_per_oz"] = None
    # price for title-only rows uses search price — mark
    if not prod:
        row["current_observed_price"] = rec.get("price")
        row["total_price"] = rec.get("price")
        if rec.get("price") and tot:
            row["price_per_oz"] = round(float(rec["price"]) / float(tot), 3)
    row["bought_past_month_est"] = L.monthly_sales(rec.get("sales_volume"))
    return row

# ---------------------------------------------------------------- run all
rows = [classify(rec) for rec in disc]

# reclassification detection: old excluded/demoted with size reason where old size in [1,4)
size_re = re.compile(r"size ([\d.]+)oz outside")
for r in rows:
    m = size_re.search(r["old_reasons"] or "")
    if m and 1.0 <= float(m.group(1)) < 4.0 and r["market_lens_status"] != "excluded":
        r["reclassified_by_size_rule"] = True
    # vision-rejected small labels that now qualify
    if "label weight" in (r["old_reasons"] or "") and r["market_lens_status"] != "excluded":
        r["reclassified_by_size_rule"] = True

# clone / family grouping across market rows
market_rows = [r for r in rows if r["market_lens_status"] != "excluded"]
def norm_title(t):
    t = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
    t = re.sub(r"\b\d+([\d.]*\s*)?(oz|ounce|ounces|lb|lbs|pound|pounds|g|grams|mg)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()
groups = []
used = set()
for i, r in enumerate(market_rows):
    if i in used: continue
    g = [r["asin"]]
    for j in range(i + 1, len(market_rows)):
        if j in used: continue
        if SequenceMatcher(None, norm_title(r["title"]), norm_title(market_rows[j]["title"])).ratio() > 0.80:
            g.append(market_rows[j]["asin"]); used.add(j)
    if len(g) > 1:
        groups.append(g); used.add(i)
dup_map = {}
for gi, g in enumerate(groups, 1):
    for a in g:
        dup_map[a] = f"dupgroup_{gi}"
for r in rows:
    r["duplicate_group"] = dup_map.get(r["asin"], "")
    r["family_id"] = (r["parent_asin"] or (r["brand"].lower().replace(" ", "_") + "::" + norm_title(r["title"])[:40])) if r["brand"] else ""

# ---------------------------------------------------------------- write outputs
FIELDS = ["asin", "parent_asin", "title", "brand", "url", "source_provider", "observation_ts", "freshness",
          "product_form", "organic_evidence", "lions_mane_evidence", "ingredients_text",
          "extract_flag", "extract_exception_100fb", "mycelium_flag", "blend_flag", "value_add_claims_flag",
          "market_lens_status", "clean_comparable_status", "status_reasons", "evidence_confidence", "visual_review_notes",
          "label_net_weight_text", "listed_size_text", "normalized_unit_weight_oz", "unit_count",
          "total_sellable_net_weight_oz", "is_multipack", "container_form", "weight_ambiguity_flag", "weight_normalization_method",
          "current_observed_price", "currency", "total_price", "price_per_oz", "rating", "review_count",
          "bought_past_month_text", "bought_past_month_est",
          "bsr_primary", "bsr_category", "bsr_est_monthly_sales", "bsr_est_formula", "bsr_est_caveat",
          "category_comparability_warning", "family_id", "duplicate_group",
          "old_verdict", "old_reasons", "reclassified_by_size_rule"]

def write_csv(path, rows_):
    rows_ = sorted(rows_, key=lambda r: (r["market_lens_status"] != "qualified_clean", r.get("bsr_primary") or 10**9))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows_)

market_csv = [r for r in rows if r["market_lens_status"] in ("qualified_clean", "qualified_flagged", "review_required") and not r["weight_ambiguity_flag"]]
clean_csv = [r for r in rows if r["clean_comparable_status"] == "clean_comparable"]
review_csv = [r for r in rows if r["market_lens_status"] == "review_required"]
excluded_csv = [r for r in rows if r["market_lens_status"] == "excluded"]

write_csv(RB / "lions_mane_market_1to32oz.csv", market_csv)
write_csv(RB / "lions_mane_clean_comparables_1to32oz.csv", clean_csv)
write_csv(RB / "lions_mane_review_required_1to32oz.csv", review_csv)
write_csv(RB / "lions_mane_excluded_1to32oz.csv", excluded_csv)

# BSR ranking (category-aware)
rank_rows = [dict(r) for r in market_csv if r.get("bsr_primary") and r.get("bsr_category")]
by_cat = defaultdict(list)
for r in rank_rows:
    by_cat[r["bsr_category"]].append(r)
for cat, rs in by_cat.items():
    rs.sort(key=lambda x: x["bsr_primary"])
    for i, r in enumerate(rs, 1):
        r["category_rank"] = i
RANK_FIELDS = ["category_rank", "bsr_category", "bsr_primary", "asin", "title", "brand",
               "market_lens_status", "clean_comparable_status", "total_sellable_net_weight_oz", "is_multipack",
               "total_price", "price_per_oz", "rating", "review_count", "bought_past_month_text",
               "bsr_est_monthly_sales", "bsr_est_formula", "bsr_est_caveat", "evidence_confidence",
               "extract_flag", "mycelium_flag", "blend_flag", "value_add_claims_flag",
               "container_form", "observation_ts", "freshness", "category_comparability_warning"]
with open(RB / "lions_mane_ranked_by_category_bsr.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=RANK_FIELDS)
    w.writeheader()
    for cat, rs in sorted(by_cat.items()):
        for r in rs:
            w.writerow({k: r.get(k) for k in RANK_FIELDS})

# counts
counts = {
    "total_asins": len(rows),
    "market_lens": len(market_csv),
    "clean_comparable": len(clean_csv),
    "review_required": len(review_csv),
    "excluded": len(excluded_csv),
    "market_qualified_clean": sum(1 for r in market_csv if r["market_lens_status"] == "qualified_clean"),
    "market_qualified_flagged": sum(1 for r in market_csv if r["market_lens_status"] == "qualified_flagged"),
    "market_review_required": sum(1 for r in market_csv if r["market_lens_status"] == "review_required"),
    "weight_ambiguous_review_only": sum(1 for r in review_csv if r["weight_ambiguity_flag"]),
    "reclassified_by_size_rule": sum(1 for r in rows if r["reclassified_by_size_rule"]),
    "with_bsr": sum(1 for r in market_csv if r.get("bsr_primary")),
    "categories": {c: len(rs) for c, rs in by_cat.items()},
}
(RB / "rebuild_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
print(json.dumps(counts, indent=2))

# raw-file hash manifest (for the validator to confirm raw evidence unchanged)
raw_files = ["discovery.json", "details.json", "vision_verdicts.json", "pass.csv", "review.csv", "rejected.csv",
             "rejected_title.json", "rejected_text.json", "rejected_visual.json", "credit_ledger.json", "funnel.json"]
manifest = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in raw_files if (OUT / f).exists()}
(RB / "raw_hash_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("raw hash manifest written:", len(manifest), "files")
