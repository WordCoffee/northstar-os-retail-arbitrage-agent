# Mogra Organics — Sourcing & Launch Working Blueprint

**WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION**
**Date:** 2026-10-02
**Entity:** T2Holdings LLC (owner-supplied spelling — NOT yet verified against business records)
**Prepared by:** Northstar research pass
**Status of supply chain:** REVIEW-READY, NOT PURCHASE-READY

---

## 1. Document status and how to read this

This is a **working blueprint**. It is designed to be reviewed, questioned and corrected. It is **not** an approval to buy, import, produce or launch.

Every material claim carries a status:

| Status | Meaning |
|---|---|
| **VERIFIED** | Authoritative or independently corroborated evidence supports the exact claim |
| **PROVISIONAL** | Useful documentation whose currency or exact applicability is unresolved |
| **SUPPLIER_CLAIMED** | Supplier marketing, specification or assertion |
| **REPORTED** | Inherited assertion not independently re-checked |
| **PROPOSED** | Recommendation or scenario — not an approved decision |
| **UNKNOWN** | Evidence or input unavailable |
| **NOT_APPLICABLE** | Only where a documented reason exists |

**A high supplier grade never implies that all of that supplier's products or processes are verified.**

---

## 2. Executive decision brief

**What this research found, in one page:**

1. **One supplier out of fifty-one has independently verified organic status.** Pearl Group Corporation (Vietnam) is certified USDA-NOP by **Control Union Certifications B.V.**, scope **CROPS + HANDLING**, confirmed in the public **USDA Organic Integrity Database on 2026-10-02**.
2. **Pearl's certified product list explicitly covers organic whole and ground black pepper**, and a broad herb/spice range relevant to Mogra.
3. **Organic turmeric powder is NOT yet verified.** Pearl's website advertises it; the certification coverage for the powder form is unconfirmed. This is a named gap with a precise closure action — not an assumption.
4. **A second material evidence gain:** JAPC (Sri Lanka) names **Control Union** as its certifier, though without a certificate number. Status **PROVISIONAL**.
5. **Three sourcing routes exist, and none is cheapest.** Route A (overseas finished), Route B (imported bulk + US co-packing), Route C (US turnkey). All landed costs are `INCOMPLETE` because **no duty, AD/CVD or freight position exists yet**.
6. **No supplier has been contacted, no account created, no sample ordered, nothing purchased.**
7. **The single largest hidden cost is certification of Mogra's own activity.** An organic input does not automatically make a Mogra pack eligible for the USDA seal. If Mogra imports, repacks or blends, that activity likely needs its own certification — a process, not a purchase.

**What the owner must decide first:** the exact legal entity spelling (D1), the initial product/form (D2), the organic labelling pathway (D3), and the preferred route (D5).

---

## 3. Current scope and brand context

### What this research actually covers
The researched scope is **organic culinary spices, herbs and associated salt-containing seasoning**, sourced for a US-branded food product. Priority products: **black pepper** and **turmeric**.

### Documented future interests (NOT researched here)
Mogra Organics is described as a premium **mushroom and herb wellness** brand with interests in **edible and topical** products and possible **future vertical integration**. These are recorded as **documented interests**, and are **not** part of this sourced blueprint. No mushroom, supplement, cosmetic or agricultural-development work was performed.

### Explicit scope boundaries
- Mogra is kept **separate** from Word Coffee, NorthstarOS, and Northstar's resale product-exclusion rules.
- **Northstar's non-food resale filters do not apply to Mogra's own products.**
- No SKU is treated as an approved launch SKU merely because an ingredient was researched.

### Owner approvals
**No owner approval of any product, route, price or label is recorded.** Anywhere a decision is implied, it is marked **OWNER_INPUT_REQUIRED**.

---

## 4. Research coverage and evidence limitations

### What was done
Systematic discovery across search engines, supplier sites, government registries, certifier pages, trade associations and university/extension resources; organic verification attempts via the USDA Organic Integrity Database; a duty and import review against official sources.

### Coverage counts (reconciled to the canonical tables)

