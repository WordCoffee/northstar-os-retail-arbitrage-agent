# OPERATOR DECISIONS — RESOLVED 2026-10-24
Recorded against `northstar-simple-mode-fix-plan.md` (A2, C1–C3) and the two
mode plans (01 simple, 02 autothink). Authority: operator delegation in session
2026-10-24 ("you know what I want — I let you choose") for A2/C1/C2; Costco is
an explicit operator directive.

## A2 — Canvas composition → KEEP LIGHTENED CELESTIAL (decided)
Ship the lightened celestial theme (commits 433b3661/561dffd7/2e67213b/487f04b2)
with composition law from the celestial pack: hero body anchored in a gutter no
panel covers, gutter luminance floor ≥5% measured in the capture harness, reading
column untouched (95.5% panel). The alternative (brighter hero band behind the
chat) is REJECTED: it re-creates the exact failure the V4.2 rebuild fixed —
bright art bleeding through the reading surface. One capture A/B still runs so
the decision is evidenced, not just stated.

## C1 — Voice → HONEST DICTATION NOW (decided)
Mic affordance becomes "Dictate" with a tooltip stating the real pipeline
(record → transcribe → answer → optional spoken reply). Zero "voice chat"
strings in Simple Mode source (grep gate). Streaming voice is a named-budget
feature, deferred — never quietly implied by the UI.

## C2 — Standalone AutothinK UI → REDIRECT + DEPRECATE (decided)
:8100 serves a 302 to `http://127.0.0.1:8101/ui/autothink`; launchers drop the
:8100 default; `autothink/launch.*` documented as legacy. One AutothinK surface
(the React focus/workbench), one theme family. No duplicate maintenance.

## C3 — Costco enrichment files → KEEP + FINISH (operator directive)
Operator: "we really need to keep those — they should be integrated into our
product finder… product cost, product names, that data."
Action now: implement the missing symbols in `brightdata_costco_enrichment.py`
(`build_enrichment_manifest`, `is_costco_product_url`, plus any other call-site
references in the four test files) so the canonical runner returns to green.
This is an ADAPTER-COMPLETION task. Full Product Finder integration (the data
housing the operator describes) is a later workstream. Nothing is deleted.
