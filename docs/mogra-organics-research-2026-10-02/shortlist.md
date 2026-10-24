# Mogra Organics — Supplier Shortlist (Corrected)

**Research folder:** `docs/mogra-organics-research-2026-10-02/`
**Purchasing entity:** T2Holdings LLC (owner-supplied) — **exact legal spelling NOT yet verified against owner business records**
**Date:** 2026-10-02
**Status:** Checkpoint 3 — qualification-and-route-comparison pass. **No supplier contacted.**

---

## Corrections applied in this pass

1. **Removed** the assertion that exporters cannot provide certified finished units. Some exporters also manufacture and pack private-label products. Pearl, for example, publicly advertises private label / ODM / OEM with bulk, pouch, jar and retail-ready packing.
2. **Reframed HANDLING** as a certification *scope*, not proof that every facility, process, product, or Mogra label is approved.
3. **Reclassified Especias Moy as D / ORGANIC_EVIDENCE_NOT_ESTABLISHED.** Its wording is ambiguous, not contradictory, so E was wrong. Quoted language preserved in `organic_verification.csv`.
4. **Replaced "structural absence"** for uncovered countries with "**no qualifying lead found within the completed searches**" — an honest statement about the search, not a claim about the market.
5. **Separated commercial suppliers from resources.** Cornell CALS was moved out of the commercial co-packer shortlist into the resource table, alongside Oregon Tilth, CoPacker Index, Penn State Extension, USDA OID, Sri Lanka EDB and IPC.
6. **Resolved the count denominators** — see below.

---

## Counts, with denominators stated explicitly

The earlier "55 records / 52 distinct entities" was wrong and is withdrawn. Actual current state:

| Measure | Count | Denominator / meaning |
|---|---|---|
| **Commercial supplier records** | **51** | distinct legal entities in `supplier_master.csv`. No duplicates. |
| **Resources / directories / referral orgs** | **7** | `resources_and_directories.csv` — **excluded** from supplier counts |
| Supplier + resource combined | 58 | what "55" was loosely pointing at |
| **Product/form rows** | 49 | supplier×product×form |
| **Organic verification rows** | 60 | supplier×product-form |

### Certification status — with correct denominator

| Label | Rows | **Suppliers** |
|---|---|---|
| **A** (verified) | 9 | **1** — Pearl Group Corporation (9 rows = 9 product forms of one supplier) |
| **CONFIRMATION_REQUIRED** | 1 | 1 — Pearl's organic turmeric powder |
| **C** (marketing claim only) | 23 | 21 |
| **D** (no organic evidence / not established) | 27 | 27 |

**So: 1 of 51 commercial suppliers is organically verified.** The "9" in the A row is nine *product forms* of a single verified operation — it must never be read as nine verified suppliers. Every certification figure below states its denominator.

---

## Grade A — the one verified supplier

### Pearl Group Corporation · Vietnam

| Field | Verified value |
|---|---|
| Operation | **PEARL GROUP CORPORATION (PEARL GROUP)** |
| Program | USDA-NOP |
| Certifier | **[CUC] Control Union Certifications B.V.** |
| Status | **Certified** |
| Country | Viet Nam |
| Scope | **CROPS + HANDLING** |

**Verified product forms** (observed in the USDA OID product list, 2026-10-02): Organic Whole Black Pepper · Organic Ground Black Pepper · Organic Dried Sliced Turmeric · Organic Fresh Turmeric · Organic Cinnamon/Cassia · Organic Dried Chilli + Flakes · Organic Ginger (fresh + dried sliced) · Organic Coriander, Cumin, Cardamom, Fennel, Mustard · dried cut-&-sifted Basil, Mint, Rosemary, Thyme, Dill, Marjoram, Parsley, Peppermint, Spearmint.

**Scope caveat, stated plainly:** HANDLING is a *certification scope*. It is **not** proof that every facility, process, product, form or label is approved. It is also not proof that the entity appearing as *exporter of record* is the certified operation, nor that a Mogra-label unit would be eligible for the seal. Those remain open — see `pearl_evidence_packet.md`.

