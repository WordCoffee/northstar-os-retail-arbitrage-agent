#!/usr/bin/env python3
"""
Strict Top-100 pull: ORGANIC LION'S MANE MUSHROOM POWDER, 4-32 oz, Amazon US.
Provider: ScrapingBee Amazon APIs (free-tier credits: 1000 max, 5 credits/request).

Stages (run in order):
  discover      amazon/search per keyword -> out_sb/discovery.json
  title-gate    cheap hard-fail on titles -> survivors_title.json / rejected_title.json
  details       amazon/product per survivor (5 credits each, budgeted) -> details.json
  text-gate     strict text gates -> candidates_visual.json / rejected_text.json
  visual        structured-data visual check (Item Form, net weight, ingredients)
  finalize      pass.csv / review.csv / rejected.csv / summary.md / funnel.json

Gate alignment with the sourcing brief:
  INCLUDE: lion's mane mushroom powder; organic stated in title or bullets;
           4-32 oz (oz/lb/g/kg converted); bag/pouch/jar/tub/small bottle;
           single-ingredient lion's mane; no blends/stacks/complex/coffee/tea/cocoa products.
  EXCLUDE: capsules, tablets, softgels, gummies, liquids, tinctures, droppers, fl oz,
           sprays, cosmetics, pet, grow kits, whole/sliced dried, mycelium,
           extract (unless 100% fruiting body powder), multi-shroom blends,
           outside 4-32 oz, unconfirmable multi-packs.
  REVIEW (never PASS): unreadable/conflicting size, extract wording without the
           100% fruiting body statement, multi-pack, other mushroom in bullets,
           form/weight/ingredients not confirmable from structured data.
"""
import os, re, sys, json, time, csv, argparse, statistics, math
from collections import Counter
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV = dotenv_values(ROOT / ".env")
SB_KEY = (ENV.get("SCRAPINGBEE_API_KEY") or os.environ.get("SCRAPINGBEE_API_KEY") or "").strip()
OUT = ROOT / "out_sb"
SB = "https://app.scrapingbee.com/api/v1"
COST_PER_REQUEST = 5
START_CREDITS = 985  # measured via /usage: 1000 max, 15 used

KEYWORDS = [
    "organic lions mane powder",
    "organic lion's mane mushroom powder",
    "lions mane powder organic",
    "organic lions mane fruiting body powder",
    "lion's mane mushroom powder bulk organic",
    "organic lion's mane powder 8 oz",
    "organic lion's mane powder 16 oz",
    "organic lion's mane powder 1 lb",
    "organic lions mane mushroom powder bag",
]
TARGET = 100
MIN_OZ, MAX_OZ = 4.0, 32.0
CREDIT_RESERVE = 40

# ---------------------------------------------------------------- ledger
def ledger_load():
    p = OUT / "credit_ledger.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"provider": "scrapingbee", "requests": [], "credits_remaining": START_CREDITS}

def ledger_save(l):
    l["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (OUT / "credit_ledger.json").write_text(json.dumps(l, indent=2), encoding="utf-8")

def sb_get(endpoint, params, purpose):
    if not SB_KEY:
        raise SystemExit("FATAL: SCRAPINGBEE_API_KEY missing")
    l = ledger_load()
    r = requests.get(f"{SB}/{endpoint}",
                     params={"api_key": SB_KEY, "domain": "com", **params}, timeout=180)
    cost = int(r.headers.get("spb-cost") or 0)
    l["requests"].append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "purpose": purpose, "endpoint": endpoint, "http": r.status_code, "cost": cost})
    l["credits_used"] = sum(int(x["cost"] or 0) for x in l["requests"]) + 15
    l["credits_remaining"] = max(0, START_CREDITS - sum(int(x["cost"] or 0) for x in l["requests"]))
    ledger_save(l)
    if r.status_code != 200:
        print(f"  [sb] {endpoint} HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json()

def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def save(name, obj):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------------------------------------------------------------- size parsing
SIZE_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*-?\s*(fl\.?\s*oz|fluid\s*ounces?|oz|ounces?|lbs?|pounds?|kg|kilograms?|grams?|g)\b", re.I)
TO_OZ = {"oz": 1, "ounce": 1, "ounces": 1, "lb": 16, "lbs": 16, "pound": 16, "pounds": 16,
         "g": 0.035274, "gram": 0.035274, "grams": 0.035274, "kg": 35.274, "kilogram": 35.274, "kilograms": 35.274}

def sizes_oz(text):
    vals, fluid = [], False
    for n, unit in SIZE_RE.findall(text or ""):
        u = re.sub(r"\s+", " ", unit.lower().replace(".", ""))
        if u.startswith("fl") or u.startswith("fluid"):
            fluid = True; continue
        vals.append(float(n) * TO_OZ[u])
    if any(v >= 1.5 for v in vals):
        vals = [v for v in vals if v >= 1.5]
    vals.sort()
    clusters = []
    for v in vals:
        if clusters and abs(v - clusters[-1]) / clusters[-1] <= 0.06:
            continue
        clusters.append(v)
    return [round(c, 2) for c in clusters], fluid

PACK_RE = re.compile(r"(?:(\d+)\s*[- ]?(?:pack|packs|ct|count|bags|jars)\b)|(?:pack of (\d+))", re.I)
SALES_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KM]?)\+?\s*bought in past\s+(month|week|day)", re.I)
SALES_MULT = {"K": 1000.0, "M": 1_000_000.0, "": 1.0}
SALES_PERIOD = {"month": 1.0, "week": 4.33, "day": 30.4}

