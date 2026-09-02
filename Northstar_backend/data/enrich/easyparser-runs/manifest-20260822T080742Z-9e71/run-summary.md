# Easyparser OFFER manifest run summary

- run-id: manifest-20260822T080742Z-9e71
- generated_at_utc: 2026-08-22T08:08:58.966255+00:00
- provider: Easyparser OFFER only (DataForSEO forbidden)
- max-requests: 10 | actual requests made: 9
- max-credits: 80 | credits used: 90.0 (reported=75, estimated=15.0)
- stop_reason: max_credits
- provider warnings: none

Disclosure: actual credits used may exceed the stated --max-credits cap by up to one ASIN's cost, because the cap is checked before each call, not continuously during it.

## Aggregate metrics

- Price delta within +/-5%: 2 of 6 rows with comparable prices
- Prime/FBA flag exact match (invoked rows): 1
- Title similarity "Exact/near-exact": 0
- Failed/unavailable: 3 | skipped_cap: 1

## Flagged ASINs (major delta / Prime mismatch / conflicting title)

- B01H40O42I: major price delta (-40.9%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Potentially conflicting
- B08R2SRN88: major price delta (-41.1%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B0CP6LXPLK: major price delta (-52.9%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated
- B00BISGJXA: title similarity: Unrelated; no usable provider data
- B00BH3HPZW: title similarity: Unrelated; no usable provider data
- B00GYZWNY6: Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Potentially conflicting
- B0045XGE9E: title similarity: Unrelated; no usable provider data
- B002L4M4M0: title similarity: Unrelated
- B081THWMDK: major price delta (-19.1%); Prime/FBA flag mismatch (csv=Yes live=FBM); title similarity: Unrelated

## Per-ASIN judgment

| asin | outcome | title_similarity | price_delta_pct | prime csv/live | judgment |
|---|---|---|---|---|---|
| B01H40O42I | partial | Potentially conflicting | -40.9% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B08R2SRN88 | partial | Unrelated | -41.1% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B0CP6LXPLK | partial | Unrelated | -52.9% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B00BISGJXA | unavailable | Unrelated | n/a | Yes / Unknown | Suspect mapping / provider limitation - needs manual review |
| B00BH3HPZW | unavailable | Unrelated | n/a | Yes / Unknown | Suspect mapping / provider limitation - needs manual review |
| B00GYZWNY6 | partial | Potentially conflicting | -1.0% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B0045XGE9E | unavailable | Unrelated | n/a | Yes / Unknown | Suspect mapping / provider limitation - needs manual review |
| B002L4M4M0 | partial | Unrelated | +0.0% | Yes / Prime | Suspect mapping / provider limitation - needs manual review |
| B081THWMDK | partial | Unrelated | -19.1% | Yes / FBM | Suspect mapping / provider limitation - needs manual review |
| B085F1QCB9 | skipped_cap | Unrelated | n/a | No (Amazon-shipped, non-Prime badge) / Unknown | Skipped - request/credit cap reached before this ASIN; no comparison possible. |

Reviews: Easyparser OFFER does not supply review counts; reviews_live is Unknown for every row. Provider does not supply bsr.

No ASIN in this run is purchase-authorized by this comparison alone.
