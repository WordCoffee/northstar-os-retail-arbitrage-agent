# PHASE 0 — Entity Resolution
**Research batch:** NorthstarOS Design Studio deep research, 2026-10-08
**Agent scope:** Phase 0 (entity resolution) + Phase 1 (product teardown) for the named general-design competitors, plus 8–12 additional Amazon-seller-relevant competitors.
**Method:** public marketing pages, official pricing pages, official help/docs pages, official press releases, and DNS lookups. No logins, no trials, no API keys, no paid calls. Every finding carries a source id from `SOURCES.csv`. Sources I contributed are `S200`–`S241`.

---

## 1. Verdict table — the seven names given by the operator

| # | Name given | Correct identity | Website | Owner / parent | Operator's hypothesis | Verdict |
|---|---|---|---|---|---|---|
| 1 | Canva | Canva | canva.com | UNKNOWN (legal entity not stated on any page fetched) | — | **CONFIRMED as named.** Real, live, and the largest general-purpose visual design suite of the set. |
| 2 | Figma | Figma | figma.com | UNKNOWN (legal entity not stated on any page fetched) | — | **CONFIRMED as named.** Real and live. Now positioned as a full-stack creative canvas with an AI agent, not a UI-only tool. |
| 3 | Adobe Firefly | Adobe Firefly | adobe.com/products/firefly.html (app: firefly.adobe.com) | **Adobe** | — | **CONFIRMED as named.** Real and live; Adobe's generative AI creative space, embedded in Creative Cloud. |
| 4 | Packify AI | **Packify** | packify.ai | **Pacdora** | "it is Packify.ai, built by Pacdora, a packaging design agent (text-to-3D concepts, dieline editor, AI photoshoots, API, manufacturer connection)" | **CONFIRMED — operator was right on every point, including the Pacdora parent.** See §2.4. |
| 5 | Creator.fyi / Creatify AI | **Creatify** (creatify.ai) only | creatify.ai | **Creatify Lab / Creatify Labs Inc.** | "probably the same product, Creatify, turning a product URL (incl. Amazon) into video ads with scripts, avatars, multiple aspect ratios" | **PARTIALLY CONFIRMED, PARTIALLY REFUTED.** Creatify is real and matches the described scope. **creator.fyi is NOT a product at all** — it is not an alias of Creatify and not a second product. See §2.5 — this is the single most important correction in this phase. |
| 6 | PicoPilot | **PicCopilot** (capital C; two words, no hyphen: Pic + Copilot) | piccopilot.com | **NEURALNETICS PTE. LTD.**; Alibaba-affiliated ecosystem | "actually PiccoPilot (piccopilot.com), selling Amazon A+ and EBC layouts, listing images, chat-to-edit on a canvas, and a social/video content tool" | **SPELLING CONFIRMED.** Domain and product confirmed real. **BUT the described product scope is substantially WRONG, and the product is shutting down.** See §2.6. |
| 7 | tryholo.ai | **Holo** | tryholo.ai | UNKNOWN — Lithuania-based; site claims $6M raised; LinkedIn slug `holoai`; legal entity not disclosed | "UNVERIFIED per operator. Locate it, confirm what it is and who owns it." | **RESOLVED — operator's caution was justified.** A real, live, funded product exists, but it is **not** a design or packaging tool. See §2.7. |

**Competitor count carried into Phase 1: 18** (the 7 named identities above, with creator.fyi retained as an explicit UNKNOWN row, plus 11 additional verified competitors).

---

## 2. Detailed findings

### 2.1 Canva — confirmed
Live at canva.com. Scope observed on official pages: documents, sheets, presentations, whiteboards, social, photo/video editors, print (including labels and posters), websites, PDF editor, logos, mockups. AI layer branded Magic Studio / Canva AI 2.0: Magic Layers (turns AI output into editable layers), AI-powered elements, Canva Code, AI-powered templates, Style Match, 3D Content Generator, Video Generator, AI photo editor, on-brand design generation, Shape Generator, Photo Generator, Magic Background, Resize, Magic Write, Interactive Activities. Plan tiers Free / Pro / Business / Enterprise are visible in navigation. Sources: S214, S215.