def monthly_sales(raw):
    if not raw or not isinstance(raw, str):
        return None
    m = SALES_RE.search(raw)
    if not m:
        return None
    return round(float(m.group(1)) * SALES_MULT[m.group(2).upper()] * SALES_PERIOD[m.group(3).lower()])

BSR_MODEL = {"health & household": (5.50, 0.70), "grocery & gourmet food": (5.45, 0.69),
             "health & personal care": (5.50, 0.70), "default": (5.47, 0.70)}

def bsr_monthly_sales(rank, category):
    try:
        rank = float(rank)
    except (TypeError, ValueError):
        return None, None
    if rank <= 0:
        return None, None
    cat = (category or "").strip()
    a, b = BSR_MODEL.get(cat.lower(), BSR_MODEL["default"])
    return round(10 ** (a - b * math.log10(rank))), f"units=10^({a}-{b}*log10(bsr)) on '{cat or 'unknown'}'"

# ---------------------------------------------------------------- gates
# Negations must not trigger ("no fillers", "not a blend", "extract free", "mycelium-free").
# Negations like "no fillers", "not a blend", "extract free" must not trigger a reject.
# The clause after the negation is consumed only while it consists of list/connector words,
# so "non-GMO fruiting body & mycelium" keeps 'mycelium' (it is NOT negated) while
# "no fillers, grains, or mycelium" removes it.
_NEG_ITEM = (r"(?:(?:fillers?|additives?|grains?|preservatives?|carriers?|chemicals?|starch|gmos?|sugars?|soy|dairy|gluten|flavors?|artificial|blends?|extracts?|myceli\w+|capsules?|liquids?|drops?|or|and|any|other|a|an)\b[\s,;&-]*)")
NEG_RE = re.compile(r"\b(?:no|not|non|never|without|free of|free from|zero|contains? no)\b[\s\-]+(?:" + _NEG_ITEM + r")+"
                    r"|\b(?:blend|extract|capsule|filler|mycelium)[\s\-]?free\b", re.I)
LM_RE = re.compile(r"lion[''\u2018\u2019`]?s?\W*mane", re.I)
# Unambiguous wrong-product forms (word-boundary; coffee/tea only as product-type phrases)
HARD_FORM = re.compile(r"\b(capsules?|caps|tablets?|gummy|gummies|softgels?|liquid|tinctures?|droppers?|sprays?|"
                       r"creams?|serums?|lotions?|shampoo|conditioner|skincare|"
                       r"pets?|dogs?|cats?|horses?|grow kits?|spawn|pills?|veg ?caps?|"
                       r"sliced|slices|chunks|cubes)\b", re.I)
# Product-type phrases for coffee/tea/cocoa (usage suggestions like "Great for Coffee" do NOT match)
BAD_PHRASE = re.compile(r"\bmushroom coffee\b|\bcoffee (mix|powder|blend|creamer)s?\b|"
                        r"\blions? ?mane coffee\b|\bmushroom latte\b|\blatte (mix|powder)s?\b|"
                        r"\bhot chocolate\b|\bcocoa (powder|mix|blend)s?\b|\bchocolate (powder|mix|drink)s?\b|"
                        r"\bcreamers?\b|\bmatcha\b|\bchai\b|\bmushroom tea\b|\btea (bags?|mix|powder)s?\b", re.I)
SOFT_PHRASE = re.compile(r"\bcoffee (substitute|alternative)s?\b", re.I)
FLUID_RE = re.compile(r"\bfl\.?\s*oz\b|\bfluid\s*ounces?\b", re.I)
NOISE_BLEND_RE = re.compile(r"\b\d{1,2}\s*[- ]?in[- ]?1\b|\bmulti[- ]?mushroom\b|\b\d{1,2}\s*[- ]?mushroom (?:blend|complex|formula)\b", re.I)
SOFT_TITLE = re.compile(r"\b(extracts?|myceli\w+|on grain|blends?|complex|mix|stack|formula|full spectrum)\b", re.I)
OTHER_SHROOMS = re.compile(r"\b(reishi|cordyceps|chaga|turkey tail|shiitake|maitake|tremella|oyster|king trumpet|agaricus|ashwagandha|ginseng"
                           r"|maca|moringa|spirulina|chlorella|turmeric|ginger|cinnamon|mucuna|rhodiola|chamomile|cacao|cocoa)\b", re.I)
HUNDRED_FB = re.compile(r"100%\s*fruiting\s*body|pure\s+fruiting\s*body|fruiting\s*body\s*only", re.I)

