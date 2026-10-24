# Browser Phase 2 — Office Supplier Validation (Goal 1 & 2)

**Date:** 2026-09-30 · **Browser:** Playwright/ChromeConnect, profile `Profile 7 = "Northstar Research"` (signed-out; Google shows "Sign in"). **Faire = data only; banned as a supplier.**
Method: in-browser Google + direct official-page reads. Quotes are copied from the live pages (evidence).

## Classification key
`VERIFIED_OFFICE_WHOLESALE_LEAD` · `PROMISING_BUT_POLICY_UNKNOWN` · `BRICK_AND_MORTAR_ONLY` · `AMAZON_PROHIBITED` · `RETAIL_ONLY` · `UNVERIFIABLE` · `REJECTED`

## S.P. Richards (spirichards.com)
- `/customers/`: **"SPR empowers resellers to grow their sales and profit with minimal capital investment by providing a competitively priced broad product offering of both branded and private label products."**
- Customer types (from search page): "JanSan distributors, office products & furniture dealers".
- Prior-phase terms line: **"Customer must provide… properly executed resale certificate exemption form(s) for all states where Customer is registered for sales tax purposes."** (sprichards.com/terms-of-use)
- Amazon/MAP policy: **not published on the site → UNKNOWN** (Google AI overview claims a pass-through manufacturer-MAP framework — treat as UNVERIFIED, lead only).
- **Classification: `VERIFIED_OFFICE_WHOLESALE_LEAD`** (legitimate national office wholesaler). Blocker: resale certificate + dealer relationship; Amazon permission **UNKNOWN**.

## Bulk Office Supply (bulkofficesupply.com) — official quotes
- `/Resellers.aspx`: **"Resellers can easily create an account online without an application process or special business license."**
- **"Please email your tax-exempt or resale certificate to tax@BulkOfficeSupply.com before placing an order."**
- **"There is no order minimum, BULK minimums may vary by manufacturer."**
- **"Invoices can be provided upon request… We cannot send an invoice PRIOR to placing your order."**
- **"We are not able to advise our resellers regarding whether or not Marketplaces will allow the sale of specific brands or manufacturers… it is the responsibility of the reseller to check directly with the Marketplace."**
- **"All brands can be purchased for resale except for Hewlett Packard."**
- **"…our invoices do have the required information by Amazon and that we cannot say if you will be permitted to sell a specific brand."**
- `/faq.aspx`: tax-exempt cert to tax@; **truck-delivery min ~$105**; **no PO/Net-30 except governmental agencies & school districts (PO min $100)**.
- **Classification: `PROMISING_BUT_POLICY_UNKNOWN`** — low friction + invoice-capable, but **explicitly cannot warrant brand/Amazon permission**. HP excluded. Good for commodity office SKUs only after per-brand check.

## uOffice Supply (uofficesupply.com)
- Homepage: **"Wholesale Office And Shipping Supplies For Ecommerce"**; volume-discount wholesale structure; account + login.
- **Classification: `PROMISING_BUT_POLICY_UNKNOWN`** (importer/distributor; no public Amazon/MAP policy found).

## Bazic Products (bazic.com) — manufacturer
- `/pages/our-team`: **"Join hundreds of businesses who trust BAZIC to supply products their customers love. Open a wholesale account and get access to competitive pricing, fast shipping, and top-selling SKUs."**; Dealer Login.
- Also listed on **Faire** (faire.com/brand/b_7gseir0xv8) — **Faire channel cannot be used as an Amazon source**; direct dealer account only.
- **Classification: `VERIFIED_OFFICE_WHOLESALE_LEAD`** (manufacturer/dealer). Amazon permission UNKNOWN.

## Essendant (essendant.com) — caution
- `/get-started/`: **"I'm interested in buying products wholesale for delivery to my warehouse or drop shipped to my customers → Become A Wholesale Customer"**.
- `/faqs/` (decisive): **"Essendant only sells to active customers. All accounts have consistent monthly minimums that need to be met for the account to remain active. Occasional bulk purchases or one-time buys do not satisfy that requirement."**
- Prior-phase news: Essendant **exiting office-products**.
- **Classification: `REJECTED` for initial office sourcing** (monthly minimums + office-market exit). Not test-order friendly.

## Independent Suppliers Group (isg.coop) — buying co-op
- About Us page is JS-light (limited text captured: "Dealer Locator"). Prior evidence: member-owned purchasing co-operative.
- **Classification: `PROMISING_BUT_POLICY_UNKNOWN`** (membership; not a direct supplier). Needs membership = business dealer.

## Kole Imports (koleimports.com) — official quote
- `/sales-faq`: **"You do not need reseller's permit to purchase products from Kole Imports. We will sell to any business, organization, or if you are just a value seeker."**
- **"…there is a per piece minimum on all of our products… We offer a price break on the higher quantity amounts."**; "one of the largest wholesale distributors in the United States… over 30 years."
- Amazon invoice acceptability: community claim only (UNVERIFIED). Prior phase: Kole dropship requires Federal Tax ID.
- **Classification: `PROMISING_BUT_POLICY_UNKNOWN`** (general/closeout; no permit needed; brand Amazon permission UNKNOWN).

## Other Google-discovered office candidates
- **Global Industrial** (globalindustrial.com) — reseller program (sponsored result: "Become a Global Industrial Reseller"); industrial/office supply; **`PROMISING_BUT_POLICY_UNKNOWN`**.
- **Uline** (uline.com) — business supplies; **`PROMISING_BUT_POLICY_UNKNOWN`**.
- OfficeCrave, OnTimeSupplies, W.B. Mason — **RETAIL_ONLY / B2B_ACCOUNT** (not wholesale-to-reseller programs).

## Google search count (in-browser this phase)
`office supplies wholesale distributor ecommerce account`; `S.P. Richards Amazon reseller policy MAP`; `Bulk Office Supply Amazon FBA invoice accepted`; plus YouTube-targeted. Blocked: **none** (no CAPTCHA encountered).

## Office rejections
- **Essendant** — monthly minimums + market exit.
- **Amazon-native brands** (prior phase) — direct competition.
- **Faire** — banned as supplier (even where a brand like BAZIC is listed there).

## Office account shortlist (owner action)
1. **Bulk Office Supply** (commodity SKUs; invoice on request; per-brand check).
2. **uOffice Supply** (importer; wholesale for ecommerce).
3. **Kole Imports** (general/closeout; no permit).
4. **Bazic Products** dealer (manufacturer) + **S.P. Richards** (resale cert) — legitimacy tier.
