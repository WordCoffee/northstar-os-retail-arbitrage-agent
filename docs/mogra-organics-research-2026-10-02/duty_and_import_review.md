# Duty and Import Review — Mogra Organics

**Date:** 2026-10-02
**Status:** preliminary review. **Not a customs ruling.** Nothing here is legal or brokerage advice, and no rate should be used in a landed-cost calculation without confirmation.

**Governing instruction followed:** AD/CVD is treated as a **question to verify**, not an established pepper liability. No AD/CVD conclusion is drawn from country of origin alone, and none is inferred from orders covering unrelated products.

---

## 1. Classification — the starting point

Spices classify in **HTS Chapter 9**. The relevant lines for the priority products:

| Product | HTS (indicative) | Note |
|---|---|---|
| Black pepper, neither crushed nor ground | **0904.11** | whole peppercorns |
| Black pepper, crushed or ground | **0904.12** | cracked + ground |
| Turmeric (curcuma) | **0910.30** | whole fingers and powder share this line |
| Cinnamon / cassia | 0906.11 / 0906.20 | species affects classification |
| Ginger, cumin, coriander, etc. | 0910.1x–0910.9x | confirm per product |

**These are indicative. The exact 8/10-digit subheading and statistical suffix must be confirmed against the current USITC Harmonized Tariff Schedule before any duty is calculated.** Whole vs ground pepper sit on different lines (0904.11 vs 0904.12), so the **form** affects classification — not just the product.

Source: USITC HTS structure; Peacock Tariff Consulting spice-import guide (industry summary of Chapter 9 classification).

---

## 2. Normal tariff (base duty)

Spice and seasoning imports generally attract **low base duty**. Most Chapter 9 spice lines are in the **0–3%** range, and several are **duty-free**.

**What I am NOT doing:** I am not quoting a specific ad valorem percentage, because the exact figure depends on the confirmed 10-digit line and I did not verify each line against the live HTS. Treat the base duty as **"low, confirm exact line"** rather than as a number.

**Action:** confirm the exact HTS line per product form, then read the base rate from the current USITC HTS.

---

## 3. Additional origin-specific tariffs — live and volatile

Beyond base duty, additional measures can apply. The categories to distinguish:

