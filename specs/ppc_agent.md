# Spec — PPC Analyst

**REBUILT.** Amazon bulk-file schema is **UNVERIFIED** (not checked against a live export this
pass). The agent's job is to be *safe*: reject a bad upload rather than guess.

## 1. Contract

Report-in, file-out. There is **no Amazon API call** anywhere in this agent — the operator uploads
reports and takes a change plan back.

## 2. Inputs

| Report | Required columns |
|---|---|
| search term | campaign, ad group, customer search term, impressions, clicks, spend, sales, orders |
| targeting (optional) | campaign, ad group, targeting, match type, + metrics |
| placement (optional) | campaign, placement, + metrics |

Column matching is case-insensitive and whitespace-trimmed, because real exports differ.

## 3. Workflow

```
validate_report(kind)     → reject the WRONG report (missing columns named in the error)
analyze(rows, target_acos)
  harvest:   orders ≥ 1 AND acos ≤ target   → propose exact-match keyword
  negatives: orders = 0 AND clicks ≥ 8      → propose negative exact
validate_change_rows(rows, source)
  every campaign / ad group must exist in the source report
  operation ∈ {create, update, archive}
  bid / budget numeric and non-negative
```

## 4. Why the validators matter

A bulk row referencing a campaign that does not exist can pause or corrupt a live campaign when
uploaded. The blueprint asks for exactly this guard, and it is the reason the agent refuses rather
than "repairs" an input.

## 5. Edge cases

| Case | Behaviour |
|---|---|
| targeting report uploaded as search term | rejected, expected columns listed |
| missing `customer search term` | rejected |
| change on campaign `Z` absent from source | rejected, problem named per row |
| empty report | rejected |
| zero-sales row with few clicks | neither harvested nor negated (insufficient evidence) |

## 6. Known limits

- No bulk-file writer yet: the agent returns validated change rows and a change log, not a
  ready-to-upload `.xlsx`. That is the next increment and must be validated against Amazon's
  current bulk template.
- No placement or bid-adjustment math beyond validation.
- The 8-click negative threshold is a starting heuristic, not a proven optimum.

## 7. Northstar improvement

Every proposal carries the **source row** it came from, so the operator can audit a change back to
the exact line of the report. That traceability is the differentiator over a black-box optimiser.
