#!/usr/bin/env python3
"""Generate lions_mane_size_price_demand_summary.md and lions_mane_rebuild_audit.md
from the rebuild CSVs. Pure computation; reads derived files only."""
import csv, json, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

RB = Path("out_sb/rebuild_1to32oz")
OBS = "2026-10-10 16:53–17:38 UTC (discovery → product details → vision pass; local Ollama vision)"
SRC = "ScrapingBee amazon/search + amazon/product; local Qwen2.5-VL for image reading; all cached files in out_sb/"
EST_NOTE = "ESTIMATE — not observed sales (category-specific BSR model)"
SUM_NOTE = "sum of row-level BSR-model estimates; not a deduplicated market-size estimate"
XLENS = "BSR is category-specific; cross-category comparisons in the 'combined' view are descriptive only."

def load_csv(name):
    return list(csv.DictReader(open(RB / name, newline="", encoding="utf-8")))

market = load_csv("lions_mane_market_1to32oz.csv")
clean = load_csv("lions_mane_clean_comparables_1to32oz.csv")
review = load_csv("lions_mane_review_required_1to32oz.csv")
excluded = load_csv("lions_mane_excluded_1to32oz.csv")
ranked = load_csv("lions_mane_ranked_by_category_bsr.csv")
counts = json.loads((RB / "rebuild_counts.json").read_text(encoding="utf-8"))

def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

BINS = [(1.0, 3.0, "1.0–<3 oz"), (3.0, 5.0, "3–<5 oz"), (5.0, 8.0, "5–<8 oz"),
        (8.0, 12.0, "8–<12 oz"), (12.0, 16.0, "12–<16 oz"), (16.0, 24.0, "16–<24 oz"),
        (24.0, 32.01, "24–32 oz")]

def med(rows, col):
    vals = [f(r.get(col)) for r in rows if f(r.get(col)) is not None]
    return round(statistics.median(vals), 3) if vals else None