| Type | What it is | Status for Mogra |
|---|---|---|
| **Section 301** | Tariffs on certain Chinese-origin goods | China is **out of scope** (owner's last-priority market, existing contacts). Not pursued. |
| **Section 232** | National-security tariffs on specific sectors | Not established for spices. |
| **Reciprocal / additional tariffs** | Origin-specific additional duties introduced in the 2025 policy environment, which have changed repeatedly | **Must be confirmed per origin at time of import.** India and Vietnam are the main origins in scope. |
| **AD/CVD** | Separate from tariffs entirely — see §4 | **Unresolved — flag for broker** |

**Important:** additional-tariff measures in this period have been **unstable** — announced, paused, revised, and re-scoped repeatedly. Any figure quoted in this document would likely be stale. **Do not carry a duty assumption from this review into a supplier comparison.** Confirm at the time of each import.

One industry source notes "Section 122 stacks" on top of base duty for spice origins including India, Vietnam, China and Indonesia. I could not independently confirm the current mechanics, so this is recorded as a **lead, not a finding**.

---

## 4. AD/CVD — the question to verify (not an established liability)

### What is confirmed

- **AD/CVD duties are NOT part of the HTS.** They are imposed under separate orders and are not ordinary customs tariffs. (USITC FAQ: "Antidumping and countervailing duties (AD/CVD) are not ordinary customs tariffs and are not in the HTS.")
- AD/CVD applies only where a **specific order** covers the **specific product** from the **specific country**, as defined by that order's **scope**.
- Where coverage is unclear, the mechanism is a **formal scope ruling** — you do not simply assume coverage.
- The official public query route is the ITA **AD/CVD search portal**: `https://access.trade.gov/adcvd/` (reachable, HTTP 200). It supports searching by HTS number. It is a JS-driven application; I did **not** query it product-by-product, and I did not reverse-engineer its endpoints.

### What is NOT established

- **I did not confirm that ANY AD/CVD order covers black pepper, turmeric, or the other Mogra spices from India, Vietnam, or any other in-scope origin.**
- The observation that the **pepper trade** has seen **countervailing-duty activity** in *some* origin/market contexts is a **signal to check**, not a finding that US AD/CVD applies to Vietnamese or Indian pepper. Different country, different order, different scope.
- No AD/CVD liability is asserted here. **No AD/CVD cost is included in any pricing or landed-cost figure in this project.**

### Why this matters for sourcing

If an AD/CVD order *did* cover a product/origin, the duty could be **very large relative to the ingredient cost** and would change supplier selection. That is exactly why it must be resolved before any international route is chosen — and why **no route is declared cheapest** in this research.

### Required action

1. Take the **confirmed HTS line** per product form.
2. Query `access.trade.gov/adcvd/` by HTS number for each origin in scope (India, Vietnam, Sri Lanka, Indonesia, Peru, Fiji).
3. If any order appears to touch the product, obtain the **order scope text** and compare it to the actual product — do not rely on the country name.
4. If scope is ambiguous, request a **scope ruling**, or have a licensed customs broker confirm.
5. **Flag for broker review** — this is the correct disposition until done.

---

## 5. Organic import certification and NOP Import Certificate

Separate from duty, organic imports carry their own documentation chain.

- **Importer obligations:** to import organic product into the US and represent it as organic, the **importer must be certified** as an organic operation (with limited exemptions), and the product must be covered by the exporter's certification.
- **NOP Import Certificate (NOPIC):** the mechanism by which an organic consignment entering the US is documented. The exporter's certifier issues it, and it is checked against the importer's certification. Practical implication: **the supplier's certifier must be willing and able to issue the NOPIC** — this is a question to ask every overseas supplier.
- **Exporter/final-handler responsibility:** the exporting operation must hold certification covering the product and the activity (export), and must be able to document the transaction.
- **Mogra's own role:** if Mogra imports organic ingredients, **Mogra is likely the importer** and therefore likely needs **its own organic certification as an importer**, even if it never touches the physical goods in an organic-processing way. This is the most commonly underestimated obligation.

> **Not assumed:** an organic input does **not** automatically make the final Mogra product eligible for the USDA organic seal. If Mogra blends, repacks, or relabels organic material, that handling activity generally requires **its own certification**, and eligibility of the finished pack depends on that — not on the supply chain upstream.

## 6. Food-safety and import responsibilities

| Obligation | Who | Notes |
|---|---|---|
| **FDA Food Facility Registration** | Facilities that manufacture/process/pack/hold food for US consumption, including **foreign** facilities | Foreign supplier's facility must be registered; bioterrorism registration numbers appear on spice entries in public import data |
| **Prior Notice** | Importer/agent | Required for food imports; filed before arrival |
| **FSVP (Foreign Supplier Verification Program)** | The **US importer** | The FSVP importer must verify the foreign supplier's food-safety compliance. If Mogra imports directly, Mogra may be the FSVP importer |
| **Importer of Record (IOR)** | Whoever files entry | Determines duty liability, FSVP and record-keeping responsibility |
| **Customs broker** | Engaged by importer | Required for entry; the right party to confirm HTS, AD/CVD and PGA requirements |

**Mogra's own role depends on an unmade decision:** whether Mogra imports directly (becoming IOR + FSVP importer + likely organic importer-of-food), or buys from a US distributor who already imported. The former adds significant compliance obligation — and is a **cost and capability item**, not just paperwork.

---

## 7. Honest status of this review

| Item | Status |
|---|---|
| HTS classification (indicative) | Stated; **exact 10-digit line NOT confirmed** |
| Base duty rate | **NOT confirmed** — must read live HTS |
| Additional origin tariffs | **NOT confirmed** — volatile; confirm per import |
| AD/CVD order coverage | **NOT confirmed either way** — **FLAG FOR BROKER REVIEW** |
| AD/CVD is separate from HTS | **CONFIRMED** (USITC) |
| Official AD/CVD query route | **IDENTIFIED** (`access.trade.gov/adcvd/`) and reachable |
| NOP Import Certificate mechanism | **Described**; supplier-by-supplier confirmation required |
| Mogra importer certification obligation | **Flagged as likely required** — confirm with certifier |
| Food facility registration / prior notice / FSVP | **Described at a high level**; confirm applicability |

### Disposition

**No AD/CVD or duty figure is included in any pricing or landed-cost output in this project.** Every international cost remains `LANDED_COST_INCOMPLETE`. The correct next step is a **licensed customs broker review** using the confirmed HTS lines and each in-scope origin — not a self-computed estimate.
