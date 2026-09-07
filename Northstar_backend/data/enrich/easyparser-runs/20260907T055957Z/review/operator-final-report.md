# Operator Final Report — Easyparser 10-ASIN Run 20260907T055957Z

1. Approved via LIVE NOW → executed `--provider easyparser --max-requests 10 --max-credits 200`.
2. Frozen manifest: exactly the 10 authorized ASINs, `purchase_authorized: false`, sha256 `899660a6…fc5c`.
3. **9 of 10 ASINs pulled** (B01H40O42I, B08R2SRN88, B0CP6LXPLK, B00BISGJXA, B00BH3HPZW, B00GYZWNY6, B0045XGE9E, B002L4M4M0, B081THWMDK). All outcomes `partial`; **0 failures, 0 mapping errors, 0 retries**.
4. **B085F1QCB9 skipped** — no provider call (credit cap hit first). Completing it needs a fresh OK (~25 reported credits).
5. Credits: **225 provider-reported** used; cap 200 was exceeded by the 9th call's charge then the run stopped (CLI cap semantics disclosed in artifacts).
6. Live titles semantically match the CSV products for all 9 (strict Jaccard labels are stricter).
7. Price flags: Minoxidil −53.8% ($15.29 live vs $33.12 CSV); Stretch Tite −16.7%; Stool Softener −12.4%; Sleep 2pk −10.5% — review before any reliance.
8. Prime/FBA: 6 rows CSV `Yes` → live buy box FBM.
9. Reviews/BSR not supplied by Easyparser OFFER → `Unknown` / n/a (never zero-filled).
10. Evidence: `data/enrich/easyparser-runs/manifest-20260907T061811Z-98b7/` + this run's `live/` + `review/` (comparison, discrepancy report, run summary).
11. No finance/pricing/Amazon settings touched; nothing purchase-authorized.
12. USD cost not locally verifiable; ~225 Easyparser credit units consumed.