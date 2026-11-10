# Prompt-only: which check actually failed

12 briefs, 9 passed, mean **86.4**. A mean of 34.5 could be one broken rule or twelve; this is the breakdown.

| check | failed in | of briefs | skipped | most common reason |
|---|---|---|---|---|
| `background` | **1** | 12 | 4 | corners [(255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, |
| `subject_fill` | **2** | 12 | 0 | subject fill 91.4% |
| `alpha_matte` | **7** | 12 | 4 | border mean 252.1 (>= 249), std 7.19 (<= 6.0) |
| `text_free` | **0** | 12 | 3 |  |
| `reference_subject` | **0** | 12 | 12 |  |
| `product_region` | **0** | 12 | 12 |  |

## Per brief

| brief | score | failed checks |
|---|---|---|
| PO-001 | 90.0 | alpha_matte |
| PO-002 | 63.6 | subject_fill |
| PO-003 | 90.0 | alpha_matte |
| PO-004 | 90.0 | alpha_matte |
| PO-005 | 70.0 | background, alpha_matte |
| PO-006 | 90.0 | alpha_matte |
| PO-007 | 100.0 | — |
| PO-008 | 100.0 | — |
| PO-009 | 100.0 | — |
| PO-010 | 63.6 | subject_fill |
| PO-011 | 90.0 | alpha_matte |
| PO-012 | 90.0 | alpha_matte |
