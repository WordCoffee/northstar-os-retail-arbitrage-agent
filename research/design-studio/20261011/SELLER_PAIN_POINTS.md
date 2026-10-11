# Seller pain points — creative & design tooling for Amazon sellers

**Research date:** 2026-10-09 (UTC). **Researcher:** Amazon-compliance & seller-voice subagent.
**Method:** public pages only. No logins, no trials, no API keys, no accounts.

**Evidence classes** (per `RULES.md` R0): VERIFIED = observed on a public page during this
research; REPORTED = claimed by a third party; UNKNOWN = not confirmed, including fetch failures.

**Retrieval reality (read this before trusting any sample size below):**

- **Reddit** blocked every direct fetch (`www.reddit.com` → HTTP 403; `old.reddit.com` and
  `api.reddit.com` → HTTP 403 or an interstitial). Reddit threads and their comments were
  therefore retrieved **through a search-engine index**, which returns the post title, body and
  the top-scoring comment threads but **truncates the full comment tree and gives no reply
  counts**. Labels are VERIFIED with the retrieval path stated as a limitation.
- **Amazon Seller Forums** (`sellercentral.amazon.com/seller-forums/discussions/...`) are
  server-rendered and were fetched directly. These give real reply counts and view counts, but
  they are **small** threads (2–5 replies, 14–526 views).
- **G2, Capterra, Trustradius, Product Hunt and Quora all returned HTTP 403** to every attempt.
  **No G2, Capterra, Trustpilot or Product Hunt review text was read for this deliverable**,
  with one exception: Trustpilot's Pacdora page surfaced through a search index (S472) and is
  labelled REPORTED because the page itself was not fetched.
- **YouTube**: video pages are fetchable, but comments are client-rendered and **not present in
  the static HTML** (no `commentRenderer` in the payload). **No YouTube comment text was
  obtained.** One tutorial video's transcript/description text was retrieved through a search
  index (S473, REPORTED).

**Consequence:** every sample size below is a count of *distinct threads or posts I actually
saw*, not a population estimate. These are **anecdote clusters**, not trends. Nothing here
should be quoted as a market statistic.

---

## Theme 1 — Inaccurate product rendering: the generated product is not the real product

**Sample size: 13 distinct threads/posts** (11 Reddit across 6 subreddits + 1 Amazon Seller Forums
thread + 1 YouTube tutorial transcript retrieved through a search index).

**Pattern signal: strong and consistent.** This is the single most repeated complaint across every
source, and it appears in both seller communities and buyer-facing communities (Amazon Vine
reviewers), which corroborates it from the demand side.

Representative paraphrased complaints with attribution:

- A seller uploading an AI-generated main image for review was told the product was not fully
  visible — "you can't see all of the handle or the lid" — and that they would not buy from a
  listing with that photo (r/FulfillmentByAmazon, S437).
- "Most AI product images look great until you compare them with the real product. Small changes
  in colour, texture, size or branding create trust issues and extra editing work" and "half the
  time the product looks different in every image" (r/AIToolsAndTips, S451) — a thread explicitly
  framed around whether AI output "can be used directly on Amazon".
- A seller in Grocery reported Amazon had **automatically** added AI-generated lifestyle images to
  their listings: "they don't even show the right appearance of my products. It may cause the
  confusion" (r/FulfillmentByAmazon, S439). Replies: "the inaccuracies are quite concerning";
  "We had a genAI image added to one of our listings. Has anyone been able to get these removed?"
- A Vine reviewer: items "literally look materially NOTHING like what they're showing" — describing
  "in-situ fantasy land garbage that doesn't represent the actual product at all", and calling it
  "deceptive advertising" (r/AmazonVine, S448).
- "AI generated images that look off. Weird hands, distorted faces, missing or extra toes, stuff
  that makes you question if the item in the photo even exists" (r/AmazonVine, S449).
- A seller comparing AI vs real lifestyle imagery for exercise gear: buyers "care most about scale
  and how it is actually used, and AI images tend to fall short there even when they look
  polished" (r/FulfillmentByAmazon, S438).
- An experienced seller asked which AI listing tools he had used: "they're pretty inconsistent…
  where they fall short is anything that requires understanding why a buyer makes a decision"
  (r/FulfillmentByAmazon, S441).