| Measure | Count | Source table |
|---|---|---|
| Commercial suppliers | **51** | supplier_master.csv |
| Resources / directories (excluded from supplier counts) | **7** | resources_and_directories.csv |
| Supplier × product × form rows | **49** | supplier_product_matrix.csv |
| Pricing lines | **15** | pricing_comparison.csv |
| Organic verification rows | **60** | organic_verification.csv |
| Priority verification checks | **15** | priority_verification_queue.csv |
| Route arrangements | **12** | route_comparison.csv |
| Evidence register entries | **20** | evidence_register.csv |
| Risks | **13** | risk_register.csv |
| Decisions | **10** | decision_register.csv |
| Unsent RFQ drafts | **5** | rfq_drafts/ |

**Correction recorded:** an earlier report stated "54 pricing lines." The canonical file contains **15**. The earlier figure was from a malformed intermediate and is withdrawn.

**Why pricing lines (15) differ from suppliers (51):** most suppliers publish no price at all, so they produce no pricing line. Pricing lines exist only where a price or an explicit "quote required" position was captured.

### Organic evidence distribution (denominator stated)

| Grade | Rows | Suppliers |
|---|---|---|
| **A** (verified) | 9 | **1** — Pearl (9 rows = 9 product forms of ONE supplier) |
| **PROVISIONAL** | 1 | 1 — JAPC (certifier named) |
| **CONFIRMATION_REQUIRED** | 1 | 1 — Pearl organic turmeric powder |
| **C** (marketing claim only) | 22 | 21 |
| **D** (no evidence / not established) | 27 | 27 |

### Honest limitations
- **Only 1 of 51 suppliers is verified.** The rest are leads.
- **The USDA OID is public and needs no login** (confirmed), but its automated interaction is unreliable — a force-click returns **unfiltered** results, which would silently create false matches. The verification pass therefore routes through **manual lookups plus supplier-supplied certificate documents**.
- **Control Union certificate verification is behind a client-portal login** — not publicly queryable, and account creation is out of bounds for this task.
- **No qualifying lead was found within the completed searches** for Cambodia, Laos, Philippines, Malaysia, Singapore, Nepal or Bangladesh. This describes the searches, not the markets.
- **Retail prices are not wholesale quotes.**
- **Unknown costs are not zero.**
- **No route has been established as cheapest.**

---

## 5. Product and form overview

Product forms are kept strictly separate throughout. They are **not** interchangeable, and certification of one does not establish another.

| Product | Forms in scope | Evidence state |
|---|---|---|
| **Black pepper** | whole, cracked, coarse-ground, fine-ground | Whole + ground **VERIFIED** at Pearl |
| **Turmeric** | dried sliced, fresh, powder | Dried sliced + fresh **VERIFIED** at Pearl; **powder CONFIRMATION_REQUIRED** |
| **Cinnamon** | whole, ground — **species must be stated** (Ceylon *verum* vs cassia) | Verified at Pearl (observed); species documentation to request |
| **Ginger** | dried sliced, powder | Dried sliced verified; powder to confirm |
| **Chilli / flakes** | dried, flaked | Verified at Pearl (observed) |
| **Coriander, cumin, fennel, cardamom, mustard** | seed/whole | Verified at Pearl (observed) |
| **Dried herbs** (basil, thyme, rosemary, parsley, dill, mint, marjoram) | dried cut & sifted | Verified at Pearl (observed) |
| **Salt (plain)** | grain, flake | **NOT_APPLICABLE for organic** — salt cannot be USDA-organic |
| **Salt-containing seasoning blend** | blend | Only route to an organic claim on a salted product |

**Never merge:** whole vs ground pepper · turmeric powder vs dried sliced vs fresh · bulk ingredient vs finished retail unit · conventional vs organic offer · packing-only vs turnkey service.

---

## 6. Supplier landscape

**51 commercial suppliers across 12+ countries.** Grouped by type:

