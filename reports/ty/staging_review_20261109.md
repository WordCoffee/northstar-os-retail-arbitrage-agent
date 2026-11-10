# Staging review — 20261109

`staging` is 1218 commit(s) ahead of `main` and the bundle contains visual or creative work, so it is refused by name and shown here instead.

- source `staging` @ `3f002e0c71a6ca89053b0a7d0b00d448b69fbc5a`
- target `main` @ `82097ac1821743306e22c2340825d1e36b97b1d9`

## Gates

| gate | result | evidence |
|---|---|---|
| suite | PASS | summary: 7329 passed, 117 skipped, 2 xfailed, 17 warning, 125 subtests run written 2026-11-09T18:09:25, newest staging commit 2026-11-09T17:51:46 |
| verifier | PASS | d15_verification.md: 20 agree, 0 FAILED, 1 BLOCKED reproduced by: not recorded (--verifier not given) |
| bundle | FAIL | bundle main..staging: 1218 commit(s), 10532 changed path(s) visual/creative paths: 271 |

Refused by: `bundle`

## Before / after

585 image(s) changed in the bundle. Composited digests come first, then dogfood/audit shots, then screenshots, newest first (24 of 585):

| after (this bundle) | before (on `main`) |
|---|---|
| `reports/audit_20261024/screenshots/desktop_home.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_home.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/desktop_home_crop.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_home_crop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/desktop_theme_v1.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_theme_v1.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/desktop_theme_v1_crop.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_theme_v1_crop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/desktop_theme_v2.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_theme_v2.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/desktop_theme_v3.png`<br>![after](../../reports/audit_20261024/screenshots/desktop_theme_v3.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/live_desktop.png`<br>![after](../../reports/audit_20261024/screenshots/live_desktop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_account.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_account.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_account_crop.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_account_crop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_home.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_home.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_home_after.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_home_after.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_home_after_crop.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_home_after_crop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_home_crop.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_home_crop.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_theme_v1.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_theme_v1.png) | _absent on main_ |
| `reports/audit_20261024/screenshots/mobile_theme_v2.png`<br>![after](../../reports/audit_20261024/screenshots/mobile_theme_v2.png) | _absent on main_ |
| `t2-13-preview.png`<br>![after](../../t2-13-preview.png) | _absent on main_ |
| `screenshots/t2_placement_fix_20261028/t2-clean-preview.png`<br>![after](../../screenshots/t2_placement_fix_20261028/t2-clean-preview.png) | _absent on main_ |
| `screenshots/mogra_t1_20261028/t1-12-preview-lightbox.png`<br>![after](../../screenshots/mogra_t1_20261028/t1-12-preview-lightbox.png) | _absent on main_ |
| `reports/ui_audit_20261016/account.png`<br>![after](../../reports/ui_audit_20261016/account.png) | _absent on main_ |
| `reports/ui_audit_20261016/adpilot.png`<br>![after](../../reports/ui_audit_20261016/adpilot.png) | _absent on main_ |
| `reports/ui_audit_20261016/autothink.png`<br>![after](../../reports/ui_audit_20261016/autothink.png) | _absent on main_ |
| `reports/ui_audit_20261016/command-center.png`<br>![after](../../reports/ui_audit_20261016/command-center.png) | _absent on main_ |
| `reports/ui_audit_20261016/commerce-ops.png`<br>![after](../../reports/ui_audit_20261016/commerce-ops.png) | _absent on main_ |
| `reports/ui_audit_20261016/competitor-monitor.png`<br>![after](../../reports/ui_audit_20261016/competitor-monitor.png) | _absent on main_ |

## Scorecard deltas

`ty/scorecards.json` is **absent on `main`** — every score here is new.

after: 29 services, at_bar **2** (hub, prospector), test_ids 7186

| service | score | at bar |
|---|---|---|
| hub | 100 | yes |
| prospector | 100 | yes |
| ledger | 86.2 | no |
| auctioneer | 86.2 | no |
| autothink | 86.2 | no |
| thewatch | 86.2 | no |
| rankledger | 86.2 | no |
| rivalboard | 86.2 | no |
| account | 86.2 | no |
| foundation | 86.2 | no |
| jobs | 86.2 | no |
| keywords | 86.2 | no |
| keyword-tracker | 86.2 | no |
| profitability | 86.2 | no |
| design-studio | 85.2 | no |
| goldengoose | 77 | no |
| golden-goose | 77 | no |
| listings | 77 | no |
| beta | 74.7 | no |
| beta-signup | 74.7 | no |
| competitor-monitor | 74.7 | no |
| beta-ops | 74.7 | no |
| offerchisel | 67 | no |
| socialpulse | 67 | no |
| product-finder | 65 | no |
| listingforge | 65 | no |
| beta-support | 63.2 | no |
| adpilot | 55 | no |
| towncrier | 55 | no |

## Merged job list (1218 commits)

| sha | date | job |
|---|---|---|
| `3f002e0c` | 2026-11-09 | defects D-006/D-007: the JSX checker read comments as code, and the contract test depended on another module's cache |
| `1e4c63d0` | 2026-11-09 | fix the two suite failures: the JSX checker no longer reads component names out of comments (it flagged a comment about an outlet), and the contract test seeds its own scanner cache instead of depending on another module having left candidates there |
| `b372544f` | 2026-11-09 | defects D-005: the suite was order-dependent in both directions, the two wrong fixes are recorded with their failure counts, and product_analysis stays byte-identical to its protected baseline |
| `defaf1dd` | 2026-11-09 | merge ux-07: workspace tabs keep state across switching and publish a tab summary to the shell |
| `d8fb4584` | 2026-11-09 | env isolation narrowed to the ten variables that actually leak, and the two modules that need them now declare them; product_analysis remains byte-identical to its protected baseline (the fallback change was reverted, not baselined) |
| `693fdd24` | 2026-11-09 | ux-07: workspace tab bar keeps each open service mounted, and publishes the open tab to Bojo |
| `4d2437cb` | 2026-11-09 | queue sel-07 (the sidecar does not say which layout made the picture) and today's state block |
| `0e2ba856` | 2026-11-09 | env isolation is per module over every name, not just the path vars: a module keeps what it set at import, a test body is undone, another module's leftover is dropped. Plus the product_analysis fallback no longer discards a fresh result over a stale LAST_SEARCH_ERROR (targeted: 167 + 37) |
| `925d34cc` | 2026-11-09 | report: the deterministic infographic and packaging stages, the Lion's Mane result (2 of 4 at 100, 2 failing only on OCR of one source), and the three scorer/generator defects they exposed |
| `c4fc7bef` | 2026-11-09 | inset the infographic's accent rule so the page corners stay at the background level; the fill measure samples the corners and a full-bleed bar read as 99% subject |
| `ad92b6fc` | 2026-11-09 | the infographic page meets the brief's background level, so subject_fill measures the panel and the copy instead of counting an off-white page as 100% subject |
| `570053d2` | 2026-11-09 | convert between the record's (left,top,right,bottom) box and the layout's (x,y,w,h) in one place; assert the quad sits inside the box so the convention cannot drift again |
| `f03bf668` | 2026-11-09 | fix the infographic's product-box mapping: scale from the crop that was actually pasted, not the pre-clamp crop |
| `77ac6363` | 2026-11-09 | deterministic infographic is a page: a 70% photo panel with copy in the margins, callouts pointing in from outside so no product pixel is overdrawn, and a fill cap for wide packaging panels; the region check compares the subject's aspect and the trimmed cutout in the quad path |
| `04475aa3` | 2026-11-09 | merge ux-06: shell chrome on every authed route (TopNav + rail + outlet, DevBanner in the shell), 72-entry route table preserved |
| `6a17ce2f` | 2026-11-09 | deterministic layouts honour the brief's aspect (extend by mirroring, never crop), reinforce the margin copy so text_expected is satisfied, and scale the product quad with the upscale so the quad check compares the right area (16 tests) |
| `1b604a6c` | 2026-11-09 | digest: a deterministic-layout section, source next to output, with the situation and the score on each row |
| `ad86d8b3` | 2026-11-09 | feat(shell): mount TopNav, side nav and workspace outlet on every service route |
| `edc7fe42` | 2026-11-09 | fix the packaging path in the generator: numpy and BytesIO were missing so the quad identity crashed; a generator-level test now runs the quad path without a GPU |
| `f36dfd78` | 2026-11-09 | deterministic layout stages: infographic copy and packaging panel warp, with a quad-aware product-region check so a warped panel is compared against its own artwork (12 tests); per-mode table with the stored-reference-only label rule (15 tests) |
| `6ae869b8` | 2026-11-09 | held-out final: 16 of 21 pass, mean 90.0 on 8 verified product images; verifier agrees and names both superseded runs (13/86.2, 16/92.0) |
| `cbce8d0b` | 2026-11-09 | held-out report states the design-vs-file distinction it used to leave implicit: three Mogra images are one pouch pair, the Word Coffee images are two box designs |
| `8fbb067e` | 2026-11-09 | defects D-003: the second half - a card on a mirror and a byte-duplicate, found by opening the files |
| `65fe3da9` | 2026-11-09 | held-out pool is a reviewed roster: the mirror shot was a card, one file was a byte copy, so 8 verified photographs of real products over 21 briefs; hashes must differ (12 tests) |
| `27e84f3e` | 2026-11-09 | defects: D-004 records the stale GPU lock and the reclaim rule |
| `e01b8491` | 2026-11-09 | gpu lock: a holder that is provably gone is reclaimed and the reclaim is recorded, so a killed render no longer wedges the lane (6 tests); D-003 records the quote-card reference pool |
| `1692871f` | 2026-11-09 | held-out references are product images only: the pool had a dozen quote cards and a wordmark, which is how a card composite reached the digest; now 10 real products, no product tested twice in one situation |
| `95eb40db` | 2026-11-09 | state: a dated director block so the load-first file carries today's held-out set, defects and owner asks |
| `a1734aa6` | 2026-11-09 | merge F0: FoundationDB removes a temp database it created (9,018 had leaked into %TEMP%) |
| `7a15d5fe` | 2026-11-09 | needs you: DIR-9 asks for more Lion's Mane photographs, the one thing limiting the held-out set to 14 distinct products |
| `b1582d48` | 2026-11-09 | held-out references: eleven distinct Word Coffee photographs instead of three photos plus a wordmark, so the 21 briefs are 14 products rather than 7; two tests pin it |
| `e3fd0035` | 2026-11-09 | digest: six held-out pairs, one per distinct product, product region read from the proof's own check instead of reported as 'not audited' |
| `16fc82e3` | 2026-11-09 | verifier task: check the bar as well as the score, so a repeat of D-002 is a DISAGREE and not a number to explain away |
| `971624d7` | 2026-11-09 | defects: D-002 records that the first held-out run applied one brief's constraints to all eight situations, and why the corrected bar will score lower |
| `a45cee7d` | 2026-11-09 | held-out briefs inherit the tuned constraint profile per situation: the first run reused one brief's constraints and put a white matte on lifestyle/infographic, failing alpha_matte on 21 of 21 (2 tests pin it) |
| `edb7d341` | 2026-11-09 | digest: composites section is no longer Mogra-only, held-out pairs come first so the six side-by-side rows are the held-out evidence, and each row says which set it is |
| `f9d58598` | 2026-11-09 | fix the 2 candidate-suite failures: the region check measures both readings of a placement box (canvas or trimmed subject) and reports which, and conftest restores the path env vars to their session baseline so the contract test stops depending on test order |
| `3718763d` | 2026-11-09 | fix F0: a FoundationDB that creates its own temp file now removes it on close and at exit; a supplied path is never touched (5 tests) |
| `02d9a674` | 2026-11-09 | OmniParser runner: 7 tests on the parts that decide a hit (normalisation against grounding.hit's 1280x800 frame, label matching, refusal, the 71.7% adoption bar); defects.md D-001 filed for the 9,018 leaked temp DBs and queued |
| `bbba7fef` | 2026-11-09 | held-out composite pass is resumable: chunks of briefs without a verdict, merged proof, and it can never overwrite the tuned three-brief proof (6 tests) |
| `fc2ef0ba` | 2026-11-09 | held-out set: 21 runnable briefs validated by the same validator (text rules, unique pairs, real references), 3 Neck Nirvana briefs declared unscorable, its own proof file, 7 tests; DIR-8 filed for the missing photograph |
| `aca1de1b` | 2026-11-09 | UI-TARS: two load attempts recorded, both killed at shard load (3.0 and 5.72 GB free); baseline stands |
| `4fd78431` | 2026-11-09 | benchmarks: OmniParser-class runner (YOLO under the GRANT + Florence-2 captioner), held-out splitter |
| `7d83b9b8` | 2026-11-09 | fix the 7 candidate-suite failures: placement is authoritative again (no trim, no fallback), route count 58->72 after ux-05, region detail assertion on evidence not geometry |
| `41876ecb` | 2026-11-09 | sel-02 explained with the per-brief diff and the coverage caveat; held-out briefs across three lines; daily RAM minimum in the digest; reverse-study default policy |
| `e0361e8b` | 2026-11-09 | governor: a held PAUSE_BUILDERS marker, so the suite and the GPU benchmarks get a quiet machine |
| `6d177661` | 2026-11-09 | status table for items 1-5 in the requested verdict format; candidate tag recorded; suite running on it |
| `269fa43a` | 2026-11-09 | promote: pathspec batching for this git, review pack on a visual refusal even under --check |
| `4e853dd1` | 2026-11-09 | merge stage-slice: candidate freeze, slice classifier, per-service review packs |
| `de52dd96` | 2026-11-09 | merge sel-02: seller mean 22.1 -> 93.5, design-studio 75.9 -> 85.2 |
| `9657cd96` | 2026-11-09 | fix: roomAdapters used a JSX tag for an argument component (and then said so in a comment the scanner also read) |
| `595fc476` | 2026-11-09 | seller_scores: timestamp the published mean from the generated pass |
| `88706b14` | 2026-11-09 | design studio seller score: judge generated composites, not replayed files |
| `a410813d` | 2026-11-09 | digest: free RAM and the builder allowance, alongside disk |
| `c684e7c3` | 2026-11-09 | status update: UI-TARS blocked on RAM after a real attempt, hosted target proven live, FLUX 3 measured at 11.93 GB and still flaky, OmniParser grant recorded |
| `24a8fd65` | 2026-11-09 | GRANT: ultralytics dev-only for the OmniParser-class grounding benchmark (AGPL confined to the bench, never served); replace_later entries for ultralytics and OmniParser |
| `94be3157` | 2026-11-09 | merge ramgov: free-RAM governor gating builder claims and launcher starts |
| `0115d768` | 2026-11-09 | bake-off: hosted target proven live and byte-identical, accuracy-first verdict separates ground truth from cost; verifier AGREE |
| `f995a911` | 2026-11-09 | item5 slices: classify the bundle by unit, gate and promote one slice at a time, review packs with 5-10 images |
| `9c8fb445` | 2026-11-09 | verify: bake-off reproduction |
| `1994a936` | 2026-11-09 | ram governor: gate builder starts on measured free RAM |
| `433c5d87` | 2026-11-09 | items 1-5 status table: five sections, grounding benchmark parked on a licence decision with both licences verified |
| `f23e918d` | 2026-11-09 | items 1-5: V9-localhost verified, unlock watcher running, reboot proof, reproducible bake-off, FLUX diagnosis with unload fix, composites at 100, promotion pipeline refusing |
| `5d89b522` | 2026-11-09 | merge item3: reproducible D17 bake-off with tracked artefacts, six cells, craft-anything default |
| `e8a92d60` | 2026-11-09 | merge item5: promotion pipeline with three gates, refusing today's visual bundle and writing the review pack |
| `f7f8b8c8` | 2026-11-09 | item5: staging-to-main promotion gate with three named refusals, plus the visual review pack |
| `8391c845` | 2026-11-09 | research/bakeoff: reproducible D17 bake-off (Craft Anything v0.5.0 vs REA 6.5.0) |
| `31c887ec` | 2026-11-09 | merge item2: reboot proof, task settings verified, launcher runs the check on first start after boot |
| `0e89783c` | 2026-11-09 | item2: the reboot proof is measured after the boot, not argued before it |
| `f48655d3` | 2026-11-09 | handoff: contract dimension in the weights, 2 at bar, the complete-dimension correction |
| `0a528cc7` | 2026-11-09 | honesty fix: complete means a callable handler, not the tool's name appearing in the source (two services were scoring 100 without one) |
| `c3072c7a` | 2026-11-09 | merge contract-01: contract dimension across 29 services, ProductFinder calls its API |
| `359ee802` | 2026-11-09 | contract-01: prove 20 of 29 service contracts, wire ProductFinder to the finder API |
| `3aad18f2` | 2026-11-09 | schema: 'retired' is a lawful tool status, so retirement can be recorded rather than only coded |
| `1950e75f` | 2026-11-09 | merge reg-03: tools offered only with a handler; queue mirror regenerated from the store |
| `bce337f9` | 2026-11-09 | reg-03: offered means callable, retire or attach the 27 unclaimed tools, queue 7 handler jobs |
| `0d0241c7` | 2026-11-09 | status confirmed (sel-01c, ux-05 ahead of ux-06); one-command unlock checks for the live walk, V3 and V9 |
| `dd754074` | 2026-11-09 | registry: confidence per entry (high/medium/low/none), never downgraded by a blocked retry; digest shows it |
| `b89cbc3e` | 2026-11-09 | vision walk: fresh tab per route with one retry, and a confidence rating per entry (high/medium/low/none) |
| `a7622075` | 2026-11-08 | reg-01 report: registry coverage, evidence mix, tool holes, workspace layouts, 13 gaps |
| `0bc9b880` | 2026-11-08 | registry merged with live vision where it could be captured; digest shows registry coverage, layouts and tools |
| `6ec62f5a` | 2026-11-08 | merge reg-01: service registry as the single source of truth, tool list and Northstar workspaces generated from it |
| `6f8b822d` | 2026-11-08 | reg-01: service registry as the single source of truth |
| `56db6023` | 2026-11-08 | composites verified: cutout+sidecar saved, box order fixed, masked SSIM 0.9958/0.9931/0.9835; registry job queued ahead of the UX chain |
| `75b59b1c` | 2026-11-08 | merge sel-01d: white-canvas main images, GPU lane unload/reload, SwinIR upscaler, FLUX3 works at 1536 |
| `2ea4bcf6` | 2026-11-08 | sel-01d: flat-white main composites, GPU lane evidence, measured SwinIR upscaler, SDXL/FLUX3 1536 |
| `405e4146` | 2026-11-08 | sel-01e merged and applied: composite passes provisional, cannot_verify fails; OCR rebuilt on real crops (rapidocr 0.875/0.906, easyocr 0.359); VLM embedding 0.93-0.99 |
| `9312d7f1` | 2026-11-08 | merge sel-01e: cannot_verify fails, provisional composites, hard OCR eval, real VLM embeddings |
| `adc9978e` | 2026-11-08 | sel-01e: an unverifiable product region fails; hard OCR crops; real vision-description cosine |
| `dfbe465e` | 2026-11-08 | handoff: two in-flight builders, the provisional/fail rule, and the queue order |
| `a3a146a8` | 2026-11-08 | queue: cutout provenance is rank 1; ux-05 recorded as merged |
| `b62274f0` | 2026-11-08 | report: composite results, honest cannot-verify state of the region check, editor leaderboard |
| `4128dd77` | 2026-11-08 | composite outputs landed: 3 Mogra composites in the digest source-next-to-output; product-region check wired but cannot verify until the generator saves its cutout (sel-01c queued at rank 2) |
| `4f67ca43` | 2026-11-08 | merge sel-01b: composite pipeline with BiRefNet cutout, Mogra end-to-end; keep both ocr and editors roles |
| `c5205bef` | 2026-11-08 | sel-01b: composite the real product, generate only the scene |
| `2ef6131b` | 2026-11-08 | report and handoff: 2 services at bar, ux-05 cause recorded, composites section live in the digest |
| `835be24e` | 2026-11-08 | composite region check, OCR benchmark (rapidocr holds at 1.0), fidelity rule with counts, ux-09 canvas queued, digest shows source next to output; ux-05 merged (60 e2e passed) |
| `011b525c` | 2026-11-08 | merge ux-05: routes render their own page (SIMPLE_KEEP_ADVANCED allowlist was the cause) |
| `fdcc548d` | 2026-11-08 | fix(ui): service routes render their own page, not the Bojo shell (UX-05) |
| `e929ec8e` | 2026-11-08 | handoff and digest: eight ranked jobs, composite design, OCR+embedding check |
| `70b8cc84` | 2026-11-08 | sel-01b redesigned for compositing; reference check now OCR + embeddings (colour proxy is diagnostic); three real Mogra uploads; shell/tabs/scene queued behind ux-05 |
| `402a3354` | 2026-11-08 | handoff: sel-01 landed with its three stated limits, sel-01b ranked first |
| `fd1c04d4` | 2026-11-08 | sel-01 merged: 56 briefs across three modes, per-mode scoring, reference check; the queue is now rank-ordered rather than insertion-ordered |
| `4cbc099a` | 2026-11-08 | merge sel-01: seller briefs gain source_mode, reference check, per-mode summary |
| `a86c7b93` | 2026-11-08 | Seller-Tester: measure the three product-picture input modes |
| `20ccd103` | 2026-11-08 | handoff: queue ranking, the 3-of-29 render finding, D17 closed, baseline updated |
| `9e7cab0b` | 2026-11-08 | UX audit: 3 of 29 routes render; queue re-ranked to seller quality first with the render defect fifth; cleanup to 215 GB |
| `93682edc` | 2026-11-08 | D17 finished: Craft Anything 0.5.0 installed (checksum verified), all six cells ran, default on all three targets; BASELINE.json updated from the 7067 run |
| `22fd9069` | 2026-11-08 | V3/V9 first real run: 3 services do not render; three driver bugs found and fixed; describe_page added |
| `9052700e` | 2026-11-08 | queue: drop the duplicate seller bundle; dev stack stopped cleanly |
| `77a0c13b` | 2026-11-08 | full suite clean on d2c29a55: 7067 passed, 0 failed, 117 skipped; scorecard reads the complete id list |
| `d310cc82` | 2026-11-08 | full-suite tally: 7066 passed, 117 skipped, 1 test defect found and fixed |
| `d2c29a55` | 2026-11-08 | gpu_budget test: hermetic against a lease left on disk by an earlier run (the one full-suite failure) |
| `0d530d0e` | 2026-11-08 | queue: one seller bundle and three complete bundles, with the loop non-idle |
| `1e1339de` | 2026-11-08 | reports: final name comparison (+451, -1) and the seller-applicability refinement |
| `7fd881cc` | 2026-11-08 | Bojo tools wired into chat_tools (4 tools, tested through run_tool); seller dimension applies only to seller-facing services; gap bundles become actionable by file |
| `9e42db2e` | 2026-11-08 | merge gap-loop B: offer_recommendation + hub_status Bojo tools |
| `358e7980` | 2026-11-08 | Bojo tools: offer_recommendation (OfferChisel) and hub_status (Operations Hub) |
| `7bb54cae` | 2026-11-08 | merge gap-loop A: catalog_pull + golden_goose_scan Bojo tools |
| `f0618b48` | 2026-11-08 | Loop A report: sourcing tools, evidence, spec-vs-disk note |
| `9f256be8` | 2026-11-08 | D15 summary: record the stricter scorecard and the drop to 0 at bar |
| `5b81739b` | 2026-11-08 | Bojo sourcing tools: catalog_pull over live_catalog.get_or_pull, golden_goose_scan over the real scorer |
| `63b30341` | 2026-11-08 | Bojo tool registry: domain modules export TOOLS, the registry loads what exists and never raises |
| `fd84631c` | 2026-11-08 | parity: --backends so the UIA challenger can be named; two runs recorded with the lock-screen reason |
| `9807cfcd` | 2026-11-08 | handoff and full-suite name comparison: +400 names, -1 name that has no file |
| `f3dea8c6` | 2026-11-08 | batch report: Chrome version, the absent toggle, the UIA route, and the seller dimension |
| `cb9c15cb` | 2026-11-08 | dogfood test data: a page without a number is not a passing seller page |
| `0abf3944` | 2026-11-08 | V9 dogfood harness (refuses on a locked desktop), digest lists the verifier FAILED items, four Bojo tools declared |
| `d968eacd` | 2026-11-08 | Chrome via UIA (no CDP, no throwaway profile), seller-tester scores in the scorecard so artefacts alone cannot pass a service, DIR-4 replaced |
| `01f9a6fb` | 2026-11-08 | test fix: a mounted route is what makes a service measurable, and the slow-app test now mounts one |
| `28cc137b` | 2026-11-08 | D15 summary, handoff, digest, and four re-plan bundles queued so the loop cannot idle |
| `1b53c526` | 2026-11-08 | D17 re-probe: the earlier bake-off had no surviving artefacts; REA on the OSS target is the only reproducible cell. Digest counts a bare list correctly |
| `0438ab9c` | 2026-11-08 | D15: independent verification |
| `6d2fe4d6` | 2026-11-08 | D12/D13/D14: three gap bundles merged with measured score lift, live mode, computer mode; id list picks the newest measured run; docs/TY_ARCHITECTURE.md |
| `3ebcd083` | 2026-11-08 | merge D11: intel plane A18-A21 (58 findings, 58 URLs verified) |
| `7619a4b1` | 2026-11-08 | merge D12 gap bundle C: rivalboard, competitor-monitor |
| `e6604c28` | 2026-11-08 | merge D12 gap bundle B: thewatch, rankledger |
| `2c5d7906` | 2026-11-08 | merge D12 gap bundle A: prospector, product-finder |
| `be1e9ac4` | 2026-11-08 | D12 bundle: measured dimension is real (route mounted + component exists + app latency), and the router eval disables thinking so qwen3.5/bojo are actually measured |
| `14f8ae31` | 2026-11-08 | test(d12): prove prospector and product-finder against the real app |
| `eee5c880` | 2026-11-08 | D12 gap C: prove rivalboard + competitor-monitor route contracts |
| `6b4385f4` | 2026-11-08 | D11: intel discovery plane (A18-A21) - 5 scouts, licence engine, vetting, ranked gaps |
| `cd740e7a` | 2026-11-08 | test: prove thewatch monitoring and rankledger rank surfaces |
| `41b000bc` | 2026-11-08 | merge D16/D17: model scout + tool bake-off |
| `5b372724` | 2026-11-08 | merge D10: visual regression gate |
| `4979785f` | 2026-11-08 | merge D9: seller-tester harness |
| `d69c722a` | 2026-11-08 | folded fixes 3-5: ComfyUI render lane owns its process, 27B needs a stated lease, disk floor + digest; launcher installed as a logon task with proven crash-restart |
| `9276ec0d` | 2026-11-08 | D8: risk classes, verify-after-act, Profile 6 lease, CDP browser layer, parity suite twice, clean-server qwen retest and 40-screen grounding |
| `b70fab7a` | 2026-11-08 | D16 model scout + D17 REA/Craft Anything bake-off |
| `a40a86c1` | 2026-11-08 | feat(seller-tester): D9 harness with 32 briefs, programmatic scorers, gap filing and escalation |
| `6cc085ba` | 2026-11-08 | D10: visual regression gate - frozen scenes, perceptual diff, armed baselines |
| `e5dccbbd` | 2026-11-08 | checkpoint before D8-D17 batch: worktree state at 2026-11-08 |
| `40184afe` | 2026-11-07 | D7: structure first (V2 20/20), and llava chosen over qwen2.5vl on measurement |
| `f1d7c988` | 2026-11-07 | D7 prep: provenance of the pins, a measured coexistence table, residency owned by the lock manager, and GPU benchmarks |
| `8f783ddb` | 2026-11-07 | D7 GPU: Ollama was never blind - it was told not to look. Four roles now 100% GPU |
| `df6761e1` | 2026-11-07 | docs(ty): handoff to D7, with the GPU blocker stated where the next session will see it |
| `442896d6` | 2026-11-07 | D6: the privacy gate exists before any pixel does - V5 and V7 pass |
| `ec3a3f6a` | 2026-11-07 | D5: the queue is the ranked gap list, and an empty queue is a defect with a paper trail |
| `e12816fc` | 2026-11-07 | fix(D4): scorecards reads the tracked registry export |
| `b68675a9` | 2026-11-07 | fix(D4): the registry export is tracked so the target spec is reproducible |
| `73cba057` | 2026-11-07 | D4: every service has a scorecard, and 0 of 29 is the honest answer |
| `ff03f6dd` | 2026-11-07 | D3: the queue refuses an overlapping scope and main moves only on the verifier |
| `dbf763a3` | 2026-11-07 | D1+D2: probe answers, a launcher that survives a kill, and a GPU budget it can refuse with |
| `2ce211ea` | 2026-11-07 | D0: director baseline - mandate saved, measured suite, and the test leak that was hiding 12 failures |
| `de464cbd` | 2026-11-07 | docs(ty): the handoff now carries the final C1-C7 state and the one honest caveat |
| `5b855176` | 2026-11-07 | docs(gate): C3 and C5 green, and the C6 diagnosis the gate asks for in place of a soak |
| `d6d3c7b2` | 2026-11-07 | fix(launcher): an undispatchable item is parked, not re-marked pending |
| `1f6e0e89` | 2026-11-07 | autonomy(cycle 45): T1-scan-files-scanned - The readiness scan report must say how many files it scanned |
| `1ba986e4` | 2026-11-07 | docs(queue): five product contracts cannot pass - their acceptance is an existing green suite |
| `4d1d6e98` | 2026-11-07 | fix(launcher): revert the candidate's real footprint, not just its declared scope |
| `11b607bb` | 2026-11-07 | fix(evaluator): freeze the candidate's patch, not the whole dirty tree |
| `805aa8b6` | 2026-11-07 | docs(ty): the gate's live state, the C3 probe, the secret triage and a handoff that needs no chat |
| `9cd8a12a` | 2026-11-07 | fix(evaluator): a pre-existing dirty test file is not the candidate's edit |
| `adfa4500` | 2026-11-07 | test(scan): a red check for C3 - the readiness report has no files_scanned |
| `66f7c952` | 2026-11-07 | feat(autonomy): a shipped cycle is a commit, not a verdict - C3's last arrow |
| `ebaa13d9` | 2026-11-07 | fix(autonomy): a green check parks, a stale result cannot complete, and the brief carries the check |
| `c12b05eb` | 2026-11-07 | docs(autonomy): A16 done - the A9-A17 gate is satisfied and product work is now the front of the queue |
| `9d6bb3b4` | 2026-11-07 | feat(autonomy): A16 work generator - the T0-T5 ladder, and starvation that names every number |
| `896b7aaa` | 2026-11-07 | fix(autonomy): the four defects the C3 probe found, before the gate claims anything |
| `6158c001` | 2026-11-07 | fix(queue): the no-skipping rule had 34 holes - product and perf items had no depends_on at all |
| `4b11b860` | 2026-11-07 | fix(autonomy): validate_contract reports a missing command list and a wrong shape, not just the first |
| `8230b730` | 2026-11-07 | feat(autonomy): A16 deltas 1, 2 and 4 - next refills, complete tops up, the watchdog backs off on starvation |
| `603f73e7` | 2026-11-07 | fix(autonomy): A16 delta 3 - dispatchable items first, and a dry-run that obeys the real selector |
| `41fdceaf` | 2026-11-07 | feat(autonomy): A13 rejection ledger - material fingerprints, hash-chained strikes, park on the third |
| `68441443` | 2026-11-06 | docs(autonomy): persist the A16 generator spec with the four runner deltas it needs |
| `2066cdbe` | 2026-11-06 | docs(ty): worktree triage - source committed, generated artefacts ignored, reports blocked on 290 secret-scanner findings |
| `e4a56fb9` | 2026-11-06 | chore(tree): commit outstanding source work from parallel sessions (backend, agents, tools, ui, shared, data, config, scripts, tests) and ignore generated exports, media and runtime state |
| `27466c73` | 2026-11-06 | docs(autonomy): record A10 as done and queue the retest preconditions |
| `0acf0ad1` | 2026-11-06 | docs(autonomy): A10 verdict STOP - 0/5, no author lane; three preconditions queued for a fair retest |
| `e805f0d1` | 2026-11-06 | spike(a10): local coding lane authors 0/5 patches - verdict STOP |
| `0753fc7b` | 2026-11-06 | docs(autonomy): A12b wired; the worktree triage is now the blocking item because the gate works |
| `9147995a` | 2026-11-06 | feat(autonomy): A12b - a cycle is judged by the evaluator, not by the launcher |
| `e21ae410` | 2026-11-06 | docs(autonomy): persist the A13 ledger spec so a fresh lane can build it without the transcript |
| `66c95388` | 2026-11-06 | docs(autonomy): A13 design exposes an unwired evaluator - queue the seam before the ledger |
| `787b5fdd` | 2026-11-06 | docs(autonomy): A12 closed; queue the 79 MB worktree triage that freezing exposed |
| `84eda331` | 2026-11-06 | feat(autonomy): A12 artifacts - freeze a candidate before it is judged |
| `4ad04194` | 2026-11-06 | docs(autonomy): record A15 as done in the queue |
| `52c888e6` | 2026-11-06 | docs(autonomy): A15 contract writer closed; gate at 15/17 with A12 and the spike in flight |
| `9f29a718` | 2026-11-06 | feat(autonomy): A15 contract writer - a proven scope becomes a dispatchable contract |
| `e3cb06b4` | 2026-11-06 | docs(autonomy): A11 evaluator closed |
| `8c529be6` | 2026-11-06 | docs(autonomy): A14 scope deriver closed |
| `8b0e848f` | 2026-11-06 | feat(autonomy): A11 evaluator - deterministic gates judge a candidate patch |
| `04615b60` | 2026-11-06 | feat(autonomy): A14 scope deriver - write_paths come from a real traceback |
| `15f0cc15` | 2026-11-06 | docs(security): close the mcp screen bypass - launcher chains, interpreter payloads and embedded host forms all refused before spawn |
| `ec1be088` | 2026-11-06 | fix(mcp): refuse launchers one hop from a shell and screen URL shapes anywhere |
| `4044e9f7` | 2026-11-06 | docs(security): close the DNS-resolved SSRF - nip.io to loopback or metadata is now refused before the request |
| `050e4188` | 2026-11-06 | fix(security): T0-callback-dns - resolve callback hostnames and refuse non-public answers |
| `acecb00d` | 2026-11-06 | docs(autonomy): A9b closed - the cap now counts real session tokens, not a guess |
| `37c18031` | 2026-11-06 | feat(autonomy): A9b - the cap counts the session, not our own summary file |
| `7f3219e3` | 2026-11-06 | docs(ty): concurrency probe - four disjoint lanes at once |
| `832c0a5b` | 2026-11-06 | docs(autonomy): A17 closed - the CLI worked, our reader read the wrong field; gate next is the coding-lane spike |
| `7c82ae71` | 2026-11-06 | docs(intel): A18 build-ready design - tracked refusals, accounting closure, measured vs unknown quotas, and three gaps named |
| `6a726c84` | 2026-11-06 | A17: correct the dispatch count in the report (eight, not nine) |
| `de2f6f2c` | 2026-11-06 | A17: fix deepseek worker lane - read part.text, real provenance, CLI preflight |
| `4d67b6de` | 2026-11-06 | docs(perf): measured baseline - two handlers recompute per request, entry bundle is 1.09 MB; four mechanical fix units queued |
| `b6eab283` | 2026-11-06 | docs(ty): two live bypasses from the verifier queued as T0 - DNS-resolved loopback and wsl -e bash |
| `d82a5b3f` | 2026-11-06 | feat(autonomy): the daily token cap is measurable, so it can be enforced (M0.3b-token-meter) |
| `64a2ad3a` | 2026-11-06 | docs(ty): log the three Amazon gate fixes and the report-download URL guard |
| `ff14b20a` | 2026-11-06 | docs(ty): report the three Amazon egress fixes with commit shas and verification output |
| `f497bcdb` | 2026-11-06 | fix(security): Ads search-term report download refuses any host but AWS S3 / Ads API (T2-report-download-host) |
| `112fef46` | 2026-11-06 | fix(security): SP-API and Ads auth classes refuse the Amazon token POST themselves (T1-amazon-auth-gate) |
| `1bfa9c9a` | 2026-11-06 | docs(ty): log the MCP client policy lane |
| `3324b71f` | 2026-11-06 | fix(security): govern the MCP client's spawn and URL arguments before dispatch |
| `cf443599` | 2026-11-06 | fix(security): amazon_guard refuses a locator passed as asin=, before any request (T1-amazon-guard) |
| `41cff584` | 2026-11-06 | feat(autonomy): dependencies are enforced by the selector - the queue is an order, not a suggestion; automation gate A1-A21 written |
| `0c98921d` | 2026-11-06 | fix(autonomy): revert with git, not a memory snapshot - the snapshot deleted committed files a parallel lane had just created |
| `f1270918` | 2026-11-06 | docs(autonomy): record the three W9 security units as done with commits + verification, and the revert-deletes-committed-files finding that forced a STOP |
| `96b5d83c` | 2026-11-06 | fix(security): dataforseo classify_endpoint checks parsed.hostname (https + api.dataforseo.com only) instead of trusting the path alone (T1-dataforseo-host) |
| `ab2e26b0` | 2026-11-06 | feat(security): the service entrypoint installs the transport-level egress guard at startup, failing closed if it cannot; proves an unchecked call site still refuses Amazon (T0-egress-hook remainder) |
| `7570b18e` | 2026-11-06 | fix(security): design_studio_async validates a caller-supplied callback_url before any request (http/https, named host, no IP literals, no loopback/link-local, Amazon refused via egress_guard) - SSRF T0-callback-ssrf |
| `0b3392ed` | 2026-11-06 | feat(security): one transport-level Amazon refusal (urllib + requests) with a caller-attributed audit log, instead of seven per-site checks |
| `8cf71401` | 2026-11-06 | feat(autonomy): watchdog keeps the launcher alive across crashes, turn ends and reboots; scheduled at logon |
| `75dc0c95` | 2026-11-06 | fix(autonomy): a failed cycle now restores the bytes it touched and a check that is already green never reaches a worker; docs: egress map (44 unguarded caller-URL sites, no global hook) |
| `8f39b034` | 2026-11-06 | fix(security): a refused Amazon URL is a skipped provider, not a 500; guard applies to the real transport only so fixture tests still run |
| `67801fb1` | 2026-11-06 | docs(agents): parallel lanes are standing practice - read-only parallel, writers disjoint, verification serialised, fan-out capped at 4 |
| `5fd12ad6` | 2026-11-06 | fix(security): refuse Amazon URLs at the Bright Data egress - amazon_adapters was building amazon.com/dp URLs with no gate on the path |
| `7e057582` | 2026-11-06 | fix(autonomy): worker uses 'opencode run --agent tys --format json' with stdin prompt and records the model that actually answered |
| `dc471e50` | 2026-11-06 | feat(agents): named lanes (tys/verifier/research) on the pinned DeepSeek model, plus a guard that refuses jailbreak personas and off-model lanes |
| `a1bd94fa` | 2026-11-06 | chore(autonomy): pin the worker to opencode-go/deepseek-v4.1-flash; drop --standalone (it hangs headlessly) |
| `bc134241` | 2026-11-06 | feat(autonomy): launcher preflight - a dead model lane stops the run instead of burning a queue attempt per refused connection |
| `49aae7dd` | 2026-11-06 | feat(autonomy): the launcher loops next->worker->complete with a heartbeat; an item without acceptance checks is never dispatched |
| `ae38fc77` | 2026-11-06 | fix(autonomy): compare test identities from pytest's own node ids, not junit classnames (junit reported 6039 removals for a green run) |
| `ea3ee19c` | 2026-11-06 | fix(autonomy): sort checkpoints by newest file, not directory mtime (caught by the full run); baseline reflects the measured 6289 with the known race named |
| `ea73e4e5` | 2026-11-06 | feat(autonomy): lane leases - a busy or starved lane defers the cycle instead of failing it |
| `621014a9` | 2026-11-06 | feat(autonomy): the runner owns the loop (lease, rotation, caps, crash resume); regression by test name; disk reclaimed 9.7 -> 14.2 GB |
| `ee84513a` | 2026-11-05 | feat(creative): designs are stored and reused only on request; A+ page built from one design with seven distinct views and a contained hero (logo and hero-key defects logged) |
| `9a51c01b` | 2026-11-05 | docs(ty): seed the three A+ quality units |
| `79aa68f5` | 2026-11-05 | docs(ty): A+ page proof measured - six real modules render, and three quality defects are logged with evidence |
| `89ca9654` | 2026-11-05 | feat(creative): identity by construction proven on a live scene - real pouch preserved (27s scene + 10s cutout); no bottom crop, identity check masked by product alpha |
| `325bf34f` | 2026-11-05 | docs(ty): cycle 6 digest and log - text guard measurement |
| `79160a1d` | 2026-11-05 | feat(creative): main images ship text-free - guard detects, cleans and re-verifies glyphs (10 boxes -> 0, text accuracy 0 -> 100 on the real artifact) |
| `4679809a` | 2026-11-05 | fix(ux): fonts load on Safari - import the font CSS through the bundler instead of linking public/ (WebKit refused /ui/ui/fonts/fonts.css); mobile console errors 10-16/page -> 0, asserted on both viewports |
| `7690c6dc` | 2026-11-05 | fix(ux): canonical style layer ends the simple.css override war (greeting visible, prompts 3-up, chips unclipped and AA); scorecard gains coverage, tab-state, scene-readability and layout gates; 12/12 desktop+iPhone |
| `34dccc27` | 2026-11-05 | feat(ux): calmer dev notice, session titles that ellipsis instead of clipping, starter prompts as full-width rows, focusable main; gates 10/10 across desktop and iPhone |
| `8ec9c0b9` | 2026-11-05 | docs(ty): handoff, log and queue reflect the UX-first and creative-identity front of the programme |
| `2f08dbc4` | 2026-11-05 | fix(a11y): muted and placeholder ink now clear 4.5:1 on paper; the UX scorecard waits out the entry fade and records selectors + measured ratios |
| `68013193` | 2026-11-05 | GRANT: mark the Qwen-Image-Edit lane weights_missing (it refused at call time); feat(creative): identity by construction (product_composite + 7 tests) and a measured E1 experiment runner |
| `54859ed6` | 2026-11-05 | feat(ux): give every route its own h1 (the app name was the page heading) + a UX scorecard; docs(research): competitor gap sweep with licences and six scoped experiments |
| `b2a6c6ae` | 2026-11-05 | test(baseline): write tests/BASELINE.json from the measured run (6247 backend, 511/1122/307/31; +51 new tests, none skipped) |
| `1d5edb3f` | 2026-11-05 | GRANT: restrict the MCP client to the local lane (the cloud lane must not gain an ungated external-tool surface) |
| `9967aa44` | 2026-11-05 | fix(scorecard): compare the product subject, not the frame (and prove reference conditioning changes the product: ssim 0.01-0.32) |
| `ff07d228` | 2026-11-05 | docs(ty): phase A probe, self-assessment, 14-workstream production plan, seeded queue, handoff, digest, needs-you |
| `a8d3c27e` | 2026-11-05 | feat(product-pictures): a stored-reference library, a 60-case fixed bench, and a scorecard that measures it (cycle 1: main-image compliance 0% -> 100%) |
| `4e69f0f1` | 2026-11-05 | GRANT: replace the local vision QC model with gemma3:4b (llava:7b fallback) because qwen2.5vl:7b returns unparseable output on this runner |
| `b19582e0` | 2026-11-05 | feat(agent): compact a long transcript at a measured 70% and write a handoff; feat(eval): one numeric scorecard for product pictures |
| `f029dd2b` | 2026-11-05 | GRANT: register the MCP client and the research lane (mcp MIT, trafilatura Apache-2.0, ddgs MIT) so Ty can consume tool servers and read the web with the Amazon blocklist evaluated first |
| `e61ba173` | 2026-11-05 | docs(rea): REA scan of goose + python-sdk - what Ty is missing and what to clone |
| `12655960` | 2026-11-05 | feat(tools): Vet a package against OSV before installing it |
| `53a878e0` | 2026-11-05 | docs(agent): Ty capability gap vs Claude Code and Perplexity Computer |
| `0d91747e` | 2026-11-05 | feat(tools): Widen the scanner to failures the UI hides |
| `af5e30e4` | 2026-11-05 | docs(readiness): production readiness sweep, 95 findings -> 1, suite 6180 |
| `c0bdf34a` | 2026-11-05 | fix(tools): Make the readiness scanner stop reporting things that are no |
| `3766d07d` | 2026-11-05 | fix(a11y): Label the remaining form controls across the admin and studi |
| `caa3c2fb` | 2026-11-05 | fix(a11y): Give the global controls an accessible name |
| `e74f5520` | 2026-11-05 | feat(tools): A repeatable production-readiness scanner |
| `cb470da8` | 2026-11-05 | fix(baseline): 6164 backend tests after the backlog tool's 10 tests |
| `309eae77` | 2026-11-05 | feat(improvement): standing backlog, 3 UI cycles shipped, creative lane proven |
| `976ace59` | 2026-11-05 | feat(ui): Keep Package Design sessions across navigation |
| `9b716830` | 2026-11-05 | feat(ui): Say when the Ty panel data was last good |
| `ff0b83b7` | 2026-11-05 | feat(ui): Show the dieline guides that are already implemented |
| `2b5d96f5` | 2026-11-05 | chore(loop): seed the queue with the six 2026-11-05 improvement contracts |
| `1edb5313` | 2026-11-05 | docs(improvement): continuous loop initialised, 6 cycles verified, suite GREEN |
| `4ea61cde` | 2026-11-05 | fix(baseline): record the measured suite counts so the canary can actually pass |
| `ed910c5f` | 2026-11-05 | fix(audio): the ad pipeline opts out of the overrun refusal and reports the truncation |
| `c459bccc` | 2026-11-05 | fix(test-harness): the runner parses its own summary, and csv-parse is declared |
| `224c1ba1` | 2026-11-05 | fix(deps): declare csv-parse and the playwright dev deps the lockfile already pinned |
| `9883b59d` | 2026-11-05 | fix(ui): Package Design reads the credit ledger and names every failure |
| `ed7fe1bd` | 2026-11-05 | tys: vision supervision - the eyes judge what a step produced and hand the assistant guidance; two dependent switches, cobalt ring while armed |
| `6c17d73b` | 2026-11-05 | fix(audio): refuse a narration that overruns the picture instead of trimming it |
| `daf59aa6` | 2026-11-05 | feat(prompt): refine an authored prompt to the contract before it renders |
| `25bc3ea7` | 2026-11-05 | probe: measure whether Ty's Vision can read code, and prove the coding lane can program |
| `ae905b65` | 2026-11-05 | chore(automation): reconcile stale proposals, record loop retry, keep the two policy blocks |
| `c9cd4190` | 2026-11-05 | docs(v3): pin the close-out commit hashes |
| `4f22b2e1` | 2026-11-05 | V3.2 close-out: 30s master ships after re-anchor drift control (30.000s/900 frames/-16.2 LUFS/5 cues); full suite 6121 passed 0 failed |
| `20444f42` | 2026-11-05 | docs(ui): record the three creative/UI improvement cycles |
| `89aed46c` | 2026-11-05 | chore(state): record the asset dashboard filter cycle |
| `9c89eb81` | 2026-11-05 | feat(studio): filter asset packages by run id, kind or date |
| `c5e5658d` | 2026-11-05 | chore(state): record the UI/creative improvement cycles |
| `5691846d` | 2026-11-05 | feat(studio): manifest export/size, human guardrail rule, section a11y |
| `27d1fb63` | 2026-11-05 | feat(ui): live Tys Assistant panel with queue, lanes, progress and memory |
| `8553bb42` | 2026-11-04 | feat(v3): merge state, wire memory/MCP/coding tools, audit overrides, print dieline, heavy readiness |
| `7a95bceb` | 2026-11-04 | V3.2/V3.4: master audio lane (-16 LUFS + script-aligned captions), graduation reports for all tys_ops modules, backlog reconciliation (20 stale rows resolved, 5 owner-blocked) |
| `110afe12` | 2026-11-04 | docs(v3): record the open items that remain after the closure pass |
| `2db1f451` | 2026-11-04 | V3.2/V3.4 close-out: 15s Wan master through the human-feature guardrail, text-suppression negative, stitched-path regression test, closure report; full backend suite 6095 passed / 0 failed |
| `d1d6b573` | 2026-11-04 | feat(vision): gemma3:4b clears the 18/20 Stage 2 bake-off; memory graduates |
| `6922c5ac` | 2026-11-04 | V3.3/V3.4: migrate PackifyDesign off services/api.js, reconcile shell-mode tests with catalog v5, stabilise watcher tests, add six-point Chrome parity harness, fix shorts stitched uuid import |
| `f7b4da2b` | 2026-11-04 | feat(v3): human-feature guardrail, graduation gate, vision verifier; V2 closure reconciliation |
| `4812f316` | 2026-11-04 | feat(local): screen-aware companion with OCR memory and live local voice |
| `fb0fac9e` | 2026-11-04 | feat(tys): live semantic memory API, eval harness, tracing and Tier-0 toolchain |
| `f5b8a2bc` | 2026-11-04 | research(expansion): wave 2 delta - 3,895 new targets, TRELLIS/SAM2/Donut sources, licence triage |
| `bf648649` | 2026-11-04 | research(expansion): 6-source scan, 7 extraction blueprints, creative spec, manifest |
| `a926bb20` | 2026-11-04 | docs(reports): Q4 sourcing guide and path deck (12pp PDF) from director brief |
| `1aa4fe32` | 2026-11-04 | research(github): scan 12,135 repos for Bojo, Tys and the master brain |
| `a9c031e6` | 2026-11-04 | feat(creative): reference-conditioned renders, best-of-N, and a real identity floor |
| `b214404a` | 2026-11-04 | feat(creative): install and calibrate the image scorers, gate per surface |
| `141f827a` | 2026-11-04 | feat(tys): review every presented image, and refuse a new module nobody calls |
| `71b3935b` | 2026-11-04 | docs: correct the FLUX 3 capability claims - 4K, references and i2i were always available |
| `e9491137` | 2026-11-04 | docs: LTX-2.3 investigated - gated weights and 16 GB RAM, not disk, are the blockers |
| `edc2348f` | 2026-11-03 | feat(creative): fetch the licensed stack (SeedVR2, Wan 2.2 A14B Q4, PickScore, HPSv2) with provenance |
| `161af2f4` | 2026-11-03 | docs: creative pipeline plan - reference conditioning first, then a detail stage, then real video |
| `15f5b77a` | 2026-11-03 | docs(session): add t20 to the probe table |
| `3ac32692` | 2026-11-03 | docs(captions): the word-timing support and the remaining scene-copy fact |
| `2d7ca1d1` | 2026-11-03 | docs(captions): word timings are supported; the video still uses scene copy |
| `73b15f4f` | 2026-11-03 | feat(captions): use measured word timings, and break cues at speech segments |
| `d4b8fa9b` | 2026-11-03 | docs(state): record the UTF-16 backlog fix in the suite fragment |
| `0f418b25` | 2026-11-03 | docs(session): add the hardening units to the index |
| `e03516c9` | 2026-11-03 | docs(hardening): job durability, id validation and plate-shape tiles |
| `453e6cfd` | 2026-11-03 | fix(video-api): validate the job-id shape before any path join |
| `f44b514e` | 2026-11-03 | fix(jobs/aplus): atomic job writes, interrupted recovery, distinct tiles on any plate shape |
| `7aaf8856` | 2026-11-03 | docs(autonomy): the UTF-16 backlog defect and the 10 proposals |
| `4af276fa` | 2026-11-03 | fix(autonomy): the backlog reads UTF-16/CRLF reports, so Windows failures become proposals |
| `687cea08` | 2026-11-03 | docs(creative): the lane map, the session index and the open product decision |
| `f6537778` | 2026-11-03 | docs(suite): the route-contract fix drops the expected count to 9 |
| `7c76e3f9` | 2026-11-03 | test(ui): resolve the dynamic HITL action with a real value, not 'sample' |
| `07d6bb8a` | 2026-11-03 | docs(suite): final 10 failed / 5918 passed, and the overwrite lesson |
| `28819ae1` | 2026-11-03 | fix(listing): restore the existing listing_image module; the new pipeline is listing_render |
| `fe68b5c2` | 2026-11-03 | fix(hitl): count unreadable records as skipped, consistently |
| `76ca0927` | 2026-11-03 | fix(coding): make the missing-artifact pressure visible in both prompt modes |
| `5f8bec1a` | 2026-11-03 | docs(video): the varied 15s master and its framing critique |
| `f61f8a98` | 2026-11-03 | feat(video): vary the camera per beat without inventing a second pouch |
| `47706050` | 2026-11-03 | docs(video): the 15s master is rendered and checked |
| `49fc267a` | 2026-11-03 | docs(aplus): live six-module page evidence, the placeholder defect and the fragment |
| `14605a9d` | 2026-11-03 | fix(aplus): three tiles are real crops of the supplied plate, not placeholder art |
| `ebca86a7` | 2026-11-03 | feat(aplus): one API call returns a measured six-module A+ page |
| `97b88f8d` | 2026-11-03 | feat(aplus): a full A+ page from product copy, every module measured |
| `1bb2a8ca` | 2026-11-03 | feat(listings): a text-safe main image, deterministically fitted to 86% fill, then gated |
| `79af4099` | 2026-11-03 | docs(video): plan/render API evidence, the 15s time note and the fragment |
| `ff6cb8bf` | 2026-11-03 | feat(video): plan first, then a confirm-gated render job over the API |
| `85a291f2` | 2026-11-03 | docs(stills): live social-frame API evidence and the new fragment |
| `a3bd53f8` | 2026-11-03 | feat(stills): POST /social-frames renders and refuses through the API |
| `4e03d66e` | 2026-11-03 | docs(suite): 16 -> 13 failures, all 13 pre-existing |
| `6f86055d` | 2026-11-03 | fix(loop): a task with no checks verified nothing; the creative tasks now carry checks |
| `dfcb2b78` | 2026-11-03 | fix(flux3): stopping the lane actually releases the ComfyUI process |
| `1d06c363` | 2026-11-03 | docs(video): the live 3s proof, the four-frame defect and the fragment |
| `a637cd2f` | 2026-11-03 | fix(video): keep the picture's length through the mix; opaque caption plate |
| `8d4dd259` | 2026-11-03 | feat(video): one command from script to a checked vertical video |
| `40f58dd0` | 2026-11-03 | docs(stills): placement evidence, the listing-rubric defect and the fragment |
| `5e144b18` | 2026-11-03 | feat(stills): placement-safe social frames, a listing prompt pack and a fixed listing gate |
| `ea984fb3` | 2026-11-03 | docs(video): script planner evidence, decisions and fragment |
| `386b7305` | 2026-11-03 | feat(video): a scene plan whose durations sum to the placement window |
| `bb2cb4b6` | 2026-11-03 | docs(video): captions and audio evidence, decisions and fragment |
| `095cae65` | 2026-11-03 | feat(video): voice, a local bed, ducking and measured loudness |
| `b868bda1` | 2026-11-03 | feat(video): burn captions inside the platform safe area, then OCR them |
| `a8c48727` | 2026-11-03 | docs(video): stitch evidence, decisions and state fragment |
| `435d0033` | 2026-11-03 | feat(video): stitch planned clips into the placement contract, then ffprobe it |
| `918d5419` | 2026-11-03 | docs(hygiene): evidence and decisions for the duplicate-definition fixes |
| `824e4284` | 2026-11-03 | fix(rubric): remove the dead score_hero copy the alias was overriding |
| `72edcb35` | 2026-11-03 | fix(listing-records): one ListingRecordIn for bulk import and single create |
| `0f07957a` | 2026-11-03 | fix(tests): the duplicate collection hook disabled the credential scrub |
| `beffb826` | 2026-11-03 | fix(studio): remove the duplicate Phase R block that silently overrode the hardened copy |
| `9ff0bf05` | 2026-11-03 | docs(creative): item 0 evidence, decisions, blockers and state fragment |
| `03df3301` | 2026-11-03 | fix(mockup): read a printed OZ when OCR reports it as 0Z |
| `91bee21a` | 2026-11-03 | feat(creative): a product picture, gated, through the product API |
| `4cf60335` | 2026-11-03 | feat(mockup): composite designed panels onto a measured pouch face |
| `5e051575` | 2026-11-03 | fix(autonomy): a resident model is not extra RAM pressure |
| `4099cb06` | 2026-11-03 | fix(autonomy): release the model when a campaign ends |
| `75930b43` | 2026-11-03 | fix(autonomy): dispatch pending work before retries |
| `14d47b07` | 2026-11-03 | fix(creative): the owner asked for a product picture, not label art - queue the mockup work |
| `283f8d7b` | 2026-11-03 | feat(creative): Mogra Organics lion's mane pouch label art (front + back, 6 oz) |
| `3f8f6f31` | 2026-11-03 | docs: creative services scan - what is built, what is proven, and the six-step work order |
| `31cbe17c` | 2026-11-03 | feat(creative): video placement contracts - a named platform now fixes canvas, fps and duration, and stitching is refused honestly |
| `03535707` | 2026-11-03 | docs: autonomy hardening - three defects fixed, the capacity envelope measured, and what the evaluator must add |
| `91b9f06b` | 2026-11-03 | feat(autonomy): --backlog turns failing tests into a PROPOSED work queue |
| `383754d9` | 2026-11-03 | fix(autonomy): never substitute an embedding model, and never silently swap the requested lane |
| `5c102e64` | 2026-11-03 | feat(autonomy): outcome memory - stop re-dispatching tasks this lane has never solved |
| `a0cd0439` | 2026-11-03 | fix(flux3): wait for start_comfyui.ps1's own readiness verdict (a cold start after a hard kill can take 2-3 min, which the fixed 180 s poll outran) |
| `43da223a` | 2026-11-03 | docs: FLUX 3 arming evidence, the text-safe subject bug, and two pre-existing e2e failures closed by the arming |
| `2e2e6d00` | 2026-11-03 | FLUX 3 is armed and integrated end to end (owner instruction, 2026-11-03) |
| `0ba4e2ab` | 2026-11-03 | docs: UX rebuild final report (U0-U15, verdict, numbers, decisions, gaps) |
| `1ceeb04a` | 2026-11-03 | U14 report: record that report PNGs are gitignored, so the committed baseline record is the manifest |
| `72c33dd4` | 2026-11-03 | U15: restore what one rewrite deleted from the AutothinK adapter and the local model lane |
| `7f45df79` | 2026-11-03 | U14 complete: the 13 e2e failures adjudicated pre-existing, per-service baseline, backend suite run |
| `c93bcfff` | 2026-11-03 | U14 follow-up: close the four verifier findings that were still open |
| `5c63ae93` | 2026-11-03 | U14 (partial): verification, docs, bundle guard, smoke fix, verifier findings |
| `f1cb6616` | 2026-11-03 | U13: the nova moment, and per-scene/per-tier frame numbers |
| `a19eb15d` | 2026-11-03 | U12: every interactive service is reachable and honest about what it is |
| `818d6894` | 2026-11-03 | U11: the Golden Goose comet scene, wired to the goose tab |
| `2fc82b39` | 2026-11-03 | U10: research black-hole scene and the research desk |
| `a760de7a` | 2026-11-03 | docs: U8 final report - package panels, dieline overlay, regression counts |
| `dacf9a32` | 2026-11-03 | U8 complete: package front/rear panels and the dieline overlay |
| `0b8cd7b3` | 2026-11-02 | U8: Bojo acts on the open canvas - backend canvas_edit tool, turn plumbing, local fast path |
| `0b8bb20e` | 2026-11-02 | U9: the PPC harvest workspace - report in, change log, validated bulk file out |
| `42fe96e8` | 2026-11-02 | U9 (partial): the PPC asteroid-field scene, wired to the AdPilot tab |
| `5c34a357` | 2026-11-02 | U8 (partial): bounded canvas instructions, published to Bojo, proven on both targets |
| `19a6e88d` | 2026-11-02 | U7: the studio canvas workspace - content types, layers, snapping, autosave, PNG/PDF export |
| `87d11d7d` | 2026-11-02 | providers: make repo-root .env authoritative for Bright Data/ChocoData/Rainforest |
| `4f4f9e19` | 2026-11-02 | docs: U5-U6 complete, U7 handoff with hazards found |
| `8a6cefff` | 2026-11-02 | U6: ringed gas-giant studio scene, scene max-colour contrast proof, legible legacy headings |
| `dd93559e` | 2026-11-02 | U5: scene engine - one canvas, tiers, fps cap, visibility pause, event bus, default starfield |
| `064d77f3` | 2026-11-02 | U4: per-service theme tokens, the glass kit and the service-switch hook |
| `d2c5168d` | 2026-11-02 | docs: U3 verified on both targets - queue, decisions and handoff |
| `b3cad214` | 2026-11-02 | U3: the workbench works on the phone profile - tab strip behind the switcher, hit-tested taps, 429-safe asset fetch |
| `8c2d1700` | 2026-11-02 | docs: record server state at the U3 handoff |
| `6b9fa1c0` | 2026-11-02 | docs: U3 handoff - desktop green, phone profile still failing |
| `234fa8ff` | 2026-11-02 | U3: the workbench shell - Bojo docked, services as tabs, state preserved |
| `32f466b0` | 2026-11-02 | docs: UX run report and handoff (U0-U2 verified, U3 blocked) |
| `67bfe665` | 2026-11-02 | U2: service registry (34 services) and the entitlement gate stub |
| `fa434f63` | 2026-11-02 | U1: name the default experience Northstar; keep the ids and migrate old values |
| `cd92d963` | 2026-11-02 | U0: UX rebuild baseline, queue machinery and the safety-gate blocker |
| `a2d12f5e` | 2026-11-02 | docs: browser verification, the free-tier reachability finding, and the WebKit install |
| `55a6dcaf` | 2026-11-02 | test(e2e): browser test for the asset dashboard, and the route fix it found |
| `268268a5` | 2026-11-02 | docs(reports): 20GB+ GPU landscape under RTX 3090 price + P40 bandwidth correction |
| `2d85a9c3` | 2026-11-02 | docs: UI wiring report and evidence |
| `38ec58e8` | 2026-11-02 | feat(studio): asset dashboard - packages, lane triggers, proposal queue |
| `fb1ff49f` | 2026-11-02 | docs(reports): OCuLink BOM + Vulkan-both-cards split plan for MI50 eGPU |
| `73e9139f` | 2026-11-02 | docs(reports): MI50 32GB eGPU plan for MSI Vector 16 HX AI RTX 5080 |
| `e3b3f10d` | 2026-11-02 | docs: relight is done, so the next decision moves on |
| `54f75440` | 2026-11-02 | fix(relight): register the asset before packaging; final report numbers |
| `c1f3d08e` | 2026-11-02 | feat(relight): make the IC-Light lane work, and keep the noise guard |
| `fd569b50` | 2026-11-02 | docs(reports): cheapest China-sourced GPU beating Tesla P40 with 20GB+ VRAM |
| `324ab12f` | 2026-11-02 | docs: record the two closing defects and the final counts |
| `6ba1de79` | 2026-11-02 | test(aplus): keep the route's packages out of the user's deliverables |
| `08bd1860` | 2026-11-02 | fix(gate): an unrequested form is not-applicable, not a mismatch |
| `623a63cb` | 2026-11-02 | docs: A-E report, evidence and the first discovery proposals |
| `a5ad7ace` | 2026-11-02 | feat(3d): mesh handoff contract and an honest Blender probe |
| `e99e4e67` | 2026-11-02 | feat(discovery): proposal queue instead of an auto-installer |
| `c4adefa5` | 2026-11-02 | feat(studio): relight lane with a noise guard that refuses garbage |
| `ef0d0944` | 2026-11-02 | feat(print): measured print master with Real-ESRGAN 4x |
| `f445fbf5` | 2026-11-02 | feat(studio): 9:16 shorts lane on the installed Wan 2.2 TI2V 5B |
| `4f4d5d0a` | 2026-11-02 | docs(reports): V100 32GB global sourcing brief |
| `cb335873` | 2026-11-02 | docs: multi-channel campaign report, evidence and two trajectories |
| `36dba6f8` | 2026-11-02 | docs(reports): GPU price scan pass 2 - verified listings with links + 2080 Ti 22GB mod options |
| `48ff4e78` | 2026-11-02 | feat(aplus): package every page with measured QA and an OCR read-back |
| `515d48fa` | 2026-11-02 | feat(studio): validated ad canvases (1:1, 9:16, 16:9) and a gibberish guard |
| `5cb963a1` | 2026-11-02 | docs: packify-quality campaign report, evidence and two trajectories |
| `d746667b` | 2026-11-02 | feat(studio): five-axis quality gate before a render becomes a deliverable |
| `86e59278` | 2026-11-02 | feat(print): refuse impossible dieline geometry instead of clamping it |
| `7c1403dd` | 2026-11-02 | docs(reports): GPU price scan - RTX 3090 / Tesla P40 / Tesla V100 |
| `a226c8dc` | 2026-11-02 | docs: Unit A/B campaign report, probe t11 and two trajectories |
| `adb376d1` | 2026-11-02 | fix(deliverables): keep the cause when the vision lane is unreachable |
| `199293d0` | 2026-11-02 | test(studio): finish the hosted-path assertions in the studio suite |
| `670792fb` | 2026-11-02 | test(lanes): assert the hosted fail-closed path, not the demo shim |
| `64a0f3af` | 2026-11-02 | feat(studio): accepted renders become a reopenable deliverable package |
| `7ee328fc` | 2026-11-02 | test: exercise the hosted fail-closed auth path, not the dev shim |
| `533f164c` | 2026-11-02 | docs(creative): transport root cause + form adherence, 2 of 3 units |
| `932ac936` | 2026-11-02 | feat(creative): form-adherent renders and a transport that cannot stall |
| `eb53fd63` | 2026-11-02 | fix(creative): the text suppressor forbids lettering, it does not choose the subject |
| `6f069143` | 2026-11-02 | fix(text-fidelity): the suppressor forbids lettering, not a subject |
| `4eb1284e` | 2026-11-02 | feat(ty): unattended author lane over the OpenCode Go subscription |
| `c0111fde` | 2026-11-02 | fix(print): refuse a degenerate dieline quad instead of measuring it |
| `9fb3f267` | 2026-11-02 | feat(ty): backlog pass - three more DeepSeek-authored fixes, six total |
| `fa46b397` | 2026-11-02 | fix(listing): refuse an impossible fill fraction on the hero image |
| `9f692f21` | 2026-11-02 | fix(image): refuse an impossible fill and an empty cutout when framing |
| `d5ba3ced` | 2026-11-02 | fix(print): refuse a dieline quad that cannot belong to the image |
| `453c0965` | 2026-11-01 | feat(ty): DeepSeek-authored, Ty-supervised repair - 3 of 3 accepted |
| `e1585917` | 2026-11-01 | fix(diff): a selected-hunk diff keeps its file headers |
| `9e8e2cdb` | 2026-11-01 | fix(artifacts): classify a JPEG artifact as an image |
| `57f1db57` | 2026-11-01 | docs(ty): MoE runtime feasibility - NO-GO, host RAM is the wall |
| `e45b03c2` | 2026-11-01 | docs(ty): bounded requalification - 20 steps did not close the two fixes |
| `bae478a3` | 2026-11-01 | chore(tasks): 20-step budget for the two remaining fixes (versioned, bounded) |
| `26ba3cba` | 2026-11-01 | docs(ty): qwen3.5:4b lane - screened, 1 of 3 fixes accepted |
| `63c90e73` | 2026-11-01 | fix(executor): read pressure counts refused reads; 14 steps for the two retries |
| `883a7fed` | 2026-11-01 | fix(hitl): report unreadable records instead of dropping them |
| `dffa68ae` | 2026-11-01 | chore(tasks): point the three qualification tasks at the screened qwen3.5:4b lane |
| `02ed2abe` | 2026-11-01 | fix(screen): state the total contract unambiguously |
| `61c5adb6` | 2026-11-01 | fix(ast): a def line passed as the body is stripped, not nested |
| `6bda9739` | 2026-11-01 | test(executor): the ast_edit stall regression includes the required read |
| `83d2474d` | 2026-11-01 | fix(executor): ast_edit counts as a change for the verify-stall guard |
| `88f722d7` | 2026-11-01 | docs(ty): parser-enabled 7B profile built and rejected - PARSER stored, not effective |
| `aa38d0a6` | 2026-11-01 | docs(ty): authorized coder install - primary rejected on tools, fallback failed the screen |
| `cb8b91a0` | 2026-11-01 | fix(screen): score a broken candidate instead of crashing on it |
| `a3ff9176` | 2026-11-01 | docs(ty): 8.3B GPU lane evaluated and rejected on capability |
| `470576e6` | 2026-11-01 | feat(executor): purpose-aware read discipline replaces the blanket reread block |
| `3442fd92` | 2026-11-01 | docs(ty): correct the floor mislabel in the lane evaluation |
| `4d791392` | 2026-11-01 | docs(ty): installed-lane evaluation - adapter fixed, no candidate qualifies |
| `ea6b4dc1` | 2026-11-01 | fix(prompt): neutral placeholders in the action examples |
| `3b5e88ef` | 2026-11-01 | fix(executor): refuse a repeated read with no edit in between |
| `366f0a66` | 2026-11-01 | fix(prompt): the stop-reading nudge names ast_edit, not write_many |
| `1da7cade` | 2026-11-01 | feat(adapter): native Ollama tool calling, judged by the same validator |
| `6cd697f7` | 2026-11-01 | docs(ty): qualification run - resource gate PASSED, model lane FAILED 0/3 |
| `654839ac` | 2026-11-01 | fix(protocol): name the writable path in a scope refusal; task wording says never edit the probe |
| `c7ed8936` | 2026-11-01 | fix(executor): a bounded edit requires a prior read of that file |
| `24427069` | 2026-11-01 | fix(prompt): the task-scoped schema shows the command that will actually run |
| `a61aebf5` | 2026-11-01 | docs(ty): resource qualification BLOCKED at 4.57 GB; launcher and frozen queue handed off |
| `990e6cd9` | 2026-11-01 | feat(ty): profile-accurate readiness, runtime floor watch, foreground launcher |
| `97c8fe14` | 2026-11-01 | docs(ty): resource-gated final run - NO-GO at gate 1, clean stop |
| `f8df145a` | 2026-11-01 | feat(celestial10): ten production UI compositions |
| `416cf00b` | 2026-11-01 | feat(chatlab): ten radical celestial chat interfaces with live sky |
| `5370d4b7` | 2026-11-01 | chore(state): write the Ty executor fragment without a BOM |
| `edbcabf2` | 2026-11-01 | chore(state): fix a typo in the Ty executor fragment |
| `31d0e74e` | 2026-11-01 | docs(ty): executor report - protocol hardened, repo task blocked by host RAM |
| `3669f651` | 2026-11-01 | feat(ty): strict action executor, bounded repair, task-scoped protocol |
| `b084924f` | 2026-11-01 | feat(celestial): ten-direction UI concept atlas |
| `bf5893d2` | 2026-11-01 | test(loop): pin the lane in the residency-dispatch test |
| `4485f1c4` | 2026-11-01 | docs(loop): Ty autonomy gate report - residency proven, model work blocked |
| `8ad91edd` | 2026-11-01 | feat(loop): sync the Ty autonomy harness fixes and small-file tasks |
| `f2fbe848` | 2026-11-01 | feat(simple): ten Simple-mode compositions with design picker |
| `dbf85b8e` | 2026-11-01 | feat(loop): gate on MEASURED resident RAM, and register three Ty fixes |
| `f3a930d9` | 2026-10-31 | docs(creative): A+ render report + queued state fragment |
| `1f087eef` | 2026-10-31 | feat(galactic): ten FLUX 3 cluster themes with meteor motion |
| `ca6c45cb` | 2026-10-31 | feat(creative): render A+ modules and measure them instead of describing them |
| `846d9ba8` | 2026-10-31 | docs(loop): refresh final readiness checkpoint |
| `e1534715` | 2026-10-31 | chore(loop): clarify STOP probe result |
| `a7a283cc` | 2026-10-31 | docs(loop): record non-helper pre-fix replay evidence |
| `25bac038` | 2026-10-31 | docs(loop): autonomy readiness handoff and campaign evidence |
| `60f0556f` | 2026-10-31 | fix(loop): record post-load RAM headroom in lane selection |
| `5e63bc32` | 2026-10-31 | fix(loop): track apply workers and align docs with total task limits |
| `a80e9ab7` | 2026-10-31 | fix(loop): separate blocked queue from remaining work in status |
| `74c7d49c` | 2026-10-31 | docs(loop): document readiness and long campaigns |
| `558eceb9` | 2026-10-31 | chore(creative): remove unused imports |
| `48daca5b` | 2026-10-31 | fix(package): refuse unknown formats as print-ready |
| `ff498524` | 2026-10-31 | fix(creative): validate the visible wrap fraction |
| `190c8e45` | 2026-10-31 | fix(prepress): refuse degenerate dieline quads |
| `03da4b07` | 2026-10-31 | fix(creative): reject bottle labels past the bottom seam |
| `ca29ceea` | 2026-10-31 | fix(creative): validate quads in bottle and tube compositors |
| `b42171c5` | 2026-10-31 | fix(hitl): accept path-like roots in hitl_counts |
| `e111977e` | 2026-10-31 | feat(loop): autonomy readiness gate and long-campaign controls |
| `750c8692` | 2026-10-31 | docs(creative): record wrap-artwork limitation |
| `85a4c952` | 2026-10-31 | fix(creative): cut bottle and tube dielines for the wrap circumference |
| `b3214171` | 2026-10-31 | feat(creative): four-format Packify-style package generation |
| `6c9a3816` | 2026-10-31 | feat(loop): complete Ty execution bridge, demos, and bounded campaign |
| `58b79cb3` | 2026-10-31 | feat(loop): Ty execution bridge, durable lifecycle, scoped workspace, rollback proof |
| `96be935d` | 2026-10-31 | cycle: Add HITL queue counts helper |
| `21bae7da` | 2026-10-31 | chore(loop): activate supervised cycles, record first run, truncate ledger output |
| `4109d158` | 2026-10-31 | chore(loop): activate continuous loop supervisor |
| `423bd9cb` | 2026-10-31 | feat(loop): autonomous continuous-loop supervisor + task registry |
| `e5facfe8` | 2026-10-31 | docs(chat): Bojo keep-alive cycle 5 report + state fragment |
| `a9adbd58` | 2026-10-31 | perf(chat): keep Bojo resident between turns with keep_alive |
| `61ae1d7c` | 2026-10-31 | docs(ui): Galactic HITL cycle 4 report + state fragment |
| `31bd8a69` | 2026-10-31 | feat(ui): HITL approval panel on the local queue |
| `c6f1e3e9` | 2026-10-31 | docs(ui): Galactic SSE cycle 3 report + state fragment |
| `4dd9f1d0` | 2026-10-31 | feat(ui): SSE snapshot stream for the Galactic deck |
| `e0808800` | 2026-10-31 | docs(ui): Galactic deck cycle 2 report + state fragment |
| `511f3fd2` | 2026-10-31 | feat(ui): Galactic command deck - topology, KV heatmap, event bus, micro-animations |
| `ad09403f` | 2026-10-31 | docs(kernel): self-improvement cycle 1 report + state fragment |
| `b132931c` | 2026-10-31 | perf(kernel): self-improvement cycle 1 - compact Ty history, adaptive Bojo budget |
| `27453ee8` | 2026-10-31 | docs(kernel): note the applied q8_0 runtime record and commits |
| `cb356643` | 2026-10-31 | chore(runtime): record q8_0 KV + FlashAttention process flags |
| `b34bbe61` | 2026-10-31 | docs(kernel): local tiering/AST/sandbox report + state fragment |
| `30df451f` | 2026-10-31 | feat(kernel): AST editing, lane policy, quantized runtime flags, sandbox, self-heal, HITL |
| `4f0e431b` | 2026-10-31 | docs(creative): hero/prepress/author report + final live evidence |
| `187706b5` | 2026-10-31 | fix(creative): refuse a cylinder mask that misses the body; add the packaging form to the author brief |
| `b9c64776` | 2026-10-31 | feat(creative): hero remediation, surface luminance, 27B author, print-DPI sidecar |
| `7e443d88` | 2026-10-31 | docs(creative): measure_surface report + live four-format evidence |
| `b0a25396` | 2026-10-31 | fix(creative): trim tube bands at horizontal cap seams |
| `ebbed6b5` | 2026-10-31 | fix(creative): continuous bottle wrap, measured tube trapezoid, visible-width wrap |
| `06776bbe` | 2026-10-31 | fix(creative): perspective warp maps the label onto the measured quad; box interior corner detected |
| `670fd5ad` | 2026-10-31 | feat(creative): measured surfaces for box/bottle/tube + live four-format runner |
| `0be3fb99` | 2026-10-31 | feat(creative): box/bottle/tube compositors, format routing, T1 rollback wired into the flow |
| `b5a2e92c` | 2026-10-31 | feat(creative): split listing vs hook rubrics, route by artifact class, floor-free prompt mode |
| `eb3b3192` | 2026-10-31 | feat(creative): offline Benchmark Evaluator wired into the flow's evaluate stage |
| `17d28ce7` | 2026-10-31 | fix(creative): pass the whole profile to brand_memory.extract (memory count was 0) |
| `9b77f47b` | 2026-10-31 | feat(creative): ban mark nouns in the Prompt Architect; first green end-to-end flow run |
| `dccbf36c` | 2026-10-31 | feat(creative): packaging geometry profiles + T1 auto-revert gate + local 27B crew binding |
| `72784288` | 2026-10-30 | feat(crew): diff-scoped snapshots, deterministic creative Flow, optional CrewAI layer |
| `1c4526f9` | 2026-10-30 | feat(creative): neutralise the label zone before realism; refuse dirty plates; Phase 3 routes |
| `96264f8b` | 2026-10-30 | feat(creative): blank-plate pipeline + compositor proof; plate stays dirty (documented) |
| `56cc08a6` | 2026-10-30 | docs: end-to-end hero verification report + evidence (pipeline proven, artefact not shippable) |
| `a022e861` | 2026-10-30 | feat(studio): mount A+ module layout preview; FLUX 3 -> cutout -> pure-white hero end-to-end with a text gate |
| `7e28db16` | 2026-10-30 | docs: Phase 1 & 3 creative report + state fragment |
| `51413de8` | 2026-10-30 | feat(creative): A+ geometry, white-isolation hero compositing, and the Phase 3 operating-loop bindings |
| `815474bd` | 2026-10-30 | feat(phase2): retire the Simple label, move the view switch into Settings, gate advanced_view to top tier |
| `e2344f81` | 2026-10-30 | docs(ui): WO UI-20 report + state fragment |
| `ad458143` | 2026-10-30 | feat(ui): 20-point UI work order - tokens, primitives, palette, toasts, a11y guardrail |
| `ee436743` | 2026-10-30 | docs(design): ten FLUX 3 interface comps - review notes and reproducible manifest |
| `52bc2c74` | 2026-10-30 | feat(tools): ten FLUX 3 interface comps - distinct layout archetypes, not recolours |
| `f1ac6eca` | 2026-10-30 | docs: galactic theme review set - what each of the ten variants changes |
| `281067cb` | 2026-10-30 | feat(ui): Interstellar backdrop - real lensed black hole, ten review variants |
| `82038d62` | 2026-10-30 | fix(tys): accept --cache-none on start_comfyui; report runnable queue head |
| `8c228029` | 2026-10-29 | feat(ui): mount the celestial backdrop as the Master Brain shell background |
| `4735ca88` | 2026-10-29 | feat(agent): gate no-op verification runs; coder lane reaches tsc exit 0 at 17K with zero patches |
| `f6d0c3f7` | 2026-10-29 | fix(lanes): detach the MoE launcher; measure coder-lane pass@1 and the 64K commit ceiling |
| `2c10b1f7` | 2026-10-29 | state: apply five pending fragments (tys ops, routing, FLUX 3 install, install health, MoE bench); unique pre-apply backup stamps |
| `e9c0f87a` | 2026-10-29 | feat(studio): install FLUX 3 (nvfp4), remove FLUX 2 and text-correcting vision models, wire flux3 gateway |
| `dce05a07` | 2026-10-29 | feat(tys): intercept visual work to FLUX 3, keep code on the coding model |
| `1fdd3958` | 2026-10-29 | fix(auth): extend dev loopback session to legacy require_session |
| `e4f50c1c` | 2026-10-29 | fix(auth): remove sign-in wall in local dev (owner directive) |
| `dbd2814a` | 2026-10-29 | docs: Gilded Void baroque theme report (verification PASS, root-cause of 403, commit 7330ab3a) |
| `7330ab3a` | 2026-10-29 | feat(ui): Gilded Void baroque hyperrealism theme (spec baroque_hyperrealism_spec_20261029_153346) |
| `09ea0b50` | 2026-10-29 | reports: full Hyperrealistic Baroque spec deliverable (tys_f3d848058579, 27B worker, 17.5k chars) |
| `5c4c6376` | 2026-10-29 | test(tys): sustained 100-profile stress report (10,000 tasks, 0 failures) + summary |
| `482e8bda` | 2026-10-29 | fix(tys): JSON repair must not rewrite smart quotes inside strings |
| `59cec0bf` | 2026-10-29 | feat(tys): operations layer - storage tiers, cloud bridge, validation, memory, budgets, self-heal, adaptive UI, stress harness |
| `ef2fe8c5` | 2026-10-29 | install health: re-recorded with the core suites (17/17 critical) |
| `e539c82b` | 2026-10-29 | state fragment lives in the tracked state/fragments/ (backups/ is gitignored); health check reads it there |
| `ec15ec5d` | 2026-10-29 | install health check (17/17 critical) + state fragment merge path for the operator-gated 00_STATE.json; model_router: bojo:latest matches bojo |
| `b26ec1e9` | 2026-10-29 | kernel benchmark: 20-brief runner with JSONL evidence + semantic validators (patch arithmetic, required keys, placeholders, headings, unchanged-from-seed); kernel derives acceptance from the workspace instead of executor_ok |
| `dcf348b1` | 2026-10-29 | engine alignment + p01/p03: model-suite drift (local text tiers -> bojo, Ty is a llama.cpp worker), one sync task contract with kernel evidence, acceptance outranks the lane self-report, atomic+bounded writes with a write denylist |
| `a78b535d` | 2026-10-29 | docs: reconcile engine-tiering spec against disk - 6 subsystems absent, p01/p03 misidentified, benchmark table not this repo's data |
| `a37c47f9` | 2026-10-29 | coding agent: required-artifact step pressure fixes p03 write-stall; targeted 2/2, post-fix hybrid 20/20; 123 tests |
| `c4fa268d` | 2026-10-29 | coding executor: re-check acceptance after loop stop; Ty p01-p05 5/5 complete; acceptance-recovery defect fixed; 122 tests |
| `c738e13d` | 2026-10-29 | docs: Northstar OS product overview - default view rationale, advanced view top-tier gate, naming rule (no user-visible 'Simple'), spec-vs-disk reconciliation |
| `06ab9db3` | 2026-10-29 | rea: V2 reverse-engineering pass recorded (restart note) |
| `fae02a12` | 2026-10-29 | rea V2: async assembly lane (ffmpeg-gated, not engine-gated) + route |
| `58c07b18` | 2026-10-29 | coding loop default when workspace; hybrid 3-run spread 18-20/20 with thresholds; Ty multi-brief p01-p05 5/5 content-valid; p01 status caveat; 121 tests |
| `64d195d4` | 2026-10-29 | rea: V3 reverse-engineering pass recorded (incl. two thin-evidence findings) |
| `f8c9b9e4` | 2026-10-29 | rea V3: hook structures as sourced data; storyboard pack carries a timed plan |
| `3dc8fbec` | 2026-10-29 | coding tool loop: hybrid 20/20 content-valid; Ty p01 end-to-end complete; apply_patch; workspace acceptance; seed builder; 121 tests |
| `6176ad0e` | 2026-10-29 | agent_kernel: add apply_patch tool (git apply, rooted, 200KB/60s capped) |
| `d0e23fc9` | 2026-10-29 | rea: correct the S5 commit hashes in the execution log |
| `25a2dedb` | 2026-10-29 | rea: S5 reverse-engineering pass recorded |
| `6bcf31c4` | 2026-10-29 | rea S5: gate the variant matrix in the harness (baseline row wired) |
| `09a2a8df` | 2026-10-29 | rea S5: social variant matrix (cover-crop + keep-in intersection) wired into the pack |
| `f4b751e7` | 2026-10-29 | coding agent: bounded list/read/grep/write/run loop, workspace safety, Ty adapter; p01/p02/p05 3/3 content-valid with real pytest/py_compile; 57 tests |
| `7bc3f4c6` | 2026-10-29 | rea: wave 3 results recorded (U3, S4, backend checks) |
| `71e16997` | 2026-10-29 | rea S4: local pre-upload validator with presets.js parity; harness gains 3 guards |
| `9c02ca8b` | 2026-10-29 | rea U3: logo placement module + place_logo chat tool (measured anchor, contrast report) |
| `ad9eb4f6` | 2026-10-29 | rea: wave 2 results recorded (L3/L4, B3/B4/B5) |
| `f07428f6` | 2026-10-29 | rea B3: both ComfyUI launchers record the cache-none marker |
| `8d571d9d` | 2026-10-29 | rea B3/B4/B5: cache-none guard for heavy lanes, eviction notice, render-lock wait stats |
| `9fe0b04c` | 2026-10-29 | rea L3/L4: inward feather derived from residual + per-plate geometry cache |
| `c60686f5` | 2026-10-29 | kernel enforces content validators (label/ad/patch/json/text/social/aplus); p13 social tool; enforced text-lane baseline 17/20; Ty-as-is 0/20; tool lane 20/20; 48 kernel tests |
| `5b406bf9` | 2026-10-29 | rea: item 1 verification, U1/U4 and V1 results recorded |
| `7df2e265` | 2026-10-29 | rea V1: deterministic video assembly service (ffmpeg + piper), with ffprobe evidence |
| `38d89be4` | 2026-10-29 | rea U1: chain apply_label after a label render when the turn names the product |
| `7c336d82` | 2026-10-28 | live text-lane baseline round 2: fence stripping + 13-node rerun, 3-run spread thresholds (p50 7.5s/p95 16.9s), content validators, tool-lane p11/p14 valid, MTP pinned off; labels |
| `677c197f` | 2026-10-28 | live NS-PROJ-20 lane baseline: 20/20 artifacts, 18/20 format-valid, p50 6.27s/p95 11.17s, thresholds set; MTP-instability recorded; file_min_bytes verifier |
| `bbff620b` | 2026-10-28 | label NS-PROJ-20 as harness validation (not a project result); record OCR spacing finding (RapidOCR merge on composite, not text_fidelity normalization); ignore local readmes |
| `03f23e86` | 2026-10-28 | ty: MOGRA presets verified; T4 gated on a 34-credit draft control |
| `e3ad82ff` | 2026-10-28 | feat(presets): approved MOGRA palette and pouch presets from the brief |
| `6f5e875c` | 2026-10-28 | Ty opt-in kernel path (run_kernel) + live inspect smoke; spec status built; clone ledger + provenance updated; v0.1 report |
| `7f56ae83` | 2026-10-28 | kernel v0.1: 12-module agent kernel (policy/plan/checkpoint/memory/graph/verify/subagents/context/skills/diff/budget/journal) + 46 tests; Ty adapter; Bojo plan_project; NS-PROJ-20 dry harness 20/20 + resume; Phase B 1500 scored/100 read/12 deep; state merge |
| `b5e68f43` | 2026-10-28 | fix(label): harden the apply_label argument contract; UI compositor green |
| `8d356a3a` | 2026-10-28 | provenance: quote the pouch_label notes field (comma inside text) |
| `3e263e16` | 2026-10-28 | provenance: quote/repair the pouch_label row's extra comma |
| `6c39b74a` | 2026-10-28 | phase A spec: agent kernel for Ty/Bojo/Autothink, clone ledger, 1500/100/12 source plan, documented limits + provenance rows; no kernel code |
| `203ac6ba` | 2026-10-28 | rea L2: sub-pixel side fit, per-side mesh bow, residual guard; item 1 acceptance (0.238 px, OCR/prepress/readiness retail_ready); 2048 decision recorded; verify-rea entry point |
| `0ac13ec5` | 2026-10-28 | fix(chat): false-success guard, deterministic asset picker, fit-box expectations |
| `845e8cef` | 2026-10-28 | ty: T2 re-accepted after the clean UI regeneration (asset 9fef9b3c) |
| `83cbfa6b` | 2026-10-28 | rea B1: attribute the latency tail from lane_telemetry; execution log |
| `489f2309` | 2026-10-28 | rea S1/S2: social spec provenance + missing canvases; regress harness; ceiling probe |
| `b245c57d` | 2026-10-28 | rea wave1: mesh warp (L1), ink-faint contrast (U4), social canvases (S2) + phase 3 plans |
| `6d1b5ddb` | 2026-10-28 | rea: phase 2 research execution - six deliverables, four probes, baseline |
| `cdf7b35d` | 2026-10-28 | rea: phase 1 research plans for Ty, Bojo, creative services and simple mode |
| `2a50c3c0` | 2026-10-28 | fix(label): measure the pouch, not the scenery, and integrate the print |
| `e79453ca` | 2026-10-28 | ty: T2 MOGRA compositor verified complete through the Design Studio UI |
| `9bb34a5f` | 2026-10-28 | ty: directive applied, controller reloaded on the new fingerprint, campaign blocked on the extension relay |
| `e077a4ed` | 2026-10-28 | owner-authorized: Owner Directive 2026-10-28 in the capsule and the constitution |
| `219c2bf3` | 2026-10-28 | ty: tested rollback system + Phase 0 state for the owner directive |
| `62075e2b` | 2026-10-28 | fix(db): wait for the SQLite write lock instead of 500 on new chat |
| `3ef7eb92` | 2026-10-28 | fix(chat): resume a chat session once per focus, and de-flake the MOGRA spec |
| `23465d16` | 2026-10-28 | fix(design-studio): reserve the chat scrollbar gutter so the composer stays actionable |
| `82213b5d` | 2026-10-28 | docs: Tys Assistant build + smoke verification report (Tasks A/B/C, VERIFIED COMPLETE) |
| `16f7fa77` | 2026-10-28 | Tys Assistant: admin automation agent (queue, lanes, checkpoints, controller handshake) |
| `c7e73056` | 2026-10-27 | chromeconnect acceptance + 3 defects: banner paint order, dev-shim rate bucket, 429 logout |
| `7adbc731` | 2026-10-27 | model placement: pin Bojo to CPU (num_gpu 0), keep 27B worker GPU-only on demand |
| `9b1a6510` | 2026-10-27 | dev-auth: loopback-only LOCAL_DEV bypass, DevBanner, safety gate, docs |
| `1117d011` | 2026-10-27 | fix: update OOM fallback map to bojo/qwen3.5:2b |
| `7ace8f0b` | 2026-10-27 | fix: route DEFAULT_LOCAL_MODEL and model router to bojo |
| `d56810ae` | 2026-10-27 | cycle: opencode.json additive deny rules + fix pouch_label RAM-gate test isolation |
| `88867188` | 2026-10-27 | STEP 1-5 COMPLETE: All tests pass, go-live gate cleared |
| `b72ad1b0` | 2026-10-27 | report: acceptance drain T2-T8/C5 complete |
| `7ebc8d5b` | 2026-10-27 | report: chromeconnect policy change + localhost interaction grant |
| `37c2281f` | 2026-10-27 | checkpoint: acceptance resume 2026-10-27 (Chrome Connect verified, T1 render verified) |
| `1b1f3ed7` | 2026-10-27 | docs(blocked): Chrome Control isolated profile lacks Playwright extension CRX |
| `862af377` | 2026-10-27 | feat(chrome-connect-3.0): profile 6 lease gate wiring, runner real session, drop amazon_public |
| `d867c689` | 2026-10-27 | docs(acceptance): T1/T3/T4/T5 renders verified via ComfyUI (Ollama stopped) |
| `01d97bfb` | 2026-10-27 | docs(acceptance): T1 FLUX render verified; VRAM root cause; Ollama restarted |
| `f2d45faf` | 2026-10-27 | docs(acceptance): note pin cleared; binding still blocked on extension relay |
| `04042103` | 2026-10-27 | docs(acceptance): R2 MOGRA acceptance report + state update (blocked on browser binding) |
| `2086ebb4` | 2026-10-26 | fix(studio): cross-process render lock, safe stop-list, encoder pairing guard |
| `e0e83199` | 2026-10-26 | fix: remove stray PY identifier in ChromeConnect.jsx (caused 'PY is not defined' runtime error) |
| `00bd47ed` | 2026-10-26 | fix(comfy_smoke): klein lane encoder mismatch (qwen_3_8b->qwen_3_4b_fp8_mixed for 4B UNet) |
| `b6f05e11` | 2026-10-26 | Chrome Connect 3.0: complete implementation report - 140 tests pass |
| `bae68f06` | 2026-10-26 | Wire evidence-first extraction into runner (P6-T4) |
| `cb470920` | 2026-10-26 | Chrome Connect 3.0: 3 new adapters (sellersprite, palletfly, prime_national_distribution) - 44 runner tests pass |
| `96ecb0a8` | 2026-10-26 | Chrome Connect 3.0: final audit report - 131 tests pass, all phases complete |
| `c3815574` | 2026-10-26 | Chrome Connect 3.0: final state update - 131 tests pass |
| `57811834` | 2026-10-26 | Chrome Connect 3.0: runner, adapters, profile lease, admin API, DB schema - 131 tests pass |
| `fbbead03` | 2026-10-26 | fix(comfy_smoke): seedvr2 -> UNSUPPORTED-WITH-REASON (custom nodes absent) |
| `a8e128fc` | 2026-10-26 | Phase 0-5 complete: Chrome Connect 3.0 build summary |
| `c1e44f83` | 2026-10-26 | Phase 5: Chrome Connect 3.0 health, evidence, alerts - 26 tests pass |
| `2fbaa86a` | 2026-10-26 | Phase 4: Chrome Connect 3.0 model benchmark - browser brain selected |
| `5e525110` | 2026-10-26 | creative session: R2 blocked - ComfyUI CUDA error (unknown) during CLIPTextEncode |
| `50390716` | 2026-10-26 | Phase 3: Chrome Connect 3.0 compile and replay - 17 tests pass |
| `a4b36888` | 2026-10-26 | Phase 2: Chrome Connect 3.0 AI loop MVP - 8 tools, 14 tests pass |
| `c781a44e` | 2026-10-26 | Phase 1: Chrome Connect 3.0 observation layer - 23 fixtures, 23 tests pass |
| `a1780c86` | 2026-10-26 | Phase 0: Chrome Connect 3.0 baseline - run logging + profile switch to Profile 7 |
| `21f67d55` | 2026-10-26 | creative session: RAM gate built (8 tests pass), comfy_smoke lanes (wan+tts OK, klein OOM, seedvr2 400) |
| `d11eb48d` | 2026-10-26 | feat(studio): system-RAM pre-render gate with stop/restore list |
| `3cf021e0` | 2026-10-26 | phase R: R2 MOGRA blocked - ComfyUI OOM (RAM 2.2GB free, need 1.2GB for text encoder) |
| `262710b1` | 2026-10-26 | phase R: R2 MOGRA deferred (ComfyUI render lanes error) + R3 SKIPPED-WITH-REASON (no FLUX3 weights) |
| `d3f416be` | 2026-10-26 | F1+F2: tailscale serve -> 8000 (verified probe 200), comfy_smoke BASE 8199->8188 |
| `07ae4c75` | 2026-10-26 | phase R: R0 preconditions + R1 Playwright real-system smoke (8/8 PASS) |
| `eb26c70c` | 2026-10-26 | step3: foundation credentials self-init (ensure_table in get_by_email/count) - login 200 verified |
| `86c6e9da` | 2026-10-26 | step4: axe - one h1 per room + sign-in color-contrast fix |
| `7ac583ab` | 2026-10-26 | step2: autothink empty-store regression tests (non-5xx) |
| `3b6f7ef3` | 2026-10-26 | step1: preserve A/C/E evidence into reports/audit-2026-10-26 |
| `b5183337` | 2026-10-26 | test: scratch-instance A/C/E evidence + FLUX3 doc grep purge |
| `2c8b3852` | 2026-10-26 | step1: FLUX 3 code cleanup - remove invented filenames, add error handling |
| `430bbab0` | 2026-10-26 | feat(e2e): Playwright Test harness for localhost testing only (Northstar OS product repo) |
| `e6062198` | 2026-10-26 | feat(guard): Playwright Test default for localhost e2e only; chromeconnect_guard.py amendment (Northstar OS product repo) |
| `05570911` | 2026-10-25 | docs(batch1): handoff report — root cause, fixes, blocked G1-G6 (Northstar OS product repo) |
| `4fc42848` | 2026-10-24 | docs(batch1): controller navigate hangs; G1-G6 still blocked (Northstar OS product repo) |
| `12278014` | 2026-10-24 | docs(batch1): note agent-CLI path works; app signed out blocks UI runs (Northstar OS product repo) |
| `8520824b` | 2026-10-24 | fix(simple): WebGL context-loss fallback (Northstar OS product repo) |
| `09f350cd` | 2026-10-24 | fix(simple): honest artifact states, real event wiring, one display-scale control (Northstar OS product repo) |
| `8db8b6a6` | 2026-10-24 | docs(simple-mode): final mission report — all requirements, gates, state classification, commits |
| `a11c9cb4` | 2026-10-24 | docs(simple-mode): update final report — crash/renderer repair verified, broader acceptance in progress |
| `e60e0f4d` | 2026-10-24 | docs: requirements matrix — 18 items with state classification |
| `3c314787` | 2026-10-24 | feat(ui): missing-asset placeholder + allow known stale asset 404 in galactic harness |
| `f7a76868` | 2026-10-24 | docs(simple-mode): final mission report — all states, gates, blocked items, commits |
| `9cfa0243` | 2026-10-24 | fix(ui): remove duplicate DisplayScaleControl declaration |
| `2d86e51c` | 2026-10-24 | docs(simple-mode): final acceptance report — root cause, gates 28/0+18/0, state classification |
| `50eae812` | 2026-10-24 | feat(simple-mode): single CosmicCanvas renderer, Vista wired via data-vista, DisplayScale restored, 18/0 galactic |
| `b5ed44bf` | 2026-10-24 | docs(simple-mode): acceptance pass report — 28/0 shell, 17/1 galactic, gates, blocked items |
| `3e7a2d76` | 2026-10-24 | fix(ui): panel opacity 0.95 (text safety), render CosmicCanvas+CelestialBackdrop, update galactic harness column check |
| `681c5317` | 2026-10-24 | docs: screenshot probe PASS — desktop + mobile @390x844, files verified, viewport restored |
| `8cac7a58` | 2026-10-24 | docs: chromeconnect restart attempt — host killed, MCP not auto-respawning, probe blocked |
| `bfa129b6` | 2026-10-24 | docs(simple-mode): capture report — blank screen root cause fixed, S1 page evidence, gates green |
| `dafdb32d` | 2026-10-24 | fix(ui): add missing Improvement import in App.jsx (blank-screen root cause) |
| `197cfaae` | 2026-10-24 | docs(simple-mode): final report with all commit hashes and blocker status |
| `a0e06b36` | 2026-10-24 | feat(simple-mode): Vista library + daily seed, interaction signatures, --ui-scale + Display Scale control |
| `92384549` | 2026-10-24 | docs(simple-mode): save deliverables + execution report with commit hashes |
| `f14144f7` | 2026-10-24 | feat(simple-mode): C1 dictation labeling, C2 standalone redirect, C3 costco adapter finished (216 tests green) |
| `eea2fff8` | 2026-10-24 | fix(simple-mode): env load in main.py + robust prompt-equality tests; add issue scan + fix plan |
| `487f04b2` | 2026-10-24 | fix(ui): further lighten celestial theme — body bg #0b1120→#1a2435, top-nav rgba(9,12,17,0.93)→rgba(18,24,38,0.65), top-nav-menu rgba(13,17,23,0.98)→rgba(18,24,38,0.85), focus chips & mb-chip rgba(9,12,17,0.62)→rgba(18,24,38,0.55) |
| `2e67213b` | 2026-10-24 | fix(ui): lighten celestial theme — body bg #04060a→#0b1120, .cb-sky #020306→#1d2a4a/#0a0e1a, .mb-scrim rgba(5,8,20,0.35)→rgba(10,17,32,0.20), .chat-shell rgba(9,12,17,0.88)→rgba(18,24,38,0.62) |
| `433b3661` | 2026-10-24 | fix(ui): lighten .cb-sky gradient (#020306 -> #1d2a4a/#0a0e1a) so celestial backdrop is not black |
| `561dffd7` | 2026-10-24 | fix(ui): lighten celestial backdrop background (#020306 -> #0a0e1a) and re-enable scrim for readability |
| `fb24eb9a` | 2026-10-24 | feat(ui): PackifyDesign workspace page (sessions, brand kit, credits, suggested prompts) + route /packify-design; build verified |
| `784b8578` | 2026-10-24 | feat(package-design): Packify-style module (templates, text-to-spec via skills+provider, copy_audit, credits ledger) + React workspace UI + route (12 tests) |
| `1d0c99bc` | 2026-10-24 | chore: cie test hygiene (reset cie:cycle latch per test); text-to-cad notes refined (cadquery works, text-to-cad is Node MCP) |
| `5f119e68` | 2026-10-24 | feat(decision): laya ONNX backend wired as optional second backend (backend='laya'); rules stays primary (12/12 vs 6/12); suite + report updated |
| `7642257f` | 2026-10-24 | feat(gate): skylos per-card evidence gate (tools/skylos_gate.py) - pass/fail/incomplete, exit codes 0/1/2 |
| `47a09d55` | 2026-10-24 | feat(blockers): typed blocker ledger with decision-layer escalation + batched report (10 tests) |
| `744ba181` | 2026-10-24 | research: second live REA capture (docs.agentconnect.md) COMPLETE; sidebar nav + Decisions surface confirmed; 6th memory entry filed |
| `7059e77a` | 2026-10-24 | research: REA live capture of agentconnect.md COMPLETE (2 pw calls, 0 refusals); blocker cleared (policy-bless + MCP restart + chromecontrol-agent.js bindProfile fix); 5th memory entry filed |
| `85cd539e` | 2026-10-24 | research+clone: AgentConnect REA scan report; suite notes record the four adopted patterns; 112 invariants green |
| `7b21f02c` | 2026-10-24 | feat(skills): operator-setup skill - checkpoint-verified onboarding, secret values never surfaced (AgentConnect setup-skill pattern) |
| `a85ab5e0` | 2026-10-24 | feat(memory): revision gate - agent memory changes stay PROPOSED until the operator approves (7 tests) |
| `29cf0ca6` | 2026-10-24 | feat(decision): Jev contract port - declarative criteria, probability distributions, fail-closed consumer matching, blocker_escalation + respond_now (12 new tests) |
| `98507611` | 2026-10-24 | feat(loop): durable OPEN-latch breaker (AgentConnect L1 clone) wired into the CIE cycle seam (17 tests) |
| `11d495c6` | 2026-10-24 | policy-log: chromecontrol_policy_owner.json domain_allowlist += agentconnect.md, www/docs/app.agentconnect.md (operator task-authorized for REA capture; read-only; no per-host grants added; prohibited_actions untouched; fingerprint baseline must be re-blessed by operator). File itself lives outside this repo (OneDrive Default Project config). |
| `6bea0147` | 2026-10-24 | research: AgentConnect rejected (second harness, Jev nugget kept), Herk Edit Kit parked (render-path + metering + job fit) |
| `678d2b40` | 2026-10-24 | docs: Autothink send path and the state entry |
| `fc63176e` | 2026-10-24 | feat(autothink): a transport for the handoff the router already offers |
| `a6a8e8aa` | 2026-10-24 | docs: BOJO-UTIL executor, the four approvals, and the state entry |
| `9aeb4c77` | 2026-10-24 | feat(utility): BOJO-UTIL executor — build the calculator instead of offering it |
| `562798f7` | 2026-10-24 | docs(briefs): operator sign-off on Package Designer, approval of Simple Mode, state update |
| `86c9e4fb` | 2026-10-24 | chore(git): separate generated output from evidence (operator-approved) |
| `fe0301bb` | 2026-10-24 | docs: note that the controller viewport change is uncommitted on main |
| `72aed954` | 2026-10-24 | docs(reports): acceptance evidence, briefs, and the 2026-10-24 follow-up |
| `570be634` | 2026-10-24 | feat(specialists): panel routing, package designer panels, gateway ledger |
| `9916943e` | 2026-10-24 | feat(chat): interface repair — render sizing, label lane, asset descriptors, voice |
| `8e15807d` | 2026-10-23 | docs: integration pass report (skills plane, decision layer, 33-tool suite, skylos proved, headroom rejected) |
| `cf90e7ff` | 2026-10-23 | feat(suite): register 13 tools (skills/decision/skylos/headroom/laya/...); evidence proof + skylos install |
| `b80ed1fd` | 2026-10-23 | feat(decision): typed copy audit with abstention, wired into listing and ad proposals (12 tests) |
| `95dc8e30` | 2026-10-23 | feat(skills): product-marketing skills plane wired into chat, listing and ad prompts (18 tests) |
| `d4e44e94` | 2026-10-23 | research: assess the 8 screenshot items (marketingskills is the one worth taking) |
| `10a1062c` | 2026-10-23 | research: OCR Marco Kaz thumbnails, 10 high-impact repos for Northstar (29 verified) |
| `87a507f0` | 2026-10-22 | research: Marco Kaz shorts repo extraction (263 videos, 12 verified repos, 5 candidates) |
| `6f6f0bc7` | 2026-10-22 | fix(router): deterministic intent routing for visual deliverable requests |
| `a78bec9a` | 2026-10-22 | fix(ui+chat): render tables, clear composer label, execute creative deliverables |
| `86da261e` | 2026-10-22 | fix(launcher): point COMFYUI_URL at the live 8188 and start ComfyUI with --cache-none |
| `1e6f2147` | 2026-10-22 | feat(browser): register Chrome Connect in this repo + fix profile recognition |
| `35599042` | 2026-10-22 | feat(local): transcription, Piper voice, and a VRAM-shy vision QC lane |
| `7799c3bb` | 2026-10-22 | chore(ops): ignore local dev-server logs |
| `a63e232d` | 2026-10-22 | feat(creative): local narration lane, wired into video |
| `3ac55eb7` | 2026-10-22 | feat(bojo): skill warehouse - every service area is a real tool |
| `82bc6d97` | 2026-10-22 | feat(creative): evidenced audit + first improvement tranche (104 findings, not 1000) |
| `99f3f2e9` | 2026-10-22 | docs(rollback): register the pre-cie and pre-bulk snapshots |
| `335080ac` | 2026-10-22 | feat(knowledge): 56 new atoms installed, 1,353 improvements queued |
| `eb3a3e25` | 2026-10-22 | test(creative): run every lane for real; fix the two things that were broken |
| `d06b1b83` | 2026-10-22 | fix(ops): clean startup, service launched, GPU state visible |
| `2f637ad2` | 2026-10-22 | fix(local): 27B loads again, Studio talks to 8188, vision points at a model that can see |
| `e470df3c` | 2026-10-22 | feat(improvement): 118-question golden set, rotating hold-out, GPU guard |
| `19d1efe9` | 2026-10-22 | chore(storage): deep clean frees 86.7 GB, and surface three red findings |
| `9f298f71` | 2026-10-22 | feat(bojo): mode selector in the composer (creative / standard / thinking) |
| `693417c0` | 2026-10-22 | feat(bojo): answer-first stream, operator ratings, live answer grading |
| `aa7fe1b6` | 2026-10-21 | feat(improvement): self-feeding knowledge loop for Bojo + Autothink |
| `80c7cc63` | 2026-10-21 | feat(brain): install UltraTex + OpenMontage on the local bench, verified live |
| `eb2d2d01` | 2026-10-21 | feat(brain): provider-scoped tool suite (local bench vs cloud lane) |
| `063cdb8b` | 2026-10-21 | feat(bojo): 100-item improvement register + creative/standard/thinking modes |
| `5c0195a5` | 2026-10-21 | feat(video): five-clip batch measured - 57 min for 25 seconds of finished video |
| `60258a2b` | 2026-10-21 | feat(video): first measured local clip - 5.04s from a still in 11.5 min |
| `2a879d9a` | 2026-10-21 | research(video): scan 38k open models/repos for the 5-10 clip ad pipeline |
| `eb0b3e70` | 2026-10-21 | docs(etsy): printables playbook - specs, build paths, packaging, policy |
| `663bedef` | 2026-10-21 | research(etsy): quick-money addendum - Alibaba timing, seed import law, speed ranking |
| `a3392829` | 2026-10-21 | research(etsy): product deep dive - small/high-margin evergreen+Q4 lane |
| `b6f190af` | 2026-10-20 | perf(brain): lock the standing profile for spend, accuracy, coding and deep work |
| `529c21f2` | 2026-10-20 | perf(brain): cut overthinking 4.3x with a reasoning discipline + level whitelist |
| `d7e6b62f` | 2026-10-20 | perf(brain): stop the token cap from deleting answers, keep the brain resident |
| `1a4f595f` | 2026-10-20 | Termly mobile bridge: live OpenCode session notes + global install |
| `d9ca2f89` | 2026-10-20 | Resolve both gaps: a real local voice engine + a stream-real voice harness |
| `1cedf70f` | 2026-10-19 | MOGRA J-series: drop dead cutout helper (no scipy import at module load) |
| `79cc66e1` | 2026-10-19 | MOGRA J-series: operator concept designs (Olive+Kraft, Botanical Luxe) with real Hericium art and live label data |
| `876cef00` | 2026-10-19 | Voice picker + frame-rate-independent theme easing + honest optional-engine 503s |
| `f454d462` | 2026-10-19 | Galactic 6-20: filaments, aurora, terminator, ring shadow, shimmer, fringe, dither, toe, vignette, dual grain, breathing, horizon shimmer, tinted comet, idle dim |
| `c951e36b` | 2026-10-19 | Voice loop: mic harness (fake audio device) + fix stale-message speak |
| `e95030a3` | 2026-10-19 | Item 2: duplex voice loop (server TTS route tested; client wired with barge-in) |
| `0ae72fdb` | 2026-10-19 | Items 3+4: operator uploads + galactic 1-5 (+ composer controls for item 1) |
| `cf2fbe81` | 2026-10-19 | Items 1+5: turn contract v2 (media/thinking/style/attachments) + paid execution |
| `0274c6e5` | 2026-10-19 | Bojo creative flow: job-scaled credit pricing, plan -> confirm, plan card, rollback |
| `34842edd` | 2026-10-19 | Report: designed PDF of the pipeline v2 improvements (+ email helper) |
| `85b813ed` | 2026-10-19 | chore: add @termly-dev/cli 1.9.5 as devDependency |
| `cfd2f389` | 2026-10-19 | N-2 trust surface: measured operational status (+ N-1 decisions resolved) |
| `ac148407` | 2026-10-19 | State: canonical runner RED is four untracked Sep-27 costco files, not a regression |
| `0130625b` | 2026-10-19 | Test: frozen-file boundary resolves the repo root, not the cwd |
| `cefb89cf` | 2026-10-19 | Guide: add the pouch-calibration command (and verify the prepress CLI form) |
| `57b2607d` | 2026-10-19 | Report addendum: Wave 2 completion, readiness, gamut mapper, PDF lane, calibration, test fix |
| `02850498` | 2026-10-19 | Test isolation: reasoning routes no longer depend on suite order |
| `64adafe4` | 2026-10-19 | Pouch calibration: the tape-measure step now produces an artifact |
| `76a0309b` | 2026-10-19 | State: record the ComfyUI-RMBG dependency chase and its measured removal |
| `eba0b16a` | 2026-10-19 | Test: end-to-end creative chain (compose -> MAIN -> prepress -> readiness) |
| `8a9895f9` | 2026-10-19 | Gamut mapper: the prepress blocker now comes with a fix, measured on real artwork |
| `51d902f0` | 2026-10-19 | Docs: operator guide for the creative pipeline v2 lanes |
| `7dc2f985` | 2026-10-19 | Corpus learner: PDF lane (pypdf) + model registry documents the local lanes |
| `fd8c409d` | 2026-10-19 | Package readiness: one verdict across prepress, copy, MAIN and dieline |
| `39f95832` | 2026-10-19 | Report: creative pipeline v2 session (research, realism, edit, cutout, prepress) |
| `eb8d79d9` | 2026-10-19 | Research Wave 2 complete (47,323 repos + 9,513 HF + 829 videos) + credential scrub |
| `47a2fde1` | 2026-10-19 | Studio lanes API: cutout / upscale / MAIN-check endpoints |
| `d11bef41` | 2026-10-19 | Upscale: deterministic LANCZOS lane + RealESRGAN failure recorded (circuit breaker) |
| `b14569ba` | 2026-10-19 | Cutout + Amazon MAIN lane: BiRefNet matting, honest framing, real compliance check |
| `d9fddcb8` | 2026-10-19 | Corpus ingest: Research Wave 2 sources wired into the local index |
| `cfe55d18` | 2026-10-19 | Print lane: prepress/check + prepress/profiles endpoints (ICC check on a real asset) |
| `6c10b986` | 2026-10-19 | Reconciliation proved + suite cleared to zero, T-8 guardrails hardened, 500-item register |
| `2af21953` | 2026-10-19 | Prepress: real ICC CMYK conversion, soft proof, gamut dE, ink-limit check |
| `dbe30682` | 2026-10-19 | Reconcile the 33 pre-existing failures to zero, without hiding any |
| `037134a8` | 2026-10-19 | Doypack planning dieline: real film structure + published-ladder proportion check |
| `b5a61c68` | 2026-10-19 | Edit-drift OCR gate: the edit lane can no longer silently rewrite the copy |
| `62eb9b13` | 2026-10-19 | Qwen-Image-Edit-2511 edit lane + real-plate realism A/B harness |
| `203b0be9` | 2026-10-19 | Corpus Learner (static-fetch) + Research Wave 2 sweeps |
| `13abe01e` | 2026-10-19 | Canvas v2: surface-realism passes in the mockup compositor (Packify-parity P0 steps 1-9) |
| `10fe9537` | 2026-10-19 | Thorn v5.0: phases T-2..T-9 complete (report + state) |
| `5c321e98` | 2026-10-19 | Thorn v5.0 T-8 + T-9: proposal-only evolution loop + BUILD presets |
| `6b779f29` | 2026-10-19 | Thorn v5.0 T-6 + T-7: self-critique evaluator + lane telemetry (wired live) |
| `159904f4` | 2026-10-19 | Thorn v5.0 T-5: privacy boundaries + memory tiers |
| `7ffc718e` | 2026-10-19 | Thorn v5.0 T-3 + T-4: input flexibility paths + deep-research graph |
| `3e41215b` | 2026-10-19 | Thorn v5.0 card T-2: preset-driven galactic visual shifts |
| `6bc6e9e4` | 2026-10-19 | Thorn v5.0 card T-1: purpose commands (read-only self-analysis) + spec-vs-disk reconciliation |
| `2f4018b8` | 2026-10-18 | Simple-mode UI rebuild (V4.2) + film-faithful Gargantua background |
| `f33abef8` | 2026-10-18 | feat(designs): MOGRA logo master v3 - ultra-2K reconstruction (fix muddy v2) |
| `12bb857f` | 2026-10-18 | Fix the foundation concurrency race that broke sign-in + stale shim identity |
| `709a7ce4` | 2026-10-18 | feat(designs): MOGRA identity v2 - sharp 8x logo master + full-lockup stamps |
| `6f1cf387` | 2026-10-18 | Local sign-in repair: pin the foundation store + provision the local operator account |
| `8ec61fa8` | 2026-10-18 | V4.1 Step 4: verification green (drift 35/0, REA 21/0, combined 243/0, build 0 errors, shell 28/0) |
| `575e0c39` | 2026-10-18 | V4.1 Step 3: operator-window REA capture harness (Packify, read-only + gated) |
| `4d02d7d7` | 2026-10-18 | V4.1 S7 5.4: embeddings drift engine (qwen3-embedding:0.6b + sqlite-vec) |
| `5c3022f8` | 2026-10-18 | V3 S5: immersive plan graph (deep-visual pass complete) |
| `de6ad082` | 2026-10-18 | V3 S8: curated corpus + local retrieval (provenance-labelled index) |
| `d3eb0f20` | 2026-10-18 | V3 S7 §5.3: AdPilot negatives/harvest + SourceScout retitle (pipeline ops) |
| `db60b49d` | 2026-10-18 | V3 S5: AutothinK workbench UI — plan / artifacts / runs panel |
| `c67c4ea1` | 2026-10-18 | V3 S5: AutothinK backend — plan graph, artifact browser, run panel |
| `e4ab0cd9` | 2026-10-18 | V3 S7 §5.4: deterministic profile learning from imported SQP |
| `b1b89a90` | 2026-10-18 | V3 S7 §5.3: cross-service SEO surface engine (all five services) |
| `a233b1ec` | 2026-10-18 | V3 S7 §5.2/§5.3: listing revisions + ListingForge SEO hook (seo_check) |
| `a7957974` | 2026-10-18 | report: V3 S7 Brand SEO Profile foundation build report |
| `422bac4f` | 2026-10-18 | V3 S7: canonical versioned Brand SEO Profile (schema, store, service, Grow-focus tool) |
| `41c5de45` | 2026-10-18 | V3 S5: session fork/rewind (non-destructive) — endpoint, lineage, UI, tests |
| `63124d20` | 2026-10-18 | report: V3 REA inject + VoiceStudio UGC pipeline build report |
| `8b211ed1` | 2026-10-18 | state: V3 REA inject (tool gateway, AG-UI cards, HITL handover) + VoiceStudio Create-focus pipeline |
| `49217000` | 2026-10-18 | V3 REA inject (tool gateway, AG-UI cards, HITL handover) + VoiceStudio Create-focus pipeline |
| `dd2d70c8` | 2026-10-18 | feat(designs): i-series 10 unique Lion's Mane bags + prominent back logo fix |
| `498c1d7d` | 2026-10-18 | feat(shell-v3): cinematic cosmic grade + hardware governor + glass shell (V3 S6) |
| `7de74346` | 2026-10-18 | feat(designs): Lion's Mane 6oz series (mfr 130x210+40) - 10 all-new designs, new type system (Cormorant+Jost), seal/ledger/contour/wreath devices, About Lion's Mane + logo on backs; arc-text + memory-lean print engine |
| `e165c31a` | 2026-10-18 | feat(shell-v3): Simple-first Master Brain shell + focus rail + cosmic canvas (V3 S4/S5/S6) |
| `9aadb70e` | 2026-10-18 | feat(shell-v3): capability gate + focus modes + hardware telemetry (V3 S4 backend) |
| `6d4e8479` | 2026-10-18 | feat(designs): earth-tone bag collection - 10 new bag styles with a NEW MOGRA ORGANICS front logo/print (sprig + serif wordmark, 3 variants), About Us + real logo on every back, flat single-folder export mode |
| `1487833d` | 2026-10-18 | docs: Creative Studio simple-mode deep scan — 100 grounded improvements (audit only, no code change) |
| `483ad620` | 2026-10-18 | feat(mockups): sharpness pass - 2x compositing (2048 mockups), filtered art pre-scale, grain removed, tighter emboss bevels; logo reads as a real brand mark |
| `5012f251` | 2026-10-18 | fix(designs): emboss the real logo - full artwork detail in the relief (tone-ramped ink keeps letters/mortar/tagline, leaf-green tint, outer rim + inner-edge bevel) replacing the flattened tone fill |
| `a339ce0e` | 2026-10-18 | feat(designs): bag series 2 (bags only) - real logo ETCHED into the bag (blind deboss bevel from the logo silhouette, foil-emboss variant); 5 new concepts b06-b10; subset export flags on both runners |
| `01c518ae` | 2026-10-18 | feat(mockups): print-integration engine v2 - designs printed INTO the package (silhouette-following mapping, baked photo lighting, wrinkle emboss, calibrated plate anchors), white studio plates, paper-texture pass on all art |
| `bd5dbd13` | 2026-10-18 | feat(designs): bold redesign - Bulk-grade fronts (Anton display, value capsule, organic seal) + fully dressed two-column backs; motif fit fix; new bold export packs |
| `97e4ef25` | 2026-10-18 | feat(mockups): shelf-ready package mockups - 10 designs wrapped onto photoreal plates (homography pouch + cylindrical tube with safe-arc design discipline), front + back each |
| `cd27ea27` | 2026-10-18 | feat(labels): fully dressed back labels - complete Supplement Facts (placeholder values), real UPC-A + QR, styled lot/best-by; requirements doc now lists exact placeholder replacements |
| `ef3ae206` | 2026-10-17 | feat(designs): MOGRA design system - 10 premium concepts (5 bags + 5 canisters) x front/back at 300dpi, refined 4x logo master, creative placements, regulatory placeholder zones + requirements doc |
| `636ab5d6` | 2026-10-17 | feat(dieline-art): model motifs extracted from raw renders (median-ground ink extraction) placed on true-scale label sheets - model art + perfect composited text |
| `9b76a199` | 2026-10-17 | ux(guardrails): rich renders are the default - text-safe becomes opt-in for Type-pass plates; neutral style suffix; UI default off |
| `189327a8` | 2026-10-16 | feat(chat): S2 tool registry + ComfyUI progress bridge + tool loop, S3 local voice PTT; live-verified (render progress frames, Ollama tool roundtrip, whisper smoke); backend restarted |
| `7861b4e9` | 2026-10-16 | research(v2): Master Plan V2 tooling sweep - 52 query families, 1904 repo records (1797 unique), HF datasets, curated report + reconciliation flags |
| `1147bab2` | 2026-10-16 | docs(state): S0/S1 milestone + evidence report (pre-existing failure attribution, harness drift log) |
| `9e62b166` | 2026-10-16 | feat(chat): S1 chat core - SSE turn stream (thinking split, cancel, partial persistence), additive chat_* migration, Creative Chat shell (Simple mode); stream_chat on UnifiedLLMAdapter; fix design-agent adapter call |
| `c58afe7e` | 2026-10-16 | feat(shell): global Simple/Advanced mode provider + Editorial Ink token scope (S0) |
| `b92eefab` | 2026-10-16 | feat(print): dieline-art lane - true-scale doypack sheets with real logo/type/drawn icons (grounds, reserved facts/QR/UPC zones, 300dpi PNG + font-embedded PDF) |
| `8b0a5e9a` | 2026-10-16 | docs(oss): record the Boxes.py adoption in the packaging scan |
| `14f4e5b6` | 2026-10-16 | feat(dielines): Box library - 12 real box structures from Boxes.py (external GPL-3.0 tool, pinned commit, separate process), generate/preview/download in Dielines & Print; API + harness 13/0; runner gains harness 40 |
| `79cd0829` | 2026-10-16 | fix(private-lane): 9B stability root-caused to the sd.cpp-converted GGUF - swapped to native QuantStack 9B-KV-Q8 as default; acceptance sequence passed (mixed 4B/9B, consecutive fresh renders, server stable, zero compat warnings) |
| `7469e38a` | 2026-10-16 | feat(print+text): doypack dieline template (true-scale, bleed/zip/weld marks); SVG inkscape namespace fix (standalone SVG rendered blank in browsers); text cleanup v2 = gradient-aware reconstruction + 2 passes + raw render preservation |
| `d1fc8cb5` | 2026-10-16 | research(oss): packaging/dieline scan - Boxes.py (GPL-3.0, external-tool candidate), FEFCO workbench, Blender carton addon; Canva-class editors verified (vue-fabric-editor MIT; tldraw declined for license); no-leaked-code posture recorded |
| `a1a5f4f8` | 2026-10-16 | art(compositor): P0 realism v2 shipped - luminance displacement + grain sync + soft-light/specular (A/B evidence); step4 AO deferred with rationale; PLAN P0 marked done |
| `b45ca7fa` | 2026-10-16 | default(private-lane): klein 9B + qwen_3_8b are the studio defaults; unload crash root-caused (our /free -> unload_all_models -> GGUF unpatch AV) and fixed via opt-in release_models; verified 2 consecutive renders server-stable |
| `e4052857` | 2026-10-16 | verify(private-lane): klein 9B smoke PASS through the studio lane (33.3s draft) - 9B needs qwen_3_8b encoder (pulled, auto-paired); known GGUF unload crash documented; engine reports true model name; smoke render committed |
| `37277760` | 2026-10-16 | feat(compositor): deterministic typography pass - homography warp + shading, logo roundel, vector cert icons, service API, UI Type-pass; conftest rate-limit default |
| `ac226e8f` | 2026-10-16 | chore: refresh the fidelity-trial report from the Phase 5 regression run |
| `c0f7b1f8` | 2026-10-16 | test(phase5): full 39-harness regression re-run (39/39 clean) + screenshots_20261016 + final room audit; smoke harness dismisses the first-run guide; ProductFinder useEffect import fixed; invite script verified; execution report closed out |
| `13064d55` | 2026-10-16 | fix(private-lane): klein 9B needs its own qwen_3_8b encoder - engine honors STUDIO_TEXT_ENCODER; smoke script pairs them automatically (dims mismatch diagnosed from live error) |
| `8201d12c` | 2026-10-16 | feat(private-lane): klein 9B Q8 GGUF (9.29GB) + refcontrol LoRAs installed; official refcontrol workflow JSONs saved; 9B smoke script through the studio lane |
| `162e0477` | 2026-10-16 | ops: partner-invite helper script; plan doc carries the execution status (Phases 0-4 done, Phase 5 in progress); monitoring overlay started (Kuma + Dozzle, loopback) |
| `6d54e659` | 2026-10-16 | feat(rea): pattern pass (tryholo fresh read; Canva limitation documented) - Start-from-ASIN seed on home + SourceScout prefill, plan-approve-export framing |
| `d42363fe` | 2026-10-16 | feat(private-lane): NC models allowed for private-brand work - klein 9B Q8 + refcontrol LoRAs pulling, Qwen-Edit-2511 confirmed on disk, flux1-dev blocked on t5xxl; engine honors STUDIO_IMAGE_MODEL override |
| `24bd9458` | 2026-10-16 | feat(ux): first-run guide (3 guided steps, dismissible) + Design Studio quick-start; build banner now carries the commit through Docker build args |
| `8821abb7` | 2026-10-16 | report: one-go production-readiness execution (Phases 0-3 + verification) + final room audit evidence |
| `b3682be2` | 2026-10-16 | fix(harnesses+security): panels harness opens the Details toggle; design-studio harness covers Dielines & Print; engineApi dev-shim gated on the compile-time LOCAL_DEV constant (prod bundle contract restored) |
| `513f5c9b` | 2026-10-16 | fix(customer): Documents + PlanUsage notices match their honest empty states |
| `f00378b1` | 2026-10-16 | research(quality): Packify-grade deep dive - 5,984-repo GitHub sweep, toolchain verdicts (Qwen-Edit-2511/LayerStyle/BiRefNet; license traps), proven Packify photoshoot mechanics + 9-step compositor realism path, REA runbook, master report + phased plan |
| `e43ef707` | 2026-10-16 | fix(rooms): ListingForge TDZ fix; final honesty pass - ProductFinder/SocialPulse/GoldenGoose wording, PlanUsage fabricated usage+billing removed |
| `2dca9c4a` | 2026-10-16 | ops: backup.sh completes the off-machine leg via rclone (LOCAL ONLY when unset), optional monitoring overlay (Uptime Kuma + Dozzle, loopback-only), one-page runbook; SocialPulse label |
| `ee545a05` | 2026-10-16 | feat(ux): task-first home (Start something + Needs your review, system panels collapsed, plain-language sources); work-first nav order; SocialPulse + ProductFinder de-seeded with honest empty states; readiness labels updated (8 rooms now Local) |
| `12ae5f93` | 2026-10-16 | feat(rooms): AdPilot reads imported ad files (real campaigns/terms, honest empties); ListingForge moves to the tenant store (create/update endpoints, no seeds); rate-limit budgets sized for humans; /v1/models compat; build banner |
| `7e0fab18` | 2026-10-16 | art(mockup): logo printed as a real lockup (direct print, no disc/sticker shadow) - real mark raster + Playfair wordmark + tagline; matched-pair type sizing; widen charcoal badge heal |
| `f36c5127` | 2026-10-16 | plan(production): record verified fixes - /engine 200 after rebuild, Caddy serving current build, rate-limit posture note |
| `78b2cdd6` | 2026-10-16 | plan(production): evidence-based production-readiness plan - room audit (25 rooms, screenshots), partial-room kill list, Canva-bar UX workstream, ops + REA program, phased execution; room-audit tool added |
| `7af82dc1` | 2026-10-16 | art(mockup): complete MOGRA front panel - deterministic compositor (real logo roundel + wordmark, Playfair/Inter type, cert roundels, weights) on the studio render; brand assets + report |
| `6b03044d` | 2026-10-16 | research(tooling): production-stack scan - ops layer (restic/rclone, Uptime Kuma, Dozzle, GlitchTip), media-runner reference (ComfyUI HTTP API), finishing primitives (rembg/BiRefNet/SAM2; IOPaint archived), LTX-2 commercial-license flag, Amazon-OSS reality check; consolidated go-live verdict |
| `9136ee88` | 2026-10-16 | art(mockup): MOGRA Forest Dusk text-safe render (text_free, 0 OCR boxes) + sidecar, task report, state entry |
| `f16e2b09` | 2026-10-16 | fix(text-fidelity): bind used_brief before the non-retry return (UnboundLocalError crashed every clean first render) + regression test for the no-retry text_safe path |
| `cf80b36e` | 2026-10-16 | research(tooling): production-quality scan - OpenDesign/Open Builder/CopilotKit verdicts + resolution stack (contract sync, schemathesis, OpenHands, Onlook, CI gates); add MOGRA text-safe render script |
| `a93d77ca` | 2026-10-16 | fix(text-fidelity): clause-level salvage keeps art direction from demand lines (colourways survive; 'Text reads...' clauses drop) |
| `697e67ca` | 2026-10-16 | feat(text-fidelity): enforced text-free render pipeline - prompt guard, OCR check, hardened auto-rerun, deterministic glyph-zone cleanup; VRAM eviction verify + OOM retry hardening |
| `82fa179e` | 2026-10-16 | feat(text-fidelity): text-safe render guard (strips lettering demands) + offline OCR verification for generated assets |
| `f4415ec7` | 2026-10-16 | fix(design-studio): raise brief cap to 20k for long design briefs; readable error extraction in local engine client |
| `055c2e12` | 2026-10-16 | fix(design-studio): tolerate cleared dieline params, clearer plan validation, readable 422 messages in Dielines UI |
| `b62c239c` | 2026-10-16 | feat(design-studio): complete RE build - public API keys + webhooks, scene/product gallery, credit meter admin, Dielines & Print UI section |
| `9aeef1c7` | 2026-10-16 | feat(design-studio): print lane (layered dielines + PDF/ZIP), async generation lane with credit metering, design-brief agent (RE build 2026-10-16) |
| `8d6c7869` | 2026-10-16 | research: record follow-up capture disconnect (no retry) in RE report |
| `297f90ae` | 2026-10-16 | research: Packify.ai & DYP.ai competitive RE via REA (report + evidence pack) |
| `e4465b6b` | 2026-10-16 | docs(design-studio): packaging capability blueprint from GitHub + web survey |
| `e0e17266` | 2026-10-16 | docs(mogra): refine pouch packaging brief to Design Studio engine lanes |
| `65a0ca62` | 2026-10-15 | feat(ui): design pass v2 - smart rail (dots + single workspace header), compact evidence strip (10 pages), studio toolbar, data-first tables; design-review screenshots + local CDP shot tool; rate-limit cookie-bucket fix |
| `454198b5` | 2026-10-15 | fix(rate-limit): cookie sessions resolve to their real bucket (owner=300/min, member=120/min) - SPA browsing no longer trips the 30/min anon limit; engine probe keeps last known state |
| `381efa56` | 2026-10-15 | chore(state): local media engine + chat units - readiness flips (design-studio, autothink) + honest remaining map; state record |
| `aa985272` | 2026-10-15 | feat(local): automatic GPU handshake - brain evicts before renders; launcher keeps ComfyUI alive (one heavy resident at a time) |
| `e6fd1619` | 2026-10-15 | fix(studio): release ComfyUI models + VRAM after each render so the 16GB card keeps the local brain resident |
| `b8a21750` | 2026-10-15 | feat(autothink): chat transcript UI - message bubbles, saved history (answers persisted), scrollable composer (Perplexity-style) |
| `c2401040` | 2026-10-15 | feat(studio): arm the local media engine - ComfyUI runner (klein image, Wan 2.2 video); Generate + Video tabs render on this machine at 0 credits |
| `63560757` | 2026-10-15 | chore(state): record alpha sign-in repair (cookie-aware gate + foundation persistence + signing key); deploy doc update |
| `00b1db59` | 2026-10-15 | test(foundation): sync session-cookie path assertions with the documented P0-04 single-origin decision |
| `7be75df1` | 2026-10-15 | fix(launch): persistent foundation DB + local signing-key wiring so the UI sign-in works end to end |
| `5b279743` | 2026-10-15 | fix(alpha): cookie-aware private-alpha gate + public pre-auth entry points (foundation login/signup/ui-mode, invite lookup) |
| `7c22c1c3` | 2026-10-15 | chore(state): record operator-requested service password reset + gated restart (no values stored) |
| `22bf7949` | 2026-10-15 | chore(state): tier-1 tooling install + private-alpha relaunch record; secret-scan findings + owner actions |
| `fc777ae9` | 2026-10-15 | fix(brain-gate): harden placeholder detection for refusal examples (intermittent FP; probe passes no tools) |
| `a54ad221` | 2026-10-15 | fix(alpha): launcher + deploy doc point at current /ui/ routes (probe, hints, verify table) |
| `6d0ad016` | 2026-10-15 | chore(security): tier-1 secret scanning - gitleaks config + pre-commit hook; agent read guards for env/credential files |
| `50d3fb0e` | 2026-10-15 | chore(launcher): point health hints + URLs at the current brain and /ui/ paths |
| `0e2c7b33` | 2026-10-15 | research: tooling & agents deep dive (safety/speed/creative) - 21 repos API-verified, Tier1-3 recommendations for Mogra go-live |
| `6a4f397b` | 2026-10-15 | state: readiness audit entry (Mogra pre-reboot, all green) |
| `6ad1aec6` | 2026-10-15 | audit: pre-reboot readiness for Mogra Organics - security + ops all green; harden gate leak detector (false-positive fix) |
| `3c68cef7` | 2026-10-14 | Local LLM perf: measured checklist verdicts (MTP +68% on CUDA lane; FA-on and q8 rejected), b11632 CUDA lane script with auto-unload, blob repair + report + state |
| `0d991cdf` | 2026-10-14 | feat(media): ComfyUI stack smoke-verified - klein/seedvr2/wan2.2/TTS all green (5/5) |
| `8d20747f` | 2026-10-14 | feat(media): clip split/concat tool, ComfyUI smoke harness, media stack map (2026-10) |
| `0ccc3232` | 2026-10-14 | feat(llm): pin HIGH reasoning mode on the llama.cpp lane (--reasoning-effort xhigh, unrestricted budget) |
| `79d1a272` | 2026-10-13 | docs(engine): note the Ollama login auto-start entry added for the 27B brain |
| `5db0bf7a` | 2026-10-13 | feat(engine): NorthstarOS Qwen 3.8 27B single-survivor install |
| `d57731b5` | 2026-10-11 | chore(studio): refresh the fidelity-trial report from the Phase 11 regression run |
| `de44b4d9` | 2026-10-11 | test(studio): Phase 11 full regression evidence (39 harnesses, 39 clean), refreshed screenshots, precise panels boundary filter, final report |
| `74a5987a` | 2026-10-11 | docs(studio): Phase 11 checkpoint section, linkage inventory updated for the Phase 11 additions, regression runner script |
| `71933031` | 2026-10-11 | test(studio): section-pack browser harness, AmazonFiles report/correct/compare/onboarding harness coverage, cross-tenant negatives for the new endpoints, fixtures + samples |
| `d19d6cfd` | 2026-10-11 | docs+guards: hosted-readiness package, generation arming package (per-tenant limits, config sketch), dated research assembly, Item Highlights UNKNOWN posture, compose guard covers all ports and opt-outs |
| `b93f45d8` | 2026-10-11 | feat(studio): brief-to-asset loop, section output packs, AmazonFiles report match/correction/comparison/onboarding, master-brain panels in 6 more rooms |
| `41f54c84` | 2026-10-11 | feat(studio): self-host fonts (zero third-party requests) + processing-report match, corrected files, SB/SD deltas, product-detail templates, before/after comparison, A+ copy slots |
| `9f6f5761` | 2026-10-11 | chore: refresh the fidelity-trial report from the Phase 10 regression run |
| `7b4b870b` | 2026-10-11 | chore(amazon-files): close the file-only workstream — docs, regression evidence, screenshots |
| `a45a7e51` | 2026-10-11 | feat(amazon-files): file-only Amazon integration — parsers, change files, approval, round-trip (Phase 10) |
| `21b139d9` | 2026-10-11 | chore(design-studio): re-verify against HEAD 7d3398a + refresh the resume pointer |
| `43e40f9c` | 2026-10-11 | reports: CI wiring delivery (baseline-aware gate; 0 new / 8 known-active / 231 allowlisted) |
| `2d958c3b` | 2026-10-11 | feat(ci): baseline-aware secret gate (known-active stays visible, only NEW fails) + workflow jobs (scan block, gitleaks/audit advisory, SBOM) + local security checker |
| `7d3398a2` | 2026-10-11 | reports: Phase 2 policy kernel delivery report (acceptance matrix; active findings: 8) |
| `56069fde` | 2026-10-11 | feat(policy): Phase 2 policy kernel - allowlist+amazon hard-block, SSRF/rebind, robots, limits, capability grants, approvals, hash-chained audit + 66 acceptance tests (139 total) |
| `6ffac490` | 2026-10-11 | chore(design-studio): close Phase 9 — mask trial paths, housekeeping evidence, full regression |
| `31cbe9a8` | 2026-10-11 | feat(design-studio): read-only master-brain evidence in ListingForge, AdPilot and SocialPulse (Phase 9 item 2) |
| `92d62f71` | 2026-10-11 | feat(design-studio): title rules VERIFIED + flat-file/Item-Highlights contract (Phase 9 items 1, 3) |
| `9dcc1690` | 2026-10-11 | reports: archive credential review for scrub decision (active findings: 8; option A recommended) |
| `66a912ad` | 2026-10-11 | feat(security): env-only config loader (Phase 1) with 9 tests; tooling doc updated (73 security tests total) |
| `3d7c7d49` | 2026-10-11 | chore(design-studio): close Phase 8 — PG lock fix, docs, full regression evidence |
| `e2558073` | 2026-10-11 | feat(design-studio): 3D scene undo/redo + layer reorder; performance-loop labels (Phase 8 items 6-7) |
| `dafd0399` | 2026-10-11 | feat(design-studio): local fidelity trial harness (Phase 8 item 5) |
| `cb62184c` | 2026-10-11 | reports: Phase 1 addendum (gitleaks results, second escalation SCAVIO/BRIGHTDATA keys, allowlist+v4) + threat model draft for owner review |
| `9aeac6b9` | 2026-10-11 | chore(security): supply chain - gitleaks 8.30.1 pinned+checksummed tooling doc + uv adoption with committed uv.lock (34 packages) |
| `ab8a2c83` | 2026-10-11 | feat(security): v4 rules (multi-prefix GitHub/github_pat_, sk_, compound env names, JSON keys) + fingerprint-exact allowlist + 64 tests |
| `f3eef9e2` | 2026-10-11 | chore(design-studio): label the synthetic test tenants + cleanup script (Phase 8 item 4) |
| `dd0c2a25` | 2026-10-11 | feat(design-studio): listing context moves to the tenant store with a one-shot migration (Phase 8 item 3) |
| `8c382fbb` | 2026-10-11 | feat(design-studio): Phase 8 registry updates — title length, AI-people window, formats, no-10MB, A+ eligibility |
| `dace8fee` | 2026-10-11 | reports: Phase 1 secret-scan findings - 1 escalation (chat-export PAT), 3 review items, 5 test-fixture allowlist candidates |
| `4b986bf2` | 2026-10-11 | feat(security): Phase 1 - offline secret scanner v3 (precision-tuned, 26 tests) + gitleaks/pre-commit/CI scaffolding + .gitignore hygiene |
| `902a2007` | 2026-10-11 | feat(data-layer): real Postgres support for the Design Studio store + PG harness (Phase 8 item 2) |
| `cda7e064` | 2026-10-11 | feat(security): Phase 1 - log redaction filter/formatter wired into logging_config; tests/security harness (23 tests) |
| `2f7ac89f` | 2026-10-10 | chore(design-studio): close Phase 7 - D10 reports, gate semantics, full regression evidence |
| `5abacf67` | 2026-10-10 | feat(design-studio): listing integration, brand-voice/keyword ingestion, performance loop |
| `94d6d8d3` | 2026-10-10 | feat(design-studio): close the Projects and 3D capability gaps (Phase 7 item 4) |
| `b9548fcd` | 2026-10-10 | reports: Phase 0 audit - service/browser/provider/security inventory for secure control-layer build |
| `d099b16e` | 2026-10-10 | feat(design-studio): Phase 7 items 1-3 — D10 identity migration, shim fail-closed, limiter guard |
| `4ce693ee` | 2026-10-10 | research(lions-mane): 1-32oz market rebuild - market/clean/review/excluded lenses, category-aware BSR ranking, validation suite |
| `c91b4a03` | 2026-10-10 | reports: external AI tool scan (9 sources) + YouTube clips channel assessment |
| `e3bfe2d7` | 2026-10-10 | chore(design-studio): close Phase 6 — audit, freshness, migration e2e, full regression evidence |
| `4c068511` | 2026-10-10 | feat(design-studio): imported marketplace evidence, briefs, variant comparison, indexing register |
| `4da7a686` | 2026-10-10 | fix(design-studio): legacy redirects must carry the sub-view (?view=) |
| `f64c9ad3` | 2026-10-10 | feat(design-studio): test build for the pixel paths; shim out of served bundles; deploy compose guard |
| `b2505d97` | 2026-10-10 | fix(auth): dev sign-in — verify the shim, fall back to real login, never fail silently |
| `080d056e` | 2026-10-10 | feat(design-studio): land the Phase 0 merge — one /design-studio route, empty seeds |
| `27a649bd` | 2026-10-10 | ﻿fix(design-studio): root-cause the compositing harness hang; add mode flag + watchdog |
| `afc0bc8c` | 2026-10-10 | feat(design-studio): compositing on all sections, tenant-scoped re-check log, generation path unarmed |
| `5880ba68` | 2026-10-10 | fix(design-studio): wire the upload check and re-check library into the UI |
| `de32c5d4` | 2026-10-10 | feat(design-studio): compositing canvas, identifiability gate, exemption verification, text rules |
| `61468122` | 2026-10-10 | feat(design-studio): AI-people disclosure, fidelity track, policy freshness, lossless migration |
| `db17322f` | 2026-10-10 | feat(design-studio): SP video sourced, Display video reconciled, rule coverage states, tenant-scoped persistence |
| `eb286b8f` | 2026-10-10 | feat(design-studio): all 9 sections on the shell, rule fixture test, registry confidence + degradation fix |
| `886368af` | 2026-10-10 | feat(design-studio): Phase 2 editor shell + Amazon spec registry + compliance pre-flight |
| `ad62b3a2` | 2026-10-09 | fix(shell): the role-vocabulary mismatch that emptied the suite rail and blocked the admin rooms |
| `16a99099` | 2026-10-09 | fix(auth): three real session bugs found standing up the local operator sign-in |
| `2a93d846` | 2026-10-09 | docs(overnight): completion report; record the pre-existing failure baseline |
| `3743ee41` | 2026-10-09 | docs(Phase 10): Oracle Always Free deploy package; A1-A9 defaults applied with evidence |
| `1395b255` | 2026-10-09 | fix(Phase 8): SERVICE_INVENTORY gains Design Studio + research tree; correct the stale S02/S04; fix the last wrong A+ dimension |
| `6c525127` | 2026-10-09 | feat(Phase 7): 31-route screenshot sweep green; honest readiness labels and provenance copy |
| `04c42576` | 2026-10-09 | fix(Phase 4): ASCII startup log line — a non-ASCII char crashed the server on Windows |
| `cdbcbc5d` | 2026-10-09 | fix(Phase 6): SourceScout default view no longer shows invented market data |
| `d76324a0` | 2026-10-09 | feat(Phase 5): live test runner + local-lane regression with a real completion |
| `4e6d14a5` | 2026-10-09 | feat(Phase 3): six isolated test roles, invite lifecycle, fix verify-live-signin |
| `5e5dac0f` | 2026-10-09 | fix(P1-01, P1-02, P1-04): silent failures now surface; update the stale autothink route tests |
| `8e7f9b68` | 2026-10-09 | fix(P0-02, P0-03, P1-05, P1-08): one hosted entrypoint; route contract test; env parseability; worker readiness |
| `6f76bd1f` | 2026-10-09 | feat(P0-04, P1-15..P1-18): authenticated, tenant-scoped AutothinK with grounding, metering, idempotency and cancellation |
| `1f38c067` | 2026-10-09 | fix(P0-01): refuse to boot an unbounded live-provider mode; prove GETs open zero provider connections |
| `93879a3b` | 2026-10-09 | docs(state): creative cluster complete — Product Designer, Design Studio, ListingForge, SocialPulse, AdPilot |
| `e5c149dd` | 2026-10-09 | feat(studio): Amazon compliance pre-flight as a hard gate, not a document |
| `c723cf08` | 2026-10-09 | feat(studio): brand profile + approve-only loop, verified A+ specs, output breadth |
| `b48cd3b4` | 2026-10-09 | docs(design studio): correct the creative inventory — the repo moved under it |
| `32daa086` | 2026-10-09 | research(design studio): phase 3 amazon compliance + phase 4 seller voice |
| `d67e83a1` | 2026-10-08 | feat(studio): ListingForge, SocialPulse and AdPilot gain real creative capability |
| `000df819` | 2026-10-08 | design studio: research, design inventory, and concept renders |
| `6bfafcbc` | 2026-10-08 | feat(studio): Design Studio — one room for ads, social, A+ content, image and clip requests |
| `f232ef80` | 2026-10-08 | feat(studio): Product Designer service — local scene designer, real 3D packaging view, mockups, provider-gated generation queue |
| `24820484` | 2026-10-08 | hosted reasoning hardening: fail-closed model selection (no silent fallback to unverified), structured no-model error, status API exposing provider/base/endpoint/configured/enabled/verified/intended-role, creative separation enforced, 65 tests |
| `0b6181ce` | 2026-10-08 | hosted reasoning: OpenCode Go correction report |
| `78c86008` | 2026-10-08 | hosted reasoning: reconfigure to the OpenCode Go contract (base /zen/go/v1, bare model IDs, provider id opencode-go); verify step-5-preview-free with a real HTTP 200 completion; correct config template and docs |
| `191d7cd9` | 2026-10-08 | hosted reasoning: live verification report (Zen endpoint/IDs/pricing corrections, FreeTier constraint, Step 5 policy) |
| `a2dc6831` | 2026-10-08 | hosted reasoning: correct Zen endpoint/model IDs/pricing, add Step 5 policy default with provider-blocked reporting, classify FreeTier/insufficient-funds errors, 49 tests |
| `ecf6b4c5` | 2026-10-08 | hosted reasoning: final integration report |
| `7eaa0d51` | 2026-10-08 | hosted reasoning: configuration and constraint documentation |
| `18ea9708` | 2026-10-08 | hosted reasoning: route-level integration tests (mocked) |
| `27b3e9f4` | 2026-10-08 | hosted reasoning UI: model selector, AutothinK hosted lane, ListingForge proposal panel, AdPilot ad-copy panel, Spreadsheet Lab page, nav/readiness wiring |
| `dd5e8d95` | 2026-10-08 | hosted reasoning: provider-neutral OpenCode Go adapter, task workflows (listing/ad/spreadsheet/generic), routes, config template, mocked tests |
| `d9f7fa8a` | 2026-10-07 | docs(agents): guardrails are operator-owned (operator-authorized) |
| `752cbfe1` | 2026-10-07 | docs(agents): add Browser control (Chrome Connect) section to capsule |
| `56ed3315` | 2026-10-07 | service complete: activate entitlement override + cancel + archive (OrgDetail) and support triage (Beta-Ops); confirmation + audit + honest states; write-path doc updated |
| `aef5aba3` | 2026-10-06 | service complete: Golden Goose real evaluate panel (10 mandatory gates + economics readiness -> backend decision state) |
| `e73f97b1` | 2026-10-06 | service complete: AutothinK real composer with local Ollama + cloud OpenRouter provider selection; real run call; sample runs removed |
| `f973c8ee` | 2026-10-06 | service complete: Listing Guardian + Competitor Monitor local-only (real local records; sample tabs removed; harness headings preserved) |
| `62aa5e5c` | 2026-10-06 | service complete: Command Center fully real (signals/queues/activity/launch); sample briefing tabs removed; verify-smoke /home deep-links updated; readiness->ready |
| `66b1517d` | 2026-10-06 | service complete: Profitability real-only (economics engine authoritative); fabricated portfolio/scenarios/inventory removed; harness headings preserved |
| `b68fc17a` | 2026-10-06 | service complete: internal systems (Memory Bank, Shared Data Layer, Provider Adapters, Master Brain) fully real; fabricated rows removed |
| `3cddf25e` | 2026-10-06 | service complete: customer account surfaces (Workspace/Account/Setup/Documents) on real entitlements/session/onboarding/legal; fabricated rows removed |
| `98d13da7` | 2026-10-06 | service complete: Beta-Ops overview/cohorts/support/reports/audit/eligibility fully real (no fabricated rows); verify-admin sample-export assertion updated |
| `b2a83b57` | 2026-10-06 | service complete: Commerce Ops fully on real local identity queue + runs + approvals; harness assertion updated; readiness->ready |
| `496c192d` | 2026-10-06 | service complete: Keyword Tracker fully on real local + foundation keyword data; sample tabs removed; readiness->ready |
| `761bce31` | 2026-10-06 | service complete: Monitoring fully derived from real local reads (alerts/health/staleness); no sample; readiness->ready |
| `9fdd34d3` | 2026-10-06 | phase3: canonical non-creative remaining-work backlog doc |
| `3aeff97b` | 2026-10-06 | phase2: real local knowledge-plane sessions read for Master Brain |
| `2fac1247` | 2026-10-06 | phase2: real local keyword sets (Keyword Tracker) + source refresh registry (Shared Data Layer) |
| `ab1ab2e3` | 2026-10-06 | phase2: real local market observations for Competitor Monitor + local activity feed for Command Center (readiness: competitor->partial) |
| `fe92b45b` | 2026-10-06 | phase2: real local reads for Commerce Ops workflow queue + Listing Guardian records (readiness: guardian->partial) |
| `b2a4b398` | 2026-10-06 | phase1: read-only non-creative API over local data (commerce-ops queue, listings health, competitor observations, activity, keywords, sources, sessions, accounts) + tests |
| `435c9a1b` | 2026-10-04 | fix dead visible controls: wire/narrate Downgraded, AutothinK, Command Center, Commerce Ops, Golden Goose, Profitability buttons |
| `b4ee796b` | 2026-10-04 | master brain: real dual-engine model catalog read (presence-only) |
| `3e7ec768` | 2026-10-04 | customer legal/account surfaces: real legal reads, real suspension state, honest recovery/reaccept disabled states |
| `8a15d5a7` | 2026-10-04 | activate plan/tier change (platform-admin only) on OrgDetail: cohort select, confirmation, no-op guard, audit visibility; doc update (harness unchanged) |
| `6fa4bdc3` | 2026-10-04 | activate grant/activate (platform-admin only) on OrgDetail: checklist-gated admission, confirmation, audit visibility; doc update (harness unchanged) |
| `8af2206d` | 2026-10-04 | activate lifecycle suspend + resume (platform-admin only) on OrgDetail: confirmation, reason, audit visibility, state guards; doc update (harness unchanged) |
| `1331617e` | 2026-10-04 | activate dashboard export CSV (platform-admin only): safe-set disclosure, confirmation, honest states; update verify-admin + write-path doc |
| `0d41be8f` | 2026-10-04 | activate invite revoke (platform-admin only): confirmation, reason, audit visibility, honest states; update verify-admin + write-path doc |
| `2a4f3f9e` | 2026-10-04 | activate invite issue (platform-admin only): confirmation, audit visibility, honest states; update verify-admin + write-path doc |
| `acc179b3` | 2026-10-04 | build: split vendor chunk (removes 500kB bundle warning) |
| `90e741ff` | 2026-10-04 | shared data layer: real data-readiness read (warehouse, file checks, catalog, services) |
| `9ed34bde` | 2026-10-04 | support: real ticket detail read + /support/:id route (queue deep-links) |
| `ff4f3fca` | 2026-10-04 | command center: live work-queue counts (golden goose + foundation approvals) |
| `a73d1165` | 2026-10-04 | internal admin: real readiness + provider-presence read (config stays sample) |
| `ca13157e` | 2026-10-04 | customer account: fix broken AccountStatus imports + real entitlements reads (workspace/account) |
| `2847ce1f` | 2026-10-04 | memory bank: real knowledge search + learning playbooks reads (local, no external calls) |
| `cb3b410c` | 2026-10-04 | autothink: real engine status + session history reads (provider-gated, sample runs labelled) |
| `30e435ef` | 2026-10-04 | beta-ops org detail: local-only operator note draft composer (no POST) |
| `7be63aae` | 2026-10-04 | beta-ops: lifecycle confirmation scaffolding + eligibility/export authorization notes |
| `16cc0681` | 2026-10-04 | beta-ops invites: authorization-boundary notes on disabled issue/reissue/revoke |
| `801407ba` | 2026-10-04 | write-path design: authorization map doc + shared AuthorizationNote component |
| `914ffffb` | 2026-10-04 | provider adapters: credential presence + scanner gate context, names only (D) |
| `adebb56a` | 2026-10-04 | monitoring: detailed backend health probe (files, scanner, readiness reasons, provider key presence) (C) |
| `83fe9a42` | 2026-10-04 | beta-ops org detail: embedded real tickets + audit with deep links (B) |
| `021b36d9` | 2026-10-04 | beta-ops invites: real org-scoped invite list + status-aware invite detail (A) |
| `60df9c0f` | 2026-10-04 | invite accept: additive real code lookup (harness-safe demo flow preserved) |
| `0c349097` | 2026-10-04 | private-beta account: real plan/usage, support, onboarding, legal, provider-registry reads |
| `365d5373` | 2026-10-04 | beta-ops admin: real foundation dashboard, org roster/detail, support queue, audit log reads |
| `cc0b9371` | 2026-10-04 | monitoring: real live checks (error rate, readiness, warehouse) |
| `50715c6e` | 2026-10-04 | competitor monitor: real cached market observations panel (room stays sample) |
| `3cf1a55d` | 2026-10-04 | commerce ops: real foundation approvals read (partial readiness) |
| `4ae28bd5` | 2026-10-04 | profitability: authoritative backend economics engine panel (partial readiness) |
| `70010c62` | 2026-10-04 | listing guardian: listing triage grouping + honest watchtower source status |
| `e38731dc` | 2026-10-04 | command center: live system signals + service launch pathways (partial readiness) |
| `4489cf1a` | 2026-10-04 | non-creative suite: fix root build scripts, truthful readiness badges, foundation keyword read, dead-surface manifest |
| `900d6905` | 2026-10-04 | turmeric sourcing: run 3 BLOCKED - isolation unprovable for all profiles; allowlist edit would move guardrail fingerprint; zero observations |
| `a8056a6f` | 2026-10-04 | turmeric sourcing: run 2 checkpoint - tool surface verified clean, preflight refused, zero observations |
| `665be71d` | 2026-09-30 | Add opt-in Rainforest API adapter with mock-only tests |
| `bd8e3853` | 2026-09-30 | Master-plan local completion — final report (Items 1-6 green locally) |
| `4c43124d` | 2026-09-30 | Item 5-6 (LOCAL): memory-limits review + runbook completion records |
| `62a2fef3` | 2026-09-30 | Item 4 (LOCAL): admin workflows verified — sample-mode UI harness + backup/restore drill + SOP |
| `147e8524` | 2026-09-30 | docs: record owner-leaning defaults (notes only, not implemented) |
| `cce95855` | 2026-09-30 | Item 3: evidence-based Golden Goose Top-5 scheduler/snapshot scope |
| `52433335` | 2026-09-30 | P4-T3b: record conservative defaults + update BUILD_STATE/00_STATE (assumptions A-01..A-06, OA-7 retained) |
| `cbc824fc` | 2026-09-30 | P4-T3b: wire data-rights provenance projection at GG customer/api boundary |
| `e5e7b26a` | 2026-09-30 | reports: Parallel B Creative Studio + SocialPulse session report |
| `124d5642` | 2026-09-30 | docs: Creative Studio + SocialPulse local status |
| `a5936ce1` | 2026-09-30 | SocialPulse: local content-operations workspace |
| `c5aa0544` | 2026-09-30 | audit/local-readiness: local runbook, service readiness matrix, service gaps + offline boot-check (Parallel Session A) |
| `05a4ea2d` | 2026-09-30 | Creative Studio: honest local creative-ops workspace |
| `6302f056` | 2026-09-30 | P5-T4: acceptance harness GG review/decision persisted round-trip (+5 assertions, 32/0) |
| `5cb248b4` | 2026-09-30 | P5-T4: wire Golden Goose Review + Decisions to persisted org-scoped routes (demo fallback preserved) |
| `f2a287a0` | 2026-09-29 | OA-1: flag pasted extension token as exposed (not used/stored); bridge still stale |
| `f30c1513` | 2026-09-29 | P5-T4 slice: golden-goose client methods + persisted queue panel + focused harness |
| `48d9ab48` | 2026-09-29 | OA-1: select Profile 6 (explicit --profile-dir-name); reconnect required, Oracle not opened |
| `c8e1d498` | 2026-09-29 | OA-1: selection-aware ChromeControl launcher in Northstar (remove Profile 6 pin); STARTUP_SELECTION_WORKING, live-switch not implemented |
| `ef57b62c` | 2026-09-29 | OA-1: record stale chrome-t2 PIDs; awaiting owner approval to clean up |
| `bd804481` | 2026-09-29 | OA-1: recheck still chrome-t2/about:blank; keep PARTIAL (no global edit, no process kill) |
| `c1f7b9f8` | 2026-09-29 | P5-T3: Golden Goose persistence (round-trip items/decisions, org-scoped) |
| `4ff2a51e` | 2026-09-29 | OA-1: project-local MCP override to Profile 6 extension; diagnose global chrome-t2 mismatch |
| `36465e9d` | 2026-09-29 | OA-1: bridge not attached after restart; awaiting owner extension approval |
| `97d80448` | 2026-09-29 | OA-1: BUILD_STATE row (Profile 6 config change, restart required) |
| `94963d57` | 2026-09-29 | OA-1: select confirmed Oracle profile (Profile 6) for extension attach; restart required |
| `c279d232` | 2026-09-29 | P5-T3: deterministic never-padded Top-5 selection + registered job (snapshots/schedule deferred) |
| `29685aa3` | 2026-09-29 | OA-1: record exact supported extension-attach owner steps (no profile data copied) |
| `ab8ea370` | 2026-09-29 | OA-1: update BUILD_STATE row (ChromeControl profile mismatch) |
| `5a1c30bc` | 2026-09-29 | OA-1: record ChromeControl profile mismatch (verification blocked, no profile data copied) |
| `e2690c51` | 2026-09-29 | P5-T2: Golden Goose decision routes (score alone never PURCHASE_READY) |
| `9a5b4a3b` | 2026-09-29 | P5-T1: update 00_STATE.json (next P5-T2, OA-1 answered) |
| `4e65a657` | 2026-09-29 | P5-T1: Resale Score spec (pure, versioned, missing=unavailable, ROI informational) |
| `725ebf39` | 2026-09-29 | protocol: persist continuous-execution workflow + owner action queue |
| `67079589` | 2026-09-29 | P4-T4: per-field freshness policy (OBSERVED/CACHED/UNKNOWN for gates) |
| `2871116a` | 2026-09-29 | P4-T3: data-rights register + external-use enforcement (INTERNAL_ONLY blocked from customer/export) |
| `42fd9974` | 2026-09-29 | P4-T2: identity ingest contract (tables, idempotent ingest, registered job, tests); correct P4-T1 source facts |
| `1fe1a7ca` | 2026-09-29 | DEPLOY-F1 verify: resolved-config port exposure regression test + verification ledger |
| `8d555fbf` | 2026-09-29 | P4-T1: pack-count diagnostic (PARTIAL) + exact unread-source artifacts |
| `005d867c` | 2026-09-29 | DEPLOY-F1: update 00_STATE.json (owner free-hosting decision, deploy cards) |
| `97d53665` | 2026-09-29 | DEPLOY-F1: local architecture preflight + hosted config separation + ARM64 build evidence |
| `7ce67767` | 2026-09-29 | P3: update 00_STATE.json (Phase 3 complete; next P4-T1) |
| `d61bef2d` | 2026-09-29 | P3-T4: labeled demo dataset toggle (SAMPLE-isolated, owner-only, never PURCHASE_READY) |
| `7bc4838f` | 2026-09-29 | P3-T3: prove Owner Test Mode does not bypass non-bypassable controls |
| `0f8d0bd0` | 2026-09-29 | P3-T2: complete owner test-mode bypasses (entitlements, quotas, env safety, per-bypass audit) |
| `dec1d8e4` | 2026-09-29 | P3: update 00_STATE.json (owner answer P2-T6=B, P3 progress) |
| `3f3d0564` | 2026-09-29 | P3-T2 (partial): RBAC bypass + owner_test_mode audit + self-approval gating (default off) |
| `0d9354b0` | 2026-09-29 | P3-T1: Owner Test Mode flag/scope/banner (off by default, audited, owner-only) |
| `2ff92d1d` | 2026-09-29 | P2-T6: reconcile BUILD_STATE/00_STATE (P2-T6 PARTIAL, hosted acceptance pending) |
| `df4f9664` | 2026-09-29 | P2-T6: add live sign-in walkthrough harness (cookie session, CSRF, guards, console/network) |
| `75be8157` | 2026-09-29 | P2-T5/T6: shared DB-backed login throttle + hosted fail-closed without shared store |
| `03f63f24` | 2026-09-29 | P2-T5/T6: login fails closed without signing key; LOCAL VERIFICATION results |
| `9d049d36` | 2026-09-29 | P2-T5: update 00_STATE.json (next_batch, baseline, history) |
| `b7a5efe2` | 2026-09-29 | P2-T5c: real cookie sign-in UI, /me-based session, explicit local-dev shim; harnesses green |
| `edc8d72a` | 2026-09-29 | P2-T5b: Foundation login endpoint + HttpOnly cookie session + CSRF + logout |
| `c7e0e011` | 2026-09-29 | P2-T5a: update 00_STATE.json (next_batch, baseline, history) |
| `60f6dad1` | 2026-09-29 | P2-T5a: owner credential store (bcrypt) + migration 008 + interactive bootstrap CLI |
| `c68821b5` | 2026-09-29 | P2-T5: record recon and implementation plan (partial) |
| `1bd6e03a` | 2026-09-29 | P2-T4: make pg test target env-configurable (NORTHSTAR_PG_TEST_PORT/USER/DB); suite 45 passed vs disposable PG |
| `0da0d86f` | 2026-09-29 | P2-T4: DB_URL driver + migration ledger + fail-closed startup check (postgres suite blocked) |
| `68593848` | 2026-09-29 | P2-T3: migrate to BrowserRouter basename /ui; rewrite harnesses to path routing |
| `c9f5d7fb` | 2026-09-29 | P1-T1 (addendum): wire HARNESS_BASE_URL (default http://127.0.0.1/ui/) into the four harnesses |
| `e320e236` | 2026-09-29 | P1-T1: verify costco 191->217 delta includes frozen Bright Data tests; set non-frozen baseline 172 |
| `28d80fda` | 2026-09-29 | P0-T4: env sanity check (hazards only, no values); record owner answers |
| `140c084c` | 2026-09-28 | docs: master build session report (P0-T1 through P2-T2) |
| `9cbd0adc` | 2026-09-28 | P2-T2: note P2-T3 base-path and harness-server open questions |
| `4fd73f80` | 2026-09-28 | P2-T2: containerize hosted skeleton (api/worker/scheduler/postgres/caddy) + health endpoint |
| `a112b7e4` | 2026-09-28 | P2-T1: log hosting intake default (local Compose only, no public URL) |
| `ab1e964f` | 2026-09-28 | P1-T3: mark frontend defect sweep done in build state |
| `9ddac870` | 2026-09-28 | P1-T3 F2/F3/F4: mount legal/account-state routes, branch shell on suspended, gate internal paths on auth (App.jsx); update frontend gate to 48 routes |
| `3f7f6f4e` | 2026-09-28 | P1-T3 F8: remove retired public stubs BetaDenied and LegalPreview |
| `0c55b15a` | 2026-09-28 | P1-T3 F11: mark legacy services/api.js deprecated (not imported by v3 rooms) |
| `b5c050a7` | 2026-09-28 | P1-T3 F8: retire unmounted orphan pages; drop /sourcing and /portfolio from AGENTS routes |
| `06ca48c5` | 2026-09-28 | P1-T3 F7: delete dead v2 components/RouteGuard.jsx |
| `84d83e01` | 2026-09-28 | P1-T3 F6: add notifications and quick-create to TopNav |
| `74d8581f` | 2026-09-28 | P1-T3 F5: add UI-to-backend role map (backend enum canonical) |
| `1736c66a` | 2026-09-28 | P1-T3 F4: guard internal paths behind auth; add signed-out guard assertions + auth stubs |
| `39895cec` | 2026-09-28 | P1-T3 F3: add suspended/downgraded/reaccept account-state pages |
| `ba132ec7` | 2026-09-28 | P1-T3 F2: add /legal router link on sign-in and mount customer/Legal |
| `1a25225c` | 2026-09-28 | P1-T3 F1: route sign-in/accept links through react-router (hash-path safe) |
| `cad937e0` | 2026-09-28 | P1-T2: assert v3 shell invariants in frontend gate (SuiteRail/TopNav/CommandPalette, 44 routes, no legacy api import) |
| `dc2f48c7` | 2026-09-28 | P1-T1: record green baseline (harnesses + backend suites) and reconcile costco count |
| `00ba0a8f` | 2026-09-28 | P0-T3: constitution diff for master build plan (21 compatible, 1 needs-amendment) |
| `39ba28fc` | 2026-09-28 | P0-T2: document two-repo data contract and disambiguate northstar.db name collision |
| `493002cd` | 2026-09-28 | P0-T1: mark state capture done in build state |
| `1711eddb` | 2026-09-28 | P0-T1: capture build state, create build/master-plan branch, back up northstar.db |
| `5967f7e6` | 2026-09-27 | Complete invite onboarding auth flow: functional local private-beta sign-in (prefill T2/123abc, establish dev-shim session, operator role, inline error, refresh-persistent) and route accept->#/sign-in with invited-org context; internal surfaces stay guarded |
| `a6ddaf30` | 2026-09-27 | Fix invite-accept 404: route Accept Invitation within the SPA hash router (add client route /beta/accept -> BetaInviteAccept; use hash navigation in BetaLanding and BetaInviteAccept) instead of absolute server path |
| `4bc0e466` | 2026-09-27 | docs: owner acceptance packet (checklist + release-state labels + not-included scope); documentation only |
| `c1274a39` | 2026-09-27 | Post-acceptance P2 hardening: responsive room-grid utilities applied to Creative Studio + Listing Guardian at phone widths (desktop preserved); Provider Adapters sample-state pills de-greened to muted + truth legend; P2-1/P2-4/A5 verified no-op; legacy-page inventory report; no backend/provider changes |
| `3120a7f2` | 2026-09-27 | Private-beta UI acceptance pass: assessment report + acceptance harness (verify-acceptance 26/26) + desktop/mobile capture harness + screenshots; reproduce build/smoke/guards; SourceScout frozen verified; SellerSprite fail-closed verified; SellerAmp REPORTED offline-only; no code fixes required beyond d068611 |
| `d0686115` | 2026-09-27 | Fix SocialPulse queue board mobile overflow: responsive kanban columns (min 170px) with horizontal scroll |
| `142e5039` | 2026-09-27 | Cluster C: Admin/Beta-Ops control room. Fix Admin pill base-class/concatenated-status defect + internal truth labels + Controls safety gates; add BetaOpsNav across /beta-ops/*; Overview Exception Queue with action routing; Organizations roster/detail lifecycle pills + Open; Invites Expired state + sample-disabled actions; Cohorts/Support/Lifecycle/Eligibility/Audit/Reports semantic pills + provenance tags + notices; global .btn:disabled styling; role guards unchanged |
| `a2238ecf` | 2026-09-27 | Retire expired SellerSprite trial provider |
| `5f8276f1` | 2026-09-27 | Cluster A/B visual-polish pass: SocialPulse queue stage actions + count footers, calendar out-of-month cells; Creative Studio library summary + intentional placeholders; Guardian enriched history timeline + Watch Summary + real change-list diffs; Keyword coverage Top Uncovered Terms + alerts Verify-in-Trends + movement summary + single cached notice; Monitoring health green limited to live-verified checks + per-destination alert counts |
| `5bc896a8` | 2026-09-27 | 00_STATE.json: Cluster B complete milestone (b60c194); SellerSprite->SellerAmp reference; backend SellerSprite flag |
| `b60c1948` | 2026-09-27 | Cluster B: Listing Guardian (Alerts/Diffs/History/Escalations + diff viewer + policy warnings), Keyword Tracker (Sets/Trends/Coverage/Alerts + sparklines + coverage bars), Monitoring (observability watchtower, de-dup Shared Data Layer/Provider Adapters, cached/observed no longer green); blueprint reference SellerSprite->SellerAmp (screenshots 50-52c) |
| `97cf8782` | 2026-09-27 | 00_STATE.json: Cluster A complete milestone (a7cd50c) |
| `a7cd50c1` | 2026-09-27 | Cluster A: rebuild SocialPulse as social content studio (Calendar/Queue/Composer/Asset Library/Presets/Approvals/Analytics, copilot, kanban, month grid) + Creative Studio as creative workshop (Briefs/Variants/Assets/Exports/Library, variant gallery, bundles); enforce divergence (screenshots 48-49e) |
| `809ca005` | 2026-09-27 | 00_STATE.json: consolidated remaining-rooms analysis milestone (ba13ad4) |
| `ba13ad47` | 2026-09-27 | Consolidated analysis: remaining rooms (SocialPulse, Creative Studio, Listing Guardian, Keyword Tracker, Monitoring, Admin/Beta-Ops) vs blueprint + SourceScout; cluster A/B/C fix plan; screenshots 41-47 (analysis only, no impl) |
| `14ad25f7` | 2026-09-27 | 00_STATE.json: Golden Goose blueprint pass milestone (ba379b3) |
| `ba379b37` | 2026-09-27 | Golden Goose blueprint conformance: Queue/Review/Decisions/History tabs, queue Rank+Score+Contradictions columns, review rail (what remains unknown / why it may fail / hold-reject-escalate) + review notes, History provenance tab, truth pill fix (screenshots 39-40d) |
| `7ddd5e89` | 2026-09-27 | 00_STATE.json: Command Center blueprint pass milestone (96d7b27) |
| `96d7b27c` | 2026-09-27 | Command Center blueprint conformance: add Overview/Exceptions/Activity/Exposure/Handoffs tabs, briefing strip (org/date-range/scope), Open Priority Queue CTA, priority routes + handoffs, structured exception stack, truth-pill tuning (screenshots 37-38e) |
| `a8c613df` | 2026-09-27 | 00_STATE.json: Profitability+Commerce Ops blueprint pass milestone (572c537) |
| `572c537f` | 2026-09-27 | Profitability + Commerce Ops blueprint conformance: blueprint tabs (Scenarios/Fee Basis/Inventory Impact/Export; Workflow/Tasks/Approvals/Blockers/History), scenario cards, approvals/blockers/history tabs, truth pills throughout (screenshots 33-36e) |
| `7eec66cd` | 2026-09-27 | 00_STATE.json: ListingForge+AdPilot blueprint conformance pass milestone (7f8f678) |
| `7f8f6782` | 2026-09-27 | ListingForge + AdPilot blueprint conformance pass: LF/AP blueprint doc, 6 approved fixes, new Assets/Revision Log/Search Terms/Placements/Rules tabs, truthful rollups (screenshots 27-32e) |
| `1d7e9561` | 2026-09-27 | CC+GG truth-pill pass: GG freshness column + Research Confidence rename; CC basis captions, portfolio truth pills, What Changed tone tags |
| `311da187` | 2026-09-27 | SourceScout P2 polish + freeze as reference-standard room (5-col gate grid, neutral statuses, full-width identity strip, avatar consistency) |
| `0a693fe9` | 2026-09-27 | SourceScout visual pass: truth pills, identity strip, invitee rail card, deduped nav/gates, ghost affordance, provenance wording |
| `6c7637db` | 2026-09-27 | fix(customer-guard): SuiteRail filters sections by role (beta-ops/admin no longer visible to customers) |
| `0dd3597c` | 2026-09-27 | fix(customer-guard): filter SuiteRail sections by role (beta-ops/admin leak); add route-guard + smoke verification scripts and report |
| `f296eecc` | 2026-09-26 | UI v3 architecture pass: room-depth correction (RoomTabs, role guards, truth labels, cleanup) |
| `014dcde8` | 2026-09-26 | S0 report: UI v3 retirement + rewire verification (routes, harness GREEN, secret scan clean) |
| `a86e3a81` | 2026-09-26 | S0 UI v3 rollout: retire legacy shell, rewire serving to northstar-os-ui |
| `e9aa6911` | 2026-09-26 | baseline: snapshot pre-v3 working tree state |

## One command

Look at the images above, then promote with the recorded approval:

```
python tools/promote_staging.py --promote --verifier "<session>" --approve-visual "<what you looked at and accepted>"
```