def clean(s):
    return NEG_RE.sub(" ", (s or "").lower())

def title_gate(rec):
    """Cheap first pass on discovery records. Returns (hard, soft)."""
    raw = rec.get("title") or ""
    t = clean(raw)
    hard, soft = [], []
    if not LM_RE.search(t):
        hard.append("title not lion's mane")
    m = HARD_FORM.search(t)
    if m:
        hard.append(f"title form word '{m.group(0)}'")
    m = BAD_PHRASE.search(t)
    if m:
        hard.append(f"wrong product type '{m.group(0)}'")
    if FLUID_RE.search(t):
        hard.append("fluid ounces (liquid)")
    m = OTHER_SHROOMS.search(t)
    if m:
        hard.append(f"other ingredient in title '{m.group(0)}'")
    m = SOFT_TITLE.search(t)
    if m:
        soft.append(f"title says '{m.group(0)}' (verify label)")
    m = SOFT_PHRASE.search(t)
    if m:
        soft.append(f"title says '{m.group(0)}' (verify product type)")
    ts, _ = sizes_oz(raw)
    if len(ts) == 1 and not (MIN_OZ <= ts[0] <= MAX_OZ):
        hard.append(f"size {ts[0]}oz outside {MIN_OZ}-{MAX_OZ}")
    return hard, soft

def _imp_sections(rec):
    d = {}
    for s in rec.get("important_information") or []:
        if isinstance(s, dict):
            d[(s.get("title") or "").lower()] = s.get("description") or ""
    return d

def _overview(rec):
    return {str(o.get("title", "")).lower(): str(o.get("description", ""))
            for o in (rec.get("product_overview") or []) if isinstance(o, dict)}

def text_gate(rec):
    """Strict gate on enriched record. Returns (hard, review, size)."""
    raw_title = rec.get("title") or ""
    title = clean(raw_title)
    feats = clean(rec.get("bullet_points") or "")
    desc = clean(rec.get("description") or "")
    ov = _overview(rec)
    imp = _imp_sections(rec)
    ing = clean(imp.get("ingredients", ""))
    det = clean(" ".join([json.dumps(rec.get("product_details") or {}), json.dumps(rec.get("sales_rank") or []),
                          ov.get("item form", ""), ing, imp.get("indications", "")]))
    allv = " ".join([title, feats, desc, det])
    why, review = [], []

    hard, soft = title_gate(rec)
    why += hard; review += soft

    form_field = ov.get("item form", "").lower()
    is_powder = ("powder" in form_field) or ("powder" in title) or ("powder" in feats)
    if not is_powder:
        why.append("not a powder (title/bullets/Item Form)")
    if "powder" not in title and "powder" not in form_field and "powder" not in feats:
        if "powder" in (desc + det):
            review.append("'powder' only in description, not title/bullets")
        else:
            why.append("no 'powder' anywhere")

    if not re.search(r"\borganic\b", allv):
        why.append("no 'organic' anywhere in text")
    elif not re.search(r"\borganic\b", title + " " + feats):
        review.append("organic only in details, not title/bullets")

    if OTHER_SHROOMS.search(feats) and not OTHER_SHROOMS.search(title):
        # educational/comparison mentions are not ingredients; inclusion-style mentions are doubt
        risky = False
        for sent in re.split(r"[.!?;]", feats):
            if OTHER_SHROOMS.search(sent) and not re.search(r"\b(popular|compar\w*|unlike|instead of|not overlook|other mushrooms?|such as|vs\.?)\b", sent):
                risky = True
                break
        ing_clean_ok = bool(ing) and bool(re.search(r"lion\w*\W*mane|hericium", ing)) \
            and not OTHER_SHROOMS.search(ing) and not re.search(r"myceli", ing)
        if risky and not ing_clean_ok:
            review.append("other mushroom mentioned in bullets")

    # mycelium = automatic exclusion (no exception exists for it)
    if re.search(r"\bmyceli\w*\b", title):
        why.append("mycelium in title")
    elif ing and re.search(r"\bmyceli\w*\b", ing):
        why.append("mycelium in Ingredients section")
    elif re.search(r"\bmyceli\w*\b", feats + " " + det):
        why.append("mycelium mentioned in bullets/details (un-negated)")
    # blend product patterns ("25 in 1", "multi-mushroom")
    m = NOISE_BLEND_RE.search(title)
    if m:
        why.append(f"blend product pattern '{m.group(0)}'")
    elif NOISE_BLEND_RE.search(feats):
        review.append("blend product pattern in bullets")
    # extract = excluded unless 100% fruiting body powder is stated
    if re.search(r"\bextracts?\b", title):
        if HUNDRED_FB.search(allv):
            review.append("extract wording in title but '100% fruiting body' statement present")
        else:
            review.append("extract wording in title without '100% fruiting body' statement")
    elif re.search(r"\bextracts?\b", feats + " " + det) and not HUNDRED_FB.search(allv):
        review.append("extract wording in bullets/details without '100% fruiting body' statement")

    t_sizes, fluid = sizes_oz(raw_title)
    w_sizes, _ = sizes_oz(ov.get("item weight", "") + " " + str((rec.get("product_details") or {}).get("product_dimensions", "")))
    if fluid:
        why.append("fluid ounces (liquid)")
    size = None
    if len(t_sizes) == 1:
        size = t_sizes[0]
    elif len(t_sizes) > 1:
        review.append(f"multiple sizes in title {t_sizes} (evaluate per variant)")
    elif len(w_sizes) == 1:
        size = w_sizes[0]  # brief: parse size from title, then item_weight
    else:
        review.append("no parseable size")
    if size and len(w_sizes) == 1 and abs(w_sizes[0] - size) / size > 0.12:
        review.append(f"title size {size}oz != item weight {w_sizes[0]}oz")
    if size is not None and not (MIN_OZ <= size <= MAX_OZ):
        why.append(f"size {size}oz outside {MIN_OZ}-{MAX_OZ}")
    m = PACK_RE.search(raw_title)
    if m and int(m.group(1) or m.group(2)) > 1:
        review.append("multi-pack: confirm per-unit size")
    if ing and OTHER_SHROOMS.search(ing):
        why.append("other ingredient in Ingredients section")
    return list(dict.fromkeys(why)), review, (round(size, 2) if size else None)