**Coverage gap — pricing.** `canva.com/pricing` returns a "Please update your browser" interstitial and no pricing content is retrievable (S216). Plan *names* are verified; plan *prices, credit allowances and seat limits are UNKNOWN*. Third-party pricing summaries exist (S241) but they conflict with each other (Canva Pro quoted anywhere from $120/yr to $180/yr across snapshots) and are recorded as REPORTED only.

### 2.2 Figma — confirmed
Live at figma.com. Now a multi-product platform: Figma Design, Figma Make, Figma Weave (node-based prompt surface), Figma Motion, FigJam, Figma Slides, Figma Draw, Figma Sites (beta), Figma Buzz (beta), Figma agent, Dev Mode. Pricing observed in full (S218): Starter free with 150 AI credits/day capped at 500/month; Professional full seat $16/mo with 3,000 AI credits/mo (dev seat $12, collab seat $3, each 500 credits); Organization billed annually — full $55, dev $25, collab $5; Enterprise billed annually — full $90, dev $35, collab $5. AI credits are purchasable as a team-wide add-on. No Amazon or marketplace-specific features are advertised anywhere on the site.

### 2.3 Adobe Firefly — confirmed
Live at adobe.com/products/firefly.html with the app at firefly.adobe.com. Owner is **Adobe** — unambiguous from the domain, branding and cross-links to Photoshop, Illustrator, Premiere, Lightroom, Express and GenStudio. Generates images, vector graphics, video, sound effects, soundtracks, speech, and translated audio/video. Firefly Boards is a shared infinite canvas for moodboards and storyboards. Partner models: Google, OpenAI, ElevenLabs, Luma AI, Runway, Topaz, Kling AI. Firefly Custom Models train on the user's own assets. Outputs carry Content Credentials. Export formats per Adobe's own FAQ: images PNG/JPG, video MP4. Sources: S219, S220.

**Coverage gap — plan credits.** The Firefly plans page renders its comparison tables as injected AEM fragments; only the tier categories (individuals / students-and-teachers / business) and the general generative-credit language were retrievable. Per-plan credit counts and prices are **UNKNOWN**.

### 2.4 Packify AI → Packify / Pacdora — operator was right, in full
`packify.ai` resolves to **Packify**, and the **Pacdora** parent is confirmed by the asset CDN (`cdn.pacdora.com`) and the billing contact (`business@packify.ai`).

Every element of the operator's scope description was verified on the vendor's own pages (S212, S213):

| Operator's claim | Verified? | Evidence |
|---|---|---|
| Text-to-3D packaging concepts | **YES** | "AI packaging design — turn ideas into 3D packaging"; "transform text into 3D packaging concepts in seconds" |
| Dieline editor | **YES** | "Concept to dielines … from mockups to manufacturable dielines"; "Print-ready dielines"; "automatic dieline generation" in a customer quote |
| AI photoshoots | **YES** | "AI photoshoot — swap backgrounds instantly", priced at 5 credits |
| API | **YES** | "Packify API — integrate our powerful generation engine directly into your e-commerce workflow"; docs at packify.ai/docs; API access is an exclusive Business-plan benefit |
| Manufacturer connection | **YES** | "Production ready — connect with verified packaging manufacturers worldwide" |

Also confirmed and worth recording for Phase 1: Brand Kits are a first-class shared object (Business/Enterprise); credit mechanics are unusually explicit — free plan = 100 one-time non-refreshing credits, AI Design/Edit = 10 credits, AI Photoshoot = 5 credits, AI Editor ≈ 10 credits per generated image, subscription credits reset monthly and do not roll over, top-ups valid 12 months and consumed only after subscription credits; Business additional seats $9.9/mo; Enterprise 4 seats; Stripe billing.

**Coverage gap — plan prices.** The pricing page renders its plan-tier values dynamically and they did not appear in retrieved content. Tier *names* (Free / Pro / Business / Enterprise) and all credit/seat/licence mechanics are verified; the **numeric prices are UNKNOWN**.

### 2.5 Creatify vs creator.fyi — **the important one**

