# Price Discrepancy Review — run 20260907T055957Z

Source of truth: both benchmark CSVs, joined by ASIN (truth baseline `truth/amazon-truth-baseline.json`, created during prep; all 10 ASINs present in both files, zero conflicts). Live numbers: Easyparser OFFER buy box + returned offer list, captured 2026-09-07T06:18Z (ZIP 19805).

Cross-cutting observation: the buy box is currently held by **cheap FBM sellers** on the four flagged ASINs (buy-box sellers rated 3.0-3.5★, 44-67% positive), while the FBA offer tier sits at or very near the CSV truth. The delta therefore comes from *which offer* the buy box exposes, not from the product price level itself.

### B0CP6LXPLK — Minoxidil Extra Strength (6-mo)
- Truth price (CSV): **$33.12** · Live buy box: **$15.29** (Δ -17.83, -53.8%)
- Buy box: **America Strong** (FBM) — rating 3.0★, 50% positive
- FBA offer prices (returned 4): [32.7, 32.96, 33.15, 33.71]
- FBM offer prices (returned 7): [15.29, 32.48, 32.49, 34.88, 38.95, 39.95, 49.99]
- Claimed offer_count=14, returned=11 (partial is noted in every snapshot).
### B081THWMDK — Stretch Tite Food Wrap (2pk)
- Truth price (CSV): **$28.79** · Live buy box: **$23.98** (Δ -4.81, -16.7%)
- Buy box: **Fiorenzo LLC** (FBM) — rating 3.5★, 67% positive
- FBA offer prices (returned 1): [28.45]
- FBM offer prices (returned 10): [23.98, 24.31, 26.9, 26.98, 26.99, 26.99, 27.99, 27.99, 28.99, 29.31]
- Claimed offer_count=30, returned=11 (partial is noted in every snapshot).
### B00BISGJXA — Stool Softener 100mg (400ct)
- Truth price (CSV): **$12.75** · Live buy box: **$11.17** (Δ -1.58, -12.4%)
- Buy box: **DesiGabbar** (FBM) — rating 3.0★, 49% positive
- FBA offer prices (returned 5): [12.5, 12.62, 12.62, 12.62, 12.62]
- FBM offer prices (returned 6): [11.12, 11.15, 11.15, 11.17, 12.4, 12.5]
- Claimed offer_count=44, returned=11 (partial is noted in every snapshot).
### B0045XGE9E — Sleep Aid Doxylamine (2pk/192ct)
- Truth price (CSV): **$13.84** · Live buy box: **$12.39** (Δ -1.45, -10.5%)
- Buy box: **OM Trading NC** (FBM) — rating 3.0★, 44% positive
- FBA offer prices (returned 5): [13.74, 13.81, 13.82, 13.82, 13.82]
- FBM offer prices (returned 6): [12.39, 12.39, 12.39, 12.99, 13.25, 13.83]
- Claimed offer_count=37, returned=11 (partial is noted in every snapshot).

### B0CP6LXPLK classification
- **Buy Box vs lowest-offer mismatch (FBM race-to-bottom), NOT missing baseline, NOT condition, NOT pack-size, NOT provider normalization**
- Why: CSV $33.12 aligns with the FBA tier ($32.70-$33.71) and the mid FBM tier ($32.48/$32.49); the box is a single 3.0★ FBM offer at $15.29 with $14.99 shipping. The low-rated (3.0★) FBM seller undervalues the box; FBA level still validates the baseline.

### B081THWMDK classification
- **Buy Box vs lowest-offer mismatch; baseline correct at FBA level**
- Why: The only returned FBA offer is $28.45 (BETTERCO), essentially the CSV $28.79; the box ($23.98, Fiorenzo LLC 3.5★/67%) is the cheapest FBM. 10 of 11 returned offers are FBM.

### B00BISGJXA classification
- **Modest genuine price drift + Buy Box vs lowest-offer mismatch**
- Why: FBA tier $12.50-$12.62 is below the $12.75 baseline (drift ~ -1% to -2%), and the FBM floor $11.12-$11.17 wins the box (DesiGabbar 3.0★/49%). Baseline slightly stale but not wrong; box understates.

### B0045XGE9E classification
- **Buy Box vs lowest-offer mismatch (clearest case)**
- Why: FBA tier $13.74-$13.83 matches the CSV $13.84 almost exactly (-0.7%); box is $12.39 from 3 FBM sellers (OM Trading NC 3.0★/44% etc.).

### Overall determination
- All four flagged deltas are **Buy Box vs lowest-offer mismatches** caused by the buy box being held by low-priced FBM sellers; none is a provider normalization error, a condition mismatch (all New), or a pack-size mismatch (live titles confirm the exact CSV items).
- B00BISGJXA additionally shows mild genuine drift (FBA tier slightly below baseline).
- Recommendation for future comparisons: compare against an **FBA-tier reference** (lowest FBA offer or FBA buy box) instead of the raw cheapest-FBM buy box, or record both `buy_box` and `lowest_fba` and flag the delta separately.
- The Easyparser `partial` status (11 offers returned vs 14-68 claimed) does not affect the buy box head, but means off-returned offers (including possible lower prices) are not enumerated.