# ---------------------------------------------------------------- stages
def stage_discover(args):
    kws = KEYWORDS[:1] if args.probe else (args.keywords or KEYWORDS)
    page = getattr(args, "page", 1) or 1
    disc = load("discovery.json")
    recs = list(disc["records"]) if disc else []
    seen = {r["asin"] for r in recs}
    new_count = 0
    print(f"ScrapingBee discovery: {len(kws)} keywords, page {page}, ~{len(kws)*COST_PER_REQUEST} credits"
          + (f" (merging into existing {len(recs)})" if recs else ""))
    for kw in kws:
        d = sb_get("amazon/search", {"query": kw, "start_page": page}, purpose=f"discover:{kw}:p{page}")
        if not d:
            print(f"  '{kw}' p{page}: FAILED"); continue
        prods = d.get("products") or []
        print(f"  '{kw}' p{page}: {len(prods)} products")
        for prod in prods:
            asin = prod.get("asin")
            if not asin or asin in seen:
                continue
            seen.add(asin); new_count += 1
            recs.append({
                "asin": asin, "title": prod.get("title"), "price": prod.get("price"),
                "rating": prod.get("rating"), "reviews": prod.get("reviews_count"),
                "sales_volume": prod.get("sales_volume"), "is_sponsored": bool(prod.get("is_sponsored")),
                "organic_position": prod.get("organic_position"),
                "sponsored_position": prod.get("sponsored_position"),
                "url_image": prod.get("url_image"), "best_seller": prod.get("best_seller"),
                "keyword": kw, "wave": page,
            })
    org = [r for r in recs if not r["is_sponsored"]]
    spo = [r for r in recs if r["is_sponsored"]]
    for i, r in enumerate(org + spo):
        r["rank"] = i + 1
    save("discovery.json", {"records": org + spo, "keywords": kws,
                            "counts": {"unique": len(recs), "organic": len(org), "sponsored": len(spo)}})
    print(f"+{new_count} new ASINs; total unique: {len(recs)} (organic {len(org)}, sponsored {len(spo)})")
    l = ledger_load(); print(f"credits remaining: {l['credits_remaining']}")

def stage_title_gate(args):
    disc = load("discovery.json")
    if not disc:
        raise SystemExit("run discover first")
    survivors, rejected = [], []
    for rec in disc["records"]:
        hard, soft = title_gate(rec)
        if hard:
            rejected.append({"asin": rec["asin"], "title": rec["title"], "rank": rec["rank"],
                             "stage": "title", "reasons": "; ".join(hard)})
        else:
            rec["soft_flags"] = soft
            survivors.append(rec)
    save("survivors_title.json", survivors)
    save("rejected_title.json", rejected)
    print(f"title gate: {len(survivors)} survive / {len(rejected)} rejected of {len(disc['records'])}")