**Creatify (creatify.ai) — CONFIRMED, and matches the operator's description.**
Creatify Lab (G2 listing: *Creatify Labs Inc.*). The URL-to-video flow is exactly as the operator described: paste a product link, the AI analyses product details/features/benefits, writes the script, and returns a ready-to-run video ad in under 60 seconds (S204, S206). Avatars: 300 AI actors on Starter, 1,500 on Pro, all on Enterprise. Multiple aspect ratios / platform specs: outputs are auto-optimised per platform spec and the site claims compatibility with Meta, TikTok, YouTube, Snap and **Amazon** (S204). Batch mode creates a dozen variations at once. Also present: Ad Flow (node-based editor), Creative Agent (chat), Performance Agent, Model Playground, ad cloner, competitor ad tracker, brand spaces, MCP for Claude/ChatGPT, and a public API with volume discounting on Enterprise.

**creator.fyi — NOT A PRODUCT. It is not an alias of Creatify and not a second product.**

Evidence, in order of strength:

1. **DNS (S200, VERIFIED).** An A-record lookup for `creator.fyi` returned `NOERROR` with an **SOA authority section but no answer section**. The domain is delegated — nameservers `ns-1089.awsdns-08.org` and `ns-1089.awsdns-09.org`-class AWS Route 53 records — but **there is no A record, so nothing is served at that hostname.**
2. **Transport failure.** `https://creator.fyi` and `https://www.creator.fyi` both failed at the transport layer with no HTTP response, consistent with the DNS finding.
3. **Search (S203, VERIFIED).** A search for the literal string `creator.fyi` surfaced **no product at that domain**. Every top hit was an unrelated "Creator FYI" — Meta/Threads/Facebook/Instagram creator-programme announcements, a `fyi.fyi` project page, and an `fyi.me` page. None is an AI ad or design tool.
4. **Corroboration (S207, REPORTED, third party).** A comparison page published by a *different* company named CreatifyHQ states that CreatifyHQ and Creatify (creatify.ai) are separate, unaffiliated products and that creatify.ai is the AI video-ad generator. This is self-interested and is used **only** to corroborate that the `creatify.ai` identity is taken by the video-ad product — not as a capability source.

**Conclusion for the matrix:** there is no distinct `creator.fyi` competitor to profile. It is retained as one row in the matrix, populated almost entirely with `UNKNOWN`, so the operator can see it was checked rather than skipped. If a product under this name is expected to exist, the operator needs to supply a correct URL — it cannot be resolved from public evidence.

### 2.6 PicCopilot — spelling confirmed, **but the described scope is wrong and the product is dying**

**Spelling and domain: confirmed.** The correct form is **PicCopilot** (two words, no hyphen, capital P and capital C) at `piccopilot.com`. The operator's `piccopilot.com` was right.

**Owner: NEURALNETICS PTE. LTD.**, a Singapore entity named in PicCopilot's own privacy policy (S210). The cookie notice is served from `contract.alibaba.com` and the site's partner list is Alibaba, AliExpress, Accio, ID Ranking and ADIC, so the product sits inside an Alibaba-affiliated ecosystem rather than being Amazon-native (S208, S210).

**The operator's product description does not match the product.** The actual tool list (S208) is: Fashion Reels, Product Avatars, Product AnyShoot, Virtual Try On, Virtual Try On Accessories, Virtual Try On Shoes, AI Model Swap, AI Templates, AI Backgrounds, AI Shadows, Style Clone, Background Remover, Image Translator, Image Enhancer, Image Upscaler, Remove Watermark, and AI Avatars.

| Operator claim | Verified? | Finding |
|---|---|---|
| Sells Amazon A+ and EBC layouts | **NOT FOUND — treat as refuted unless operator supplies evidence** | No A+ content, EBC, or listing-layout module appears anywhere in the tool list, templates page, or pricing feature matrix. |
| Listing images | **PARTIALLY** | Generates on-model and product imagery; "Amazon" appears only as one of several claimed export destinations (Instagram, TikTok, Amazon, Shopify, Etsy, Pinterest). No Amazon-specific listing-image module is described. |
| Chat-to-edit on a canvas | **NOT CONFIRMED** | The site shows template-fill and drag-and-drop scene composition. No chat-to-edit surface was observed. Recorded as UNKNOWN rather than assumed. |
| A social/video content tool | **YES** | Fashion Reels, AI Avatars, social-post sizing, 74,000+ marketing templates. |

