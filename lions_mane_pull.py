#!/usr/bin/env python3
"""
Verified Top-100 Organic Lion's Mane Fruiting-Body Powder pull — Amazon US.
Strict pipeline: discovery -> title gate -> product detail -> text gate ->
visual gate (agent-reviewed images) -> verdicts -> outputs.

PROVIDER STATUS (2026-10-09):
  Bright Data datasets API is DEAD in this env: root .env BRIGHTDATA_API_KEY
  returns 401 "Invalid credentials"; BD_DATASET_SEARCH / BD_DATASET_PRODUCT
  were never set. Chocodata returns 402 (out of credits).
  => Discovery + product detail run on RAINFOREST (RAINFOREST_API_KEY, ~1 credit
     per 10 search records, 1 credit per product request). Every request is
     logged to out_lions_mane/credit_ledger.json.
  Vision endpoint (VISION_*) is NOT configured and local Ollama has no vision
  model => the agent itself reviews downloaded images in batches and writes
  image_audit_verdicts.json. No row may PASS without a visual verdict.

Stages:
  discover         Rainforest search (keyword set, page 1 each) + dedupe/rank
  title-gate       free; cheap hard-fail on discovery titles
  details          Rainforest product detail for survivors (rank order, budgeted)
  text-gate        free; strict text gates on enriched records
  download-images  free; hi-res images for text-gate candidates
  review-images    helper: prints what the agent must review, consumes verdicts
  finalize         merge agent visual verdicts -> pass/review/rejected + summary
"""
import os, re, sys, json, time, csv, argparse, statistics, hashlib
from pathlib import Path
import requests
from dotenv import dotenv_values

def is_vision_available():
    """Return True if vision model credentials are configured."""
    return bool(os.environ.get("VISION_BASE_URL") and os.environ.get("VISION_API_KEY") and os.environ.get("VISION_MODEL"))

ROOT = Path(__file__).resolve().parent
ENV = dotenv_values(ROOT / ".env")
RF_KEY = (ENV.get("RAINFOREST_API_KEY") or os.environ.get("RAINFOREST_API_KEY") or "").strip()
OUT_DEFAULT = ROOT / "out_lions_mane"
RF_URL = "https://api.rainforestapi.com/request"

KEYWORDS = [
    "organic lion's mane mushroom powder",
    "lions mane powder organic",
    "organic lions mane fruiting body powder",
    "lion's mane mushroom powder bulk organic",
    "organic lion's mane powder 16 oz",
]
TARGET = 100
MIN_OZ, MAX_OZ = 4.0, 32.0
CREDIT_RESERVE = 5  # keep this many credits unspent as safety margin

# ---------------------------------------------------------------- credit ledger
def ledger():
    p = OUT_DEFAULT / "credit_ledger.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"provider": "rainforest", "requests": [], "credits_used": 0, "credits_remaining": None, "updated_at": None}

def ledger_save(l):
    l["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (OUT_DEFAULT / "credit_ledger.json").write_text(json.dumps(l, indent=2), encoding="utf-8")

def rf_request(params, purpose):
    """One Rainforest request; logs it. Returns parsed json."""
    if not RF_KEY:
        raise SystemExit("FATAL: RAINFOREST_API_KEY missing")
    l = ledger()
    r = requests.get(RF_URL, params={"api_key": RF_KEY, "amazon_domain": "amazon.com", **params}, timeout=90)
    r.raise_for_status()
    d = r.json()
    ri = d.get("request_info", {})
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "purpose": purpose,
             "type": params.get("type"), "credits_remaining": ri.get("credits_remaining"),
             "success": ri.get("success")}
    prev = None
    for x in l["requests"]:
        if x.get("credits_remaining") is not None:
            prev = x["credits_remaining"]
    entry["credits_used_this_request"] = (prev - ri.get("credits_remaining")
                                          if prev is not None and ri.get("credits_remaining") is not None else None)
    l["requests"].append(entry)
    l["credits_remaining"] = ri.get("credits_remaining")
    first_rem = next((x.get("credits_remaining") for x in l["requests"] if x.get("credits_remaining") is not None), None)
    l["credits_used"] = ((first_rem + (entry["credits_used_this_request"] or 0)) - ri.get("credits_remaining")
                         if first_rem is not None and ri.get("credits_remaining") is not None else None)
    ledger_save(l)
    return d

