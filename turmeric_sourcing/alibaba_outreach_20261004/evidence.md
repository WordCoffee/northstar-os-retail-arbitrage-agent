# Alibaba Sourcing + Outreach — evidence checkpoint

**Run folder:** turmeric_sourcing/alibaba_outreach_20261004/
**Policy profile:** alibaba_sourcing_outreach_v1 (fingerprint a9bb98b6bdb9e17c4e4efd39c79e192e721153819bb66a076b47c5637fa0636b)
**Model:** DeepSeek V4.1 Flash (OpenCode-configured).

## Checkpoint 0 — setup (done)
- `config/alibaba_sourcing_outreach_v1.json` + `lib/chromecontrol/outreach-policy.js` created (separate; commerce/Amazon + public_sourcing_readonly_v1 untouched).
- Outreach mode wired: pw-tool (navigate/read/screenshot/extract/click/type on alibaba.com only; denies purchase/checkout/payment/cart/contract/credential), agent-loop (signed-out rendered-state stop disabled), mcp-server (`CHROMECONNECT_OUTREACH=1`).
- Bridge repair: live-page read now polls until rendered text appears.
- Regressions: agent-loop 145/145, sourcing 45/0, rendered-state 12/0.

## Checkpoint 1 — preflight (done)
- Profile selected by operator via native picker; recorded by Chrome as **Profile 7 "Northstar Research"** (signed out).
- Preflight: transport_profile_binding VERIFIED (nonce 5dbbd119a978385a, child pinned `--profile-dir-name "Profile 7"`, extension answered); all 6 required checks passed; relay present.

## Checkpoint 2 — filters discovered (done)
- Verified/Assessed Supplier filter = `assessmentCompany=true`
- Store reviews 4.0 & up = `reviewScore=4`
- Country filter = `country=IN|PK|BD|LK|NP|BT|MV|AF`
- Filtered URL: `https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&assessmentCompany=true&reviewScore=4&tab=all&country=<CC>&keywords=<q>`

## Checkpoint 3 — country x form searches (verified + 4.0*)
- **India**: powder — candidates found; whole — candidates found.
- Pakistan: powder none; whole only unrelated (beauty cream) listings.
- Bangladesh, Sri Lanka, Nepal, Bhutan, Maldives, Afghanistan: NO qualifying verified 4.0* results (either form).
- US, Canada, Mexico: no verified 4.0* results.

### India candidates (visible platform signals)
Powder: ISAR INTERNATIONAL LLP (10y, 4.6/10, ground turmeric for cooking); GINGERLY NATURALS PVT LTD (9y, 5.0/3); AEROZ INTERNATIONAL (3y, 4.7/3, extract); HIMALAYAN HERBARIA INC (10y, 4.9/7, curcumin extract); VANITY VISION (7y, 5.0/1, extract).
Whole: HIMALAYAN HERBARIA INC (10y, 4.9/7, whole finger); AMERA EXPORTS PVT LTD (5y, 4.2/8, extract); AARNAV GLOBAL EXPORTS (9y, 4.8/5, essential oil — exclude); SALVIA COSMECEUTICALS (5y, 5.0/4, cosmetic — exclude).

## Checkpoint 4 — PAUSED for login
- Profile 7 is signed out; Alibaba shows "Sign in / Create account".
- Section 6 outreach (Contact Supplier / RFQ forms) requires the operator's Alibaba session.
- Next after login: deep-review product pages + certificates, then send the section-6 inquiry template to the shortlist.