**⚠ Service closure — this is the headline finding for PicCopilot.** The site carries a prominent **"PicCopilot Service Closure Notice"** banner on every page (S208, S209). A third-party blog reporting the notice states that PicCopilot will discontinue services on **8 December 2026 00:00:00 (UTC+8)** and that **payments from new users stop on 27 September 2026** (S211, REPORTED). The pricing page is already broken in a way consistent with a winding-down service: all three plan tiers render as **$0 / Month** and the headline cost-per-image claim renders as the literal string **"$NaN"**.

**Implication:** PicCopilot should be treated as a *former* competitor and a source of orphaned users rather than a live target. Any strategic read that assumes a healthy PicCopilot in the market is wrong.

Pricing mechanics captured before the breakage: tiers Free / Pro / Pro+, monthly or yearly (yearly 16% off); currency is **Pcoins**; monthly Pcoin distribution expires when the next month's coins are distributed; Pro+ has a distinctive **"pay-for-certainty"** refund — click "Not Satisfied" and Pcoins return instantly, valid within 24 hours of generation, some tools only; top-ups available; a business API/SDK is sold through sales contact.

### 2.7 tryholo.ai → **Holo** — operator's "UNVERIFIED" flag was justified

The domain resolves to a live product, and it is a real, funded, revenue-generating company — but it is **not a design tool and not a packaging tool**.

- **Name:** Holo (brand mark reads "Holo"; domain tryholo.ai; login at app.tryholo.ai).
- **What it is (S201, VERIFIED):** an autonomous marketing platform. The pitch is "your whole marketing department, one hire" — you paste your website and Holo plans, writes and publishes ads, socials, emails and SEO content every day on autopilot; you tap approve. Channels covered: paid ads, organic social, SEO and GEO, email.
- **Who owns it:** **UNKNOWN.** The site says "Proudly made in 🇱🇹 Lithuania", claims $6M raised and "backed by VC funds", and links a LinkedIn company slug of `holoai` plus Instagram `tryholo.ai`. **No legal entity name appears on any page fetched.** Do not guess a Lithuanian entity name from the flag.
- **Pricing (S202, VERIFIED):** Starter $8.13/mo on the 6-month option (list $20.33/mo), 100 credits + daily credits, 125 creations, 1 brand workspace, up to 2 parallel generations. Scale $19.33/mo on 6-month (list $48.33), 500 credits + daily, 325 creations, 3 brand workspaces, up to 6 parallel, credit rollover. Agency $300/mo on 6-month (list $750), 2,600 credits + daily, up to 1,375 creations, unlimited brand profiles, unlimited seats, unlimited parallel. Credit rollover is **off** on Starter and **on** for Scale and Agency. Free daily grants: 1/day Starter, 5/day Scale. SOC 2 Type II claimed. Payments via Solidgate.
- **Why it matters anyway:** it is the clearest example in the set of the "agentic, approve-only, no canvas" end of the market, and the only one that explicitly positions *against* templates. It is a genuine competitor for the *attention* of an Amazon seller, but not for the *design-studio* feature set NorthstarOS is building.

**No guess was made.** If the operator meant a different product by "tryholo.ai", the domain in the brief is taken by Holo and a corrected URL is needed.

---

## 3. Additional competitors — verification and justification

Each candidate the operator suggested was checked before inclusion. 11 additional competitors were verified and included.