| Type | Count | Representative |
|---|---|---|
| Exporters / processor-exporters | 20 | **Pearl (A)**, Radiance, Shree Agro, JAPC (PROVISIONAL), DK Commodity |
| Importers / distributors | 12 | Flavoric, Bata Food, Multiple Organics, Frontier, Starwest |
| Co-packers / private-label manufacturers | 7 | Spices Inc, Specialty Food Co-Packers, Organic Spices Inc, Rocky Mountain |
| Producers | 3 | White Rabbit Acres (US-FL), Amazon Andes (PE), SBimal (FJ) |
| Salt | 5 | Cargill, SF Salt, Sea Salt Superstore, SeaSalt.com, Baker's Authority |
| Other brands/manufacturers | 4 | Badia, Quintal, Especias Moy, Canadian Organic Spice |

**Separated resources (not suppliers):** USDA OID · Oregon Tilth co-packer list · CoPacker Index · **Cornell CALS (university resource)** · Penn State Extension · Sri Lanka EDB · International Pepper Community.

**No supplier-wide grade is a product approval.** Pearl's grade A applies to the specific product forms listed on its certificate.

---

## 7. Priority shortlist

Ordered by **commercial usefulness and evidence strength**, not by prior ranking:

| Rank | Supplier | Country | Type | Organic evidence | Why it is on the list |
|---|---|---|---|---|---|
| 1 | **Pearl Group Corporation** | Vietnam | processor-exporter | **A — VERIFIED** | Only verified organic supplier; covers pepper + many herbs |
| 2 | **JAPC** | Sri Lanka | processor-exporter | **PROVISIONAL** (Control Union named) | Broad organic range; best public spec sheet; private label |
| 3 | **Radiance Overseas** | India | exporter | C | Most specific public claims; per-shipment OTC; MOQ 1 MT |
| 4 | **Bata Food** | TR/NL/US | importer-distributor | C | Only published MOQ (800 kg); customs-cleared Rotterdam |
| 5 | **Amazon Andes** | Peru | producer-exporter | C (Control Union Peru named) | Most checkable unverified bulk turmeric |
| 6 | **Spices Inc** | US | co-packer | C | Best turnkey operational fit; salt blends too |
| 7 | **Specialty Food Co-Packers** | US | co-packer | C | USDA Organic + SQF + GMP claimed |
| 8 | **Organic Spices Inc** | US | importer-co-packer | C | Contract manufacturing + private label (McKinney cluster) |
| 9 | **Prime Food Products** | Sri Lanka | processor-exporter | C | Only SL pepper lead claiming USDA organic with specs |
| 10 | **White Rabbit Acres** | US (FL) | producer | C | Only US-domestic organic turmeric grower (pilot scale) |

---

## 8. Pearl evidence and remaining gaps

**Full detail: `pearl_evidence_packet.md`.** Summary:

| Field | Value |
|---|---|
| Operation | **PEARL GROUP CORPORATION (PEARL GROUP)** |
| Program | USDA-NOP |
| Certifier | **[CUC] Control Union Certifications B.V.** |
| Status | **Certified** |
| Scope | **CROPS + HANDLING** |

**Product-form separation (critical):**

| Form | Status |
|---|---|
| Organic Whole Black Pepper | **VERIFIED** |
| Organic Ground Black Pepper | **VERIFIED** |
| Organic Dried Sliced Turmeric | **VERIFIED** |
| Organic Fresh Turmeric | **VERIFIED** |
| **Organic Turmeric Powder** | **CONFIRMATION_REQUIRED** — website advertises it; certificate coverage not confirmed |

**HANDLING scope is a certification scope, not proof that every facility, process, product or Mogra label is approved.** The entity appearing as *exporter of record* has not been matched to the certified operation.

**Open items (all CONFIRMATION_REQUIRED):** MOQ · facility scope · grinding within certified scope · treatment method · retail packing organic status · Mogra-label permission · lot COAs · exporter/importer responsibilities · finished-unit pricing · certificate number and expiry.

---

## 9. Domestic co-packer comparison

**NOP organic evidence is kept strictly separate from SQF/GMP food-safety evidence.** SQF and GMP are **not** organic certification.

