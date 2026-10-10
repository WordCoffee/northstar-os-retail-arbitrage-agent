# Amazon's own creative tools ? Competitor Deep Dive

> Track A of the Northstar Design Studio research corpus. Every claim carries a
> source URL and a tag: [documented] (vendor's own docs/pricing), [observed]
> (seen in product, demo, or video), [inferred] (derived reasoning or
> third-party claim, not confirmed by the vendor).
> Pulled at: 2026-10-10.

## 1. What it is, who it's for, pricing tiers and generation limits

Amazon ships its own creative tooling, and it is the compliance authority. The
suite the Design Studio must interoperate with: A+ Content Manager (basic,
premium, Brand Story, with "AI Ready" modules and a "Select content to
generate" flow), Amazon Brand Store / Storefront builder with tiles, Sponsored
Brands video builder, Posts, and an image/video generator reachable through
Creative Assets. Documented gating: A+ Content requires a Professional selling
account plus a Brand Representative or Reseller role on a Brand Registry
enrolled brand (or generic products); Premium A+ requires Brand Story published
on all brand-owned listings plus additional approved content; Sponsored Brands
requires Brand Registry ownership; Manage Your Experiments requires Brand
Registry.

## 2. Feature inventory

| Feature | How it works | Source | Tier |
|---|---|---|---|
| A+ Content Manager | Basic A+ (970x300, 5 modules) and Premium A+ (1464x600, 7 modules); AI Ready modules with Select content to generate for text and image fields; bulk upload REQUIRED above 1,000 ASINs; Suspend removes content from the detail page | sell.amazon.com/tools/a-content | Brand Registry |
| Brand Story | Carousel with full-screen background on desktop and mobile, image and text cards, links to products and the Brand Store; applied across all ASINs; renders ABOVE A+ Content when both exist | A+ Best Practices PDF | Brand Registry |
| A+ alt text / image keywords | REQUIRED field per image module; must describe the image for screen readers or content is rejected | sellercentral A+ guidelines | Brand Registry |
| AI-generated people disclosure | Vendor provides the metadata path: add IPTC keyword contains-synthetic-performer to dc:subject (XMP), or tick AI-generated / AI-generated people at upload | sellercentral A+ guidelines | Brand Registry |
| Storefront / Brand Store builder | Tile sizes Full Width 4:2, Large 2:2, Medium 2:1, Small 1:1; hero image 3000x600-3000x1200 with 5MB cap; brand logo 400x400; image tiles 3000x1500 / 1500x1500 / 1500x750 / 750x750; gallery up to 8 images at 1500x750; product grid 2 rows max 100 products; best-seller tile auto-appears when criteria met | Amazon Stores PDF + Ads support | Brand Registry |
| Sponsored Brands video builder | Video creative plus brand logo image 400x400+ (1MB, PNG/JPG), headline max 50 chars (30 Japan), brand name, 1-3 advertised products depending on goal; vertical 9:16 supported via Ads API | Ads API guide | Brand Registry |
| Manage Your Experiments | A/B test product title, main images, bullet points, description, A+ Content and Brand Story; customers randomly split into two groups; experiment-to-significance concludes at 66% significance; own-duration recommended 8-10 weeks, to-significance as fast as ~4 weeks; results update weekly with probability the winner is better; auto-publish option | sell.amazon.com/tools/manage-your-experiments | Brand Registry + traffic |
| Upload images tool | Bulk or single image upload, global or country-specific, or image URL in inventory files; images may take up to 24 hours to appear | sellercentral G16881 | all |
| Bulk listing-quality fixes | Manage all inventory > Optimize listings > Improve Listing Quality in bulk > Generate report > upload values file > Review upload status with batch ID and processing report | sellercentral GWCP3XGYFS2NLRTM | all |
| Fix Blocked Listings | Inventory > Manage All Inventory > Fix Blocked Listings > Listing Quality tab states the suppression reason and offers Edit | seller forum / SellerSprite | all |
| Category style guides | Per-category image rules OVERRIDE general rules on conflict; lifestyle main image allowed only for BED, BED_FRAME, MATTRESS, RUG, RUG_PAD, SOFA | sellercentral G200270100 | all |

## 3. User workflow, step by step (clicks to first output)

A+ path: A+ Content Manager ? Start creating A+ Content ? choose content type ?
Add module ? fill fields (image keywords required) ? Apply ASINs (bulk upload
above 1,000) ? submit for approval ? published. Storefront path: Store builder
? page templates ? add tiles by size ? upload images at the documented sizes ?
review and publish. MYE path: pick an eligible ASIN ? Create a New Experiment ?
select experiment type (title / image / bullets / description / A+ / Brand
Story) ? Version B (duplicate Version A for A+ experiments) ? set duration to
significance ? run ? review weekly results ? auto-publish winner.

## 4. UI / layout patterns

Amazon's UIs are administrative forms rather than design surfaces. A+ Content
Manager is a module picker plus field forms; Store builder is a tile picker with
a preview window, tile manager, page manager and status bar; MYE is a wizard that
ends in a results table. There is no canvas, no layers, no safe-zone overlay, no
keyword panel. **This is precisely why a Design Studio has a reason to exist:
Amazon owns the rules and the measurement but not the production surface.**

## 5. What users love / hate

Documented Amazon-side failures that a creative tool can prevent: listing
suppression from search and browse until a compliant main image is provided;
A+ content rejection for non-descriptive alt text, CMYK colour space, files over
2MB, animated GIFs, or reused gallery images; Brand Registry enrollment rejection
for mock-up or digitally altered product images as IP proof, with possible
removal from the program; MYE experiment invalidity if both A+ versions are not
applied to the exact same ASIN set. Documented Amazon-side quality signal: images
"help a customer choose one search result over another" ? that is the entire
documented basis, and it is deliberately vague.

## 6. Gaps for Amazon sellers specifically

Gaps that Amazon does NOT fill (and therefore the Design Studio's opportunity):
1. No production surface ? Amazon accepts compliant assets, it does not help
   make them.
2. No cross-format spec registry ? each tool documents its own sizes with no
   single place to see every size at once.
3. No pre-flight compliance check before you spend time producing an asset.
4. No keyword/search-term input to creative.
5. No product-fidelity guarantee on AI-generated imagery.
6. No provenance per asset.
7. No unified asset library across A+, Storefront, ads and social.

## 7. Output quality notes and known failure modes

Documented Amazon-side failure modes a seller must design around: the
auto-crop of main images that trims blank white and can change composition;
variation families where each child ASIN needs its own compliant main image;
the 24-hour delay before image changes appear, which makes a bad upload look
like a failed upload; and the 970x600 vs 970x300 A+ size ambiguity that sellers
still argue about in the forums (no staff resolution captured).
