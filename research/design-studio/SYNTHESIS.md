# SYNTHESIS ? Northstar Design Studio Research

Max 3 pages. Pulled at 2026-10-10. Corpus: 149 vetted sources in `sources.db`,
10 competitor files, 6 track files. Targets vs actual are in coverage-report.md.

## Top findings

**1. Amazon documents the rules but owns no production surface.**
Amazon's own docs specify every dimension, format, colour space, DPI and file
cap we need, and document that a non-compliant main image gets the listing
SUPPRESSED FROM SEARCH AND BROWSE. Amazon's creative tools (A+ Content Manager,
Store builder, Sponsored Brands video builder) are administrative form
interfaces ? no canvas, no layers, no spec check. **The gap between "Amazon
tells you the rules" and "Amazon helps you make a compliant asset" is the entire
opportunity, and it is closed by deterministic code, not by a model.**

**2. Nobody validates before you spend a credit.**
Every competitor validates after production or never. Claid markets a fidelity
vocabulary (label preservation, packaging consistency, seam accuracy, fine
detail retention, physically coherent scenes) but it is a marketing list, not a
verdict. Photoroom and Pebblely show you the result. **Inverting this ? run the
compliance check first, spend the generation credit second ? is cheap, free, and
no competitor does it.**

**3. The keyword?creative link is open.**
Helium 10's Listing Builder is the closest implementation: 5 product images, a
competitor ASIN for tone inference, brand voice applied across the listing, and
keywords pushed to the live listing. It produces TEXT and stops. No creative tool
in this corpus accepts a keyword cluster as input. Northstar already holds the
keyword, product and search-term data ? including an empty
`search_query_performance` schema built for exactly this.

**4. "Canva Magic Studio" no longer exists.**
Canva retired the Magic Studio brand; canva.com/magic-studio 404s. The
replacement is Canva AI 2.0 (April 2026), a conversational design partner.
Magic Switch is gone as a name; Magic Design has no pricing row. **Anyone
benchmarking "Magic Studio" in 2026 is benchmarking a retired product.**

**5. Packify is Pacdora, not a separate competitor.**
Packify is the AI-native packaging brand BY Pacdora. The directive warned this
might be a different tool; it is not. Treating them as two competitors would
have produced a false matrix.

**6. "PicoPilot" is unresolved and should not be guessed.**
Three distinct entities share the name: PicCopilot (e-commerce AI content),
PICopilot (an LLM agentic framework for PIC scripting, arxiv 2608.01791), and a
thin Tracxn record for pic-copilot.online. PicCopilot also carries a "Service
Closure Notice". No deep-dive was written rather than invent features for the
wrong tool.

**7. Credit opacity is the #1 complaint class in the paid-creative market.**
Creatify's G2 cons with counted mentions: Credit Limitations (76), Credit Issues
(76), Expensive (71), Needs Improvement (68), Insufficient Credits (65) ? the
top four are all about credits. Canva's cons: Limited Features (585), Limited
Options (560), Missing Features (498), Expensive (473), Limited Customization
(451). **Northstar's local ComfyUI generation has no credit meter at all, which
is a structural advantage the UI must make visible.**

**8. Amazon's own measurement tool is under-exploited.**
Manage Your Experiments A/B tests title, main images, bullets, description, A+
Content and Brand Story, requires the exact same ASIN set for both versions,
concludes at 66% significance, and reports sales/conversion with the probability
the winner is better. No competitor connects production to it. **This is the
only defensible way to claim creative impact ? Amazon measures, we record.**

**9. The honesty gap is real and specific.**
A vendor guide states plainly that "Amazon has not published documentation
specifying exactly which image signals influence recommendation outcomes". Two
vendors publish irreconcilable overlap numbers (22% vs 63.9% non-overlap).
Amazon's own Store guidance discourages embedded image text for external search
and screen readers while vendors claim an internal AI reads it. **Any claim
about image text improving rank is folklore on both sides.**

**10. Adobe's legal position is the real product, not quality.**
Firefly's indemnification requires teams/enterprise AND a specific plan, excludes
beta outputs, and Custom Models need a second licence, are internal-use-only,
and must be retrained if Adobe's foundational models change. **Legal safety
alone does not stop a listing suppression.**

## Best of each competitor