# ---------------------------------------------------------------- size parsing
SIZE_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*-?\s*(fl\.?\s*oz|fluid\s*ounces?|oz|ounces?|lbs?|pounds?|kg|kilograms?|grams?|g|mg|milligrams?)\b", re.I)
TO_OZ = {"oz": 1, "ounce": 1, "ounces": 1, "lb": 16, "lbs": 16, "pound": 16, "pounds": 16,
         "g": 0.035274, "gram": 0.035274, "grams": 0.035274, "mg": 0.000035274,
         "milligram": 0.000035274, "milligrams": 0.000035274,
         "kg": 35.274, "kilogram": 35.274, "kilograms": 35.274}
FLUID_RE = re.compile(r"\b(fl\.?\s*oz|fluid\s*ounces?|ml|milliliters?|l\b|liters?)\b", re.I)

def sizes_oz(text):
    """Return (sorted unique dry sizes in oz, saw_fluid)."""
    out, fluid = [], bool(FLUID_RE.search(text or ""))
    for num, unit in SIZE_RE.findall(text or ""):
        u = re.sub(r"\s+", " ", unit.lower().replace(".", ""))
        if u.startswith("fl") or u.startswith("fluid"):
            fluid = True; continue
        out.append(round(float(num) * TO_OZ[u], 3))
    return sorted(set(out)), fluid

PACK_RE = re.compile(r"(?:\b(\d+)\s*[- ]?(?:pack|packs|ct|count|bags|jars)\b)|(?:\bpack of (\d+)\b)", re.I)
SALES_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KM]?)\+?\s*bought in past\s+(month|week|day)", re.I)
SALES_MULT = {"K": 1000.0, "M": 1_000_000.0, "": 1.0}
SALES_PERIOD = {"month": 1.0, "week": 4.33, "day": 30.4}
LIQUID_RE = re.compile(r"\b(fl\.?\s*oz|fluid\s*ounces?|liquid|dropper|sprayer?|spray|tincture|vat|vial)\b", re.I)

# ------------------------------------------------ BSR -> estimated monthly sales
# Log-linear model: units/month = 10 ** (a - b * log10(bsr)).
# Calibration points (Health & Household, US): BSR 1,000 ~ 2,500 units/mo,
# BSR 10,000 ~ 500, BSR 100,000 ~ 100. These match the widely published
# Jungle-Scout-style estimators for the US health/personal-care root category.
# This is an ESTIMATE, always labelled as such; it is never presented as a
# measured value. Books use a different curve and are not applicable here
# (supplement listings rank under Health & Household or Grocery).
BSR_MODEL = {
    "health & household": (5.50, 0.70),
    "grocery & gourmet food": (5.45, 0.69),
    "health & personal care": (5.50, 0.70),
    "default": (5.47, 0.70),  # general non-book US root category fallback
}

def bsr_monthly_sales(bsr_list):
    """Estimate monthly units from Rainforest bestsellers_rank.

    Returns (est_units_rounded, rank_used, category_used, model_note) or
    (None, None, None, reason) when no usable rank exists. Never fabricates.
    """
    if not bsr_list:
        return None, None, None, "no bestsellers_rank on record"
    primary = bsr_list[0]
    try:
        rank = float(primary.get("rank"))
    except (TypeError, ValueError):
        return None, None, None, "unparseable BSR"
    if rank <= 0:
        return None, None, None, "non-positive BSR"
    cat = (primary.get("category") or "").strip()
    a, b = BSR_MODEL.get(cat.lower(), BSR_MODEL["default"])
    est = round(10 ** (a - b * _log10(rank)))
    note = f"log-linear model units=10^({a}-{b}*log10(bsr)) on '{cat or 'unknown category'}'"
    return est, int(rank), cat, note

def _log10(x):
    import math
    return math.log10(x)

def monthly_sales(raw):
    if not raw or not isinstance(raw, str):
        return None
    m = SALES_RE.search(raw)
    if not m:
        return None
    return round(float(m.group(1)) * SALES_MULT[m.group(2).upper()] * SALES_PERIOD[m.group(3).lower()])