- On AI listing generators generally: "Fine product details sometimes get distorted, which hurts
  trust" and people/lifestyle scenes "can feel unnatural or stiff" (r/AmazonFBA, S443).
- On Amazon's own AI-added images: "riddled with nonsense and errors… images with incorrect
  installation instructions, and images saying the items are used on completely irrelevant items"
  (Amazon Seller Forums, S429 — 5 replies, 129 views).
- A seller found AI tools "looked fake and consistently keep on changing the product. Too perfect,
  too clean, obviously AI" (r/smallbusiness, S450).
- A seller in the AI-image thread advised splitting the set: "Main image stays a real photo of the
  actual unit — it has to match what ships, pure white background, or you risk suppression. AI is
  fine for backgrounds, lifestyle scenes and infographic art" (r/AmazonFBA, S442).

**Tools named as the source of the complaint:** mostly unnamed ("AI tools", "these tools").
Where named, it is the AI-image-generator class as a whole rather than one vendor. One seller
reported an AI tool inventing an OLED screen on a product that does not have one, and noted it
would have been against Amazon's terms because "that's not the actual product" (S473, REPORTED).

**What this implies for a Design Studio:** product fidelity is the load-bearing requirement, not
aesthetic quality. A studio that composites the seller's **real** product pixels (real cutout,
real label text, real proportions) and restricts generative AI to background/scene work has a
defensible answer to the top complaint. A studio that generates the product itself does not.

---

## Theme 2 — Garbled, misspelled or altered text in images

**Sample size: 5 distinct threads/posts** (3 Reddit + 1 Amazon Seller Forums thread + 1 YouTube
tutorial transcript, plus corroboration inside Theme 1 threads).

**Pattern signal: consistent but smaller sample.** Text damage is reported both as a tool-output
defect and as an Amazon-side enforcement problem.

- "AI generated images with text are always one typo away from looking unprofessional"
  (r/notebooklm, S499, from a tutorial about fixing typos in AI infographics — the tutorial exists
  *because* the defect is routine).
- A Vine reviewer found "spelling errors in the marketing photos for 'Handle', 'Corner', and
  'Control' — yet all three are spelled correctly on the one they are trying to tell you doesn't
  have all these cool features" (r/AmazonVine, S447).
- On AI listing generators: "Logos, text, and branding often look slightly off or need tweaks"
  (r/AmazonFBA, S443).
- Amazon Seller Forums: Premium A+ images **rejected for containing a brand logo**, with the
  stated reason that "text is no longer allowed on images"; the same seller reports product
  images rejected because of text that is part of the product itself, citing the word "Volume"
  printed below a volume knob (S430 — 3 replies, 139 views).
- An AI-image tutorial observed the generator producing "the characteristic cliché AI gibberish"
  on small text, requiring a manual fix in a design tool afterwards (S473, REPORTED).

**What this implies for a Design Studio:** text in listing images is a two-sided trap — generative
tools damage it, and Amazon increasingly rejects it. A studio should (a) never generate text
pixels it does not control, (b) render all text as real, editable vector type, and (c) surface a
"Amazon may reject text in A+ images" warning rather than promising compliance.

---

## Theme 3 — Off-brand output and template drift

**Sample size: 5 distinct threads/posts** (4 Reddit across 4 subreddits + 1 Amazon-side A+
governance article). **Caveat: only one of these is Amazon-specific; the rest are general design
tooling.**

**Pattern signal: present but small and mostly non-Amazon.** Most of this evidence is from
designers and SaaS marketing teams, not Amazon sellers, so it should not be read as an
Amazon-seller finding.

- "Every time a non-designer on the team touches a template, it goes off-brand. They'll use the
  wrong shade of blue, some weird font weight, and stretch the logo out. We tried Canva Pro and
  the element locking is close, but it's kinda inconsistent" (r/graphic_design, S464).
- A designer laid off after their work was moved to Canva: "There's no strategy in their designs,
  nothing is on-brand, and they rely entirely on Canva templates. The graphics now look so
  juvenile and random" (r/graphic_design, S465).