| Supplier | Contracting entity / facility | Organic claim | Food-safety claim | Packing-only | Turnkey |
|---|---|---|---|---|---|
| **Spices Inc** | Spices Inc., Lowell MA | claimed, certifier not named | — | yes | yes (sourcing+blending) |
| **Specialty Food Co-Packers** | claimed USDA Organic facility | claimed, certifier not named | SQF + GMP | yes | yes |
| **Organic Spices Inc** | McKinney TX | claimed, certifier not named | — | yes | yes (contract mfg) |
| Rocky Mountain Spice | — | USDA badge, no certifier | — | yes | blending |
| Vanns Spices | — | not stated | — | yes | yes |
| 1000 Springs Mill | — | claimed, certifier not named | — | yes | yes |

**Unverified for all:** actual NOP handler certification, certifier name, certificate number, scope covering **repacking**.

---

## 10. Route comparisons by product

Three routes, each with two plausible arrangements where evidence supported it.

| Product | Route | Arrangement | Evidence state |
|---|---|---|---|
| **Black pepper** | **A** | Pearl — certified finished/private-label | Organic **VERIFIED**; packing **claimed** |
| Black pepper | A (alt) | Radiance / JAPC | Organic **unverified** |
| **Black pepper** | **B** | Pearl/Bata/Radiance bulk + US co-packer | Bulk organic verified; co-packer organic **unverified** |
| Black pepper | B (alt) | India bulk + US co-packer | Different duty treatment possible |
| Black pepper | C | Spicy Organic / Spices Inc + US co-packer | Ingredient + co-packer **unverified** |
| Black pepper | C (alt) | McKinney TX cluster | Cluster relationship unconfirmed |
| **Turmeric** | **A** | Pearl | Organic verified for sliced/fresh; **powder blocked** on certificate confirmation |
| Turmeric | A (alt) | JAPC | Organic provisional |
| **Turmeric** | **B** | Radiance/Shree Agro/Ecopharma bulk + US co-packer | Organic unverified |
| Turmeric | B (alt) | Amazon Andes (Peru) bulk + US co-packer | Certifier named; certificate not sighted |
| Turmeric | C | White Rabbit Acres / Spicy Organic + US co-packer | Thin domestic supply |
| Turmeric | C (alt) | McKinney TX cluster | All costs unknown |

### Tradeoffs, stated plainly
- **Speed vs control:** Route A is fastest and simplest, but concentrates on one overseas entity.
- **MOQ vs cash exposure:** the only published MOQ is Bata Food's 800 kg; Spicy Organic's 5 lb entry is the lowest published quantity.
- **Domestic simplicity vs international complexity:** Route C avoids import entirely but likely costs more per unit (unproven).
- **Finished-unit convenience vs bulk flexibility:** Route A is turnkey; Route B lets Mogra own the blend and the label.
- **Certification certainty vs advertised capability:** only Pearl is verified. Every other route rests on **claimed** capability.

**Per `route_comparison.csv`:** ingredient, packaging, packing, testing, freight/import and Amazon channel costs are held **separately**, and every one is `unknown`.

---

## 11. Organic labelling pathways

Four distinct pathways apply, and they are not interchangeable:

| Pathway | When it applies | Seal |
|---|---|---|
| **"100% organic"** | Product contains only organic ingredients (excluding salt and water) | USDA seal permitted |
| **"Organic"** | ≥95% organic ingredients (excluding salt and water) | USDA seal permitted |
| **"Made with organic [ingredient/category]"** | ≥70% organic ingredients | **No USDA seal** — limited identification only |
| **Ingredient-only organic identification** | <70% organic ingredients; organic items named only in the ingredient panel | No seal |

**Key distinctions the blueprint relies on:**
- A **single-ingredient** spice (e.g. black pepper) can be certified "organic" **if the finished pack is certified** — the ingredient being organic is not sufficient.
- A **multi-ingredient blend containing salt** may only support "made with organic" because salt cannot itself be organic.
- **Removing the seal does not necessarily remove certification obligations.**
- Not every category fits every single-ingredient SKU.

**For every proposed SKU this remains unresolved:** the specific pathway is a certifier/label-review question. **Final approval is NOT documented.**

**Proposed packaging use of "Mogra Organics"** is flagged for certifier label review — no legal conclusion is drawn here.

**Business activities assessed separately:** brand ownership · buying/selling · importing · storage · processing · packing · distribution. Each may or may not trigger certification. **A certifier or qualified professional must confirm the specific arrangement.**

