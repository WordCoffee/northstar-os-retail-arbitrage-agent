# Prompt-only: which check actually failed

12 briefs, 0 passed, mean **41.5**. A mean of 34.5 could be one broken rule or twelve; this is the breakdown.

| check | failed in | of briefs | skipped | most common reason |
|---|---|---|---|---|
| `dimensions` | **12** | 12 | 0 | 768x768 |
| `aspect` | **2** | 12 | 0 | aspect 1.0000 |
| `background` | **8** | 12 | 4 | corners [(187, 187, 189), (119, 118, 118), (203, 202, 204), (176, 176, |
| `subject_fill` | **5** | 12 | 0 | subject fill 94.3% |
| `alpha_matte` | **8** | 12 | 4 | border mean 171.4 (>= 249), std 29.84 (<= 6.0) |
| `text_free` | **1** | 12 | 3 | margin ink 2.65% |
| `reference_subject` | **0** | 12 | 12 |  |
| `product_region` | **0** | 12 | 12 |  |

## Per brief

| brief | score | failed checks |
|---|---|---|
| PO-001 | 50.0 | dimensions, background, alpha_matte |
| PO-002 | 63.6 | dimensions |
| PO-003 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-004 | 50.0 | dimensions, background, alpha_matte |
| PO-005 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-006 | 15.0 | dimensions, background, subject_fill, alpha_matte, text_free |
| PO-007 | 57.1 | dimensions, aspect |
| PO-008 | 45.5 | dimensions, aspect |
| PO-009 | 50.0 | dimensions, background, alpha_matte |
| PO-010 | 27.3 | dimensions, subject_fill |
| PO-011 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-012 | 50.0 | dimensions, background, alpha_matte |