- On auto-generated catalogues: "the biggest issue was branding consistency. Auto-generated stuff
  always looked generic or off-brand compared to what our designer was doing. Ended up being
  faster but looked cheaper" (r/nocode, S466).
- A marketer on generative content tools: "they're always so busy/messy and against our brand
  vibe" (r/SocialMediaMarketing, S467).
- Amazon-side (REPORTED, S476): an A+ governance article describes brand fragmentation at
  catalogue scale — conflicting tone across detail pages, multiple logo/palette/typeface versions
  live simultaneously, off-template creatives circulating outside any approval workflow, and the
  detail page, Brand Store and ad creative each promising something different. It also notes that
  a brand-name mismatch between the listing and the Brand Registry record causes Amazon to stop
  recognising the ASIN as part of the brand, blocking all future A+ and Brand Story deployment
  until corrected.

**What this implies for a Design Studio:** brand-consistency enforcement (locked palette,
locked type scale, locked logo lockup, no logo stretching) is a real differentiator, and it is
the one area where a general tool's weakness is documented first-hand. It is also an Amazon
operational risk, not just an aesthetic one.

---

## Theme 4 — Credit burn, failed renders and billing lock-in

**Pattern signal: strong and specific to two named tools.** Photoroom accounts for 4 threads and
Creatify for 5, plus one cross-tool thread naming Creatify and HeyGen.

Photoroom:

- A paying Ultra subscriber: "They have us now pay for a specific amount of AI credits. So if the
  item drops out, I am still charged for the credit and I have no picture. That's $99 a month of
  wasting my time." Same seller reports 13 days without successful support, batch edits being
  dropped mid-job, and background removal creating "white cloud like spots" (r/Flipping, S456).
- "I am only able to use the retouch tool for 3 items before it reaches 99.9% usage rate, and I
  have to wait for an entire month for the usage rate to refresh. My export limit is 250 and I can
  only use 3/250 of that limit" (r/photoroom, S453).
- On batch-limit changes landing mid-subscription: "you want me to go from paying £49.99 a year to
  paying £249.99 a year? You must be joking. Another customer lost" (r/photoroom, S454).
- A cancellation thread where the help article only explained App Store / Google Play / Stripe
  cancellation and not web purchases (r/photoroom, S455).

Creatify:

- "One single 4:59 lip sync video used all 100 credits — my entire month's subscription… The
  output was terrible… I asked for a refund on principle. They refused and cited their 'strict no
  refund policy.' So I paid $39 for one unusable video and now can't use the product for the rest
  of the month" (r/FacebookAds, S458).
- "Credits get used even if the video fails, no automatic refund for failed renders" and
  "complaints about billing continuing after cancellation" (r/content_marketing, S459).
- "I ended up spending a whopping $200 in that first month alone… Every single video was complete
  garbage… My videos kept getting flagged for 'no reason' with zero helpful feedback"
  (r/AIToolsInsider / r/FacebookAds, S460).
- "The avatars look a bit off, too much shine on their faces. Lip sync is really horrible."
  Reply: "It doesn't work at all I tried it. Useless" (r/AI_UGC_Marketing, S461).
- A positive-leaning long review that still records the friction: "first few weeks were hit or
  miss… if you just throw random scripts at it, the results aren't great" (r/advertising, S462).

Cross-tool:

- A reply in the same thread describes "the credit drain on failed renders is absolutely brutal
  when you're trying to scale testing" (r/content_marketing, S459).

**Sample size: 9 distinct threads/posts** (9 Reddit across 7 subreddits) — **Photoroom (4 threads:
S453, S454, S455, S456) and Creatify (5 threads: S458–S462)**, plus a cross-tool thread naming
Creatify and HeyGen. This is the largest single-vendor complaint cluster in the whole research.

**Vendor response observed (context, not endorsement):** Photoroom's own help centre documents an
AI-credit refund system for "unsuccessful generations", with a time limit, an exclusion list, and
a discretionary "bad result" submission flow (S474). A Photoroom community post announced that
AI Shadows, AI Retouch, Expand, Resize, Fill and Upscale would stop consuming credits and that
credit balances would be made more transparent — with replies calling the change overdue
(S475). Both are REPORTED/VERIFIED as vendor statements, not as evidence the complaints are
resolved.