---

## 12. Certification chain and approval gaps

```
Grower ──► Processor ──► Exporter ──► [importer] ──► [Mogra handling] ──► Finished pack
   │           │             │              │                │
 verified    verified      ???           ???              ???
 (Pearl)     (Pearl)    entity match  Mogra obligation  label eligibility
```

**What is verified:** Pearl's grower/processor certification covers the listed product forms.

**What is not:**
- The exporter-of-record entity match to the certified operation.
- Whether the **importer** (Mogra) needs its own organic certification.
- Whether a **Mogra-handled or Mogra-packed** product is seal-eligible.
- The **label review** required before printing.

**An organic input does not make the final Mogra product eligible for the USDA organic seal.** This is the central unresolved certification point.

---

## 13. Food-safety and documentation requirements

For the current spice scope, the relevant controls and documentation are:

| Control | Applies to | Evidence state |
|---|---|---|
| Product identity (botanical/species) | All; **critical for cinnamon** | Supplier spec needed |
| Lot traceability | All | Supplier claim; verify |
| Microbiological hazards (e.g. Salmonella) | All spices | Shree Agro publishes "Salmonella absent/25 g" |
| Heavy metals | All; **critical for turmeric** | White Rabbit publishes independent results |
| **Adulteration** (lead chromate, colourants) | **Turmeric especially** | Must be requested explicitly |
| Pesticide residues | All organic | Supplier COA |
| Allergen / cross-contact | Herbs; co-packers | Ask co-packers |
| Treatment / processing information | All | Treatment must be organic-compatible (irradiation is not) |
| Shelf life, storage | All | Supplier data |
| Packaging suitability | Finished units | Co-packer |
| COA and testing arrangements | All | Ask for a sample COA |
| Recall capability | All | Supplier claim |

**A generic COA does not prove every safety requirement.** Specific limits must come from the supplier and, where regulatory, from official sources.

---

## 14. Import responsibility map

Multiple distinct roles exist, and no single party absorbs all of them:

| Role | Who | Notes |
|---|---|---|
| **Importer of Record** | Mogra or its importer | Files entry; liable for duty and AD/CVD cash deposits |
| **FSVP importer** | The US importer | Must verify foreign supplier food-safety compliance |
| **Certified organic importer** | The importer | Generally must itself be certified organic to import organic product |
| **Exporter / final handler** | Overseas supplier | Must hold certification covering product and export |
| **Manufacturer / processor** | Overseas supplier | FDA food-facility registration |
| **Customs broker** | Engaged by importer | Classification, PGA flags, entry filing |
| **Freight forwarder** | Engaged by importer | Transport, not compliance |

**Do not assume a broker, forwarder, overseas supplier or delivery term assumes every obligation.** The delivery term (Incoterm) allocates cost and risk for transport — not regulatory responsibility.

---

## 15. Customs and tariff review status

**Status: preliminary. NOT a customs determination.**

- **Indicative HTS:** black pepper 0904.11 (whole) / 0904.12 (crushed or ground); turmeric 0910.30; cinnamon 0906.11/0906.20.
- **Base duty: NOT confirmed** — must be read from the live USITC HTS per confirmed line.
- **AD/CVD:** confirmed that **AD/CVD is not in the HTS** (USITC) and depends on specific orders and scope. **No AD/CVD order covering pepper or turmeric from in-scope origins has been confirmed.** Absence of a confirmed order is **not** confirmation that no order applies.
- **Additional origin-specific tariffs:** volatile; must be confirmed per import.
- **Official query route identified:** `access.trade.gov/adcvd/`.

**Disposition: customs-broker review required.** See `customs_broker_review_packet.md`. **No duty or AD/CVD figure appears anywhere in this blueprint.**

---

## 16. Cost coverage and missing quotes

**What is known:** **three published prices only**, all US domestic, **all retail or retail-tier references — none is a wholesale quote**:

| Item | Price | Status |
|---|---|---|
| Flavoric organic turmeric | $12.98–$111.98 / lb | PUBLISHED_RETAIL_REFERENCE |
| Flavoric organic black pepper | $49.98–$369.98 / lb | PUBLISHED_RETAIL_REFERENCE |
| Spices Inc chipotle salt | $6.55 / unit | PUBLISHED_RETAIL_REFERENCE |