| Competitor | Verified? | One-line justification for inclusion |
|---|---|---|
| **Amazon Ads AI creative solutions** (Creative Studio / Creative Agent) | **YES** (S221–S224) | The single most important competitor for Amazon sellers: free, ASIN-first, native to Sponsored Brands / Sponsored Display / DSP / Brand Store, with an agentic conversational creative partner built on Amazon Nova and Anthropic Claude. Anything NorthstarOS builds for Amazon creative is competing against a zero-price incumbent. |
| **Helium 10** | **YES** (S225–S227) | The default Amazon seller suite; owns the keyword and listing-optimisation workflow that any creative tool must feed into. Included specifically to check whether it has creative features — it does not appear to. |
| **Jungle Scout** | **YES** (S228, S229) | Major Amazon intelligence vendor (Catalyst / Cobalt / Cloud / MCP); occupies the same seller budget line and the same keyword-research surface. |
| **Pacvue** | **YES** (S230, S231) | Enterprise commerce-media OS across 100+ retail media networks with an Amazon flagship and AMC integration; the enterprise-grade comparator for any Amazon-adjacent platform. |
| **Perpetua** | **YES** (S232) | Retail-media optimisation platform with an Amazon-first PPC/DSP focus and an explicit video advertising product line; the natural "what does the ad-optimisation side look like" comparator. |
| **Flair** | **YES** (S233, S234) | Closest like-for-like competitor to an Amazon design studio: drag-and-drop canvas, brand asset management, custom models trained on your own products, ad generation, API, and Amazon in its customer list. |
| **Photoroom** | **YES** (S235, S236) | High-volume e-commerce visual platform with batch processing, Brand Library governance, marketplace sync, an MCP connector and a marketplace-listing API playground — the "catalogue scale" competitor. |
| **Pebblely** | **YES** (S237, S238) | Low-cost, high-volume product-photo generator explicitly aimed at marketplace sellers and multi-channel commerce; sets the price floor for simple background/scene generation. |
| **AdCreative.ai** *(added by me, not on the operator's list)* | **YES** (S239) | Creative-generation platform with a scoring/prediction layer trained on stated ad-spend data, a compliance checker and a custom-template builder — the closest analogue to "generate on-brand ad creative and predict whether it will work". |
| **Claid.ai** *(added by me, not on the operator's list)* | **YES** (S240) | API-first product/fashion photography platform (Let's Enhance, Inc.) with ten discrete API products and explicit marketplace/seller-onboarding positioning — the reference implementation for an API-composable design backend. |

**Rejected / excluded:** `creator.fyi` (not a product — see §2.5) and **PicCopilot**'s implied A+/EBC product (no such module exists).

---

## 4. Coverage gaps and limits (R7)

Stated plainly — what was **not** inspected:

1. **Any logged-in surface.** No product was used. Nothing behind a login, no trials, no API keys, no paid calls. Every capability in the matrix is vendor-*claimed* (REPORTED) until noted otherwise in `SOURCES.csv`; the matrix does not distinguish claim-from-observation field-by-field, so treat vendor claims accordingly.
2. **Canva pricing, credit mechanics and plan limits — UNKNOWN.** `canva.com/pricing` is behind a browser-update interstitial. Third-party figures exist but conflict and are REPORTED only.
3. **Adobe Firefly per-plan credit counts and prices — UNKNOWN.** The plans page renders comparison tables as injected fragments.
4. **Packify and AdCreative.ai plan prices / credit mechanics — UNKNOWN.** Both render pricing sections dynamically.
5. **Pacvue and Perpetua — surface only.** Both are demo-gated and their deeper product pages returned HTTP 403. It was therefore **not possible to confirm or rule out** creative-generation modules for these two. Recorded as UNKNOWN rather than assumed absent.
6. **Helium 10 tool sub-pages — no body content retrieved.** The module list comes from official site navigation. All Helium 10 pricing is third-party REPORTED and the third-party figures conflict with each other (Diamond quoted at $229, $279 and $359/month).
7. **Claid API pricing page and AdCreative pricing section — not fetched** (budget). Their credit mechanics are UNKNOWN.
8. **No Amazon Seller Central / Brand Registry / A+ content requirement pages were fetched by this agent.** That work belongs to whoever owns `AMAZON_REQUIREMENTS.md`. Amazon requirements are date-sensitive and must be re-verified before use.
9. **Model names are almost universally UNKNOWN.** No competitor except Amazon (Nova + Claude on Bedrock) and Adobe (partner model list) discloses its generation models. Where undisclosed I wrote UNKNOWN — I did not infer from prior knowledge.
10. **SOURCES.csv is shared.** Another agent is appending to it concurrently and had appended ~81 rows (S243+) by the time I validated. My rows are S200–S241 only. Two rows already present in the file from the other agent (S344 and S345, both photoroom.com URLs) are **malformed — 9 fields instead of 7**, because of unescaped commas. I left them untouched per the append-only instruction, but they should be repaired before the register is consumed.

---

## 5. Source register

All sources are in `SOURCES.csv`. My rows are **S200–S241**, with `accessed` = 2026-10-08 for every row. Labels used: VERIFIED (directly observed on a public page, doc or free surface during this research), REPORTED (a vendor claim, third-party article, review or search snippet), UNKNOWN (fetch failed and nothing was substituted). `S207` is retained as corroboration for the Creatify/creator.fyi resolution and is not cited by a matrix row.