**What this implies for a Design Studio:** credit mechanics are a churn driver, and the specific
complaint is **paying for failed or unusable output**. A studio that (a) prices per *accepted*
output rather than per attempt, (b) auto-refunds failed renders, and (c) never charges credits for
a generation the seller rejects as unusable is answering a documented, repeated complaint from
two named competitors.

---

## Theme 5 — Rejected and suppressed listings (image compliance failures)

**Sample size: 4 distinct threads/posts** (all Reddit, all r/FulfillmentByAmazon). Small but
high-signal, because the complaint is about *silent* failure modes.

- "I have resubmitted the same product photo 4 times now and it keeps bouncing. Pure white
  background, product is the only thing in the frame, no text, no watermark. I even measured the
  frame fill at like 83%… apparently not. **85% is a hard floor. I found that out from a random
  2022 comment here, not from Amazon.**" The seller fixed it by recropping and it passed on the
  next submit (r/FulfillmentByAmazon, S435). A reply adds: "Amazon's docs say 'product fills at
  least 85% of the frame' but they don't tell you the exact measurement method they use. I've had
  images bounce at 84.7% before."
- A thread asking how strict image requirements really are, with a reply enumerating the flags
  that commonly bite: a *pure* white background (RGB 255,255,255) where "even RGB 254,254,254 can
  trigger rejection"; shadows that cannot touch the frame edge; products touching frame edges
  being rejected. The reply states that non-adherence "can result in full listing suppression from
  search, not just image rejection, which can take days to weeks to resolve, resulting in loss of
  sales" (r/FulfillmentByAmazon, S436).
- A seller with professional studio photography (with badges, logos and "premium quality"
  graphics) reports "every single time Amazon rejects them during the listing process" while
  competitors using the same style of enhanced image stay live, and asks whether competitors
  "pass some kind of internal review differently" (r/FulfillmentByAmazon, S440).

**Vendor-side corroboration (REPORTED, S477):** a third-party diagnostic article lists six
main-image rejection groups (background not pure white; text/logo/badge/graphic detected; product
does not fill enough; props or extra items; blurry/pixelated/jagged; product or variant mismatch)
and notes that Amazon's *general technical guidance* (accepted range starting at 500 px) and its
*main-image/zoom guidance* (at least 1,000 px, recommend larger) "are not always expressed with
identical thresholds". This corroborates the sellers' experience that Amazon's own documents are
inconsistent — but it is a third-party summary, so it is REPORTED and used only as corroboration.

**What this implies for a Design Studio:** sellers cannot determine compliance from Amazon's
documentation alone, and the failure mode is invisible until it costs search visibility. A studio
that measures and *shows* the white background value, the frame-fill percentage, the longest-side
pixel count and the file format **before upload**, with a plain "this will likely be rejected"
verdict, is selling something no competitor in the set was observed to provide.

---

## Theme 6 — A+ Content rejections, delays and soft-hiding

**Sample size: 7 distinct threads/posts** (5 Amazon Seller Forums + 2 Reddit). The Amazon Seller
Forums threads are official Amazon properties and give real reply/view counts.

| Thread | Source | Replies | Views |
|---|---|---|---|
| "A+ Content – Text on Images No Longer Allowed" (2025-04-09) | S430 | 3 | 139 |
| "A+ content rejection Issue." | S431 | — | 273 |
| "Wondering why your A+ is hidden behind a 'click for more' button?" (2026-01-30) | S432 | 3 | 526 |
| "Premium A+ Content not granted despite all requirements approved" (2024-11-01) | S433 | 3 | 14 |
| "A+ / EBC Content taking over 7 Days For Approval" (2024-07-10, UK) | S434 | — | — |
| "Amazon A+ Content getting rejected." (2021-04-16) | S445 | — | — |
| "Why are all my Amazon Premium A+ Content images pixellated?" (2026-02-24) | S446 | — | — |

**Pattern signal: moderate, and it is mostly about *opacity* rather than tooling quality.**