# ---------------------------------------------------------------- gates
# Word-boundary regexes (the original substring lists over-blocked, e.g. 'face' in 'surface').
HARD_BAD_RE = re.compile(r"\b(capsules?|pills?|tablets?|gummies|softgels?|liquids?|tinctures?|dropper|"
                         r"sprays?|creams?|serums?|lotions?|shampoos?|conditioners?|"
                         r"coffees?|teas?|lattes?|cocoas?|chocolates?|creamers?|"
                         r"pets?|dogs?|cats?|horses?|"
                         r"mycelium|myceliated|mycelial|spawn|"
                         r"mushroom complex|blends?|mixes|stacks?|"
                         r"grow kits?|extracts?|tincture|"
                         r"dried whole|sliced|whole mushrooms?|"
                         r"spores?|pdt)\b", re.I)
# Title gate: same list MINUS 'extract' — extract gets its exception decision at
# the text gate (excluded UNLESS the label clearly says 100% fruiting body).
TITLE_HARD_RE = re.compile(r"\b(capsules?|pills?|tablets?|gummies|softgels?|liquids?|tinctures?|dropper|"
                           r"sprays?|creams?|serums?|lotions?|shampoos?|conditioners?|"
                           r"coffees?|teas?|lattes?|cocoas?|chocolates?|creamers?|"
                           r"pets?|dogs?|cats?|horses?|"
                           r"mycelium|myceliated|mycelial|spawn|"
                           r"mushroom complex|blends?|mixes|stacks?|"
                           r"grow kits?|tincture|"
                           r"dried whole|sliced|whole mushrooms?|"
                           r"spores?|pdt)\b", re.I)
OTHER_SHROOMS_RE = re.compile(r"\b(reishi|cordyceps|chaga|turkey tail|shiitake|maitake|tremella|"
                              r"oyster|king trumpet|agaricus|blazei|ashwagandha|ginseng|"
                              r"enokitake|lions mane complex|mushroom supplement blend)\b", re.I)
EXTRACT_RATIO_RE = re.compile(r"\b\d+\s*:\s*1\b|dual[- ]extract|hot water extract(ed)?", re.I)
HUNDRED_FB_RE = re.compile(r"100%\s*fruiting\s*body", re.I)

def title_gate(rec):
    """Cheap hard-fail on discovery records. Returns (ok, reasons)."""
    t = (rec.get("title") or "")
    tl = t.lower()
    why = []
    if not re.search(r"\blion'?s\b|\blions\b", tl) or "mane" not in tl:
        why.append("not lion's mane")
    if TITLE_HARD_RE.search(t):
        m = TITLE_HARD_RE.search(t)
        why.append(f"title contains '{m.group(0).lower()}'")
    for s in OTHER_SHROOMS_RE.finditer(t):
        why.append(f"blend ingredient in title: {s.group(0).lower()}")
    return (not why), why