def bin_table(rows, title):
    out = [f"**{title}**\n",
           "| bin | SKUs | brands | med price | med $/oz | med BSR | med est sales/mo | med reviews | med recent-sales | containers | extract/myc/blend | clean |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for lo, hi, label in BINS:
        b = [r for r in rows if f(r.get("total_sellable_net_weight_oz")) is not None
             and lo <= f(r["total_sellable_net_weight_oz"]) < hi]
        if not b:
            continue
        brands = len({(r.get("brand") or "").strip().lower() for r in b if r.get("brand")})
        conts = Counter((r.get("container_form") or "unknown") for r in b)
        flags = sum(1 for r in b if r.get("extract_flag") == "True" or r.get("mycelium_flag") == "True" or r.get("blend_flag") == "True")
        cl = sum(1 for r in b if r.get("clean_comparable_status") == "clean_comparable")
        recent = med(b, "bought_past_month_est")
        out.append(f"| {label} | {len(b)} | {brands} | {('$%s' % med(b, 'total_price')) if med(b, 'total_price') else 'n/a'} | "
                   f"{('$%s' % med(b, 'price_per_oz')) if med(b, 'price_per_oz') else 'n/a'} | "
                   f"{med(b, 'bsr_primary') or 'n/a'} | {med(b, 'bsr_est_monthly_sales') or 'n/a'} | "
                   f"{med(b, 'review_count') or 'n/a'} | {recent or 'n/a'} | "
                   f"{', '.join(f'{k}:{v}' for k, v in conts.most_common(3))} | {flags} | {cl} |")
    out.append("")
    return out

def bsr_leaders(cat, n=25):
    rows = [r for r in ranked if r["bsr_category"] == cat]
    rows.sort(key=lambda r: int(r["bsr_primary"]))
    out = [f"**{cat} — BSR leaders (ascending category BSR, top {min(n, len(rows))} of {len(rows)} with BSR)**\n",
           "| category_rank | ASIN | BSR | size oz | mp | price | $/oz | rating | reviews | recent-sales | est sales/mo (ESTIMATE) | container | flags |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows[:n]:
        flags = ",".join(k for k, cond in [("extract", r["extract_flag"] == "True"), ("myc", r["mycelium_flag"] == "True"),
                                           ("blend", r["blend_flag"] == "True"), ("clean", r["clean_comparable_status"] == "clean_comparable")] if cond)
        out.append(f"| {r['category_rank']} | {r['asin']} | {r['bsr_primary']} | {r['total_sellable_net_weight_oz']} | {r['is_multipack']} | "
                   f"${r['total_price']} | {r['price_per_oz'] or 'n/a'} | {r['rating'] or 'n/a'} | {r['review_count'] or 'n/a'} | "
                   f"{r['bought_past_month_text'] or 'n/a'} | {r['bsr_est_monthly_sales']} | {r['container_form']} | {flags or '-'} |")
    out.append("")
    return out

def demand_leaders(cat, n=25):
    rows = [r for r in ranked if r["bsr_category"] == cat and f(r["bsr_est_monthly_sales"])]
    rows.sort(key=lambda r: -f(r["bsr_est_monthly_sales"]))
    out = [f"**{cat} — estimated demand leaders (descending BSR-model estimate; mathematically tied to BSR, not independent demand evidence)**\n",
           "| ASIN | est sales/mo | BSR | size oz | price | $/oz | reviews | recent-sales | flags |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows[:n]:
        flags = ",".join(k for k, cond in [("extract", r["extract_flag"] == "True"), ("myc", r["mycelium_flag"] == "True"),
                                           ("blend", r["blend_flag"] == "True"), ("clean", r["clean_comparable_status"] == "clean_comparable")] if cond)
        out.append(f"| {r['asin']} | {r['bsr_est_monthly_sales']} | {r['bsr_primary']} | {r['total_sellable_net_weight_oz']} | ${r['total_price']} | "
                   f"{r['price_per_oz'] or 'n/a'} | {r['review_count'] or 'n/a'} | {r['bought_past_month_text'] or 'n/a'} | {flags or '-'} |")
    out.append("")
    return out

def price_arch(rows):
    out = ["**Price architecture by size tier** (P25 / median / P75; raw rows when n<3)\n",
           "| tier | n | P25 | median | P75 |", "|---|---|---|---|---|"]
    for lo, hi, label in BINS:
        b = [r for r in rows if f(r.get("total_sellable_net_weight_oz")) is not None
             and lo <= f(r["total_sellable_net_weight_oz"]) < hi and f(r.get("price_per_oz"))]
        if len(b) >= 3:
            vals = sorted(f(r["price_per_oz"]) for r in b)
            p25 = vals[int(0.25 * len(vals))]; p50 = statistics.median(vals); p75 = vals[min(len(vals) - 1, int(0.75 * len(vals)))]
            out.append(f"| {label} | {len(b)} | ${p25:.2f} | ${p50:.2f} | ${p75:.2f} |")
        elif b:
            raw = "; ".join(f"{r['asin']} ${f(r['price_per_oz']):.2f}/oz" for r in b)
            out.append(f"| {label} | {len(b)} | raw: {raw} | — | — |")
    out.append("")
    return out

def positioning():
    def txt(r):
        return (r.get("title") or "") + " "
    buckets = {
        "factual product descriptors": r"\b(powder|fruiting bod\w*|freeze[- ]?dried|finely milled|ground|pure|single ingredient|whole mushroom)\b",
        "certifications / evidence": r"\b(usda organic|organic|certified organic|non[- ]?gmo|kosher|vegan|gluten[- ]?free|lab[- ]?tested|third[- ]?party tested|beta[- ]?glucans)\b",
        "usage occasions": r"\b(smoothies?|coffee|teas?|lattes?|drinks?|baking|recipes?|soups?|cooking|juice)\b",
        "health/performance claims": r"\b(nootropic|memory|focus|brain|cognitive|nerve|ngf|immune|energy|mood|clarity|sleep|gut)\b",
    }
    out = ["**Packaging & positioning word counts (market lens, from cached titles)**\n"]
    conts = Counter((r.get("container_form") or "unknown") for r in market)
    out.append(f"- Container forms: " + ", ".join(f"{k} ({v})" for k, v in conts.most_common()))
    out.append("")
    out.append("| bucket | top terms (count) |")
    out.append("|---|---|")
    for bucket, pat in buckets.items():
        c = Counter()
        for r in market:
            for m in re.finditer(pat, txt(r).lower()):
                c[m.group(0)] += 1
        out.append(f"| {bucket} | {', '.join(f'{k} ({v})' for k, v in c.most_common(12))} |")
    out.append("")
    out.append("_Health/performance claim terms are recorded as observed listing language only; no copy recommendation is made._")
    out.append("")
    return out

# ---------------- summary.md ----------------
cats = sorted({r["bsr_category"] for r in ranked})
S = []
S.append("# Organic Lion's Mane Mushroom Powder — Amazon US size/price/demand summary (1.0–32.0 oz rebuild)\n")
S.append(f"- Source: {SRC}")
S.append(f"- Observation window: {OBS}")
S.append(f"- Scope: {counts['total_asins']} unique ASINs cached from the study; widened inclusion 1.0–32.0 oz; two lenses (market vs clean comparable).")
S.append(f"- Counts: market lens **{counts['market_lens']}** ({counts['market_qualified_clean']} clean + {counts['market_qualified_flagged']} flagged + {counts['market_review_required']} review-required, all with known weights), review-required additional (weight-ambiguous) **{counts['weight_ambiguous_review_only']}**, excluded **{counts['excluded']}**.")
S.append(f"- Clean comparable (launch lens): **{counts['clean_comparable']}**.")
S.append(f"- Categories represented among BSR-known market rows: " + ", ".join(f"{c} ({n})" for c, n in counts['categories'].items()))
S.append(f"- Observed fields: price, rating, review count, 'bought in past month' text, label net weight (vision), BSR.")
S.append(f"- Estimated fields: `bsr_est_monthly_sales` ({EST_NOTE}). Never treat estimates as observed sales.")
S.append(f"- Cross-category rule: {XLENS}")
S.append("")
title_only_n = sum(1 for r in market if r["evidence_confidence"] == "title_only")
flagged_n = sum(1 for r in market if r["market_lens_status"] == "qualified_flagged")
S.append(f"**Limitations:** {title_only_n} of {len(market)} market rows carry title-only evidence (no cached product-detail/label reading); those are kept in the market lens but flagged `review_required` for the clean lens. {len(clean)} rows are clean comparables; {flagged_n} market rows carry categorical flags (extract / mycelium / blend wording) and are excluded from the clean lens by rule. Amazon 'item weight' fields include packaging and are never used as net weight. Multipacks use label per-unit weight × confirmed unit count. Price is the cached listing price at observation time.")
S.append("")
S.append("## A. BSR leaders by category\n")
for c in cats:
    S += bsr_leaders(c)
S.append("## B. Estimated demand leaders by category\n")
for c in cats:
    S += demand_leaders(c)
S.append("## C. Pack-size clusters\n")
S += bin_table(market, "Market lens — all qualified/flagged/review rows (weights in range)")
S += bin_table(clean, "Clean comparable lens")
S += bin_table([r for r in market if r["bsr_category"] == "Health & Household"], "Health & Household (descriptive)")
S += bin_table([r for r in market if r["bsr_category"] == "Grocery & Gourmet Food"], "Grocery & Gourmet Food (descriptive)" if any(r["bsr_category"] == "Grocery & Gourmet Food" for r in market) else "Grocery & Gourmet Food")
S.append("## D. Price architecture\n")
S += price_arch(market)
S.append("Clean-lens price architecture:\n")
S += price_arch(clean)
S.append("## E. Packaging & positioning\n")
S += positioning()
S.append("## Market-size caveat\n")
S.append(f"Any subtotal of `bsr_est_monthly_sales` is a {SUM_NOTE}. Variant families and duplicate search returns can inflate it.")
summ = "\n".join(S)
(RB / "lions_mane_size_price_demand_summary.md").write_text(summ, encoding="utf-8")
print("summary written:", len(summ), "chars")

# ---------------- audit.md ----------------
A = []
A.append("# Rebuild audit — old 4.0–32.0 oz rule → new 1.0–32.0 oz rule\n")
A.append(f"- Old rule: `MIN_OZ = 4.0, MAX_OZ = 32.0` in `lions_mane_sb.py` (title gate line 196, text gate line 292, visual gate lines 511/530) and `lions_mane_pull.py` line 50.")
A.append("- New rule: 1.0–32.0 oz applied ONLY inside the rebuild script (`rebuild_1to32oz.py` sets `MIN_OZ = 1.0` at runtime). Original scripts and raw outputs are unchanged (hash-verified).")
A.append("")
matrix = defaultdict(Counter)
union = {}
for r in market + review + excluded:
    union.setdefault(r["asin"], r)   # review rows also appear in market CSV; count once per ASIN
for r in union.values():
    matrix[r["old_verdict"]][r["market_lens_status"]] += 1
A.append("## Old verdict → new status (all 676 ASINs)\n")
A.append("| old \\ new | qualified (clean+flagged) | review required (incl. ambiguous weight) | excluded |")
A.append("|---|---|---|---|")
for oldv in ("PASS", "REVIEW", "REJECTED", "UNKNOWN"):
    q = matrix[oldv]["qualified_clean"] + matrix[oldv]["qualified_flagged"]
    rv = matrix[oldv]["review_required"]
    ex = matrix[oldv]["excluded"]
    A.append(f"| {oldv} | {q} | {rv} | {ex} |")
A.append(f"\n_Note: 'review required' counts here include market rows with review status and the weight-ambiguous row (counted once per ASIN in the union view; the market CSV contains {counts['market_lens']} rows, plus {counts['weight_ambiguous_review_only']} weight-only review row = {counts['market_lens'] + counts['weight_ambiguous_review_only']} non-excluded ASINs)._")
A.append("")
rec = [r for r in market + review + excluded if r["reclassified_by_size_rule"] == "True"]
rec_unique = {r["asin"]: r for r in rec}
A.append(f"## Records reclassified because the 4 oz floor became 1 oz ({len(rec_unique)})\n")
A.append("| ASIN | old verdict / reason | old size | new status (market / clean) | normalized oz | note |")
A.append("|---|---|---|---|---|---|")
for r in sorted(rec_unique.values(), key=lambda x: x["asin"]):
    m = re.search(r"([\d.]+)oz", r["old_reasons"] or "")
    size = m.group(1) if m else "?"
    note = "label weight re-evaluated" if "label weight" in (r["old_reasons"] or "") else "title size re-evaluated"
    A.append(f"| {r['asin']} | {r['old_verdict']}: {str(r['old_reasons'])[:70]} | {size} | {r['market_lens_status']} / {r['clean_comparable_status']} | {r['total_sellable_net_weight_oz']} | {note} |")
A.append("")
A.append("## What stayed excluded and why (size changes did not rescue them)")
A.append("- Records below 1.0 oz by best evidence (e.g. vision label ~0.25–0.88 oz) or above 32 oz remain excluded.")
A.append("- Records whose only cached evidence fails other rules (not LM, named blends, non-powder form, no organic evidence, pet products, additional label ingredients) remain excluded regardless of size.")
A.append("- Title-only records with no powder wording (e.g. 'Dried Whole', 'sliced', 'blends') remain excluded with evidence-gap reasons; they could only qualify after enrichment (details + label vision), which was not performed (no paid/provider calls).")
A.append("")
A.append("## Extracts, mycelium, blends under the widened market lens")
A.append("- Extract/myc/full-spectrum wording: market-lens includable with explicit flags (`extract_flag`, `mycelium_flag`), clean lens excluded unless resolved.")
A.append("- Verified additional ingredients on the LABEL (e.g. pterostilbene, collagen) or named multi-species blends remain excluded: these are different products, not LM powder.")
A.append("")
A.append("## Method notes")
A.append("- Weight normalization: label net weight (vision) > title/item-weight text; multipacks = label per-unit × unit count; conflicts route to review; serving-size readings never become net weight.")
A.append("- BSR model formulas were verified present in `lions_mane_sb.py` BSR_MODEL (H&H 5.50/0.70; Grocery 5.45/0.69; default 5.47/0.70) and are labelled estimates in every output.")
A.append(f"- Raw evidence read-only; sha256 manifest: `raw_hash_manifest.json`.")
(RB / "lions_mane_rebuild_audit.md").write_text("\n".join(A), encoding="utf-8")
print("audit written:", len("\n".join(A)), "chars")
