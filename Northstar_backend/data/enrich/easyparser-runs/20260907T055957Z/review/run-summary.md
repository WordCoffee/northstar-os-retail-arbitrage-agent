# Run Summary — Easyparser 10-ASIN Live Pull (20260907T055957Z)

- CLI evidence run: `manifest-20260907T061811Z-98b7` · provider **easyparser** (OFFER/G).
- Caps: `--max-requests 10` `--max-credits 200` → **9 requests made, stop_reason `max_credits`.**
- Credits: provider-reported **225** used (21–29 per request), exceeding the 200 cap by the 9th
  call's charge; cap is checked before each call (CLI discloses this). Balance series 100→71 is
  not self-consistent with credits_used (both provider-reported, recorded verbatim).
- Outcomes: **9 partial, 0 available, 0 failed/unavailable, 0 mapping_error, 1 skipped_cap**
  (B085F1QCB9 — no provider call made; credit cap reached first).
- Title review: all 9 live titles **semantically confirm** the frozen CSV products
  (`match_confirmed_semantically`). Strict Jaccard labels (`Unrelated`/`Potentially
  conflicting`) reflect metric strictness on long titles, not product mismatches.
- Price deltas vs truth: 5 within ±5%; B0CP6LXPLK **−53.8%** ($15.29 live vs $33.12 CSV);
  B081THWMDK **−16.7%**; B00BISGJXA **−12.4%**; B0045XGE9E **−10.5%** — flagged for human review.
- Prime/FBA flag: 6 rows show CSV `Yes` (Prime/FBA) but live buy box FBM today.
- Fields not supplied live: reviews count and BSR → `Unknown` / `provider does not supply BSR`
  (never zero-filled; no substitute source used).
- **No purchase authorization** results from this comparison. Nothing in this run changes
  finance/pricing inputs or Amazon settings.
- Follow-up (NOT automatic): completing ASIN B085F1QCB9 needs a fresh operator decision +
  approval; estimated ~25 provider-reported credits for 1 request.