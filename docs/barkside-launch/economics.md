# BARKSIDE — 80 g unit economics

Every cost here is an **ESTIMATE** unless it comes from `sodium_model.py` (ingredient
cost, which is itself built on estimated bulk spice prices). Nothing in this file is a
supplier quote. Replace the marked lines before anyone commits money.

**Verified by computation:** ingredient cost per pouch — COPPER $0.86 · GOLD $0.59 ·
CRIMSON $0.71.

**Estimated:** packaging, fill, FBA fees, ad rates.

---

## 1. Landed cost per pouch

| Line | Pilot (3,000 units) | Scale (25,000 units) |
|---|---:|---:|
| Ingredients (avg of 3) | $0.72 | $0.72 |
| Pouch — foil-lined, matte, zip, printed | $0.18 | $0.12 |
| Fill + seal + code (co-packer) | $0.35 | $0.18 |
| Carton, labour, shrink | $0.04 | $0.03 |
| **Landed COGS** | **$1.29** | **$1.05** |
| Organic tier (+35% ingredients) | $1.54 | $1.30 |

At 80 g, ingredients are 56% of cost. **Packaging and fill are the lever, not the
spice.** A 5k pouch order instead of 3k is worth more than haggling turmeric down 8%.

---

## 2. Price and contribution

### US, FBA

| | Single 80 g | 3-pack |
|---|---:|---:|
| Price | **$10.99** | **$29.99** |
| Amazon referral (15%) | −$1.65 | −$4.50 |
| FBA fulfilment *(estimate)* | −$3.15 | −$3.75 |
| Landed COGS | −$1.29 | −$3.87 |
| **Contribution** | **$4.90 (44.6%)** | **$17.87 (59.6%)** |
| Ads at 25% / 20% of revenue | −$2.75 | −$6.00 |
| **Net before fixed costs** | **$2.15 (19.6%)** | **$11.87 (39.6%)** |

The 3-pack does two jobs: it carries 2.4× the contribution per order and it is the only
realistic way to get a new brand's three SKUs into one household. Price it so the
discount is obvious — $29.99 against $32.97 bought singly.

### UK, FBA (if market 1 is UK)

| | Single 80 g |
|---|---:|
| Price (inc VAT) | **£8.95** |
| ex-VAT | £7.46 |
| Amazon referral (15% of ex-VAT) | −£1.12 |
| FBA fulfilment *(estimate)* | −£2.10 |
| Landed COGS | −£0.98 |
| **Contribution** | **£3.26 (43.7% of ex-VAT)** |
| Ads at 20% of gross | −£1.79 |
| **Net** | **£1.47 (19.7% of ex-VAT)** |

£7.45 would be too thin: at that price the UK single nets under £1 and a single return
wipes out three sales. Hold £8.95, and let the 3-pack at £23.50 carry the volume.

---

## 3. What the money actually costs

| Tier | Volume | Ingredients | Packaging | Fill | Artwork + lab | **Total cash** | Pouches |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Sample** | 3 × 20 | $45 | $12 | $21 | $250 artwork | **~$330** | 60 |
| **Pilot** | 3 × 500 | $1,080 | $270 | $525 | $800 | **~$2,700** | 1,500 |
| **First run** | 3 × 1,250 (100 kg/SKU) | $2,710 | $675 | $1,310 | $1,200 | **~$5,900** | 3,750 |

The pilot is the right first move. $2,700 buys a real product, real photos, real
reviews and a real answer to "does this sell" — and 1,500 pouches is enough to run
three months of Amazon without a reorder.

The first run at $5,900 is only justified after the pilot clears 30 units/week.

---

## 4. Sensitivities

| Change | Effect on single-unit contribution |
|---|---|
| FBA fee is $4.20 not $3.15 | $4.90 → $3.85 (−21%) |
| Supplier fill fee is $0.55 not $0.35 | $4.90 → $4.70 (−4%) |
| Price dropped to $9.99 to match a competitor | $4.90 → $4.05 (−17%) |
| Organic tier | $4.90 → $4.65 (−5%) |
| 3-pack cannibalises 60% of singles | Blended contribution rises — this is the good case |

The single is fee-sensitive, not ingredient-sensitive. **Do not start a price war on
the single SKU to win a comparison you cannot win.** Win on the 3-pack and on the
fact that no competitor prints their salt percentage.

---

## 5. Break-even

Fixed costs to launch: artwork ~$600, lab panel ~$450, photography ~$400, initial ad
test ~$750 = **~$2,200**.

At blended contribution of ~$7.50/order, that is **~295 orders** to recover launch
spend. At 10 orders/day that is a month. At 1 order/day it is ten months — which is
the honest reason to keep the pilot small.

---

## 6. Unit-economics verdict

| Question | Answer |
|---|---|
| Is 80 g at $10.99 defensible? | Yes, as a **3-pack-led** strategy. $3.89/oz on the single is high; the 3-pack at $3.54/oz with a visible saving is what closes it. |
| Is the margin real? | Yes — 44% single, 60% 3-pack contribution before ads. Spice blends are gross-margin products; the cost is customer acquisition, not COGS. |
| Biggest financial risk | FBA fee tier. If the pouch dimensions push it out of small standard, the single loses ~20% of contribution. **Measure the filled pouch before ordering packaging.** |
| Second biggest | Amazon returns on food. Sealed dry goods are usually non-returnable, but confirm the policy per marketplace before assuming. |
| Cash at risk | ~$2,700 for a real pilot. That is the number to approve, not $30k. |