- **Rejection reasons are undisclosed.** A seller rejected three times received only: "Your
  content contains specific words that may be cause for rejection. You may still submit the
  content. However, it may be rejected if the specific words are deemed invalid" (S431). Amazon's
  community-manager reply points to the A+ content guidelines page without naming the words. A UK
  seller reports waiting **over 12 days** past the published 7-business-day review window with no
  response (S434); an Amazon reply there attributes that specific alert to pesticide-type claims
  (e.g. antimicrobial, kills germs) or to mentions of a brand or logo without specific approval.
- **Text in A+ images is being rejected.** Premium A+ images rejected for containing a brand logo,
  with the stated reason that "text is no longer allowed on images", and product images rejected
  because of text printed on the product itself (the word "Volume" below a volume knob)
  (S430). Another seller's A+ was rejected with the instruction to remove the word "Amazon"
  (S445).
- **Soft-hiding by an Amazon-side quality model.** A seller reports that 66 of their A+ contents
  are hidden behind a "click for more" button because they "Lack diverse images" and
  "professional usage context", discovered only via a new "Content Quality Analysis" tab in A+
  Content Manager. The same seller notes that two ASINs differing only in pack quantity, with
  **identical** A+ content, are treated differently — one hidden, one not — and that comparison
  tables they were previously encouraged to use are now penalised (S432, 526 views — the
  highest-traffic thread in this set).
- **Premium A+ eligibility gate.** A seller reports having met the stated requirements (3 ASINs
  with an active Brand Story, 16 approved A+ modules in 12 months) and still being denied access,
  with support giving automated responses (S433).
- **Export → upload quality loss.** A designer exporting at the documented 1464 × 600 minimum and
  even scaling natively in Illustrator still gets pixelated uploads; replies attribute it to
  Amazon compression and advise designing at 2× and downscaling in sRGB (S446). This is a real
  **spec-vs-reality gap**: the published minimum is not a quality target.

**What this implies for a Design Studio:** A+ is a rejection-and-delay minefield with undisclosed
trigger words and a new quality gate that penalises exactly the comparison tables Amazon used to
promote. A studio that ships A+ module templates at the documented per-module minimums, *plus*
a 2× supersampled export with an sRGB downscale, plus a "text-in-image risk" warning and an
explicit "these words commonly trigger A+ rejections" pre-check, addresses a documented,
high-traffic pain. No competitor in the set was observed to do any of this.

---

## Theme 7 — Mockups, renders and dielines that do not match the printed/shipped product

**Sample size: 5 distinct threads/posts** (4 Reddit across r/Packaging and r/PackagingDesign +
1 Trustpilot review page surfaced through a search index). **Caveat: this is a packaging-design
community, not an Amazon seller community — it maps to Packify.ai / Pacdora, not to listing
images.**

**Pattern signal: consistent within a small, specialist community.**

- "Everything looks amazing on the website — renders are amazing. But the moment I want to download
  the dielines for print through AI or PDF, the quality becomes AWFUL. I've had packaging that went
  to print and was such low quality… I have downloaded 5 different designs and every print company
  is telling me the same thing — too blurry" (Trustpilot, Pacdora, S472 — REPORTED, page not
  directly fetchable).
- "I feel like social media makes AI packaging design look easy. People post these beautiful box
  concepts… The hard part is figuring out how those images become packaging — dimensions, CMYK
  colours, bleed areas, print resolution and dielines. None of that is obvious when you are just
  trying to build a brand" (r/Packaging, S468).
- "I am always worried that the final product won't look like the mock-up" (r/Packaging, S470) —
  the standard mitigations offered are colour proofs, trial print runs and contract proofs, not
  mockups.
- "Unfortunately I've had some issues with Pacdora especially around the final product not being
  good for production"; "It's okay but a lot of the standards are not ideal for production";
  "good for mockups, not too great for structural designs… Almost every corrugated design needed
  tweaking" (r/PackagingDesign, S469).
- "For quick concepts or client previews I usually take a dieline and run it through Pacdora since
  it's fast and easy to visualise in 3D. For final high-end renders Adobe still gives more control"
  (r/PackagingDesign, S471).

**What this implies for a Design Studio:** in the packaging half of the market, the recurring
complaint is that the *concept* render and the *production* file diverge. If the Design Studio
touches packaging at all, the divider between "concept render" and "print-ready dieline" must be
explicit and labelled, not blended.

---