**Two corrections carried into the packet:**
- **Turmeric powder**: Pearl's *website* lists "Organic Tumeric Powder". That is a genuine **product-level supplier claim** — not an inference from fresh/sliced. The earlier OID capture was **truncated**, so absence of "powder" in it was not evidence of absence. Status: claimed, awaiting full list / certificate addendum.
- **Private label**: Pearl publicly advertises private label, ODM, OEM and retail packing (bulk bags, pouches, jars), with flexible sizing and labelling. Capability **claimed**, packing-operation organic status **unconfirmed**.

**Full detail:** `pearl_evidence_packet.md`. **Open items:** `priority_verification_queue.csv` priority 1.

---

## Commercial suppliers by category (51 total)

| Category | Count | Examples |
|---|---|---|
| Exporters / processor-exporters | 20 | Pearl (A), Radiance, Shree Agro, DK Commodity |
| Importers / distributors (US & other) | 12 | Flavoric, Bata Food, Multiple Organics, Frontier, Starwest |
| Co-packers / private-label manufacturers | 7 | Spices Inc, Specialty Food Co-Packers, Organic Spices Inc, Rocky Mountain |
| Producers | 3 | White Rabbit Acres (US, FL), Amazon Andes (PE), SBimal (FJ) |
| Salt | 5 | Cargill, SF Salt, Sea Salt Superstore, SeaSalt.com, Baker's Authority |
| Other brands/manufacturers | 4 | Badia, Quintal, Especias Moy, Canadian Organic Spice |

**None of the 50 non-Pearl suppliers carries verified organic status.** All are leads.

---

## Black pepper — leads, ranked by verification-worthiness (all C unless noted)

| Supplier | Country | Why worth verifying |
|---|---|---|
| **Pearl Group** | Vietnam | **A — verified.** Whole and ground pepper both on certificate |
| Radiance Overseas | India | Most specific public claims; per-shipment OTC; MOQ 1 MT; lead time published |
| Prime Food Products | Sri Lanka | Only SL lead claiming USDA organic on pepper with public piperine/density specs |
| JAPC | Sri Lanka | Broad range; in-house steam sterilization; low-MOQ private label claimed |
| Bata Food | TR/NL/US | Only published MOQ (800 kg); customs-cleared Rotterdam stock |
| DK Commodity | Vietnam | Dedicated pepper processor; ASTA lab; Rainforest Alliance |

## Turmeric — leads

| Supplier | Country | Why worth verifying |
|---|---|---|
| **Pearl Group** | Vietnam | **A — fresh + dried sliced verified; POWDER claimed, pending confirmation** |
| JAPC | Sri Lanka | Best public spec sheet: curcumin ≥4%, mesh, moisture, steam sterilization |
| Radiance Overseas | India | Curcumin 3–5% by origin; per-lot assay; 3 mesh options |
| Shree Agro International | India | Purity 99.00%; Salmonella absent/25 g |
| Ecopharma | Indonesia | **Lowest MOQ found (300 kg)**; COA per shipment — but **no organic claim** |
| Amazon Andes | Peru | **Only unverified lead that names a certifier** (Control Union Peru); cert not sighted |
| White Rabbit Acres | USA (FL) | Only US-domestic organic turmeric grower; pilot scale |

---

## Resources separated from suppliers

These are **not** commercial suppliers and must not be counted as leads:

| Resource | Type | Use |
|---|---|---|
| USDA Organic Integrity Database | government registry | **primary verification route** |
| Oregon Tilth Co-Packer Information | certifier-published | co-packer discovery |
| CoPacker Index (Kosher + Organic) | third-party directory | co-packer discovery |
| Cornell CALS Food Venture Center | **university resource** | *moved out of commercial shortlist* |
| Penn State Extension Co-Packer List | university/extension | co-packer discovery |
| Sri Lanka Export Development Board | government directory | lead generation |
| International Pepper Community | industry association | lead generation |