**What is quote-required:** ingredient, processing/packing, packaging, setup, testing, freight/insurance, duty/entry/broker, domestic transport, storage, Amazon fees.

**What is unknown:** duty and AD/CVD (broker-dependent), Mogra's own certification cost (role-dependent), Amazon fees and demand (no authorised data).

**Consequence:** **every international route is `LANDED_COST_INCOMPLETE`.** No total is computed from incomplete inputs. **Retail prices must not become wholesale costs.**

---

## 17. Economic scenarios (clearly labelled)

No owner volumes or prices exist, so the model is built as **illustrative scenarios with an isolated assumption register**. The full register is `assumptions_register.csv`.

**Scenario caveats, stated up front:**
- Scenario quantities are **illustrative**, **NOT** owner-approved demand forecasts.
- No Amazon fee or sales estimate is invented.
- Unknowns remain **null** — they are not zero.
- Any total from incomplete inputs would be false, so **none is presented**.

**Illustrative assumption set (PROPOSED, isolated from observed facts):**

| Assumption | Value | Status |
|---|---|---|
| Pilot finished units | 500 | PROPOSED illustrative |
| Retail pack net weight | 2 oz | PROPOSED illustrative |
| Yield loss in grinding/packing | 2% | PROPOSED placeholder |
| Organic premium on bulk ingredient | 20% | PROPOSED placeholder |
| Lead time | — | UNKNOWN |
| Freight / duty / AD-CVD / broker | — | UNKNOWN |
| Amazon fees and demand | — | UNKNOWN |
| Mogra certification cost | — | UNKNOWN |

**Sensitivity:** landed cost is dominated by **freight + duty + AD/CVD**, all currently unknown. Ingredient cost is secondary. Unit economics cannot be meaningfully assessed until the broker review and at least one supplier quote exist.

**Cash commitments needed before each stage:**
- **Before samples:** sample cost + courier (quote-required).
- **Before pilot:** co-packer setup/plate + packaging + ingredient pilot lot + testing.
- **Before production:** all of the above at scale + duty/broker position + certification arrangement.

---

## 18. Packaging and channel-readiness considerations

- **Formats under consideration:** jar, pouch, sachet. **PROPOSED** — not decided.
- **FBA implications:** pouch is lighter and less breakage-prone than glass; relevant only if Amazon is confirmed as primary.
- **Label dependencies:** organic pathway choice (D3), species identity for cinnamon, net quantity, country of origin.
- **Amazon readiness checklist (not asserted as existing):** Seller Central account · category/grocery approval where required · FBA-ready packaging and labelling · compliance documentation · listing content. **None of these is claimed to exist.**

---

## 19. RFQ readiness

**Five finalized, unsent RFQ drafts** in `rfq_drafts/`:

1. Pearl — bulk organic
2. Pearl — certified finished / private-label
3. Spices Inc — packing-only + turnkey
4. Specialty Food Co-Packers — packing-only + turnkey
5. Organic Spices Inc — packing-only + turnkey

Each requests: specifications · certification documents and coverage · MOQ and real price breaks · pack formats · packaging/setup costs · separated ingredient/processing/packing/testing prices · samples · lead time · quote validity · currency · Incoterm + named place · origin and shipping point · lot traceability · testing documentation · label-review responsibilities.

**Outreach-readiness blocker:** the legal entity spelling (D1) is a placeholder in every draft. **Nothing has been sent.**

---

## 20. Sample, pilot and launch gates

Dependency-based (no invented dates):