## Theme 8 — No tool observed: "compliance checking" as a missing product category

**Sample size: 0 threads/posts.** This theme is recorded as an **absence**, not a finding, and is
flagged as such to avoid inflating it.

Across ~40 distinct threads and forum posts, **not one seller described a creative tool that
checks Amazon compliance before upload**. Sellers describe the opposite: discovering the 85% rule
"from a random 2022 comment here, not from Amazon" (S435), asking on Reddit whether anything
"would still cause Amazon to reject it" (S437), and asking for "the actual full list of silent
rejection reasons Amazon uses" (S435). The workaround sellers describe is entirely manual —
"generate images, then edit them in Photoshop or Canva before uploading" (S443), "run everything
through a background remover app… saves me a good 10–15 minutes per product" (S452).

**What this implies for a Design Studio:** the gap is real and repeatedly *described* by sellers,
but it is an inference from absence, not a measured demand. Treat it as a hypothesis to validate,
not as a proven market.

---

## Coverage limits (stated plainly)

1. **Review sites were not read.** G2, Capterra, Trustradius, Product Hunt and Quora all returned
   HTTP 403 on every attempt (S480–S483). The operator's expected sources for tool-level
   complaints are therefore **almost entirely missing** from this deliverable. The only review-site
   text obtained is the Pacdora Trustpilot page via a search index (S472, REPORTED). **No G2 or
   Capterra review sample sizes exist for any of the ten competitors.**
2. **Reddit was not directly fetched.** All Reddit evidence came through a search index. Reply
   counts, comment counts and vote scores are **unknown** for every Reddit thread cited. The
   search index returns top-scoring comment threads, which biases toward strong opinions and
   against moderate ones.
3. **YouTube comments were not read.** Comment threads are client-rendered and absent from the
   static video page payload. One tutorial transcript/description was retrieved via search index
   (S473, REPORTED). **Zero YouTube comment sample.**
4. **Seller Central forums are small.** The five Seller Forums threads cited have 2–5 replies and
   14–526 views each. They are useful as official Amazon properties and as evidence of specific
   rejection behaviours, but they are not a statistically meaningful seller sample.
5. **Subreddit coverage was opportunistic, not systematic.** Searches surfaced
   r/FulfillmentByAmazon, r/AmazonFBA, r/AmazonSeller, r/AmazonVine, r/photoroom, r/Flipping,
   r/advertising, r/AI_generated_ads, r/FacebookAds, r/content_marketing, r/AIToolsInsider,
   r/AI_UGC_Marketing, r/dropshipping, r/graphic_design, r/nocode, r/SocialMediaMarketing,
   r/Packaging, r/PackagingDesign, r/AdobeIllustrator, r/smallbusiness and r/notebooklm. **r/PPC
   was not searched** (it was only reachability-tested). **No Facebook group, Discord, Slack
   community, or paid-course/community content was accessed** — those require logins.
6. **Themes 3 and 7 are not Amazon-seller evidence.** Theme 3 is mostly general design/SaaS
   marketing and Theme 7 is packaging-design. They are included because the operator named
   "off-brand output" and "mockups that don't match the real product" as expected themes, and they
   are labelled so they are not miscounted as Amazon-seller findings.
7. **Tool attribution is thin.** Sellers mostly complain about "AI tools" as a class. Only
   Photoroom and Creatify are named by tool in this sample (Theme 4). **No first-hand complaint
   thread was found for Canva, Figma, Adobe Firefly, PiccoPilot, Packify/Pacdora, Helium 10,
   Pebblely or Flair** in the searches performed — that is an absence of evidence, not evidence of
   absence.
8. **Only the English/US surface was searched.** No non-English seller communities were read, and
   no non-US marketplace forums beyond one UK Seller Forums thread (S434).
9. **Third-party blogs were excluded from the pain-point themes.** Two seller-tooling blogs
   (S476, S477) contain quantified tool comparisons and Amazon-compliance claims. They are
   REPORTED, vendor-adjacent, and in at least one case publish numbers that conflict with Amazon's
   own reachable documents. They are listed in `SOURCES.csv` for completeness but were **not**
   used as evidence for any theme above, except as explicitly labelled corroboration in Theme 5.