| Take | From | Why |
|---|---|---|
| Format-aware safe-zone overlays | Adobe Express | The exact primitive Amazon's crop rules need |
| Resize to many formats in one file | Adobe Express / Canva Magic Resize | With a spec registry behind it, not just scaling |
| Master-then-data bulk creation (150 fields) | Canva Bulk Create | Correct order for bulk variation sets |
| Structure chosen before artwork | Pacdora | Enforces product fidelity by construction |
| Pre-flight that blocks, not review that catches | Canva Brand Controls | Translate to compliance blocking export |
| One AI workspace with a tool rail | Adobe Firefly Image Editor | Avoids "one-and-done" mode fragmentation |
| Auto-layout + components/variants + variables | Figma | The data model for one-master-many-sizes |
| Role-determined surfaces over one file | Figma seat types | Author vs review vs export-manifest |
| Zero-click onboarding | Holo (URL) | Northstar's version: ASIN or keyword cluster, visible and correctable |
| Prompt-first single image | Pebblely / Flair | For the hero shot |
| Operation-first batch (250/run) | Photoroom | For catalogue-scale main images |
| URL-to-video in ~60s + batch 10+ | Creatify | The benchmark for Video & UGC |
| Brand DNA inference | Holo / Helium 10 | But with inspect-and-correct, which they lack |
| Export render + dieline from one brief | Pacdora | For packaging, the only one who does it |
| Dieline-to-3D folding from SVG/DXF | Pacdora | Free, deterministic, no 3D software |

## Biggest gaps (the lane Northstar should own)

1. Pre-flight Amazon compliance before generation ? nobody.
2. Product-fidelity as an enforced contract ? nobody.
3. Keyword cluster ? creative brief ? Helium 10 does keywords ? text only.
4. Ad search term ? hook ? nobody.
5. Manage Your Experiments linkage ? nobody.
6. Local, free, unlimited generation ? nobody.
7. Per-asset provenance in a queryable store ? nobody.
8. Brand memory with confidence, provenance and unlearn ? nobody.
9. AI-people disclosure automation ? Amazon documents it; nobody automates it.
10. One product record ? packaging + mockup + 3D + listing images ? Pacdora does packaging only.

## What we already have vs what we need

**Have:** 173 live product rows + 1024 total in `products`; `keywords` (10);
`keyword_performance` (4); `campaigns` (4); `memory_entries` (23); `live_pulls`
(3 real chocodata pulls, 2026-09-23); an empty `search_query_performance`
schema; local ComfyUI running; a 5070/5080-class 16 GB GPU; a new
`ds_projects`/`ds_assets`/`ds_jobs` store with `source_record_id`,
`source_record_type`, `pulled_at` and a JSON `metadata` column; the existing
studio engine (doc, scene, mockups, three.js, compliance, presets, loop);
`check-jsx-imports.py`; an operator harness that verified 21/21 rail
destinations.

**Need:** search-term-report ingestion (schema exists, 0 rows); review data;
a spec registry; a compliance checker; a ComfyUI workflow set for the four
generation modes; brand-fact ingestion into `memory_entries`; MYE outcome
recording; a manual/ad-library competitor collection (ToS-safe path only).

## Recommended content-type list for the Design Studio

Ordered by seller value and buildability. Each gets a purpose-built workspace:

1. **Listing Images** ? main image (compliance-checked, deterministic white
   background), infographic/A+ modules, lifestyle scene. Highest value because a
   non-compliant main image suppresses the listing.
2. **A+ / Brand Story** ? modules at documented sizes, alt text authored for
   screen readers, uniqueness enforced.
3. **Ads** ? Sponsored Brands video (horizontal AND 9:16 vertical), custom
   images, DSP display presets. Highest-value priced output.
4. **Video & UGC Clips** ? local generation, hook-first from search terms.
   Marginal on 16 GB; scope carefully.
5. **Storefront** ? hero with crop safe zone, four tile sizes, link-title
   obscuration overlay.
6. **Social** ? reuse the listing/master canvas; Attribution measurement if
   authorised.
7. **Packaging & Mockups** ? Pacdora-style structure-first, marketing-only
   (never Brand Registry proof).
8. **3D Product Scene** ? already built locally.

## Open questions for the operator
1. "PicoPilot" ? which entity did you mean?
2. Author A+ alt text, given the unverified claim Amazon is removing it?
3. LoRA per brand or IP-Adapter conditioning?
4. Authorise the manual + Meta Top Ads Library competitor-scan path?
5. Non-US marketplaces in scope?