def stage_details(args):
    surv = load("survivors_title.json") or []
    enriched = load("details.json") or {}
    l = ledger_load()
    rem = l["credits_remaining"] or 0
    todo = [r for r in surv if r["asin"] not in enriched]
    budget = min(len(todo), max(0, (rem - CREDIT_RESERVE) // COST_PER_REQUEST))
    if args.budget:
        budget = min(budget, args.budget)
    print(f"details: {len(todo)} to fetch, budget {budget} requests ({budget*COST_PER_REQUEST} credits), {rem} remaining")
    for i, r in enumerate(todo[:budget]):
        d = sb_get("amazon/product", {"query": r["asin"]}, purpose=f"detail:{r['asin']}")
        if d:
            p = d.get("product") or d
            p.pop("html", None)
            p.pop("screenshot", None)
            enriched[r["asin"]] = p
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{budget}...")
            save("details.json", enriched)
    save("details.json", enriched)
    print(f"enriched: {len(enriched)} of {len(surv)} survivors")

def stage_text_gate(args):
    surv = load("survivors_title.json") or []
    enriched = load("details.json") or {}
    candidates, rejected, not_fetched = [], [], []
    for rec in surv:
        p = enriched.get(rec["asin"])
        if not p:
            not_fetched.append({"asin": rec["asin"], "title": rec["title"], "reason": "not fetched (budget)"})
            continue
        p = dict(p); p["asin"] = rec["asin"]
        why, review, size = text_gate(p)
        sr = p.get("sales_rank") or []
        rank = sr[0].get("rank") if sr else None
        cat = ((sr[0].get("ladder") or [{}])[0].get("name") if sr else None)
        est, note = bsr_monthly_sales(rank, cat)
        imp = _imp_sections(p)
        price = p.get("price")
        row = {
            "rank": rec["rank"], "asin": rec["asin"], "title": p.get("title"), "brand": p.get("brand"),
            "price": price, "size_oz": size,
            "price_per_oz": (round(price / size, 3) if price and size else None),
            "rating": p.get("rating"), "reviews": p.get("reviews_count"),
            "sales_volume": p.get("sales_volume") or rec.get("sales_volume"),
            "bought_past_month_est": monthly_sales(p.get("sales_volume") or rec.get("sales_volume")),
            "bsr_primary": rank, "bsr_category": cat, "bsr_est_monthly_sales": est, "bsr_est_note": note,
            "item_form_overview": _overview(p).get("item form"),
            "item_weight_overview": _overview(p).get("item weight") or (p.get("product_details") or {}).get("product_dimensions"),
            "ingredients_section": imp.get("ingredients"),
            "url": f"https://www.amazon.com/dp/{rec['asin']}",
            "main_image": (p.get("images") or [None])[0],
            "images": (p.get("images") or [])[:6],
        }
        if why:
            rejected.append({**row, "stage": "text", "reasons": "; ".join(why)})
        else:
            candidates.append({**row, "text_review": review})
    save("candidates_visual.json", candidates)
    save("rejected_text.json", rejected)
    save("not_fetched.json", not_fetched)
    print(f"text gate: {len(candidates)} candidates, {len(rejected)} rejected, {len(not_fetched)} not fetched")

def _ingredient_analysis(ing):
    """Analyze an Ingredients section string -> (mentions_lm, has_mycelium, has_extract, extra_text)."""
    if not ing:
        return False, False, False, ""
    s = clean(ing.lower())  # negation-aware: 'no mycelium' must not count as mycelium
    mentions_lm = bool(LM_RE.search(s)) or "hericium" in s
    has_mycelium = bool(re.search(r"\bmyceli\w*\b", s))
    has_extract = bool(re.search(r"\bextract", s))
    # extra ingredients check: everything except the lion's mane ingredient itself
    body = re.split(r"other ingredients?:", s)[0]
    body = re.sub(r"lion\W{0,4}s?\W{0,4}mane[a-z]*|hericium(\s*erinaceus)?|melena[\W]*(de[\W]*)?le\w*", " ", body)
    body = re.sub(r"\b(100%|pure|organic|certified|certificado|single|ingredients?|mushrooms?|hongo[s]?|suplemento|"
                  r"powder|polvo|superfood|fruiting\s*bods?(y|ies)|sporocarp|entire|stalks?|caps?|stems?|"
                  r"freeze[- ]?dried|whole|raw|natural|ground|biomass|and|with|from|of|the|de|"
                  r"org\s?nico|organico|melena|le\s?n|just|only|real)\b", " ", body)
    body = re.sub(r"\(|\)", " ", body)
    body = re.sub(r"\b\d+(\.\d+)?\s*(mg|g|oz)?\b", " ", body)
    body = re.sub(r"[^a-z\s]", " ", body)
    body = re.sub(r"\s+", " ", body).strip(" &,.-")
    return mentions_lm, has_mycelium, has_extract, body

REAL_INGREDIENT_RE = re.compile(r"\b(reishi|cordyceps|chaga|turkey tail|shiitake|maitake|tremella|oyster|king trumpet|agaricus|ashwagandha|ginseng|maca|moringa|spirulina|chlorella|turmeric|ginger|cinnamon|mucuna|rhodiola|chamomile|collagen|creatine|"
                                r"maltodextrin|dextrose|stevia|silicon dioxide|natural flavors?|gelatin|rice flour|rice extract|pterostilbene|chicory|inulin|acacia|tapioca|honey|myceli\w*|sugar(?![\s\-]?free))\b", re.I)

def _badge_noise(entries):
    """Filter vision 'other ingredients' entries down to real ingredient-like items."""
    real = []
    for e in entries or []:
        s = str(e)
        if REAL_INGREDIENT_RE.search(s) or re.search(r"\b\d+\s+(essential\s+)?mushrooms?\b", s, re.I):
            real.append(s)
    return real

def stage_visual(args):
    """Visual gate merge: structured data + optional vision-model verdicts
    (vision_verdicts.json). PASS requires BOTH sources clean. Anything uncertain -> REVIEW."""
    cands = load("candidates_visual.json") or []
    verdicts = load("vision_verdicts.json") or {}
    passed, review, rejected_visual = [], [], []
    for c in cands:
        why, rev = [], []
        asin = c["asin"]
        form = (c.get("item_form_overview") or "").lower()
        w = (c.get("item_weight_overview") or "")
        w_sizes, _ = sizes_oz(w)
        size = c.get("size_oz")
        ing = (c.get("ingredients_section") or "")
        lm_ok, myc, extr, extras = _ingredient_analysis(ing)
        fb100 = HUNDRED_FB.search(" ".join([str(c.get("title") or ""), str(c.get("ingredients_section") or "")]))

        # ---- structured evidence ----
        if ing:
            if not lm_ok:
                why.append("Ingredients section does not mention lion's mane/hericium")
            if myc:
                why.append("mycelium in Ingredients section")
            if extr and not fb100:
                rev.append("extract wording in Ingredients without 100% fruiting body")
            if extras:
                rev.append(f"possible extra ingredients: '{extras[:60]}'")
        elif not verdicts.get(asin):
            rev.append("no Ingredients data and no vision verdict")
        if w_sizes and size and abs(w_sizes[0] - size) / size > 0.35:
            rev.append(f"item weight {w_sizes[0]}oz far from listing {size}oz (packaging or variant mismatch)")

        # ---- vision evidence ----
        v = verdicts.get(asin)
        if not v or v.get("error"):
            rev.append("no vision verdict - visual verification not completed (never PASS)")
        if v and not v.get("error"):
            if v.get("capsules_or_tablets_visible") or v.get("liquid_or_dropper_visible"):
                why.append("vision: capsules/tablets/liquid visible")
            vform = (v.get("form") or "").lower()
            if any(x in vform for x in ("capsule", "tablet", "liquid", "gummy", "softgel", "cosmetic")):
                why.append(f"vision: form={vform}")
            other = _badge_noise(v.get("other_ingredients_on_label"))
            if other:
                why.append(f"vision: other ingredients on label ({'; '.join(other)[:120]})")
            if v.get("mentions_extract_or_mycelium"):
                why.append("vision: label mentions extract/mycelium")
            if not v.get("label_says_lions_mane"):
                rev.append("vision: label not clearly lion's mane")
            if not (v.get("label_says_organic") or v.get("usda_organic_seal_visible")):
                rev.append("vision: organic not visible on label")
            nw = v.get("net_weight_oz")
            if nw is None:
                rev.append("vision: net weight not readable")
            elif nw < 1.0:
                rev.append(f"vision: weight reading '{str(v.get('net_weight_on_label'))[:30]}' looks like a serving size, not net weight")
            else:
                in_range = MIN_OZ <= nw <= MAX_OZ
                match = (size is None) or abs(nw - size) / size <= 0.12
                if in_range and match:
                    if size is None:
                        # vision weight supplies the size when the title lacked one
                        c = {**c, "size_oz": nw, "price_per_oz": (round(c["price"] / nw, 3) if c.get("price") else None)}
                        c["text_review"] = [x for x in (c.get("text_review") or []) if "no parseable size" not in x]
                    else:
                        # label weight confirmed: item-weight-vs-title flags are packaging artifacts
                        c = {**c, "text_review": [x for x in (c.get("text_review") or []) if "item weight" not in x]}
                else:
                    mult = None
                    if size:
                        for k in (2, 3, 4):
                            if abs(nw * k - size) / size <= 0.12:
                                mult = k; break
                    if mult:
                        rev.append(f"vision: per-unit {nw}oz x{mult} ~ listing {size}oz (multi-pack per-unit check)")
                    elif not in_range:
                        why.append(f"vision: label weight {nw}oz outside {MIN_OZ}-{MAX_OZ}")
                    else:
                        rev.append(f"vision: label weight {nw}oz != listing {size}oz")

        row = dict(c)
        row.update({"vision_form": (v or {}).get("form") or form or None,
                    "label_net_weight": (v or {}).get("net_weight_on_label") or w or None,
                    "vision_confidence": (v or {}).get("confidence", 0.5),
                    "vision_evidence": (v or {}).get("evidence") or f"structured: form='{form}', weight='{w}', ingredients='{ing[:80]}'",
                    "images_checked": (v or {}).get("images_checked", 0)})
        if why:
            rejected_visual.append({**row, "stage": "visual", "reasons": "; ".join(why)})
        elif rev:
            review.append({**row, "visual_reasons": "; ".join(rev)})
        else:
            passed.append(row)
    save("visual_pass.json", passed)
    save("visual_review.json", review)
    save("rejected_visual.json", rejected_visual)
    print(f"visual: {len(passed)} pass / {len(review)} review / {len(rejected_visual)} rejected "
          f"(vision verdicts available: {len(verdicts)})")

def stage_finalize(args):
    vpass = load("visual_pass.json") or []
    vreview = load("visual_review.json") or []
    vrej = load("rejected_visual.json") or []
    rej_text = load("rejected_text.json") or []
    rej_title = load("rejected_title.json") or []
    not_fetched = load("not_fetched.json") or []

    passed, review = [], []
    for r in vpass:
        if r.get("text_review"):
            review.append({**r, "reasons": "; ".join(r["text_review"])})
        else:
            passed.append(r)
        if len(passed) >= TARGET:
            break
    review += vreview
    rejected = rej_text + vrej + rej_title + not_fetched

    def dump(name, rows):
        if not rows:
            (OUT / name).write_text("", encoding="utf-8")
            return
        order = ["rank", "asin", "title", "brand", "price", "size_oz", "price_per_oz", "rating", "reviews",
                 "bought_past_month_est", "sales_volume", "bsr_primary", "bsr_category", "bsr_est_monthly_sales",
                 "bsr_est_note", "item_form_overview", "item_weight_overview", "ingredients_section",
                 "url", "main_image", "vision_form", "label_net_weight", "vision_confidence", "vision_evidence",
                 "images_checked", "text_review", "visual_reasons", "stage", "reasons"]
        keys = [k for k in order if any(k in r for r in rows)]
        keys += [k for k in dict.fromkeys(k for r in rows for k in r) if k not in keys]
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    dump("pass.csv", passed); dump("review.csv", review); dump("rejected.csv", rejected)

    l = ledger_load()
    funnel = {"discovered_unique": (load("discovery.json") or {}).get("counts", {}).get("unique"),
              "after_title": len(load("survivors_title.json") or []),
              "enriched": len(load("details.json") or []),
              "text_candidates": len(load("candidates_visual.json") or []),
              "text_rejected": len(rej_text),
              "visual_rejected": len(vrej),
              "visual_review": len(vreview),
              "not_fetched": len(not_fetched),
              "PASS": len(passed), "REVIEW": len(review), "REJECTED": len(rejected),
              "credits_used": l.get("credits_used"), "credits_remaining": l.get("credits_remaining"),
              "requests": len(l.get("requests", []))}
    hist = Counter()
    for r in rejected:
        for part in str(r.get("reasons", "")).split("; "):
            hist[re.sub(r"[\d.]+", "#", part)] += 1
    funnel["reject_reason_histogram"] = dict(hist.most_common(25))
    save("funnel.json", funnel)
    print(json.dumps(funnel, indent=2))
    if len(passed) < TARGET:
        print(f"** Only {len(passed)} listings met every filter. Target {TARGET} NOT met - not padded. **")

def stage_summarize(args):
    passed = read_csv("pass.csv"); review = read_csv("review.csv"); rejected = read_csv("rejected.csv")
    l = ledger_load()
    lines = ["# Organic Lion's Mane Powder - verified pull (Amazon US)\n",
             f"Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
             "Provider: ScrapingBee Amazon APIs (5 credits/request). Visual gate: local Qwen2.5-VL vision model "
             "reads the actual product images (form/container, label text, net weight) + structured data cross-check.\n",
             "## Verdict counts\n",
             f"- PASS: {len(passed)} (target {TARGET})" + (" **TARGET NOT MET - list is complete, not padded.**" if len(passed) < TARGET else ""),
             f"- REVIEW: {len(review)}", f"- REJECTED: {len(rejected)}",
             f"- Credits: {l.get('credits_used')} used / {l.get('credits_remaining')} remaining "
             f"({len(l.get('requests', []))} requests; log: credit_ledger.json)\n",
             "## Size buckets (PASS rows only)\n",
             "| size bucket (oz) | n | median price | median $/oz | median reviews | median recent-sales signal | median BSR-est. monthly sales |",
             "|---|---|---|---|---|---|---|"]
    for lo, hi in [(4, 8), (8, 12), (12, 16), (16, 24), (24, 32.01)]:
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
    with_est = [r for r in passed if r.get("bsr_est_monthly_sales")]
    lines.append("## Demand signal coverage\n")
    lines.append(f"- PASS rows with BSR-based monthly-sales estimate: {len(with_est)} of {len(passed)}")
    if with_est:
        lines.append(f"- Sum of estimated monthly units across those rows: **{sum(float(r['bsr_est_monthly_sales']) for r in with_est):,.0f}**")
        lines.append("- Model: units/month = 10^(5.50 - 0.70 x log10(BSR)) on the primary category rank; ESTIMATE only.")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def read_csv(name):
    p = OUT / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def stage_analyze(args):
    """Append the requested analysis to summary.md (each conclusion labelled with sample size)."""
    import difflib
    passed = read_csv("pass.csv")
    lines = ["", "## Analysis (sample sizes in brackets)", ""]
    if not passed:
        lines.append("_No PASS rows; analysis not applicable._")
        (OUT / "summary.md").write_text((OUT / "summary.md").read_text(encoding="utf-8") + "\n".join(lines), encoding="utf-8")
        print("no pass rows"); return

    def f(r, k):
        v = r.get(k)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # 1) price per oz curve
    lines.append("### 1. Price-per-oz curve")
    pts = sorted([(f(r, "size_oz"), f(r, "price_per_oz")) for r in passed
                  if f(r, "size_oz") and f(r, "price_per_oz")])
    if pts:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
        corr = cov / den if den else None
        lines.append(f"- n={n} PASS rows with parseable size and price.")
        lines.append(f"- Pearson correlation size vs $/oz: {corr:.2f} (negative = price/oz falls as size grows)."
                     if corr is not None else "- correlation n/a")
        for lo, hi in [(4, 8), (8, 12), (12, 16), (16, 24), (24, 32.01)]:
            b = [r for r in passed if (f(r, "size_oz") or 0) >= lo and (f(r, "size_oz") or 0) < hi and f(r, "price_per_oz")]
            if b:
                vals = sorted(f(r, "price_per_oz") for r in b)
                lines.append(f"  - {lo}-{int(hi) if hi != 32.01 else 32} oz: n={len(b)}, median ${vals[len(vals)//2]:.2f}/oz")
    else:
        lines.append("- insufficient data (n=0).")

    # 2) demand signal vs competition density
    lines.append("")
    lines.append("### 2. Demand signal by size tier")
    for lo, hi in [(4, 8), (8, 12), (12, 16), (16, 24), (24, 32.01)]:
        b = [r for r in passed if (f(r, "size_oz") or 0) >= lo and (f(r, "size_oz") or 0) < hi]
        if b:
            sales = [f(r, "bought_past_month_est") for r in b if f(r, "bought_past_month_est")]
            revs = [f(r, "reviews") for r in b if f(r, "reviews")]
            est = [f(r, "bsr_est_monthly_sales") for r in b if f(r, "bsr_est_monthly_sales")]
            lines.append(f"- {lo}-{int(hi) if hi != 32.01 else 32} oz: n={len(b)}, "
                         f"median 'bought past month'={sorted(sales)[len(sales)//2] if sales else 'n/a'}, "
                         f"median reviews={sorted(revs)[len(revs)//2] if revs else 'n/a'}, "
                         f"median BSR-est units/mo={sorted(est)[len(est)//2] if est else 'n/a'}")
    lines.append("- Competition density = PASS count per tier (see table above).")

    # 3) price bands for 8/16/lb
    lines.append("")
    lines.append("### 3. Price bands (P25 / median / P75)")
    for label, lo, hi in [("8 oz", 7.0, 9.0), ("16 oz / 1 lb", 15.0, 17.0), ("24-32 oz", 24.0, 33.0)]:
        b = [f(r, "price") for r in passed if lo <= (f(r, "size_oz") or 0) <= hi and f(r, "price")]
        if b:
            b.sort()
            q = lambda p: b[min(len(b) - 1, int(p * len(b)))]
            lines.append(f"- {label} (n={len(b)}): ${q(0.25):.2f} / ${q(0.5):.2f} / ${q(0.75):.2f}")

    # 4) private-label clone flags (near-identical titles/brand families)
    lines.append("")
    lines.append("### 4. Possible private-label clone groups (near-identical titles)")
    def norm(t):
        t = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
        t = re.sub(r"\b\d+([\d.]*\s*)?(oz|ounce|ounces|lb|lbs|pound|pounds|g|grams|mg)\b", " ", t)
        return re.sub(r"\s+", " ", t).strip()
    groups, used = [], set()
    for i, r in enumerate(passed):
        if i in used:
            continue
        grp = [r["asin"]]
        for j in range(i + 1, len(passed)):
            if j in used:
                continue
            if difflib.SequenceMatcher(None, norm(r.get("title")), norm(passed[j].get("title"))).ratio() > 0.80:
                grp.append(passed[j]["asin"]); used.add(j)
        if len(grp) > 1:
            groups.append(grp); used.add(i)
    if groups:
        for g in groups:
            lines.append(f"- group: {', '.join(g)}")
    else:
        lines.append("- none detected above 0.80 title similarity.")
    lines.append("")
    lines.append(f"_All analysis above is based on the {len(passed)} PASS rows verified in this run._")
    (OUT / "summary.md").write_text((OUT / "summary.md").read_text(encoding="utf-8") + "\n".join(lines), encoding="utf-8")
    print("analysis appended to summary.md")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["discover", "title-gate", "details", "text-gate", "visual", "finalize", "summarize", "analyze"])
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--page", type=int, default=1, help="search results page for discovery (1-7)")
    ap.add_argument("--keywords", nargs="*", default=None, help="override keyword list for discovery")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    {"discover": stage_discover, "title-gate": stage_title_gate, "details": stage_details,
     "text-gate": stage_text_gate, "visual": stage_visual, "finalize": stage_finalize,
     "summarize": stage_summarize, "analyze": stage_analyze}[a.stage](a)

if __name__ == "__main__":
    main()
