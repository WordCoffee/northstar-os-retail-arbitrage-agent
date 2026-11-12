# BARKSIDE — brand + formulation pack

**Date:** 2026-11-12
**Task:** build a competitive brand against an Amazon BBQ seasoning listing; 3 low-sodium blends, 80 g pouches.
**Status:** complete for the formulation and brand layers. Nothing purchased, nothing sent, nothing listed.

---

## What was done

| Layer | File | State |
|---|---|---|
| Brand platform + lineup | `docs/barkside-launch/README.md` | Ready |
| Gram-level formulas + production spec | `docs/barkside-launch/formulas.md` | Ready |
| Claims, allergens, label copy | `docs/barkside-launch/compliance.md` | Ready |
| 80 g unit economics | `docs/barkside-launch/economics.md` | Ready |
| Supplier brief / RFQ | `docs/barkside-launch/supplier_brief.md` | Ready, unsent |
| Formulation model | `docs/barkside-launch/sodium_model.py` | Runs, exit 0 |
| Computed output | `docs/barkside-launch/sodium_report.md` | Generated |

## The product

BARKSIDE BBQ Co. — *The bark is the point.*

| | No.1 COPPER | No.2 GOLD | No.3 CRIMSON |
|---|---|---|---|
| Use | brisket + pork butt | pulled pork + chicken | steak + chicken + veg |
| Salt | 13.0% | 12.0% | 11.0% |
| Sodium / 100 g | 5,078 mg | 4,704 mg | 4,319 mg |
| Sodium / 1/4 tsp | 34 mg | 32 mg | 29 mg |
| vs 35%-salt rub | −63% | −65% | −68% |
| Turmeric | 4.5% (copper bark) | 5.0% (gold bark) | — |
| Ingredient cost / 80 g | $0.86 | $0.59 | $0.71 |

COPPER is the dual-purpose blend: coarse pepper for bark texture, zero sugar so it
survives a 14-hour cook, and turmeric + coffee + cocoa for a copper bark that sets
before the stall.

## Evidence

```
python docs/barkside-launch/sodium_model.py
exit 0
COPPER  salt 13.0  Na/100g 5,078  Na/0.68g 34  -63%
GOLD    salt 12.0  Na/100g 4,704  Na/0.68g 32  -65%
CRIMSON salt 11.0  Na/100g 4,319  Na/0.68g 29  -68%
all three formulas assert to 100.000 %
```

Model only. A finished-goods lab panel is required before any sodium number goes to
print — stated in every document.

## The finding that matters most

**"Low sodium" is a US-only claim.** The FDA threshold is per serving (RACC 1/4 tsp),
which we clear with 75–79% headroom. UK/EU nutrition claims are assessed per 100 g,
where "low salt" means ≤ 0.12 g per 100 g — roughly 100× below any real BBQ rub.

So if the competitor's 80 g format means a UK/EU listing, they cannot legally use the
claim either, and the winning play is the stated salt percentage on the front of the
pouch plus a substantiated "reduced salt" claim (we are 63–68% under a 35%-salt
reference). This fork decides the claim set, the label text and the price architecture,
and it is the first decision outstanding.

## Not done, and why

- **The Amazon listing was not opened.** `a.co/d/05KK8RFQ` resolves to Amazon, a
  standing gate. Approval was asked and not given (the question came back as a
  question about agent visibility rather than approval). The competitive read is
  therefore category-level. Paste the title, ingredients, price and top three
  complaints, and the differentiation sharpens in minutes.
- **No supplier contacted.** The brief is ready; sending it is a commercial commitment.
- **`00_STATE.json` could not be updated** — the edit was permission-rejected. This
  report is the durable record instead.
- **No trademark clearance.** BARKSIDE is a proposal, not a cleared mark.

## Next actions, in value order

1. Decide market 1: US or UK/EU. Everything downstream branches on it.
2. Send the supplier brief under NDA; order the salt ladder (13/10, 12/9, 11/8).
3. Order a finished-goods nutrition panel on the winning salt level.
4. Knockout search BARKSIDE on USPTO and EUIPO.
5. Pilot: 3 × 500 pouches, ~$2,700 including artwork and lab.