---

## Sourcing routes — comparison (detail in `route_comparison.csv`)

Three routes, each with two plausible arrangements where evidence supported it. **Self-repacking is not assumed as the launch route.**

| Route | What it is | Pepper arrangements found | Turmeric arrangements found |
|---|---|---|---|
| **A** | Certified **overseas finished** Mogra units | Pearl (verified organic, packing capability claimed) · Radiance/JAPC (unverified) | Pearl (powder pending) · JAPC |
| **B** | **Overseas organic bulk** + certified **US co-packer** | Pearl/Bata/Radiance bulk + US co-packer | Radiance/Shree Agro/Ecopharma bulk + US co-packer · Amazon Andes bulk + US co-packer |
| **C** | **US organic ingredients** + certified **US co-packer** | Spicy Organic / Spices Inc + US co-packer · McKinney TX cluster | White Rabbit Acres or Spicy Organic + US co-packer |

**No route is declared cheapest.** Every cost line is `unknown` because no comparable quotes exist. Ingredient, packaging, packing, testing, freight/import and Amazon channel costs are held **separately** in `route_comparison.csv`. No public price found is a wholesale quote for a Mogra specification.

**Certification dependency that cuts across all routes:** if Mogra blends, repacks or relabels organic material, that **handling activity generally requires its own certification**, and eligibility of the finished pack depends on it — not on the upstream supplier's certificate. This is a **process, not a purchase**, and it is the largest single unknown in routes B and C.

---

## Uncovered coverage — honest statement

**No qualifying lead was found within the completed searches** for: **Cambodia, Laos, Philippines, Malaysia, Singapore, Nepal, Bangladesh.** This describes the searches performed, not the markets. It is not a claim that certified organic spice suppliers do not exist there.

Similarly, secondary products — garlic powder/granules, onion powder/flakes, paprika and smoked paprika, chili/cayenne/flakes, mustard, nutmeg, allspice, oregano, basil, thyme, rosemary, parsley, dill, sage, bay, culinary mint — have **thin** coverage. Some are covered incidentally by Pearl's certificate; most were not individually searched.

---

## Amazon opportunity — still not scored

No Amazon scraping, SP-API or Seller Central was used. No sales, BSR, fees or profit figures are asserted. **`MARKET_DATA_INCOMPLETE`** for every product. A branded-resale ASIN's history is not evidence a new Mogra private-label listing performs similarly.

---

## Salt

**Plain culinary salt cannot carry USDA organic certification** — mineral, not agricultural; no NOP pathway. No supplier in the salt track claims otherwise, and none should.

- **Cargill** states "Contains no anticaking or free flowing" agents — the additive-free evidence pattern required.
- **SF Salt** — up to 400 lbs online, free shipping, private label for CPG brands.
- **Spices Inc** — exotic/smoked/flavoured salt blends, bridging salt into organic seasoning blends (the only route to an organic claim).
- **SeaSalt.com** — also sells bath salts; excluded from culinary scope.

---

## Next actions, in value order

1. **Run the manual USDA OID lookups** in `priority_verification_queue.csv` (15 queued). Automation is blocked by tooling, not access; the DB is public. A person with a browser does these quickly. Never accept unfiltered registry results as a supplier match.
2. **Request Pearl's certificate PDF + full product list** — closes turmeric powder, packing scope, expiry, and exporter-of-record in one step.
3. **Customs-broker review** of confirmed HTS lines + AD/CVD scope per origin (see `duty_and_import_review.md`). No landed cost is valid without it.
4. **Verify T2Holdings LLC's exact legal spelling** from owner records — still unresolved in all drafts.
5. **Confirm the two US co-packers' NOP handler certification** (Spices Inc, Specialty Food Co-Packers) — SQF/GMP are food-safety schemes, **not** NOP organic certification.
