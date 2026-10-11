NorthstarOS Amazon file samples (synthetic)
===========================================

These are REDACTED, synthetic files with fake IDs (C100, K300, SKU-1, B01TEST0001).
Use them to try the whole round-trip before touching a real account file:

1. sp_bulksheet.xlsx ........ Ads Sponsored Products bulksheet (what you download from Ads).
2. sb_bulksheet.xlsx ........ Sponsored Brands bulksheet with Creative / Product Collection rows.
3. sp_search_terms.xlsx ..... Search-term report (feeds briefs).
4. listing_template.txt ..... Seller Central listing update template (tab-delimited).
5. listing_detail_template.txt  Product-detail template (bullets, description, keywords).
6. aplus_list.csv ........... A+ ASIN list (produces an asset pack, not a module file).
7. ads_error_report.xlsx .... Ads processing report with an Error column (upload after a real submit).
8. listing_processing_report.txt  Seller Central processing report (sku + error columns).
9. metrics_before.xlsx / metrics_after.xlsx  Two periods for the before/after comparison.

Nothing here contacts Amazon. The workflow is: download from Amazon, upload here,
approve rows, download the change file, upload it to Amazon yourself.
