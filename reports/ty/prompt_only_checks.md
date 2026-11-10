# Prompt-only: which check actually failed

12 briefs, 0 passed, mean **34.5**. A mean of 34.5 could be one broken rule or twelve; this is the breakdown.

| check | failed in | of briefs | skipped | most common reason |
|---|---|---|---|---|
| `dimensions` | **12** | 12 | 0 | 768x768 |
| `aspect` | **2** | 12 | 0 | aspect 1.0000 |
| `background` | **8** | 12 | 4 | corners [(216, 216, 220), (198, 197, 198), (203, 204, 201), (194, 193, |
| `subject_fill` | **8** | 12 | 0 | subject fill 90.5% |
| `alpha_matte` | **8** | 12 | 4 | border mean 199.3 (>= 249), std 25.11 (<= 6.0) |
| `text_free` | **1** | 12 | 3 | margin ink 2.27% |
| `reference_subject` | **0** | 12 | 12 |  |
| `product_region` | **0** | 12 | 12 |  |

## Per brief

| brief | score | failed checks |
|---|---|---|
| PO-001 | 50.0 | dimensions, background, alpha_matte |
| PO-002 | 27.3 | dimensions, subject_fill |
| PO-003 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-004 | 15.0 | dimensions, background, subject_fill, alpha_matte, text_free |
| PO-005 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-006 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-007 | 28.6 | dimensions, aspect, subject_fill |
| PO-008 | 45.5 | dimensions, aspect |
| PO-009 | 50.0 | dimensions, background, alpha_matte |
| PO-010 | 27.3 | dimensions, subject_fill |
| PO-011 | 30.0 | dimensions, background, subject_fill, alpha_matte |
| PO-012 | 50.0 | dimensions, background, alpha_matte |