| Stage | Required inputs | Acceptance criteria | Stop/go gate |
|---|---|---|---|
| 1. Owner scope selection | D1–D5 answered | Product/form + route chosen | Stop if entity unresolved |
| 2. Supplier/document confirmation | Certificate PDFs, specs | Organic scope matches activity | Stop if scope mismatch |
| 3. Quote collection & normalisation | Tier prices, Incoterms | Comparable quotes | Stop if MOQs unworkable |
| 4. Compliance-role confirmation | Certifier opinion; broker position | Importer/FSVP/certification roles settled | Stop if duty unknown |
| 5. Sample evaluation | Samples | Meets spec; COA supports | Stop if adulteration/purity fails |
| 6. Packaging & label review | Chosen format; pathway | Certifier label review completed | Stop if label unapproved |
| 7. Pilot production | Setup paid; ingredient | Units meet spec | Stop if yield/fill fails |
| 8. Receiving & lot acceptance | COA + inspection | Lot accepted | Stop if lot fails |
| 9. Channel setup | Amazon readiness items | Listing + compliance docs ready | Stop if category blocked |
| 10. Controlled launch | Inventory; pricing | First orders fulfilled | Stop/go on sell-through |
| 11. Reorder evaluation | Actual costs + sales | Margin assessed on real data | Stop if margin fails |

**Evidence to retain at every stage:** certificates, COAs, quotes, label approvals, entries, lot records.

---

## 21. Risk register

Full detail in `risk_register.csv`. Highest-impact risks:

| ID | Risk | Impact |
|---|---|---|
| RK-01 | Supplier-wide organic grade mistaken for product/process approval | High |
| RK-02 | Certified input mistaken for approved finished pack | High |
| RK-03 | No-seal pathway assumed to remove certification obligations | High |
| RK-05 | **AD/CVD order applies but unverified — material unbudgeted duty** | Very High |
| RK-06 | Origin-specific tariffs change after quoting | High |
| RK-07 | Turmeric adulteration not detected | High |
| RK-09 | Missing costs treated as zero → false economics | High |

---

## 22. Owner decisions

Full detail in `owner_decision_brief.md` and `decision_register.csv`. The ten decisions:

**Now:** D1 legal entity · D2 initial product/form · D3 organic labelling pathway
**Before outreach:** D4 target volumes · D5 preferred route · D6 budget
**Before samples:** D7 package format/net quantity
**Before importing/production:** D8 importer & FSVP posture · D9 certification arrangement
**Before launch:** D10 sales channels

---

## 23. Recommended next actions

1. **Confirm T2Holdings LLC exact legal spelling** — blocks all outreach (D1).
2. **Request Pearl's certificate PDF + full product list** — closes turmeric powder, packing scope, expiry, exporter-of-record in one step.
3. **Commission customs-broker review** using `customs_broker_review_packet.md` — no landed cost is valid without it.
4. **Verify JAPC's certificate** (certifier now named: Control Union) — highest-value provisional lead.
5. **Confirm NOP handler certification** (distinct from SQF/GMP) for the three US co-packers.
6. **Run the manual USDA OID lookups** in `priority_verification_queue.csv`.
7. **Decide D2 (product/form) and D5 (route)** so quotes can be collected.

---

## 24. Evidence appendix

Full register: `evidence_register.csv` (20 entries). Key sources:

| ID | Source | Observation | Limitation |
|---|---|---|---|
| EV-001 | USDA Organic Integrity Database | 2026-10-02 | Truncated product list; no cert number |
| EV-006 | JAPC certifications page | 2026-10-02 | Certifier named; no cert number |
| EV-011 | USDA NOP framework | 2026-10-02 | Regulatory, not a supplier fact |
| EV-012 | USITC FAQ | 2026-10-02 | AD/CVD not in HTS |
| EV-013 | ITA AD/CVD portal | 2026-10-02 | Not queried per product |
| EV-014 | Control Union certificate listing | 2026-10-02 | Client login required |
| EV-018 | Vietnam Pepper & Spice Association | 2026-01 | Aggregate market anchor only |
| EV-019 | Peacock Tariff Consulting | 2026-10-02 | Industry secondary source |

**Corrections log:**
- "54 pricing lines" → **15** (withdrawn).
- "Exporters cannot provide certified finished units" → **withdrawn** (removed).
- HANDLING reframed as **scope, not facility/process/product approval**.
- Especias Moy **E → D** (ambiguous, not contradictory).
- "Structural absence" → **"no qualifying lead found within the completed searches."**
- Pearl turmeric powder: **inference-from-absence corrected** to supplier-claimed + truncated-capture caveat.

---

*End of working blueprint. WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION.*