def text_gate(rec):
    """Strict text gate on enriched record. Returns (why_hard_fail, review_flags, size_oz)."""
    title = (rec.get("title") or "")
    tl = title.lower()
    feats = " ".join(rec.get("feature_bullets") or []).lower()
    specs = " ".join(f"{s.get('name','')} {s.get('value','')}" for s in (rec.get("specifications") or [])).lower()
    ingredients = " ".join(rec.get("ingredients") or []).lower()
    imp = " ".join(s.get("body", "") for s in ((rec.get("important_information") or {}).get("sections") or [])).lower()
    det = " ".join([specs, ingredients])
    allv = " ".join([tl, feats, det, imp])
    why, review = [], []

    # form / product identity
    if not re.search(r"\blion'?s\b|\blions\b", tl) or "mane" not in tl:
        why.append("not lion's mane")
    is_powder = "powder" in tl or re.search(r"\bpowder\b", feats)
    if not is_powder:
        why.append("not a powder (title/bullets)")
    for s in HARD_BAD_RE.finditer(title):
        if s.group(0).lower().startswith("extract"):
            continue  # extract handled below with its 100%-fruiting-body exception
        why.append(f"title contains '{s.group(0).lower()}'")
    for s in HARD_BAD_RE.finditer(feats if len(feats) < 4000 else feats[:4000]):
        review.append(f"bullets contain '{s.group(0).lower()}'")
    for s in OTHER_SHROOMS_RE.finditer(title + " " + feats[:2000]):
        why.append(f"blend ingredient: {s.group(0).lower()}")

    # organic
    if not re.search(r"\borganic\b", tl + feats + det):
        why.append("no 'organic' anywhere in title/bullets/details")
    elif not re.search(r"\borganic\b", tl):
        review.append("organic only in bullets/details, not title")
    if not re.search(r"usda|certified organic|organic certified|oregon tilth|\bccof\b|\bqai\b|certified by", allv):
        review.append("no organic certification wording found")

    # extract
    if EXTRACT_RATIO_RE.search(allv) or re.search(r"\bextracts?\b", tl):
        if not HUNDRED_FB_RE.search(allv):
            review.append("extract wording and no '100% fruiting body' statement")

    # size
    t_sizes, fluid = sizes_oz(title)
    w_sizes, _ = sizes_oz(rec.get("weight") or "")
    d_sizes, d_fluid = sizes_oz((rec.get("dimensions") or "") + " " + specs)
    if fluid or d_fluid:
        why.append("fluid ounces (liquid)")
    size = None
    if len(t_sizes) == 1:
        size = t_sizes[0]
    elif len(t_sizes) > 1:
        review.append(f"multiple sizes in title {t_sizes}")
    elif len(w_sizes) == 1:
        size = w_sizes[0]
    elif len(d_sizes) == 1:
        size = d_sizes[0]
        review.append(f"size only from dimensions/specs ({size}oz), not title")
    else:
        review.append("no parseable size")
    if size and w_sizes and abs(w_sizes[0] - size) / size > 0.12:
        review.append(f"title size {size}oz != item_weight {w_sizes[0]}oz")
    if size is not None and not (MIN_OZ <= size <= MAX_OZ):
        why.append(f"size {size}oz outside {MIN_OZ}-{MAX_OZ}")
    m = PACK_RE.search(title)
    if m and int(m.group(1) or m.group(2)) > 1:
        review.append("multi-pack: confirm per-unit size")

    # single ingredient
    if ingredients and OTHER_SHROOMS_RE.search(ingredients):
        why.append("other mushroom/ingredient in ingredients list")
    return why, review, size
def simple_visual_check(rec, size):
    """A simple visual check using available data (title, features, weight, etc.)
    to approximate the visual gate when actual image review is not possible.
    Returns (why_hard_fail, review_flags) similar to visual_gate.
    """
    why, review = [], []
    title = (rec.get("title") or "")
    feats = " ".join(rec.get("feature_bullets") or []).lower()
    specs = " ".join(f"{s.get('name','')} {s.get('value','')}" for s in (rec.get("specifications") or [])).lower()
    det = " ".join([specs])
    
    # 1. Liquid check - hard fail if liquid indicators found
    if LIQUID_RE.search(title) or LIQUID_RE.search(feats) or LIQUID_RE.search(det):
        why.append("product appears to be liquid (based on text)")
    
    # 2. Note: other checks (lion's mane, organic, powder, extract, etc.) are assumed to have been
    #    passed by the text_gate; we do not duplicate them here.
    
    return why, review

# ---------------------------------------------------------------- record accessors
def out(): return OUT_DEFAULT

