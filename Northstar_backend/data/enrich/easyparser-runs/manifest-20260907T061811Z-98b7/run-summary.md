# Manifest run summary

- run-id: manifest-20260907T061811Z-98b7
- generated_at_utc: 2026-09-07T06:18:55.171424+00:00
- provider: easyparser
- max-requests: 10 | actual requests made: 9
- max-credits: 200 | credits used: 225.0 (reported=225, estimated=0.0)
- stop_reason: max_credits
- provider warnings: none

Disclosure: actual credits used may exceed the stated --max-credits cap by up to one ASIN's cost, because the cap is checked before each call, not continuously during it.

## Aggregate metrics

- Price delta within +/-5%: 5 of 9 rows with comparable prices
- Prime/FBA flag exact match (invoked rows): 3
- Title similarity "Exact/near-exact": 0
- Failed/unavailable: 0 | skipped_cap: 1

## Flagged ASINs (major delta / Prime mismatch / conflicting title)

- B01H40O42I: Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Potentially conflicting
- B08R2SRN88: Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B0CP6LXPLK: major price delta (-53.8%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B00BISGJXA: major price delta (-12.4%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B00BH3HPZW: title similarity: Unrelated
- B00GYZWNY6: title similarity: Potentially conflicting
- B0045XGE9E: major price delta (-10.5%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B002L4M4M0: title similarity: Unrelated
- B081THWMDK: major price delta (-16.7%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated

## Per-ASIN judgment

| asin | outcome | title_similarity | price_delta_pct | prime csv/live | judgment |
|---|---|---|---|---|---|
| B01H40O42I | partial | Potentially conflicting | +0.9% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B08R2SRN88 | partial | Unrelated | +0.0% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B0CP6LXPLK | partial | Unrelated | -53.8% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B00BISGJXA | partial | Unrelated | -12.4% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B00BH3HPZW | partial | Unrelated | -1.0% | Yes / Prime | Suspect mapping / provider limitation - needs manual review |
| B00GYZWNY6 | partial | Potentially conflicting | +0.0% | Yes / Prime | Suspect mapping / provider limitation - needs manual review |
| B0045XGE9E | partial | Unrelated | -10.5% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B002L4M4M0 | partial | Unrelated | +0.0% | Yes / Prime | Suspect mapping / provider limitation - needs manual review |
| B081THWMDK | partial | Unrelated | -16.7% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B085F1QCB9 | skipped_cap | Unrelated | n/a | No (Amazon-shipped, non-Prime badge) / Unknown | Skipped - request/credit cap reached before this ASIN; no comparison possible. |

Reviews: the selected provider does not supply review counts; reviews_live is Unknown for every row. Provider does not supply bsr.

No ASIN in this run is purchase-authorized by this comparison alone.
