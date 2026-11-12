"""BARKSIDE BBQ Co. - blend formulation + sodium model.

Pure, offline, deterministic. No network, no credentials, no supplier contact.
Emits markdown tables to stdout so the numbers in formulas.md / compliance.md
are computed, not typed by hand.

Sodium values are USDA FoodData Central approximations for the raw ground
spice, expressed as mg sodium per 100 g of ingredient. They are a formulation
screen, NOT a label. A finished-goods lab panel (AOAC 984.27 / ICP-MS or
equivalent) is required before any sodium claim goes to print.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------- constants
POUCH_G = 80.0
BATCH_KG = 100.0          # pilot production batch per SKU
SALT_NA_MG = 38758.0      # mg sodium per 100 g NaCl (NaCl is 39.34% Na)
CONVENTIONAL_SALT_PCT = 35.0   # category-typical salt load in a BBQ rub

# bulk density of a coarse-ground rub, g/mL
DENSITY_G_PER_ML = 0.55
TSP_ML = 4.929
TABLESPOON_ML = 14.787

# ------------------------------------------------- ingredient sodium table
# mg sodium per 100 g of ingredient
SODIUM = {
    "black pepper, coarse": 20.0,
    "black pepper, ground": 20.0,
    "smoked paprika": 68.0,
    "paprika": 68.0,
    "garlic, granulated": 60.0,
    "onion, granulated": 73.0,
    "sea salt, coarse": SALT_NA_MG,
    "mushroom powder": 15.0,
    "coffee, ground roasted": 4.0,
    "turmeric, ground": 38.0,
    "tomato powder": 180.0,
    "mustard, ground": 13.0,
    "celery seed, ground": 160.0,
    "coriander, ground": 35.0,
    "ancho chile, ground": 60.0,
    "guajillo chile, ground": 60.0,
    "cocoa powder": 21.0,
    "citric acid": 0.0,
    "bay leaf, ground": 23.0,
    "ginger, ground": 27.0,
    "thyme, ground": 9.0,
    "allspice, ground": 28.0,
    "rice bran": 5.0,
    "vinegar powder": 200.0,
    "coconut sugar": 30.0,
    "cumin, ground": 168.0,
    "lime powder": 20.0,
    "oregano, ground": 25.0,
    "chipotle, ground": 90.0,
}

# landed bulk cost, USD per kg - ESTIMATES, replace with real quotes
COST = {
    "black pepper, coarse": 16.00,
    "black pepper, ground": 16.00,
    "smoked paprika": 11.00,
    "paprika": 11.00,
    "garlic, granulated": 9.00,
    "onion, granulated": 6.00,
    "sea salt, coarse": 1.20,
    "mushroom powder": 42.00,
    "coffee, ground roasted": 9.00,
    "turmeric, ground": 7.00,
    "tomato powder": 11.00,
    "mustard, ground": 5.00,
    "celery seed, ground": 8.00,
    "coriander, ground": 4.00,
    "ancho chile, ground": 11.00,
    "guajillo chile, ground": 12.00,
    "cocoa powder": 7.00,
    "citric acid": 2.60,
    "bay leaf, ground": 12.00,
    "ginger, ground": 6.00,
    "thyme, ground": 9.00,
    "allspice, ground": 8.00,
    "rice bran": 2.00,
    "vinegar powder": 14.00,
    "coconut sugar": 7.00,
    "cumin, ground": 6.00,
    "lime powder": 16.00,
    "oregano, ground": 7.00,
    "chipotle, ground": 14.00,
}

# ------------------------------------------------------------- the blends
BLENDS = {
    "COPPER": {
        "no": "No.1",
        "role": "Brisket + pork butt (dual-purpose bark blend)",
        "pitch": "Copper bark, no brine.",
        "formula": {
            "black pepper, coarse": 23.0,
            "smoked paprika": 13.5,
            "garlic, granulated": 8.5,
            "onion, granulated": 8.5,
            "sea salt, coarse": 13.0,
            "mushroom powder": 5.0,
            "coffee, ground roasted": 4.0,
            "turmeric, ground": 4.5,
            "tomato powder": 3.0,
            "mustard, ground": 2.5,
            "celery seed, ground": 2.0,
            "coriander, ground": 2.0,
            "ancho chile, ground": 2.0,
            "cocoa powder": 1.5,
            "citric acid": 0.8,
            "bay leaf, ground": 0.5,
            "ginger, ground": 1.5,
            "thyme, ground": 1.0,
            "allspice, ground": 1.2,
            "rice bran": 2.0,
        },
    },
    "GOLD": {
        "no": "No.2",
        "role": "Pulled pork + chicken (Carolina mustard-vinegar)",
        "pitch": "Gold bark, tang on the back end.",
        "formula": {
            "mustard, ground": 15.0,
            "vinegar powder": 7.0,
            "paprika": 10.0,
            "turmeric, ground": 5.0,
            "garlic, granulated": 11.0,
            "onion, granulated": 10.0,
            "coconut sugar": 8.0,
            "black pepper, ground": 7.0,
            "sea salt, coarse": 12.0,
            "celery seed, ground": 3.0,
            "ginger, ground": 2.5,
            "citric acid": 1.5,
            "coriander, ground": 3.0,
            "cumin, ground": 2.0,
            "bay leaf, ground": 1.0,
            "rice bran": 2.0,
        },
    },
    "CRIMSON": {
        "no": "No.3",
        "role": "Steak + chicken thighs + charred veg (chile-lime)",
        "pitch": "Red bark, bright finish.",
        "formula": {
            "ancho chile, ground": 17.0,
            "guajillo chile, ground": 11.0,
            "smoked paprika": 8.0,
            "cumin, ground": 9.0,
            "garlic, granulated": 10.0,
            "onion, granulated": 8.0,
            "black pepper, ground": 7.0,
            "lime powder": 6.0,
            "sea salt, coarse": 11.0,
            "coriander, ground": 5.0,
            "oregano, ground": 3.0,
            "citric acid": 1.5,
            "cocoa powder": 1.0,
            "chipotle, ground": 1.0,
            "rice bran": 1.5,
        },
    },
}


# ----------------------------------------------------------------- helpers
def serving_grams(ml: float) -> float:
    return ml * DENSITY_G_PER_ML


def analyse(name: str, spec: dict) -> dict:
    f = spec["formula"]
    total_pct = sum(f.values())
    if abs(total_pct - 100.0) > 0.001:
        raise SystemExit(f"{name}: formula sums to {total_pct:.3f}, must be 100.000")

    na_per_100g = 0.0
    cost_per_kg = 0.0
    for ing, pct in f.items():
        na_per_100g += pct * SODIUM[ing] / 100.0
        cost_per_kg += pct * COST[ing] / 100.0

    salt_pct = f["sea salt, coarse"]
    salt_contrib = salt_pct * SALT_NA_MG / 100.0
    conventional_na = CONVENTIONAL_SALT_PCT * SALT_NA_MG / 100.0

    quarter_tsp = serving_grams(TSP_ML / 4.0)
    one_tsp = serving_grams(TSP_ML)
    one_tbsp = serving_grams(TABLESPOON_ML)

    return {
        "name": name,
        "no": spec["no"],
        "role": spec["role"],
        "pitch": spec["pitch"],
        "formula": f,
        "salt_pct": salt_pct,
        "na_per_100g": na_per_100g,
        "na_from_salt_pct": 100.0 * salt_contrib / na_per_100g,
        "na_quarter_tsp": na_per_100g * quarter_tsp / 100.0,
        "na_teaspoon": na_per_100g * one_tsp / 100.0,
        "na_tablespoon": na_per_100g * one_tbsp / 100.0,
        "na_per_lb_15g": na_per_100g * 15.0 / 100.0,
        "reduction_pct": 100.0 * (1.0 - na_per_100g / conventional_na),
        "cost_per_kg": cost_per_kg,
        "cost_per_pouch": cost_per_kg * POUCH_G / 1000.0,
        "quarter_tsp": quarter_tsp,
        "one_tsp": one_tsp,
        "one_tbsp": one_tbsp,
        "pouches_from_batch": BATCH_KG * 1000.0 / POUCH_G,
    }


# ------------------------------------------------------------------ output
def main() -> int:
    rows = [analyse(k, v) for k, v in BLENDS.items()]
    out: list[str] = []
    w = out.append

    w("# BARKSIDE - computed formulation report")
    w("")
    w(f"Generated by `sodium_model.py`. Serving basis: {DENSITY_G_PER_ML} g/mL bulk density.")
    w("")
    w("| | " + " | ".join(r["name"] for r in rows) + " |")
    w("|---|" + "---|" * len(rows))
    w("| SKU | " + " | ".join(r["no"] for r in rows) + " |")
    w("| Role | " + " | ".join(r["role"] for r in rows) + " |")
    w("| Salt (% w/w) | " + " | ".join(f"{r['salt_pct']:.1f}" for r in rows) + " |")
    w("| Sodium mg/100 g | " + " | ".join(f"{r['na_per_100g']:,.0f}" for r in rows) + " |")
    w("| Sodium from salt (%) | " + " | ".join(f"{r['na_from_salt_pct']:.1f}" for r in rows) + " |")
    w(f"| Sodium per {rows[0]['quarter_tsp']:.2f} g (1/4 tsp) | " + " | ".join(f"{r['na_quarter_tsp']:.0f} mg" for r in rows) + " |")
    w(f"| Sodium per {rows[0]['one_tsp']:.2f} g (1 tsp) | " + " | ".join(f"{r['na_teaspoon']:.0f} mg" for r in rows) + " |")
    w(f"| Sodium per {rows[0]['one_tbsp']:.2f} g (1 tbsp) | " + " | ".join(f"{r['na_tablespoon']:.0f} mg" for r in rows) + " |")
    w("| Sodium per lb of meat @ 15 g rub | " + " | ".join(f"{r['na_per_lb_15g']:,.0f} mg" for r in rows) + " |")
    w(f"| vs {CONVENTIONAL_SALT_PCT:.0f}%-salt rub | " + " | ".join(f"-{r['reduction_pct']:.0f}%" for r in rows) + " |")
    w("| Ingredient cost, USD/kg | " + " | ".join(f"${r['cost_per_kg']:.2f}" for r in rows) + " |")
    w(f"| Ingredient cost, {POUCH_G:.0f} g pouch | " + " | ".join(f"${r['cost_per_pouch']:.2f}" for r in rows) + " |")
    w(f"| Pouches from {BATCH_KG:.0f} kg batch | " + " | ".join(f"{r['pouches_from_batch']:,.0f}" for r in rows) + " |")
    w("")

    for r in rows:
        w(f"## {r['name']} ({r['no']}) - {r['pitch']}")
        w("")
        w(f"*{r['role']}*")
        w("")
        w(f"| Ingredient | % w/w | g per {POUCH_G:.0f} g pouch | kg per {BATCH_KG:.0f} kg batch | mg Na/100 g |")
        w("|---|---:|---:|---:|---:|")
        for ing, pct in sorted(r["formula"].items(), key=lambda kv: -kv[1]):
            w(
                f"| {ing} | {pct:.1f} | {pct * POUCH_G / 100:.1f} | "
                f"{pct * BATCH_KG / 100:.1f} | {SODIUM[ing]:.0f} |"
            )
        w(f"| **Total** | **100.0** | **{POUCH_G:.0f}** | **{BATCH_KG:.0f}** | **{r['na_per_100g']:,.0f}** |")
        w("")

    # claim margin check
    w("## Low-sodium claim margin (US, per RACC of 1/4 tsp)")
    w("")
    w("| SKU | mg Na per serving | Limit (140 mg) | Headroom |")
    w("|---|---:|---:|---:|")
    for r in rows:
        head = 140.0 - r["na_quarter_tsp"]
        w(f"| {r['name']} | {r['na_quarter_tsp']:.0f} | 140 | {head:.0f} mg ({100 * head / 140:.0f}%) |")
    w("")
    w("If the declared serving were raised to 1 tsp, the numbers become:")
    w("")
    for r in rows:
        flag = "PASS but too close to defend" if r["na_teaspoon"] <= 140 else "FAILS the claim"
        w(f"- {r['name']}: {r['na_teaspoon']:.0f} mg - {flag}")
    w("")
    w("Conclusion: declare 1/4 tsp. Keep 1 tsp on the panel as a transparency column,")
    w("never as the basis for the claim.")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
