# ADDENDUM — post-audit reconciliation (2026-10-09)

**Purpose:** correct the audit record for what changed *after* the audit closed. This addendum supersedes conflicting statements in the primary artifacts.

**Audit baseline:** `2482048` (branch `feature/creative-social-local`)
**HEAD at addendum:** `d67e83a` (branch `feature/product-designer-studio`)

## 1. Commits that landed after the audit closed

```
d67e83a feat(studio): ListingForge, SocialPulse and AdPilot gain real creative capability
000df81 design studio: research, design inventory, and concept renders
6bfafcb feat(studio): Design Studio — one room for ads, social, A+ content, image and clip requests
f232ef8 feat(studio): Product Designer service — local scene designer, real 3D packaging view, mockups, provider-gated generation queue
```
**54 files changed, +12,639 / −822**, including a new `docs/design_studio_deep_research_20261008/` tree (research, workflow and seller-pain-point analysis, mockups, a 1,304-line `render_mockups.py`, a 514-line `svgkit.py`) and 3 rewritten room pages.

## 2. P0 findings — UNCHANGED AND STILL OPEN (verified at `d67e83a`)

| ID | Re-verified at HEAD | Evidence |
|---|---|---|
| **P0-01** | `Northstar_backend/.env` still has `SCANNER_LIVE_ALLOWED=1`; `live_gate.py`, `amazon_search.py` untouched | grep at HEAD |
| **P0-02** | `northstar-os-ui/src/foundation/api.js` untouched (still `/foundation/reasoning/*`) | `git diff 2482048..HEAD -- .../foundation/api.js` = empty |
| **P0-03** | `Dockerfile.api` CMD still `uvicorn foundation.app:app`; `docker-compose.yml`, `Caddyfile` untouched | grep at HEAD |
| **P0-04** | `main.py:1035/1046/1059` still declare `/api/autothink/{models,run,history}` with no `Depends` | grep at HEAD |
| **P0-05** | Three more commits landed; the repo was still being written to | reflog |

**Conclusion: the P0 set is valid and none of it has been remediated.**

## 3. P2 findings now STALE (the studio commits fixed them)

| Original finding | Original citation | Status at HEAD |
|---|---|---|
| P2-03 AdPilot "Bulk Actions" had no `onClick` | `AdPilot.jsx:149` | **FIXED** — now `AdPilot.jsx:288`, an `onClick` that toasts an honest boundary ("nothing is sent to an ad platform") |
| P2-02 SocialPulse "New Campaign" was broken (missing setter) | `SocialPulse.jsx:136,347` | **FIXED** — now `SocialPulse.jsx:403`, an `onClick` that toasts an honest "(sample) - no channel is connected" |
| ListingForge 5 dead buttons | `ListingForge.jsx:249,250,312,345,366` | **FIXED** — now wired to `saveRevision` (`:425`, `:457`), `restoreRevision` (`:608`), template apply (`:528`) |
| AdPilot/ListingForge/SocialPulse classified `STUB_MOCK` | `SERVICE_INVENTORY.csv` S08/S09/S10 | **SUPERSEDED** — all three gained real capability (`+169/−5`, `+406/−167`, `+235/−42`). Their implementation status must be re-assessed before remediation. |

**Action required:** re-audit these three rooms before acting on any P2 item that touches them. Do not "fix" controls that already have handlers.

## 4. New scope that did not exist at audit time

- **Product Designer Studio** (`f232ef8`) — already flagged unaudited (P2-01).
- **Design Studio** (`6bfafcb`) — a *second* studio surface: ads, social, A+ content, image and clip requests. **Not in `SERVICE_INVENTORY.csv` at all.**
- **`research/design_studio_deep_research_20261008/`** — a 26-file research tree (corrected path: `research/`, not `docs/`): `MASTER_BLUEPRINT.md` (197), `SEO_AD_LOOP.md` (452), `WORKFLOWS.md` (778), `SELLER_PAIN_POINTS.md` (403), `OPPORTUNITIES.md` (241), `SOURCES.csv` (225), `RULES.md` (104), `SYNTHESIS_NOTES.md` (114), `COMPETITOR_MATRIX.csv`, `PHASE1_COMPETITOR_MATRIX.csv`, plus 10 SVG mockups, `render_mockups.py` (1,304) and `svgkit.py` (514).

**Action required:** add Design Studio and this research tree to `SERVICE_INVENTORY.csv`, and audit them.

### Correction to this addendum (2026-10-09, after writing it)
My first draft of this section said two things that verification disproved. Both are corrected here so the record is right:
1. I wrote that the research tree was at `docs/design_studio_deep_research_20261008/`. **It is at `research/design_studio_deep_research_20261008/`** — verified with `git ls-files` and a disk check.
2. I wrote that `App.jsx` gained 2 route lines for Design Studio. **It did not.** The 2 lines are the `import` and `<Route path="/product-designer">` for the already-audited **Product Designer** (from `f232ef8`). There is **no `DesignStudio.jsx` page and no `/design-studio` route at HEAD (`d67e83a`)** — only `ProductDesigner.jsx` and `/product-designer`.

**Consequence for the backlog:** "Design Studio" exists only as a *research tree and three rewritten room pages* (ListingForge, SocialPulse, AdPilot), not as a distinct routed room. Its service status is therefore **UNDECIDED-IN-IMPLEMENTATION** rather than MISSING, and it still needs an entry in `SERVICE_INVENTORY.csv`. This is exactly the spec-vs-disk reconciliation the audit protocol requires, caught only because I checked my own claim before reporting it.

## 5. Net effect on the backlog

- **Valid and unremediated:** all 5 P0, all 22 P1, and 19 of 22 P2.
- **Stale (3):** P2-02, P2-03, and the ListingForge subset of `CREATIVE_COMPLETENESS.md` §C.2.
- **Not yet inventoried:** Design Studio, and the design-studio research tree.

**The readiness verdicts do not change:** Gate 1 = NOT READY, Gate 2 = NOT TESTED. The remediation is *more* urgent, not less, because the concurrent workstream is now producing features faster than the backlog is being closed.