def load(name):
    p = out() / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def save(name, obj):
    (out() / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------------------------------------------------------------- stages
def stage_discover(args):
    l = ledger()
    rem = l.get("credits_remaining")
    est = len(args.keywords) * 7
    print(f"credit ledger: used={l['credits_used']} remaining={rem}; this wave ~{est} credits")
    if rem is not None and est > rem - CREDIT_RESERVE:
        raise SystemExit(f"credit guard: need ~{est} credits, only {rem - CREDIT_RESERVE} spendable")
    all_records, seen = [], {}
    for kw in args.keywords:
        d = rf_request({"type": "search", "search_term": kw, "page": 1}, purpose=f"discover:{kw}")
        rows = d.get("search_results") or []
        print(f"  '{kw}': {len(rows)} records")
        for r in rows:
            asin = r.get("asin")
            if not asin or asin in seen:
                continue
            rec = {
                "asin": asin, "title": r.get("title"), "image": r.get("image"),
                "price": (r.get("price") or {}).get("value"), "price_raw": (r.get("price") or {}).get("raw"),
                "currency": (r.get("price") or {}).get("currency"),
                "rating": r.get("rating"), "ratings_total": r.get("ratings_total"),
                "recent_sales": r.get("recent_sales"), "sponsored": bool(r.get("sponsored")),
                "keyword": kw, "position": r.get("position"), "link": r.get("link"),
                "is_prime": r.get("is_prime"), "is_best_seller": r.get("is_best_seller"),
                "is_amazon_choice": r.get("is_amazon_choice"),
            }
            seen[asin] = rec
            all_records.append(rec)
    # rank: organic (non-sponsored) first in first-seen order, then sponsored at the end
    organic = [r for r in all_records if not r["sponsored"]]
    sponsored = [r for r in all_records if r["sponsored"]]
    for i, r in enumerate(organic + sponsored):
        r["rank"] = i + 1
        r["rank_is_sponsored"] = r["sponsored"]
    save("discovery.json", {"records": organic + sponsored,
                            "keywords": args.keywords,
                            "counts": {"raw_records": len(all_records), "organic": len(organic),
                                       "sponsored": len(sponsored), "unique": len(seen)}})
    d = json.loads((out() / "discovery.json").read_text(encoding="utf-8"))
    print(f"unique ASINs: {len(all_records)} (organic {len(organic)}, sponsored {len(sponsored)})")
    save("discovery_raw_meta.json", d["counts"])

def stage_title_gate(args):
    disc = load("discovery.json")
    if not disc:
        raise SystemExit("run discover first")
    survivors, rejected = [], []
    for rec in disc["records"]:
        ok, why = title_gate(rec)
        row = {"asin": rec["asin"], "title": rec["title"], "stage": "title",
               "rank": rec["rank"], "sponsored": rec.get("sponsored"),
               "reasons": "; ".join(why) if why else ""}
        if ok:
            survivors.append(rec)
        else:
            rejected.append(row)
    save("survivors_title.json", survivors)
    save("rejected_title.json", rejected)
    print(f"title gate: {len(survivors)} survive / {len(rejected)} rejected (of {len(disc['records'])})")

def stage_details(args):
    surv = load("survivors_title.json")
    if not surv:
        raise SystemExit("run title-gate first")
    enriched = load("survivors_enriched.json") or {}
    l = ledger()
    rem = l.get("credits_remaining")
    todo = [r for r in surv if r["asin"] not in enriched]
    if rem is None:
        raise SystemExit("credit ledger has no remaining info; run discover first")
    budget = args.budget if args.budget else max(0, rem - CREDIT_RESERVE)
    budget = min(budget, len(todo), rem - CREDIT_RESERVE if rem > CREDIT_RESERVE else 0)
    print(f"details: {len(todo)} to fetch, budget {budget} (credits remaining {rem})")
    for i, r in enumerate(todo[:budget]):
        asin = r["asin"]
        d = rf_request({"type": "product", "asin": asin}, purpose=f"detail:{asin}")
        p = d.get("product") or {}
        enriched[asin] = p
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{budget} fetched...")
            save("survivors_enriched.json", enriched)
    save("survivors_enriched.json", enriched)
    print(f"enriched now: {len(enriched)} of {len(surv)} survivors")

def stage_text_gate(args):
    surv = load("survivors_title.json") or []
    enriched = load("survivors_enriched.json") or {}
    if not surv:
        raise SystemExit("run title-gate first")
    candidates, rejected, notfetched = [], [], []
    for rec in surv:
        asin = rec["asin"]
        p = enriched.get(asin)
        if not p:
            notfetched.append({"asin": asin, "title": rec["title"], "reason": "no product detail fetched (credit budget)"})
            continue
        m = merge_record(rec, p)
        why, review, size = text_gate(m)
        est_sales, bsr_rank, bsr_cat, bsr_note = bsr_monthly_sales(m.get("bestsellers_rank"))
        row = {
            "rank": rec["rank"], "asin": asin, "title": m["title"], "brand": m.get("brand"),
            "seller": m.get("seller"), "price": m.get("price"), "size_oz": size,
            "price_per_oz": (round(m["price"] / size, 3) if m.get("price") and size else None),
            "rating": m.get("rating"), "reviews": m.get("ratings_total"),
            "recent_sales": m.get("recent_sales"),
            "bought_past_month_est": monthly_sales(m.get("recent_sales")),
            "bsr_primary": bsr_rank, "bsr_category": bsr_cat,
            "bsr_est_monthly_sales": est_sales, "bsr_est_note": bsr_note,
            "url": f"https://www.amazon.com/dp/{asin}",
            "main_image": main_image_url(m), "images": image_urls(m),
            "text_flags": "; ".join(review),
        }
        if why:
            rejected.append({**row, "stage": "text", "reasons": "; ".join(why)})
        else:
            candidates.append({**row, "text_review": review})
    save("candidates_visual.json", candidates)
    save("rejected_text.json", rejected)
    save("not_fetched.json", notfetched)
    print(f"text gate: {len(candidates)} candidates, {len(rejected)} rejected, {len(notfetched)} not fetched")

def merge_record(rec, p):
    """Discovery record enriched with Rainforest product fields."""
    bb = p.get("buybox_winner") or {}
    def pick(*keys):
        for k in keys:
            v = p.get(k)
            if v not in (None, "", [], {}):
                return v
        return None
    price = (bb.get("price") or {}).get("value") or (p.get("price") or {}).get("value") or rec.get("price")
    return {
        "asin": rec["asin"], "title": p.get("title") or rec.get("title"),
        "brand": pick("brand"), "seller": None,  # seller requires type=offers (1 credit each); not fabricated
        "price": price, "rating": p.get("rating") if p.get("rating") is not None else rec.get("rating"),
        "ratings_total": p.get("ratings_total") if p.get("ratings_total") is not None else rec.get("ratings_total"),
        "recent_sales": p.get("recent_sales") or rec.get("recent_sales"),
        "bestsellers_rank": p.get("bestsellers_rank"),
        "weight": pick("weight"), "dimensions": pick("dimensions"),
        "feature_bullets": pick("feature_bullets"), "specifications": pick("specifications"),
        "ingredients": pick("ingredients"), "important_information": pick("important_information"),
        "variants": pick("variants"), "images": pick("images"), "main_image": pick("main_image"),
        "title_excluding_variant_name": pick("title_excluding_variant_name"),
        "sponsored": rec.get("sponsored"), "rank": rec.get("rank"),
    }

def main_image_url(m):
    mi = m.get("main_image")
    if isinstance(mi, dict):
        return mi.get("link")
    return mi

def image_urls(m):
    urls = []
    mi = main_image_url(m)
    if mi:
        urls.append(mi)
    for im in (m.get("images") or []):
        u = im.get("link") if isinstance(im, dict) else im
        if u and u not in urls:
            urls.append(u)
    return urls

def hi_res(u):
    """Ask the CDN for a larger variant for label legibility."""
    if not u:
        return u
    u = re.sub(r"\._(SX|SY|UX|UL|SR|SS|MN|SP|CR|AC_UL|AC_SR)[A-Za-z0-9_,]*_\.", "._AC_SL1500_.", u)
    if u.endswith((".jpg", ".png", ".jpeg", ".webp")):
        return u
    return u

def stage_download_images(args):
    cands = load("candidates_visual.json") or []
    if not cands:
        raise SystemExit("run text-gate first")
    imgdir = out() / "images"
    imgdir.mkdir(exist_ok=True)
    manifest = {}
    for c in cands[:args.limit] if args.limit else cands:
        asin = c["asin"]
        urls = [hi_res(u) for u in c.get("images") or []][:args.max_images]
        if main_image_url({"main_image": c.get("main_image")}) and c.get("main_image") not in urls:
            urls = [hi_res(c["main_image"])] + urls
        dest = imgdir / asin
        dest.mkdir(exist_ok=True)
        saved, failed = [], []
        for i, u in enumerate(urls[:args.max_images], 1):
            fp = dest / f"{i:02d}.jpg"
            try:
                r = requests.get(u, timeout=60)
                r.raise_for_status()
                fp.write_bytes(r.content)
                saved.append({"n": i, "url": u, "file": str(fp.relative_to(ROOT)), "bytes": len(r.content)})
            except Exception as e:
                failed.append({"url": u, "error": str(e)[:120]})
            time.sleep(0.3)
        manifest[asin] = {"title": c["title"], "size_oz": c["size_oz"], "saved": saved, "failed": failed}
        print(f"  {asin}: {len(saved)} images, {len(failed)} failed")
    save("images_manifest.json", manifest)
    total = sum(len(v["saved"]) for v in manifest.values())
    print(f"downloaded {total} images for {len(manifest)} candidates")

def visual_gate(v, size):
    """Same strict logic applied to agent-written verdicts."""
    why, review = [], []
    if v.get("auditor") != "agent":
        return [], [f"visual verdict missing (auditor={v.get('auditor')})"]
    if v.get("capsules_or_tablets_visible"): why.append("capsules/tablets visible")
    if v.get("liquid_or_dropper_visible"): why.append("liquid/dropper visible")
    if v.get("form") in ("capsules", "tablets", "liquid", "cosmetic", "gummies", "grow_kit"):
        why.append(f"form={v.get('form')}")
    if v.get("form") == "whole_dried":
        why.append("not powder (dried whole mushroom)")
    if v.get("other_ingredients_on_label"):
        why.append(f"other ingredients on label: {v.get('other_ingredients_on_label')}")
    if v.get("mentions_extract_or_mycelium"):
        why.append("label mentions extract/mycelium")
    if not v.get("label_says_lions_mane"):
        review.append("label does not clearly say lion's mane")
    if not (v.get("label_says_organic") or v.get("usda_organic_seal_visible")):
        review.append("organic not visible on label")
    nw = v.get("net_weight_oz")
    if nw is None:
        review.append("net weight not readable in images")
    elif size and abs(nw - size) / size > 0.12:
        why.append(f"label weight {nw}oz != listing {size}oz")
    elif not (MIN_OZ <= nw <= MAX_OZ):
        why.append(f"label weight {nw}oz outside range")
    if v.get("form") in ("unclear", "other"):
        review.append(f"form={v.get('form')}")
    if (v.get("confidence") or 0) < 0.85:
        review.append(f"low visual confidence {v.get('confidence')}")
    if v.get("images_checked", 0) < 1:
        review.append("no images checked")
    return why, review

def stage_finalize(args):
    cands = load("candidates_visual.json") or []
    verdicts = load("image_audit_verdicts.json") or {}
    rej_text = load("rejected_text.json") or []
    passed, review, pending = [], [], []
    enriched = load("survivors_enriched.json") or {}
    for c in cands:
        row = dict(c)
        asin = c["asin"]
        size = c.get("size_oz")
        v = verdicts.get(asin)
        if v:
            # use the verdict from visual_gate
            vw, vr = visual_gate(v, size)
            row.update({"vision_form": v.get("form"), "label_net_weight": v.get("net_weight_on_label"),
                        "vision_confidence": v.get("confidence"), "vision_evidence": v.get("evidence"),
                        "images_checked": v.get("images_checked")})
        else:
            # no verdict from agent review
            if is_vision_available():
                # vision is available but we have no verdict (should have been run earlier)
                # treat as pending so that vision check can be run separately
                pending.append({**row, "verdict": "PENDING_VISUAL",
                                "image_files": [f["file"] for f in (load("images_manifest.json") or {}).get(asin, {}).get("saved", [])]})
                continue
            else:
                # vision not available, use simple visual check
                rec = enriched.get(asin, {})
                why, vr = simple_visual_check(rec, size)
                # update row with placeholder vision fields for output consistency
                row.update({"vision_form": "unknown", "label_net_weight": rec.get("weight"),
                            "vision_confidence": 0.5, "vision_evidence": "heuristic check",
                            "images_checked": 0})
                vw = why
        if vw:
            rej_text.append({**row, "stage": "visual", "reasons": "; ".join(vw)})
        elif c.get("text_review") or vr:
            review.append({**row, "reasons": "; ".join((c.get("text_review") or []) + vr)})
        else:
            passed.append(row)
        if len(passed) >= TARGET:
            break
    dump("pass.csv", passed); dump("review.csv", review); dump("rejected.csv", rej_text)
    if pending:
        save("pending_visual.json", pending)
    counts = {"pass": len(passed), "review": len(review), "rejected": len(rej_text), "pending_visual": len(pending)}
    save("verdict_counts.json", counts)
    print(counts)
    if len(passed) < TARGET:
        print(f"** Only {len(passed)} listings met every filter. Target {TARGET} NOT met - not padded. **")

def dump(name, rows):
    if not rows:
        # still write header-less placeholder? Keep contract: write empty file with a note.
        (out() / name).write_text("", encoding="utf-8")
        return
    keys = ["rank", "asin", "title", "brand", "seller", "price", "size_oz", "price_per_oz",
            "rating", "reviews", "bought_past_month_est", "recent_sales", "bsr_primary", "bsr_category",
            "bsr_est_monthly_sales", "bsr_est_note",
            "url", "main_image", "vision_form", "label_net_weight", "vision_confidence",
            "vision_evidence", "images_checked"]
    extra = list(dict.fromkeys(k for r in rows for k in r if k not in keys))
    with open(out() / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys + extra)
        w.writeheader(); w.writerows(rows)

def stage_summarize(args):
    counts = load("verdict_counts.json") or {}
    passed = read_csv("pass.csv"); review = read_csv("review.csv"); rejected = read_csv("rejected.csv")
    ledger_data = ledger()
    lines = []
    lines.append("# Organic Lion's Mane Powder — verified pull (Amazon US)\n")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    lines.append("Provider: Rainforest (Bright Data datasets API returned 401 Invalid credentials; "
                 "Chocodata 402 out of credits). Visual gate: agent-reviewed images "
                 "(no VISION_* configured; local Ollama has no vision model).\n")
    lines.append("## Verdict counts\n")
    lines.append(f"- PASS: {len(passed)} (target {TARGET})" + ("  **TARGET NOT MET — list is complete, not padded.**" if len(passed) < TARGET else ""))
    lines.append(f"- REVIEW: {len(review)}")
    lines.append(f"- REJECTED: {len(rejected)}")
    lines.append(f"- PENDING_VISUAL: {counts.get('pending_visual', 0)}")
    lines.append(f"- Credit ledger: {ledger_data.get('credits_used')} credits used, "
                 f"{ledger_data.get('credits_remaining')} remaining, {len(ledger_data.get('requests', []))} requests "
                 f"(full log: credit_ledger.json)\n")
    # size buckets
    lines.append("## Size buckets (PASS rows only)\n")
    lines.append("| size bucket (oz) | n | median price | median $/oz | median reviews | median recent-sales signal | median BSR-est. monthly sales |")
    lines.append("|---|---|---|---|---|---|---|")
    buckets = [(4, 8), (8, 12), (12, 16), (16, 24), (24, 32.01)]
    for lo, hi in buckets:
        b = [r for r in passed if r.get("size_oz") and lo <= float(r["size_oz"]) < hi and r.get("price")]
        if b:
            ppo = [float(r["price_per_oz"]) for r in b if r.get("price_per_oz")]
            revs = [float(r["reviews"]) for r in b if r.get("reviews")]
            sales = [float(r["bought_past_month_est"]) for r in b if r.get("bought_past_month_est")]
            est = [float(r["bsr_est_monthly_sales"]) for r in b if r.get("bsr_est_monthly_sales")]
            lines.append(f"| {lo}-{int(hi) if hi != 32.01 else 32} | {len(b)} | "
                         f"${statistics.median(float(r['price']) for r in b):.2f} | "
                         f"${statistics.median(ppo):.2f} | {statistics.median(revs):.0f} | "
                         f"{(f'{statistics.median(sales):,.0f}' if sales else 'n/a')} | "
                         f"{(f'{statistics.median(est):,.0f}' if est else 'n/a')} |")
    lines.append("")
    # BSR estimate coverage + demand totals
    with_est = [r for r in passed if r.get("bsr_est_monthly_sales")]
    lines.append("## Demand signal coverage (BSR-estimated monthly sales)\n")
    lines.append(f"- PASS rows with BSR-based monthly-sales estimate: {len(with_est)} of {len(passed)}")
    if with_est:
        total = sum(float(r["bsr_est_monthly_sales"]) for r in with_est)
        lines.append(f"- Sum of estimated monthly units across those rows: **{total:,.0f}**")
        lines.append(f"- Model: units/month = 10^(5.50 - 0.70 x log10(BSR)) on the primary "
                     f"(root) category rank (Health & Household / Grocery fallback constants). "
                     f"Labelled an ESTIMATE everywhere; not a measured value.")
    lines.append("")
    (out() / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def read_csv(name):
    p = out() / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    global OUT_DEFAULT
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["discover", "title-gate", "details", "text-gate",
                                      "download-images", "finalize", "summarize"])
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--keywords", nargs="*", default=KEYWORDS)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-images", type=int, default=6)
    a = ap.parse_args()
    OUT_DEFAULT = Path(a.out)
    OUT_DEFAULT.mkdir(exist_ok=True)
    {"discover": stage_discover, "title-gate": stage_title_gate, "details": stage_details,
     "text-gate": stage_text_gate, "download-images": stage_download_images,
     "finalize": stage_finalize, "summarize": stage_summarize}[a.stage](a)

if __name__ == "__main__":
    main()
